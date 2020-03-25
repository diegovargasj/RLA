# Create your views here.
import operator
import random
from decimal import Decimal, getcontext

import requests

from audit.forms import BRAVOAuditForm
from audit.models import BRAVOAudit, DHONDTAudit


def initBRAVO(request):
    getcontext().prec = 100
    form = BRAVOAuditForm(request)
    if form.is_valid():
        audit = form.init_audit()


def get_random_seed(timestamp):
    """
    Obtains the random pulse at the specified time from the beacon
    @param timestamp    :   {django.db.models.DateTimeField}
                            Datetime specified for the pulse
    @return             :   {bytes}
                            Random pulse value in bytes format
    """
    beacon_api = 'https://random.uchile.cl/beacon/2.0/pulse/time/'
    seed_time = timestamp.timestamp()
    response = requests.get(beacon_api + seed_time)
    random_seed = bytes.fromhex(response.json()['pulse']['localRandomValue'])
    return random_seed


def get_n_random_ballots(audit, n, page, seed):
    random.seed(seed)
    ballots = []
    for table in audit.table_set:
        tot = 0
        for registry in table.tableregistry_set:
            tot += registry.preliminary_votes

        for i in range(tot):
            ballots.append((table, i))

    return random.shuffle(ballots)[n * page:n * (page + 1)]


def validated(T, alpha):
    """
    Checks if the election has been validated
    @param T    :   {dict<models.Candidate->dict<models.Candidate->float>>}
                    Dictionary of dictionaries containing the current inverse of
                    p-values for all the null hypothesis being checked
    @param alpha:   {float}
                    Risk limit for this audit
    @return     :   {bool}
                    True if the election has been validated given the selected
                    risk limit, else False
    """
    for winner in T:
        for loser in T[winner]:
            if T[winner][loser] < 1 / alpha:
                return False

    return True


def d(s):
    """
    Returns the divisor for column s. In this case, the divisor of
    column s is always s
    @param s    :   {int}
                    Column number
    @return     :   {int}
                    Divisor of column s
    """
    return s


def t(p, vote_count):
    """
    Gets the reported number of votes for party p
    @param p            :   {models.Party}
                            The party in question for which we want to get the
                            reported number of votes
    @param vote_count   :   {dict<models.Party->int>}
                            Dictionary with the reported number of votes
                            per party
    @return             :   {int}
                            Reported number of votes for party p
    """
    return vote_count[p]


def p(party, vote_count, s):
    """
    Returns the reported number of votes for party p, divided by the divisor
    of column s
    @param party        :   {models.Party}
                            Party in question
    @param vote_count   :   {dict<models.Party->int>}
                            Dictionary with the reported number of votes
                            per party
    @param s            :   {int}
                            Column number
    @return             :   {float}
                            Reported number of votes for party p, divided by
                            the divisor of column s
    """
    return t(party, vote_count) / d(s)


def gamma(p, q, Sw, Sl, vote_count):
    """
    Likelihood ratio for the null/alternative hypothesis
    (depending on which candidate is reportedly winning)
    between reported winning and reported losing candidates
    @param p            :   {models.PseudoCandidate}
                            First pseudo candidate
    @param q            :   {models.PseudoCandidate}
                            Second pseudo candidate
    @param Sw           :   {dict<models.PseudoCandidate->int>}
                            Max seat number for each winning party
    @param Sl           :   {dict<models.PseudoCandidate->int}
                            Min seat number for each losing party
    @param vote_count   :   {dict<models.PseudoCandidate->int>}
                            Dictionary with the reported number of votes
                            per pseudo candidate
    @return             :   {float}
                            Likelihood ratio between pseudo candidates p and q,
                            given a vote for p
    """
    y1 = t(p, vote_count) / (t(p, vote_count) + t(q, vote_count))
    y2 = (d(Sw[p]) + d(Sl[q])) / d(Sw[p])
    return Decimal(y1 * y2)


def ballot_polling(audit, W, L, vote_count, recount, Sw, Sl):
    T = audit.T
    alpha = audit.risk_limit
    for w in W:
        for l in L:
            if T[w][l] < 1 / alpha:
                y1 = gamma(w, l, Sw, Sl, vote_count)
                y2 = gamma(l, w, Sl, Sw, vote_count)
                T[w][l] = y1 ** recount[w] * y2 ** recount[l]

    audit.T = T
    audit.save()
    return validated(T, alpha)


