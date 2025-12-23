import json

from dlgo.goboard_fast import GameState, Move, GoString
from dlgo.utils import print_board
from position import translate_label_to_point
from personalities.best import pick_best


def pick_no_atari(analysis: dict, game: GameState):
    """This personality picks the best move that is not an atari, unless a pass gets an equivalent result."""
    # print(f'# {json.dumps(analysis, indent=4)}')

    remove = []
    for move_label, entry in analysis.items():
        move_point = translate_label_to_point(move_label)
        if not move_point:
            continue

        move = Move(move_point)
        if not game.is_valid_move(move):
            print(f'# Skipping invalid move {move_label}')
            remove.append(move_label)
            continue

        next_game = game.apply_move(move)
        atari = False
        for neighbor in next_game.board.neighbors(move_point):
            group: GoString = next_game.board.get_go_string(neighbor)
            if group and group.color == next_game.next_player and group.num_liberties == 1:
                atari = True
                break
        if atari:
            remove.append(move_label)
            print(f'# Skipping atari {move_label}')

    for move_label in remove:
        analysis.pop(move_label, False)

    return pick_best(analysis, game)
