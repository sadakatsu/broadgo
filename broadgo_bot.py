import io
import re
import requests
import subprocess
import sys
import time

from threading import Thread
from typing import Callable, List, Union, Tuple

from dlgo.goboard_fast import GameState, Board
from dlgo.utils import point_from_coords, print_board
from katago import LineType
from personalities.best import pick_best
from personalities.no_atari import pick_no_atari
from personalities.random_personality import pick_random
from personalities.simple import pick_simple
from personalities.worst import pick_worst
from position import Position


class BroadGoServer:
    def __init__(self):
        katago_ready_pattern = re.compile(r'^.*Started, ready to begin handling requests.*$')
        server_ready_pattern = re.compile(r'^.*Running on (\S+) \(Press CTRL\+C to quit\).*$')

        def read_stream(_, stream, _type, buffer):
            while True:
                line = stream.readline().rstrip()
                if line:
                    # print(f'# {line}')
                    if not self.ready:
                        if not self._katago_ready:
                            matcher = katago_ready_pattern.match(line)
                            if matcher:
                                self._katago_ready = True
                        if not self._server_ready:
                            matcher = server_ready_pattern.match(line)
                            if matcher:
                                self._server_ready = True
                                self._host = matcher.group(1)
                    buffer.append((_type, line))
                else:
                    break

        self._process = subprocess.Popen(
            'python main.py',
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )

        self._buffer = []
        self._server_ready = False
        self._katago_ready = False
        self._host = None

        stderr = io.TextIOWrapper(self._process.stderr, encoding='utf-8', errors='strict')
        self._errors = Thread(target=read_stream, args=('ERR', stderr, LineType.error, self._buffer))
        self._errors.daemon = True
        self._errors.start()

        stdout = io.TextIOWrapper(self._process.stdout, encoding='utf-8', errors='strict')
        self._outputs = Thread(target=read_stream, args=('OUT', stdout, LineType.output, self._buffer))
        self._outputs.daemon = True
        self._outputs.start()

    @property
    def ready(self):
        return self._server_ready and self._katago_ready

    def analyze(self, position: Position):
        response = requests.post(self._host, json=position.to_dict())
        if response.status_code != 200:
            raise Exception(f'FAILED: {response}')

        url = f'{self._host}{response.json()}'
        finished = False
        while not finished:
            response = requests.get(url)
            if response.status_code != 200:
                raise Exception(f'FAILED: {response}')

            analysis = response.json()
            progress = analysis['movesComplete'] / analysis['moves']
            finished = analysis['complete']
            print(f'# Progress: {progress * 100:0.2f}%\n', sep=None, end=None)

            if not finished:
                time.sleep(0.5)

        policy = analysis['direct']['policy']
        human_policy = analysis['direct']['humanPolicy']
        results = analysis['analyses']
        for k, v in results.items():
            if k == 'pass':
                index = 361
            else:
                point = point_from_coords(k)
                opposite_row = 19 - point.row
                index = 19 * opposite_row + point.col - 1
            # I don't know why I am correcting these anymore...
            v['prior'] = policy[index]
            v['humanPrior'] = human_policy[index]
        return results

    def kill(self):
        while not self.ready:
            time.sleep(0.001)
        self._process.kill()


label_regex = re.compile(r'[A-HJ-T](?:[1-9](?!\d)|1[0-9])')


