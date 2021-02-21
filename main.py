from threading import Lock, Thread
from typing import Callable, List, Optional, Dict
import time
import yaml

from dlgo.gotypes import Point
from dlgo.utils import coords_from_point
from flask import Flask, request
from flask_cors import CORS
from flask_restful import Resource, Api
from position import Position, get_transformation, get_undo, translate_label_to_point
from katago import KataGo, Response, LineType, Command

app = Flask(__name__)
api = Api(app)
CORS(app)


def point_to_label(point: Optional[Point]) -> str:
    return 'pass' if not point else coords_from_point(point)


policy_points = [Point(row, col) for row in range(19, 0, -1) for col in range(1, 20)]


class KataGoExecution:
    def __init__(
        self,
        executable,
        configuration,
        model,
        analysis_threads,
        search_threads
    ):
        self.completed_count = 0
        self.elapsed = 0
        self.submitted_count = 0
        self.start = None
        self.visits = 0

        self.critical_section = Lock()
        self.position_results: Dict[str, Response] = {}
        self.query_to_positions = {}
        self.submitted = set()

        self.katago = KataGo(
            executable,
            configuration,
            model,
            analysis_threads=analysis_threads,
            search_threads=search_threads
        )

        while not self.katago.ready:
            time.sleep(0.001)

        def handle_katago_output():
            nonlocal self

            while True:
                result = self.katago.next_line()
                if not result:
                    time.sleep(0.001)
                else:
                    channel, line = result
                    if channel == LineType.error:
                        print('KataGo Log >', line)
                    else:
                        try:
                            # print('KataGo sent:', line)
                            response = Response.from_json(line)

                            # KataGo 1.8.0 seems to have broken the rootInfo field insofar as its documented purpose
                            # goes.  The documentation states:
                            # > A JSON dictionary with fields containing overall statistics for the requested turn
                            # > itself calculated in the same way as they would be for the next moves.
                            # Instead, the reported values are reported as they would be from the current position.
                            # Solving this requires negating the appropriate fields manually.
                            response.rootInfo = response.rootInfo.negate()

                            self.position_results[response.id] = response

                            self._log_received(response)
                        except Exception as e:
                            print('ERROR:', e)

        result_thread = Thread(target=handle_katago_output, args=())
        result_thread.daemon = True
        result_thread.start()

    def _log_received(self, response: Response):
        if not response.isDuringSearch:
            with self.critical_section:
                current_time = time.time()
                last_elapsed = current_time - self.start
                self.elapsed += last_elapsed
                self.completed_count += 1
                self.visits += response.rootInfo.visits

                if self.completed_count == self.submitted_count:
                    self.start = None
                else:
                    self.start = current_time

    def analyze(self, position_json):
        data = Position.from_json(position_json)
        game = data.game

        command, orientation = data.command()
        if command.id not in self.query_to_positions:
            commands: List[Command] = [command]

            transformation = get_transformation(orientation)

            package = {}
            self.query_to_positions[command.id] = package

            for move in game.legal_moves():
                if move.is_resign:
                    continue
                c, _ = data.command(move)
                commands.append(c)

                # NOTE: The game is in the orientation in which the server received the position.  All the analysis is
                # being done from the canonical representation's orientation.  That means we need to transform the legal
                # move before storing it in the package if we are to be able to correctly restore the analysis later!
                if move.is_pass:
                    move_label = 'pass'
                else:
                    move_label = coords_from_point(transformation(move.point))
                package[move_label] = c.id

            self._write_commands(commands)

        return f'{command.id}_{orientation}'

    def _write_commands(self, commands: List[Command]):
        with self.critical_section:
            if self.start is None:
                self.start = time.time()

            for c in commands:
                if c.id not in self.submitted:
                    self.katago.write_message(c.to_dict())
                    self.submitted_count += 1
                    self.submitted.add(c.id)

    def get_analysis_results(self, position_id: str, undo: Callable[[Optional[Point]], Optional[Point]]):
        global policy_points

        if position_id not in self.query_to_positions:
            raise Exception(f'There is no stored query with ID {position_id}.')

        def correct_label(canonical_label: str):
            return point_to_label(
                undo(
                    translate_label_to_point(canonical_label)
                )
            )

        payload = {'complete': True, 'moves': 1, 'movesComplete': 0, 'analyses': {}, 'direct': None}

        if position_id in self.position_results:
            position = self.position_results[position_id]
            payload['direct'] = position.to_dict()

            # We need to correct all the searched move and principal variation move labels to match the reference
            # orientation.
            for moveInfo in payload['direct']['moveInfos']:
                moveInfo['move'] = correct_label(moveInfo['move'])
                moveInfo['pv'] = [correct_label(x) for x in moveInfo['pv']]

            # We need to reorder the policy values so they match the reference orientation.  KataGo's documentation
            # states:
            # > Values are in row-major order, starting at the top-left of the board (e.g. A19) and going to the bottom
            # > right (e.g. T1). The last value in the array is the policy value for passing.
            for i, original_point in enumerate(policy_points):
                reference_point = undo(original_point)
                index = (19 - reference_point.row) * 19 + (reference_point.col - 1)
                payload['direct']['policy'][index] = position.policy[i]

            payload['movesComplete'] += 1

        for original_k, v in self.query_to_positions[position_id].items():
            restored_k = correct_label(original_k)

            payload['moves'] += 1
            if v in self.position_results:
                payload['analyses'][restored_k] = self.position_results[v].rootInfo.to_dict()
                payload['analyses'][restored_k]['id'] = self.position_results[v].id
                payload['movesComplete'] += 1

                # TODO: How can I make the included ID provide the correct transformation for the nested position?  I
                #  cannot use the parent position's orientation directly, since subsequent move can lead to its own
                #  unique canonical orientation.

        if payload['moves'] != payload['movesComplete']:
            payload['complete'] = False

        return payload

    def get_stats(self):
        with self.critical_section:
            return {
                "active": self.completed_count != self.submitted_count,
                "completed": self.completed_count,
                "searchTime": self.elapsed,
                "secondsPerPosition": self.elapsed / self.completed_count if self.completed_count else 0,
                "submitted": self.submitted_count,
                "visits": self.visits,
                "visitsPerSecond": self.visits / self.elapsed if self.elapsed else 0
            }


katago_execution: Optional[KataGoExecution] = None


class PositionResource(Resource):
    def get(self, id=None):
        if not id:
            response = self._return_statistics()
        else:
            response = self._return_query_result(id)
        return response

    def _return_statistics(self):
        global katago_execution
        return katago_execution.get_stats(), 200

    def _return_query_result(self, id_orientation):
        global katago_execution

        try:
            id = id_orientation[:-2]
            undo = get_undo(int(id_orientation[-1]))
            return katago_execution.get_analysis_results(id, undo), 200
        except Exception as e:
            print(e)
            return str(e), 400

    def post(self):
        global katago_execution
        return katago_execution.analyze(request.data), 200


api.add_resource(PositionResource, '/', '/<id>')

if __name__ == '__main__':
    with open('broadgo.yaml') as infile:
        application_configuration = yaml.load(infile)

    executable = application_configuration['executable']
    configuration = application_configuration['configuration']
    model = application_configuration['model']
    analysis_threads = application_configuration['analysisThreads']
    search_threads = application_configuration['searchThreads']

    katago_execution = KataGoExecution(executable, configuration, model, analysis_threads, search_threads)
    app.run(debug=True, use_reloader=False)