######################### BRAVO ######################################


def BRAVO_get_W_L_sets(vote_count, n_winners):
    """
    Obtains the winner and loser sets, given the amount of votes
    for each candidate
    @param vote_count   :   {dict<models.Candidate->int>}
                            Dictionary with the reported amount of votes
                            per candidate
    @param n_winners    :   {int}
                            Number of winners for the election
    @return             :   {tuple<list<models.Candidate>,list<models.Candidate>}
                            Tuple with the winners and losers sets
    """
    tuples = list(vote_count.items())
    sorted_tuples = sorted(tuples, key=operator.itemgetter(1), reverse=True)
    W = [c[0] for c in sorted_tuples[:n_winners]]
    L = [c[0] for c in sorted_tuples[n_winners:]]
    return W, L


def bravo(audit_pk):
    """
    Applies the BRAVO algorithm to determine if the audit has been verified.
    It counts the number of votes for each candidate, calculates the inverse of
    the p-values for each of the null hypothesis and determines if the
    conditions have been met
    @param audit_pk :   {int}
                        Primary key for the BRAVOAudit model
    @return         :   {bool}
                        True if the election has been verified, else False
    """
    audit = BRAVOAudit.objects.get(pk=audit_pk)

    candidates = audit.candidate_set
    preliminary_count = {}
    recount = {}
    # For each candidate sum the preliminary votes and recounted ballots
    for candidate in candidates:
        preliminary_count[candidate] = 0
        recount[candidate] = 0
        for table in candidate.tableregistry_set:
            for registry in table.tableregistry_set:
                preliminary_count[candidate] += registry.preliminary_votes
                recount[candidate] += registry.audited_votes

    W, L = BRAVO_get_W_L_sets(preliminary_count, audit.winners)
    Sw = {}
    for w in W:
        Sw[w] = 1

    Sl = {}
    for l in L:
        Sl[l] = 1

    return ballot_polling(audit, W, L, preliminary_count, recount, Sw, Sl)


######################### D'Hondt ######################################


def DHONDT_get_W_L_sets(vote_count, S):
    """
    Returns the reported winning and losing sets of parties
    @param vote_count   :   {dict<models.Party->int>}
                            Dictionary with the reported number of votes
                            per party
    @param S            :   {int}
                            Number of seats being competed for
    @return             :   {tuple<list<models.Party>, list<models.Party>>}
                            Tuple with the reported winning and losing
                            sets of parties
    """
    full_set = []
    for i in range(1, S + 1):
        for party in list(vote_count.keys()):
            full_set.append((party, i))

    sorted_tuples = sorted(full_set, key=(lambda x: p(x[0], vote_count, x[1])), reverse=True)
    W = sorted_tuples[:S]
    L = sorted_tuples[S:]
    return W, L


def dhondt(audit_pk):
    """
    Applies a risk limiting audit for a D'Hondt type election and determines if
    it has been verified or not. Tries to calculate the p-values for each
    null hypothesis between the reported winning and losing parties.
    @param audit_pk :   {int}
                        Primary key for the DHONDTAudit model
    @return         :   {bool}
                        True if the election has been verified, else False
    """
    audit = DHONDTAudit.objects.get(pk=audit_pk)

    parties = audit.party_set
    preliminary_count = {}
    recount = {}
    for party in parties:
        preliminary_count[party] = 0
        recount[party] = 0
        for party_member in party.partymember_set:
            for table in party_member.table_set:
                for registry in table.tableregistry_set:
                    preliminary_count[party] += registry.preliminary_votes
                    recount[party] += registry.audited_votes

    W, L = DHONDT_get_W_L_sets(preliminary_count, audit.seats)

    Sw = {}
    Sl = {}

    for party in parties:
        wp = list(filter(lambda x: x[0] == party, W))
        lp = list(filter(lambda x: x[0] == party, L))
        if wp:
            Sw[party] = max(wp, key=lambda x: x[1])[1]

        if lp:
            Sl[party] = min(lp, key=lambda x: x[1])[1]

    return ballot_polling(audit, W, L, preliminary_count, recount, Sw, Sl)
