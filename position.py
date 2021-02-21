import base64
from dataclasses import dataclass
from dataclasses_json import dataclass_json
from dlgo.goboard_fast import Board, GameState, Move
from dlgo.gotypes import Player, Point
from dlgo.utils import coords_from_point, point_from_coords
from typing import Callable, Iterable, List, Optional, Tuple

from katago import Command, MoveInfo, KataGoPlayer


def batch_translate_labels_to_coordinates(labels: Iterable[str]) -> Iterable[Point]:
    return [] if not labels else map(translate_label_to_point, labels)


def translate_label_to_point(label: str) -> Optional[Point]:
    return None if not label or label.lower() == 'pass' else point_from_coords(label)


def smart_transformation(transformation: Callable[[Point], Point]):
    def curried(x: Optional[Point]):
        return transformation(x) if x else None
    return curried


def transform_0(point: Point): return point
def transform_1(point: Point): return Point(point.row, 20 - point.col)
def transform_2(point: Point): return Point(20 - point.row, point.col)
def transform_3(point: Point): return Point(20 - point.row, 20 - point.col)
def transform_4(point: Point): return Point(point.col, point.row)
def transform_5(point: Point): return Point(point.col, 20 - point.row)
def transform_6(point: Point): return Point(20 - point.col, point.row)
def transform_7(point: Point): return Point(20 - point.col, 20 - point.row)


transformations = [
    smart_transformation(transform_0),
    smart_transformation(transform_1),
    smart_transformation(transform_2),
    smart_transformation(transform_3),
    smart_transformation(transform_4),
    smart_transformation(transform_5),
    smart_transformation(transform_6),
    smart_transformation(transform_7)
]

# Nearly every transformation undoes itself.  The exceptions are 5 and 6, since they are diagonal mirrors.  This list is
# needed to be able to restore the original position from a transformed one.
undo_transformations = [
    transformations[0],
    transformations[1],
    transformations[2],
    transformations[3],
    transformations[4],
    transformations[6],
    transformations[5],
    transformations[7]
]


def get_transformation(ordinal: int) -> Callable[[Optional[Point]], Point]:
    global transformations
    return transformations[ordinal]


def get_undo(ordinal: int) -> Callable[[Optional[Point]], Point]:
    global undo_transformations
    return undo_transformations[ordinal]


intersections = [Point(row, col) for row in range(1, 20) for col in range(1, 20)]

# This code is here to prove that the transformations and the undo transformations are correct.
for i in range(len(transformations)):
    do = transformations[i]
    undo = undo_transformations[i]
    flipped = [undo(do(x)) for x in intersections]
    assert intersections == flipped


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

    def command(self, move: Move = None) -> Tuple[Command, int]:
        # Get the game that reflects the passed move having been played (if supplied).
        game = self.game if not move else self.game.apply_move(move)

        # Process the game board to get the necessary information to generate canonical encodings.
        point_plus_code: List[Tuple[Point, int]] = []
        for i in intersections:
            color = game.board.get(i)
            if not color:
                code = 0 if game.is_valid_move(Move.play(i)) else 3
            else:
                code = 1 if color == Player.black else 2
            if code:
                point_plus_code.append((i, code))

        # Select the transformation that leads to the lowest canonical position representation.
        selected_form = float('inf')
        selected_ordinal = -1
        selected_transformation = None
        for ordinal, transformation in enumerate(transformations):
            encoding = self._encode_point_colorings(point_plus_code, transformation)
            if encoding < selected_form:
                selected_form = encoding
                selected_ordinal = ordinal
                selected_transformation = transformation

        # Encode the resulting board position as a string.
        position_representation = self._convert_code_to_dense_string(selected_form)

        # Transform the starting stone points using the selected transformation.
        initial_positions_plus_colors: List[Tuple[Point, int]] = []
        initial_stones: List[Move] = []
        if self.initial_black:
            transformed_black_points = [
                selected_transformation(translate_label_to_point(x)) for x in self.initial_black
            ]
            initial_positions_plus_colors += [(x, 1) for x in transformed_black_points]
            initial_stones += [MoveInfo(KataGoPlayer.b, coords_from_point(x)) for x in transformed_black_points]
        if self.initial_white:
            transformed_white_points = [
                selected_transformation(translate_label_to_point(x)) for x in self.initial_white
            ]
            initial_positions_plus_colors += [(x, 2) for x in transformed_white_points]
            initial_stones += [MoveInfo(KataGoPlayer.w, coords_from_point(x)) for x in transformed_white_points]
        initial_form = self._encode_point_colorings(initial_positions_plus_colors)
        initial_representation = self._convert_code_to_dense_string(initial_form)

        # Compose an ID to use when communicating with KataGo.  Because it is possible to arrive at the same position
        # in multiple paths and/or transformations, this ID does NOT contain the information necessary to return to the
        # original representation.  That exists for communicating between the UI and the server ONLY.
        next_player = "b" if game.next_player == Player.black else "w"
        id = f'{self.ruleset}_{self.komi}_{next_player}_{initial_representation}_{position_representation}'

        # Build the command!
        command = Command()
        command.id = id
        command.komi = self.komi
        command.initialPlayer = KataGoPlayer.b if self.initial_player == 'b' else KataGoPlayer.w
        command.rules = self.ruleset
        command.initialStones = initial_stones

        command.moves = []
        player = command.initialPlayer
        for move in game.history:
            move_info = MoveInfo(
                player,
                'pass' if not move or move.is_pass else coords_from_point(selected_transformation(move.point))
            )
            command.moves.append(move_info)
            player = player.opposite

        command.analyzeTurns = [len(command.moves)]

        return command, selected_ordinal

    def _encode_point_colorings(
        self,
        point_plus_code: List[Tuple[Point, int]],
        transformation: Optional[Callable[[Optional[Point]], Optional[Point]]] = None
    ) -> int:
        encoding = 0
        for point, code in point_plus_code:
            transformed = transformation(point) if transformation else point
            power = (transformed.row - 1) * 19 + (transformed.col - 1)
            encoding += code * (4 ** power)
        return encoding

    def _convert_code_to_dense_string(self, value: int) -> str:
        if not value:
            value = 0
        bit_count = value.bit_length()
        return base64.b64encode(
                value.to_bytes(
                    bit_count // 8 + (0 if bit_count % 8 == 0 else 1),
                    byteorder='big'
                )
            ).decode('utf-8')
