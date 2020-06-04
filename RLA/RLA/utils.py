import math
import operator
from decimal import Decimal

import requests

SIMPLE_MAJORITY = 'simplemajority'
SUPER_MAJORITY = 'supermajority'
DHONDT = 'dhondt'

BALLOT_POLLING = 'ballotpolling'
COMPARISON = 'comparison'

PRIMARY = 'primary'


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
    """
    Gets a random sample of size sample_size from all the ballots cast at the election
    @param audit        :   {Audit}
                            Audit model
    @param sample_size  :   {int}
                            Number of ballots to sample
    @return             :   {dict<str->str>}
                            Dictionary with the ballots to sample per table
    """
    sample = audit.shuffled[:sample_size]
    tables = {}
    for table, ballot in sample:
        if table not in tables:
            tables[table] = []

        tables[table].append(str(ballot))

    for table in tables:
        tables[table].sort()

    tables = {table: ', '.join(tables[table]) for table in sorted(tables)}
    return tables


def max_p_value(T):
    """
    Calculates the maximum p-value from a Wald's SPRT matrix
    @param T    :   {dict<str->dict<str->float>>}
                    Wald's SPRT matrix with the inverse of the p-values for the
                    null hypothesis for each contest between winner-loser
    @return     :   {float}
                    Max p-value for all the contests
    """
    p_value = 0
    for w in T:
        for l in T[w]:
            p_value = max(p_value, 1 / T[w][l])

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


def e(p, reported, recount):
    """
    Error between reported and recounted cast ballots for a party
    @param p        :   {str}
                        Party name
    @param reported :   {dict<str->int>}
                        Reported cast ballots per party
    @param recount  :   {dict<str->int>}
                        Recounted cast ballots per party
    @return         :   {int}
                        Reported - recounted cast ballots for party p
    """
    return t(p, reported) - t(p, recount)


def d(s):
    """
    Returns the divisor for column s, starting from 0. In this case,
    the divisor of column s is always s + 1
    @param s    :   {int}
                    Column number
    @return     :   {int}
                    Divisor of column s
    """
    return s + 1


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


def ballot_polling_SPRT(vote_count, recount, T, risk_limit, Sw, Sl):
    """
    Calculates Wald's Sequential Probability Ratio Test for each contest between
    winner-loser, for the recounted ballots in ballot polling form
    @param vote_count   :   {dict<str->int>}
                            Reported ballots casted for each candidate
    @param recount      :   {dict<str->int}>
                            Recounted ballots for each candidate
    @param T            :   {dict<str->dict<str->float>>}
                            Wald's SPRT matrix
    @param risk_limit   :   {float}
                            Maximum p-value accepted to validate the election
    @param Sw           :   {dict<str->float>}
                            SPRT coefficients for each winner
    @param Sl           :   {dict<str->float>}
                            SPRT coefficient for each loser
    @return             :   {dict<str->dict<str->float>>}
                            Wald's SPRT matrix
    """
    for winner in T:
        for loser in T[winner]:
            if T[winner][loser] < 1 / risk_limit:
                y1 = gamma(winner, loser, Sw, Sl, vote_count)
                y2 = gamma(loser, winner, Sl, Sw, vote_count)
                T[winner][loser] *= y1 ** recount[winner] * y2 ** recount[loser]

    return T


def comparison_SPRT(report_count, table_report, table_recount, W, L, um, U, gamma=0.95):
    """
    Calculates Wald's Sequential Probability Ratio Test for the worst possible case
    in the table
    @param report_count :   {dict<str->int>}
                            Reported cast ballots for each candidate
    @param table_report :   {dict<str->int>}
                            Reported cast ballots for each candidate in a single table
    @param table_recount:   {dict<str->int>}
                            Recounted cast ballots for each candidate in a single table
    @param W            :   {list<tuple<str,int>>}
                            List of tuples with pairs winning candidate, column
    @param L            :   {list<tuple<str,int>>}
                            List of tuples with pairs losing candidate, column
    @param um           :   {float}
                            Upper bound on the MICRO for the table, scaled for multiple
                            votes per table
    @param U            :   {float}
                            Upper bound on the MICRO for the whole contest
    @param gamma        :   {float}
                            Security factor for escalating on errors
    @return             :   {float}
                            Update factor for the probability ratio on the contest
    """
    micro = MICRO(report_count, table_report, table_recount, W, L)
    Dm = micro / um
    return gamma * (1 - Dm) / (1 - 1 / U) + 1 - gamma


def ASN(risk_limit, vote_count, W, L):
    """
    Wald's Average Sample Number to estimate the number of ballots needed to
    sample to verify the election, assuming no invalid votes (nearly true, since
    they are usually a very small portion of the total)
    @param risk_limit   :   {float}
                            Maximum p-value acceptable for any null hypothesis
                            to consider the election verified
    @param vote_count   :   {dict<str->int>}
                            Number of reported ballots per candidate
    @param W            :   {list<str>}
                            List of winning candidates
    @param L            :   {list<str>}
                            List of losing candidates
    @return             :   {int}
                            Estimated number of ballots needed to audit to
                            verify the election
    """
    asn = 0
    for w in W:
        for l in L:
            pw = vote_count[w] / (vote_count[w] + vote_count[l])
            pl = vote_count[l] / (vote_count[w] + vote_count[l])
            sw = pw
            zw = math.log(2 * sw)
            zl = math.log(2 - 2 * sw)
            curr_asn = (math.log(1 / risk_limit) + zw / 2) / (pw * zw + pl * zl)
            asn = max(asn, curr_asn)

    return math.ceil(asn)


