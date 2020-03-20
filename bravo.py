import sys

import matplotlib.pyplot as plt
import pandas as pd
from numpy.random import choice


def validated(T, alpha):
    for winner in T:
        for loser in T[winner]:
            if T[winner][loser] < 1 / alpha:
                return False

    return True


def ballot_for_winner(T, S, alpha, w):
    for loser in T[w]:
        if T[w][loser] < 1 / alpha:
            T[w][loser] *= 2 * S[w][loser]

    return T


def ballot_for_loser(T, S, alpha, l):
    for winner in T:
        if T[winner][l] < 1 / alpha:
            T[winner][l] *= 2 * (1 - S[winner][l])

    return T


def simulate(df, alpha):
    vote_count = df.groupby('Candidato').sum()['Votos TRICEL']
    T = 1
    m = 0
    M = len(df)

    W = ['SEBASTIAN PIÑERA ECHENIQUE', 'ALEJANDRO  GUILLIER ALVAREZ']
    L = ['ALEJANDRO NAVARRO BRAIN', 'EDUARDO ARTES BRICHETTI', 'MARCO  ENRIQUEZ-OMINAMI GUMUCIO',
         'CAROLINA GOIC BOROEVIC', 'JOSE ANTONIO KAST RIST', 'BEATRIZ SANCHEZ MUÑOZ']
    T = {}
    S = {}
    for w in W:
        T[w] = {}
        S[w] = {}
        for l in L:
            T[w][l] = 1.0
            S[w][l] = vote_count[w] / (vote_count[w] + vote_count[l])

    candidates = [x for x, y in df.groupby('Candidato').sum()['Votos TRICEL'].items()]
    weights = [y for x, y in df.groupby('Candidato').sum()['Votos TRICEL'].items()]
    weight_sum = sum(weights)
    for i in range(len(weights)):
        weights[i] = weights[i] / weight_sum

    T_history = []
    while not validated(T, alpha):
        ballot = choice(candidates, p=weights)
        m += 1
        if ballot in W:
            T = ballot_for_winner(T, S, alpha, ballot)

        elif ballot in L:
            T = ballot_for_loser(T, S, alpha, ballot)

        min_T = 2 ** 31
        for w in T:
            for l in T[w]:
                min_T = min(min_T, T[w][l])

        T_history.append(max(0, 1 - 1.0 / min_T))
        if m >= M:
            return 'Preliminary count is incorrect', T_history

    return f'Election validated with {m} ballots', T_history


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print(f'Usage: {sys.argv[0]} risk-limit input-file reps')
        exit(1)

    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', None)

    alpha, input_file, n = sys.argv[1:4]
    alpha = float(alpha)
    df = pd.read_parquet(input_file)
    ms = []
    for i in range(int(n)):
        result, m = simulate(df, alpha)
        ms.append(m)
        print(result)

    for i, T in enumerate(ms):
        plt.plot(T)

    plt.show()
