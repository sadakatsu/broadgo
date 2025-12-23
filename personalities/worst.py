from personalities.best import pick_best


def pick_worst(analysis, ignored):
    """This personality picks the least likely move that gets the worst result, unless a pass gets an equivalent
    result."""

    # Pass iff passing is the best move on the board to avoid early game termination.
    best = pick_best(analysis)
    if best[0] == 'pass':
        return best

    worst = None

    ordered = sorted(analysis, key=lambda x: analysis[x]['prior'])
    for move in ordered:
        if move == 'pass':
            continue
        entry = analysis[move]
        candidate = move, entry['scoreLead'], entry['winrate'], entry['prior']
        if worst is None or worst[1] - candidate[1] > -0.1:
            worst = candidate

    print(
        f'# Selected {worst[0]} with expected result {worst[1]:0.1f}, win rate {worst[2]:0.3f}, and prior '
        f'{worst[3]:0.3f}'
    )

    return worst