def run_gtp(broadgo: BroadGoServer, heuristic: Callable[[dict, GameState], Tuple[str, float, float, float]]):
    known = {
        'boardsize',
        'clear_board',
        'fixed_handicap',
        'genmove',
        'known_command',
        'komi',
        'list_commands',
        'name',
        'place_free_handicap',
        'play',
        'protocol_version',
        'quit',
        'set_free_handicap',
        'undo',
        'version'
    }
    representation = '\n'.join([x for x in known])

    handicap_placements = {
        0: [],
        2: ['D4', 'Q16'],
        3: ['D4', 'Q16', 'D16'],
        4: ['D4', 'Q16', 'D16', 'Q4'],
        5: ['D4', 'Q16', 'D16', 'Q4', 'K10'],
        6: ['D4', 'Q16', 'D16', 'Q4', 'D10', 'Q10'],
        7: ['D4', 'Q16', 'D16', 'Q4', 'D10', 'Q10', 'K10'],
        8: ['D4', 'Q16', 'D16', 'Q4', 'D10', 'Q10', 'K4', 'K16'],
        9: ['D4', 'Q16', 'D16', 'Q4', 'D10', 'Q10', 'K4', 'K16', 'K10'],
    }

    komi = 6.5
    chosen_handicap = []
    history: Union[List[Position], None] = None

    def reset_history():
        nonlocal history
        history = [
            Position(
                komi=komi,
                initial_black=chosen_handicap,
                initial_player='w' if len(chosen_handicap) else 'b',
                moves=[]
            )
        ]

    reset_history()

    stop = False
    for line in sys.stdin:
        # Parse input
        sanitized = re.sub(r'[^\t\n -~]', '', line)
        uncommented = re.sub(r'#.*$', '', sanitized)
        spaced = uncommented.replace('\t', ' ')
        condensed = re.sub(' +', ' ', spaced)
        trimmed = condensed.strip()
        if not trimmed:
            continue

        tokens = trimmed.split()
        count = len(tokens)

        if count > 1:
            try:
                message_id = int(tokens[0])
                command = tokens[1]
                arguments = [] if count < 3 else tokens[2:]
            except ValueError:
                message_id = None
                command = tokens[0]
                arguments = tokens[1:]
        else:
            message_id = None
            command = tokens[0]
            arguments = []

        # Handle commands
        error = ''
        success = ''
        if command not in known:
            error = f'unknown command "{command}"'
        elif command == 'boardsize':
            if len(arguments) != 1:
                error = 'wrong number of arguments'
            elif arguments[0] != '19':
                error = 'unacceptable size # broadgo only plays 19x19'
            else:
                reset_history()
        elif command == 'clear_board':
            reset_history()
            print_board(history[-1].game.board, prefix='# ')
        elif command == 'fixed_handicap' or command == 'place_free_handicap':
            if len(arguments) != 1:
                error = 'wrong number of arguments'
            elif len(history) > 1:
                error = 'game in progress'
            else:
                try:
                    handicap_count = int(arguments[0])
                    if not (handicap_count == 0 or 2 <= handicap_count <= 9):
                        error = 'illegal handicap value; must be 0 or [2, 9]'
                    else:
                        chosen_handicap = handicap_placements[handicap_count]
                        reset_history()
                        success = ' '.join(chosen_handicap)
                except ValueError:
                    error = 'invalid value'
        elif command == 'genmove':
            if len(arguments) != 1:
                error = 'wrong number of arguments'
            else:
                try:
                    color = parse_color(arguments[0])

                    current_position = history[-1]
                    next_position = Position(
                        ruleset=current_position.ruleset,
                        komi=current_position.komi,
                        initial_black=current_position.initial_black,
                        initial_white=current_position.initial_white,
                        initial_player=current_position.initial_player,
                        moves=[x for x in current_position.moves]
                    )
                    moves_so_far = len(current_position.moves)
                    should_play_offset = moves_so_far % 2
                    if should_play_offset:
                        expected = 'w' if current_position.initial_player == 'b' else 'b'
                    else:
                        expected = 'b' if current_position.initial_player == 'b' else 'w'

                    if color != expected:
                        next_position.moves.append('pass')

                    analysis = broadgo.analyze(next_position)
                    move, expected_result, win_rate, prior = heuristic(analysis, next_position.game)
                    next_position.moves.append(move)
                    history.append(next_position)
                    success = move
                    # success = f'{move}\n# expected result {expected_result}, win rate {win_rate}, prior {prior}'
                    print_board(next_position.game.board, prefix='# ')
                except ValueError:
                    error = f'invalid arguments: {arguments[0]} {arguments[1]}'
        elif command == 'known_command':
            if len(arguments) != 1:
                error = 'wrong number of arguments'
            else:
                success = 'true' if arguments[0] in known else 'false'
        elif command == 'komi':
            if len(arguments) != 1:
                error = 'wrong number of arguments'
            try:
                komi = float(arguments[0])
                for entry in history:
                    entry.komi = komi
            except ValueError:
                error = 'invalid value'
        elif command == 'list_commands':
            success = representation
        elif command == 'name':
            success = 'broadgo'
        elif command == 'play':
            if len(arguments) != 2:
                error = 'wrong number of arguments'
            try:
                color = parse_color(arguments[0])
                move = parse_move(arguments[1])

                current_position = history[-1]
                next_position = Position(
                    ruleset=current_position.ruleset,
                    komi=current_position.komi,
                    initial_black=current_position.initial_black,
                    initial_white=current_position.initial_white,
                    initial_player=current_position.initial_player,
                    moves=[x for x in current_position.moves]
                )
                moves_so_far = len(current_position.moves)
                should_play_offset = moves_so_far % 2
                if should_play_offset:
                    expected = 'w' if current_position.initial_player == 'b' else 'b'
                else:
                    expected = 'b' if current_position.initial_player == 'b' else 'w'

                if color != expected:
                    next_position.moves.append('pass')
                next_position.moves.append(move)

                history.append(next_position)

                print_board(next_position.game.board, prefix='# ')
            except ValueError as e:
                print(f'# {e}')
                error = f'invalid arguments: {arguments[0]} {arguments[1]}'
        elif command == 'protocol_version':
            success = '2'
        elif command == 'quit':
            stop = True
        elif command == 'set_free_handicap':
            if len(arguments) < 2 or len(arguments) > 360:
                error = 'wrong number of arguments'
            elif len(history) > 1:
                error = 'game in progress'
            else:
                try:
                    converted = [parse_label(x) for x in arguments]
                    if len(set(converted)) != len(converted):
                        error = 'labels had at least one duplicate'
                    else:
                        chosen_handicap = converted
                        reset_history()
                except ValueError:
                    error = 'received value that is not a valid label'
        elif command == 'undo':
            if len(history) == 1:
                error = 'cannot undo'
            else:
                history.pop()
                print_board(history[-1].game.board, prefix='# ')
        elif command == 'version':
            success = ''

        # Write results
        if error:
            print(f'?{message_id or ""} {error}\n\n', sep=None, end=None)
        else:
            print(f'={message_id or ""}{" " + success if success else ""}\n\n', sep=None, end=None)
        sys.stdout.flush()

        # Determine continuation
        if stop:
            break


def parse_color(value):
    simplified = value.lower()
    if simplified in ('b', 'black'):
        color = 'b'
    elif simplified in ('w', 'white'):
        color = 'w'
    else:
        raise ValueError(f'could not parse {value}')
    return color


def parse_move(move):
    simplified = move.upper()
    if simplified == 'PASS':
        result = 'pass'
    else:
        result = parse_label(move)
    return result


def parse_label(label):
    simplified = label.upper()
    if not label_regex.match(simplified):
        raise ValueError(f'could not parse {label}')
    return simplified


def run_bot(heuristic):
    broadgo = BroadGoServer()
    while not broadgo.ready:
        pass

    try:
        run_gtp(broadgo, heuristic)
    finally:
        broadgo.kill()


if __name__ == '__main__':
    choice = None if len(sys.argv) < 2 else sys.argv[1]
    if not choice or choice == 'best':
        heuristic = pick_best
    elif choice == 'worst':
        heuristic = pick_worst
    elif choice == 'random':
        heuristic = pick_random
    elif choice == 'no-atari':
        heuristic = pick_no_atari
    elif choice == 'simple':
        heuristic = pick_simple
    else:
        raise Exception(f'unknown personality: {choice}')
    run_bot(heuristic)
