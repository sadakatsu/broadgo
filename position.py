import base64
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
    _game: Optional[GameState] = None

    @property
    def game(self) -> GameState:
        if not self._game:
            black = batch_translate_labels_to_coordinates(self.initial_black)
            white = batch_translate_labels_to_coordinates(self.initial_white)
            move_points = batch_translate_labels_to_coordinates(self.moves)
            player = Player.black if self.initial_player == 'b' else Player.white

            board = Board(19, 19)
            for b in black:
                board.place_stone(Player.black, b)
            for w in white:
                board.place_stone(Player.white, w)

            self._game = GameState(board, player, None, None)
            for move_point in move_points:
                move = Move.pass_turn() if not move_point else Move.play(move_point)
                self._game = self._game.apply_move(move)

        return self._game

    def command(self, move: Move = None) -> Command:
        command = Command()
        command.id = self._generate_id(move)
        command.komi = self.komi
        command.initialPlayer = KataGoPlayer.b if self.initial_player == 'b' else KataGoPlayer.w
        command.rules = self.ruleset

        command.initialStones = []
        if self.initial_black:
            command.initialStones += [MoveInfo(KataGoPlayer.b, x) for x in self.initial_black]
        if self.initial_white:
            command.initialStones += [MoveInfo(KataGoPlayer.w, x) for x in self.initial_white]

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
            # command.includePolicy = False

        command.analyzeTurns = [len(command.moves)]

        return command

    def _generate_id(self, move: Move = None) -> str:
        game = self._game if not move else self._game.apply_move(move)

        initial_black_encoding = self._encode_initial_placements(self.initial_black, 1)
        ibe_base64 = self._convert_code_to_dense_string(initial_black_encoding)

        initial_white_encoding = self._encode_initial_placements(self.initial_white, 2)
        iwe_base64 = self._convert_code_to_dense_string(initial_white_encoding)

        next_player = "b" if game.next_player == Player.black else "w"

        encoding = 0
        for row in range(1, 20):
            for column in range(1, 20):
                encoding *= 4
                point = Point(row, column)
                color = game.board.get(point)
                if not color:
                    play = Move.play(point)
                    if not game.is_valid_move(play):
                        encoding += 3
                elif color is Player.black:
                    encoding += 1
                else:
                    encoding += 2
        encoding_base64 = self._convert_code_to_dense_string(encoding)

        return f'{self.ruleset}_{self.komi}_{next_player}_{ibe_base64}_{iwe_base64}_{encoding_base64}'

    def _encode_initial_placements(self, placements, code):
        result = 0
        if placements:
            for label in placements:
                point = point_from_coords(label)
                power = (point.row - 1) * 19 + (point.col - 1)
                result += code * (4 ** power)
        return result

    def _convert_code_to_dense_string(self, value):
        if not value:
            value = 0
        bit_count = value.bit_length()
        return base64.b64encode(
                value.to_bytes(
                    bit_count // 8 + (0 if bit_count % 8 == 0 else 1),
                    byteorder='big'
                )
            ).decode('utf-8')
