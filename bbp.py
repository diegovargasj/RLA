import numpy as np
from scipy.stats import binom
import scipy as sp
from tqdm import tqdm


def ballot_polling_sprt(sample, popsize, alpha, Vw, Vl,
                        null_margin=0):
    """
    Conduct Wald's SPRT for the difference in population counts for two out of three categories:

    H_0: Nl = Nw + null_margin
    H_1: Nl = Vl, Nw = Vw with Vw>Vl

    The type II error rate, usually denoted beta, is set to 0%.
    In doing so, the inverse of the likelihood ratio can be interpreted as a
    p-value.

    Parameters
    ----------
    sample : array-like
        random sample to audit. Elements should be labelled 1 (ballots for w),
        0 (ballots for l), and np.nan (the rest)
    popsize : int
        total size of population being audited
    alpha : float
        desired type 1 error rate
    Vw : int
        total number of votes for w under the alternative hypothesis
    Vl : int
        total number of votes for l under the alternative hypothesis
    null_margin : int
        vote margin between w and l under the null hypothesis; optional
        (default 0)
    Returns
    -------
    dict
    """

    # Set parameters
    beta = 0
    lower = beta / (1 - alpha)
    upper = (1 - beta) / alpha
    n = len(sample)
    sample = np.array(sample)
    Wn = np.sum(sample == 1)
    Ln = np.sum(sample == 0)
    Un = n - Wn - Ln
    decision = "None"

    # Set up likelihood for null and alternative hypotheses
    #    assert Vw > Vl, "Invalid alternative hypothesis. Vw must be larger than Vl"
    Vw = int(Vw)
    Vl = int(Vl)
    Vu = int(popsize - Vw - Vl)
    assert Vw >= Wn and Vl >= Ln and Vu >= Un, "Alternative hypothesis isn't consistent with the sample"
    alt_logLR = np.sum(np.log(Vw - np.arange(Wn))) + \
                np.sum(np.log(Vl - np.arange(Ln))) + \
                np.sum(np.log(Vu - np.arange(Un)))

    np.seterr(divide='ignore', invalid='ignore')
    null_logLR = lambda Nw: np.sum(np.log(Nw - np.arange(Wn))) + \
                            np.sum(np.log(Nw - null_margin - np.arange(Ln))) + \
                            np.sum(np.log(popsize - 2 * Nw + null_margin - np.arange(Un)))

    # This is for testing purposes. In practice, number_invalid will be unknown.
    upper_Nw_limit = np.ceil((popsize - Un + null_margin) / 2)
    lower_Nw_limit = int(np.max([Wn, Ln + null_margin]))

    # For extremely small or large null_margins, the limits do not
    # make sense with the sample values.
    if upper_Nw_limit < Wn or (upper_Nw_limit - null_margin) < Ln:
        return {'decision': 'Null is impossible, given the sample',
                'lower_threshold': lower,
                'upper_threshold': upper,
                'LR': np.inf,
                'pvalue': 0,
                'sample_proportion': (Wn / n, Ln / n, Un / n),
                'Nu_used': None,
                'Nw_used': None
                }

    if lower_Nw_limit > upper_Nw_limit:
        lower_Nw_limit, upper_Nw_limit = upper_Nw_limit, lower_Nw_limit

    #        print("null_margin=", null_margin)
    #        print("lower, upper limits=", lower_Nw_limit, upper_Nw_limit)

    LR_derivative = lambda Nw: np.sum([1 / (Nw - i) for i in range(Wn)]) + \
                               np.sum([1 / (Nw - null_margin - i) for i in range(Ln)]) - \
                               2 * np.sum([1 / (popsize - 2 * Nw + null_margin - i) for i in range(Un)])

    # Sometimes the upper_Nw_limit is too extreme, causing illegal 0s.
    # Check and change the limit when that occurs.
    if np.isinf(null_logLR(upper_Nw_limit)) or np.isinf(LR_derivative(upper_Nw_limit)):
        upper_Nw_limit -= 1

    # Check if the maximum occurs at an endpoint
    if np.sign(LR_derivative(upper_Nw_limit)) == np.sign(LR_derivative(lower_Nw_limit)):
        nuisance_param = upper_Nw_limit if null_logLR(upper_Nw_limit) >= null_logLR(
            lower_Nw_limit) else lower_Nw_limit
    # Otherwise, find the (unique) root of the derivative of the log likelihood ratio
    else:
        root = sp.optimize.brentq(LR_derivative, lower_Nw_limit, upper_Nw_limit)
        nuisance_param = np.floor(root) if null_logLR(np.floor(root)) >= null_logLR(np.ceil(root)) else np.ceil(
            root)
    number_invalid = popsize - nuisance_param * 2 + null_margin

    if nuisance_param < 0 or nuisance_param > popsize:
        return {'decision': 'Number invalid is incompatible with the null',
                'lower_threshold': lower,
                'upper_threshold': upper,
                'LR': np.inf,
                'pvalue': 0,
                'sample_proportion': (Wn / n, Ln / n, Un / n),
                'Nu_used': number_invalid,
                'Nw_used': nuisance_param
                }
    if nuisance_param < Wn or (nuisance_param - null_margin) < Ln \
            or number_invalid < Un:
        return {'decision': 'Null is impossible, given the sample',
                'lower_threshold': lower,
                'upper_threshold': upper,
                'LR': np.inf,
                'pvalue': 0,
                'sample_proportion': (Wn / n, Ln / n, Un / n),
                'Nu_used': number_invalid,
                'Nw_used': nuisance_param
                }

    logLR = alt_logLR - null_logLR(nuisance_param)
    LR = np.exp(logLR)

    if LR <= lower:
        # accept the null and stop
        decision = 0

    if LR >= upper:
        # reject the null and stop
        decision = 1

    return {'decision': decision,
            'lower_threshold': lower,
            'upper_threshold': upper,
            'LR': LR,
            'pvalue': min(1, 1 / LR),
            'sample_proportion': (Wn / n, Ln / n, Un / n),
            'Nu_used': number_invalid,
            'Nw_used': nuisance_param
            }


def compute_unconditional_power(Nw, Nl, popsize, pi, alpha, reps=10000):
    """
    Estimate unconditional power of the test: sample at rate pi, then run the SPRT on that sample.
    Calculations assume that the reported margin is correct and that the nuisance parameter
    (total number of ballots for either w or l) is known.

    Nw = total number of votes reported for w,
    Nl = total number of votes reported for l,
    popsize = total population size,
    pi = the sampling probability,
    alpha = the type I error rate,
    reps = number of simulations
    """
    pvalues = np.zeros(reps)
    population = np.array([0] * Nl + [1] * Nw + [np.nan] * (popsize - Nw - Nl))  # Population of ballots (truth)
    np.random.shuffle(population)
    for i in tqdm(range(reps)):
        n = binom.rvs(popsize, pi)
        sam = np.random.choice(population, size=n, replace=False)
        res = ballot_polling_sprt(sample=sam, popsize=popsize, alpha=alpha, Vw=Nw, Vl=Nl)
        pvalues[i] = res['pvalue']

    power = np.mean(pvalues <= alpha)
    return power


alpha = 0.05
N = [10**5, 10**6, 10**7]
power = [0.8, 0.9, 0.99]
popsize = 10 ** 5
reps = 10000
lo_pi = 0.04

m = 0.01
Nw = int(0.5*popsize*(m+1))
Nl = popsize - Nw

x = compute_unconditional_power(Nw=Nw, Nl=Nl, popsize=popsize, pi=lo_pi, alpha=alpha, reps=reps)
print(x)
