import math
from decimal import Decimal

import requests


def get_random_seed(timestamp):
    """
    Obtains the random pulse at the specified time from the beacon
    @param timestamp    :   {django.db.models.DateTimeField}
                            Datetime specified for the pulse
    @return             :   {bytes}
                            Random pulse value in bytes format
    """
    beacon_api = 'https://random.uchile.cl/beacon/2.0/pulse/time/'
    seed_time = int(timestamp.timestamp() * 1000)  # 13 digits with 0's at the end (1587495000000)
    response = requests.get(beacon_api + str(seed_time))
    random_seed = bytes.fromhex(response.json()['pulse']['localRandomValue'])
    return random_seed


def get_sample(audit, sample_size):
    sample = audit.shuffled[:sample_size]
    tables = {}
    for table, ballot in sample:
        if table not in tables:
            tables[table] = []

        tables[table].append(ballot)

    for table in tables:
        tables[table].sort()

    tables = {table: ', '.join(tables[table]) for table in sorted(tables)}
    return tables


def max_p_value(subaudit):
    p_value = 0
    for w in subaudit.T:
        for l in subaudit.T[w]:
            p_value = max(p_value, 1 / subaudit.T[w][l])

    return p_value


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
    if Sw is None:
        Sw = {p: 1}

    if Sl is None:
        Sl = {q: 1}

    y1 = t(p, vote_count) / (t(p, vote_count) + t(q, vote_count))
    y2 = (d(Sw[p]) + d(Sl[q])) / d(Sw[p])
    return Decimal(y1 * y2)


def SPRT(vote_count, recount, T, risk_limit, Sw=None, Sl=None):
    for winner in T:
        for loser in T[winner]:
            if T[winner][loser] < 1 / risk_limit:
                y1 = gamma(winner, loser, Sw, Sl, vote_count)
                y2 = gamma(loser, winner, Sl, Sw, vote_count)
                T[winner][loser] *= y1 ** recount[winner] * y2 ** recount[loser]

    return T


def ASN(risk_limit, pw, pl, tot):
    """
    Wald's Average Sample Number to estimate the number of ballots needed to
    sample to verify the election
    @param risk_limit   :   {float}
                            Maximum p-value acceptable for any null hypothesis
                            to consider the election verified
    @param pw           :   {int}
                            Number of reported ballots for the winner with
                            the least votes
    @param pl           :   {int}
                            Number of reported ballots for the loser with
                            most votes
    @param tot          :   {int}
                            Total number of casted ballots
    @return             :   {int}
                            Estimated number of ballots needed to audit to
                            verify the election
    """
    margin = (pw - pl) / tot
    return int(2 * math.log(1 / risk_limit) / margin ** 2)
