import random

from personalities.best import pick_best


def pick_random(analysis, ignored):
    """This personality picks the least likely move that gets the worst result, unless a pass gets an equivalent
    result."""

    # Pass iff passing is the best move on the board to avoid early game termination.
    best = pick_best(analysis)
    if best[0] == 'pass':
        return best

    options = [x for x in analysis.keys() if x != 'pass']
    move = random.choice(options)
    entry = analysis[move]
    return move, entry['scoreLead'], entry['winrate'], entry['prior']
