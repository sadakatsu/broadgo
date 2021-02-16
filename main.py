from threading import Lock, Thread
from typing import Optional, List
import sys
import time
import yaml

from dlgo.utils import coords_from_point
from flask import Flask, request
from flask_cors import CORS
from flask_restful import Resource, Api
from position import Position
from katago import KataGo, Response, LineType, Command

app = Flask(__name__)
api = Api(app)
CORS(app)


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
        self.position_results = {}
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

        command = data.command()
        if command.id not in self.query_to_positions:
            commands: List[Command] = [command]

            package = {}
            self.query_to_positions[command.id] = package

            for move in game.legal_moves():
                if move.is_resign:
                    continue
                c = data.command(move)
                package['pass' if move.is_pass else coords_from_point(move.point)] = c.id
                commands.append(c)

            self._write_commands(commands)

        return command.id

    def _write_commands(self, commands: List[Command]):
        with self.critical_section:
            if self.start is None:
                self.start = time.time()

            for c in commands:
                if c.id not in self.submitted:
                    self.katago.write_message(c.to_dict())
                    self.submitted_count += 1
                    self.submitted.add(c.id)

    def get_analysis_results(self, position_id: str):
        if position_id not in self.query_to_positions:
            raise Exception(f'There is no stored query with ID {position_id}.')

        payload = {'complete': True, 'moves': 1, 'movesComplete': 0, 'analyses': {}, 'direct': None}

        if position_id in self.position_results:
            payload['direct'] = self.position_results[position_id].to_dict()
            payload['movesComplete'] += 1

        for k, v in self.query_to_positions[position_id].items():
            payload['moves'] += 1
            if v in self.position_results:
                payload['analyses'][k] = self.position_results[v].rootInfo.to_dict()
                payload['movesComplete'] += 1

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

    def _return_query_result(self, id):
        global katago_execution

        try:
            return katago_execution.get_analysis_results(id), 200
        except Exception as e:
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