def uMax(party_votes, Sw, Sl):
    """
    Finds the upper bound on the overstatement per ballot on the MICRO for the contest
    @param party_votes  :   {dict<str->int>}
                            Reported casted ballots per party
    @param Sw           :   {dict<str->int>}
                            Largest divisor for any seat the party won
    @param Sl           :   {dict<str->int>}
                            Smallest divisor for any seat the party lost
    @return             :   {float}
                            Upper bound on overstatement per ballot
    """
    u = 0
    for w in Sw:
        for l in Sl:
            if w != l:
                u = max(u, (d(Sw[w]) + d(Sl[l])) / (d(Sl[l]) * party_votes[w] - d(Sw[w]) * party_votes[l]))

    return u


def dhondt_sample_size(ballots, risk_limit, party_votes, Sw, Sl, gamma=0.95):
    """
    Finds the minimum sample size to audit a D'Hondt election
    @param ballots      :   {int}
                            Number of ballots cast in the contest
    @param party_votes  :   {dict<str->int>}
                            Total ballots cast per party
    @param Sw           :   {dict<str->int>}
                            Largest divisor for any seat the party won
    @param Sl           :   {dict<str->int>}
                            Smallest divisor for any seat the party lost
    @param risk_limit   :   {float}
                            Maximum p-value acceptable for any null hypothesis
                            to consider the election verified
    @param gamma        :   {float}
                            Hedge against finding a ballot that attains
                            the upper bound. Larger values give less protection
    @return             :   {int}
                            Sample size to audit
    """
    u = uMax(party_votes, Sw, Sl)
    return math.ceil(
        math.log(1 / risk_limit) / math.log(gamma / (1 - 1 / (ballots * u)) + 1.0 - gamma)
    )


def dhondt_W_L_sets(vote_count, n_winners):
    """
    Obtains the winner and loser sets, given the amount of votes
    for each candidate
    @param vote_count   :   {dict<str->int>}
                            Dictionary with the reported amount of votes
                            per candidate
    @param n_winners    :   {int}
                            Number of winners for the election
    @return             :   {tuple<list<str>,list<str>>}
                            Tuple with the winners and losers sets
    """
    tuples = list(vote_count.items())
    sorted_tuples = sorted(tuples, key=operator.itemgetter(1), reverse=True)
    W = [c[0] for c in sorted_tuples[:n_winners]]
    L = [c[0] for c in sorted_tuples[n_winners:]]
    return W, L


def get_table_votes(vote_count_df, table):
    """
    Gets the number of votes for each candidate in a specific table
    @param vote_count_df    :   {DataFrame}
                                Pandas dataframe with the vote count
    @param table            :   {str}
                                Table identifier
    @return                 :   {dict<str->int>}
                                Number of votes per candidate in the table
    """
    df = vote_count_df[vote_count_df['table'] == table]
    return df.groupby('candidate').sum()['votes'].to_dict()


def MICRO(reported, table_report, recount, W, L):
    """
    Maximum In Contest Relative Overstatement for a table
    @param reported     :   {dict<str->int>}
                            Reported cast ballots per candidate
    @param table_report :   {dict<str->int>}
                            Reported cast ballots per candidate in a single table
    @param recount      :   {dict<str->int>}
                            Recounted cast ballots per candidate in a single table
    @param W            :   {list<tuple<str,int>>}
                            List of tuples with pairs winning candidate, column
    @param L            :   {list<tuple<str,int>>}
                            List of tuples with pairs losing candidate, column
    @return             :   {float}
                            MICRO for the recounted table
    """
    micro = 0
    for pw, sw in W:
        for pl, sl in L:
            if pw != pl:
                x = d(sl) * e(pw, table_report, recount) - d(sw) * e(pl, table_report, recount)
                y = (d(sl) * reported[pw] - d(sw) * reported[pl])
                micro = max(micro, x / y)

    return micro


def MICRO_upper_bound(reported, Wp, Lp, Sw, Sl):
    """
    MICRO upper bound for the contest
    @param reported :   {dict<str->int>}
                        Reported cast ballots per candidate
    @param Wp       :   {list<str>}
                        List of candidates that won at least 1 seat
    @param Lp       :   {list<str>}
                        List of candidates that lost at least 1 seat
    @param Sw       :   {dict<str->int>}
                        Largest divisor for any seat the party won
    @param Sl       :   {dict<str->int>}
                        Smallest divisor for any seat the party lost
    @return         :   {float}
                        Upper bound for MICRO in the contest
    """
    u = 0
    for w in Wp:
        for l in Lp:
            if w != l:
                curr_u = (d(Sl[l]) + d(Sw[w])) / (d(Sl[l]) * reported[w] - d(Sw[w]) * reported[l])
                u = max(u, curr_u)

    return u


def batch_error_upper_bound(batch_count, margin, Wp, Lp):
    """
    Upper bound on the error for a specific batch
    @param batch_count  :   {dict<str->int>}
                            Vote count for each candidate on the batch
    @param margin       :   {dict<str->dict<str->int>>}
                            Margin between each winner and loser
    @param Wp           :   {list<str>}
                            List of candidates that won at least 1 seat
    @param Lp           :   {list<str>}
                            List of candidates that lost at least 1 seat
    @return             :   {float}
                            Maximum upper bound on the error for the batch
    """
    up = 0
    np = sum(batch_count.values())
    for w in Wp:
        for l in Lp:
            if w != l:
                up = max(
                    up,
                    (batch_count[w] - batch_count[l] + np) / margin[w][l]
                )

    return up
