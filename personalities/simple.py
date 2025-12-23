import random

# import numpy as np

# EPSILON = np.finfo(float).eps


def pick_simple(analysis, ignored):
    # Find the best move score.
    best_score = -float('inf')
    for info in analysis.values():
        if info['scoreLead'] > best_score:
            best_score = info['scoreLead']

    # Short-circuit if passing is equivalent to the best move.
    info = analysis['pass']
    if info['scoreLead'] + 0.5 > best_score:
        move = 'pass'
        score = info['scoreLead']
        winrate = info['winrate']
        prior = info['humanPrior']

    # Otherwise, randomly select a move that does not lose too many points using the human priors.
    else:
        candidates = []
        total = 0.
        for move, info in analysis.items():
            if info['scoreLead'] + 0.5 <= best_score:
                continue
            score = info['scoreLead']
            winrate = info['winrate']
            prior = info['humanPrior']
            candidates.append((move, score, winrate, prior))
            total += prior

        p = random.random() * total
        random.shuffle(candidates)
        for move, score, winrate, prior in candidates:
            p -= prior
            if p <= 0.:
                break

    print(
        f'# Selected {move} with expected result {score:0.1f}, win rate {winrate:0.3f}, and prior {prior:0.3f}.'
    )

    return move, score, winrate, prior
