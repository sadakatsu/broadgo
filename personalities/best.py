def pick_best(analysis, ignored):
    """This personality picks the most likely move that gets the best result, unless a pass gets an equivalent
    result."""
    _pass = analysis['pass']
    best = 'pass', _pass['scoreLead'], _pass['winrate'], _pass['prior']

    ordered = sorted(analysis, key=lambda x: analysis[x]['prior'], reverse=True)
    for move in ordered:
        if move == 'pass':
            continue
        entry = analysis[move]
        candidate = move, entry['scoreLead'], entry['winrate'], entry['prior']
        if best[1] - candidate[1] < -0.1:
            best = candidate

    print(
        f'# Selected {best[0]} with expected result {best[1]:0.1f}, win rate {best[2]:0.3f}, and prior {best[3]:0.3f}'
    )

    return best
