from threading import Thread

from dlgo.utils import print_board, coords_from_point
from flask import Flask, request
from flask_restful import Resource, Api
from position import Position
from katago import KataGo, Response, LineType
import sys
import time
import uuid

katago = None

app = Flask(__name__)
api = Api(app)

position_results = {}
query_to_positions = {}


class PositionResource(Resource):
    def get(self, id=None):
        if not id:
            response = self._return_statistics()
        else:
            response = self._return_query_result(id)
        return response

    def _return_statistics(self):
        return 'This will be a statistics page some day.', 200

    def _return_query_result(self, id):
        if id not in query_to_positions:
            response = f'There is no stored query with ID {id}.', 400
        else:
            payload = {'complete': True, 'moves': 1, 'movesComplete': 0, 'analyses': {}, 'direct': None}

            if id in position_results:
                payload['direct'] = position_results[id].to_dict()
                payload['movesComplete'] += 1

            for k, v in query_to_positions[id].items():
                payload['moves'] += 1
                if v in position_results:
                    payload['analyses'][k] = position_results[v].rootInfo.to_dict()
                    payload['movesComplete'] += 1

            if payload['moves'] != payload['movesComplete']:
                payload['complete'] = False

            response = payload, 200
        return response

    def post(self):
        global katago, query_to_positions

        id = str(uuid.uuid4())
        package = {}
        query_to_positions[id] = package

        data = Position.from_json(request.data)
        game = data.game

        command = data.command()
        command.id = id
        katago.write_message(command)

        for move in game.legal_moves():
            if move.is_resign:
                continue
            command = data.command(move)
            package['pass' if move.is_pass else coords_from_point(move.point)] = command.id
            katago.write_message(command.to_dict())

        return id, 200


api.add_resource(PositionResource, '/', '/<id>')

if __name__ == '__main__':
    executable = sys.argv[1]
    configuration = sys.argv[2]
    model = sys.argv[3]

    katago = KataGo(executable, configuration, model)
    while not katago.ready:
        time.sleep(0.001)

    def handle_katago_output():
        global katago, position_results

        while True:
            result = katago.next_line()
            if not result:
                time.sleep(0.001)
            else:
                channel, line = result
                if channel == LineType.error:
                    print('KataGo Log >', line)
                else:
                    try:
                        response = Response.from_json(line)
                        position_results[response.id] = response
                    except Exception as e:
                        print('ERROR:', e)


    result_thread = Thread(target=handle_katago_output, args=())
    result_thread.daemon = True
    result_thread.start()

    app.run(debug=True, use_reloader=False)