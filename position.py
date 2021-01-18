import uuid
from dataclasses import dataclass
from dataclasses_json import dataclass_json
from dlgo.goboard_fast import Board, GameState, Move
from dlgo.gotypes import Player, Point
from dlgo.utils import coords_from_point, point_from_coords
from typing import Iterable, List, Optional

from katago import Command, MoveInfo, KataGoPlayer


def batch_translate_labels_to_coordinates(labels: Iterable[str]) -> Iterable[Point]:
    return [] if not labels else map(translate_label_to_point, labels)


def translate_label_to_point(label: str) -> Optional[Point]:
    return None if not label or label.lower() == 'pass' else point_from_coords(label)


@dataclass_json
@dataclass
class Position:
    ruleset: str = 'japanese'
    komi: float = 6.5
    initial_black: Optional[List[str]] = None
    initial_white: Optional[List[str]] = None
    initial_player: Optional[str] = 'b'
    moves: Optional[List[str]] = None

    @property
    def game(self) -> GameState:
        black = batch_translate_labels_to_coordinates(self.initial_black)
        white = batch_translate_labels_to_coordinates(self.initial_white)
        move_points = batch_translate_labels_to_coordinates(self.moves)
        player = Player.black if self.initial_player == 'b' else Player.white

        board = Board(19, 19)
        for b in black:
            board.place_stone(Player.black, b)
        for w in white:
            board.place_stone(Player.white, w)

        game = GameState(board, player, None, None)
        for move_point in move_points:
            move = Move.pass_turn() if not move_point else Move.play(move_point)
            game = game.apply_move(move)

        return game

    def command(self, move: Move = None) -> Command:
        command = Command()
        command.id = str(uuid.uuid4())
        command.komi = self.komi
        command.initialPlayer = KataGoPlayer.B if self.initial_player == 'b' else KataGoPlayer.W
        command.rules = self.ruleset

        command.initialStones = []
        if self.initial_black:
            command.initialStones += [MoveInfo(KataGoPlayer.B, x) for x in self.initial_black]
        if self.initial_white:
            command.initialStones += [MoveInfo(KataGoPlayer.W, x) for x in self.initial_white]

        command.moves = []
        player = command.initialPlayer
        if self.moves:
            for m in self.moves:
                move_info = MoveInfo(player, m)
                command.moves.append(move_info)
                player = player.opposite
        if move:
            command.moves.append(
                MoveInfo(
                    player,
                    'pass' if move.is_pass else coords_from_point(move.point)
                )
            )
            command.includePolicy = False

        command.analyzeTurns = [len(command.moves)]

        return command
