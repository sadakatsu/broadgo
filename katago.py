import enum
import io
import jsons
import os
import subprocess
from collections import namedtuple
from dataclasses import dataclass, field

from enum import auto, Enum
from threading import Thread
from typing import List, Optional

from dataclasses_json import dataclass_json


class LineType(Enum):
    error = auto()
    output = auto()


class KataGo:
    def __init__(self, executable, configuration, model, analysis_threads=10, search_threads=1, output=False):
        self.output = output
        if output:
            print('  Launching KataGo...')

        def read_stream(name, stream, type_, buffer):
            if output:
                print(f'  {name} thread has begun.')
            while True:
                line = stream.readline().rstrip()
                if (
                    not self._ready and
                    type_ is LineType.error and
                    line.endswith('Started, ready to begin handling requests')
                ):
                    self._ready = True
                    if output:
                        print('  KataGo is ready to accept inputs.')
                if output:
                    print(f'  {name} read: {line}')
                if line:
                    buffer.append((type_, line))
                else:
                    if output:
                        print(f'  {name} thread has finished.')
                    break

        command = f'{executable} analysis -config {configuration} -model {model} -analysis-threads {analysis_threads} ' \
                  f'-override-config numSearchThreads={search_threads}'
        self._process = subprocess.Popen(
            command,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )

        self._buffer = []
        self._ready = False

        stderr = io.TextIOWrapper(self._process.stderr, encoding='utf-8', errors='strict')
        self._errors = Thread(target=read_stream, args=('ERR', stderr, LineType.error, self._buffer))
        self._errors.daemon = True
        self._errors.start()

        stdout = io.TextIOWrapper(self._process.stdout, encoding='utf-8', errors='strict')
        self._outputs = Thread(target=read_stream, args=('OUT', stdout, LineType.output, self._buffer))
        self._outputs.daemon = True
        self._outputs.start()

        if output:
            print('  KataGo has launched.')

    @property
    def ready(self):
        return self._ready

    def write_message(self, message):
        if self.output:
            print(f'  KataGo::write_message() called...')
        if not self._ready:
            raise Exception('KataGo is not ready!  Learn some damn patience.')
        command = jsons.dumps(message, strip_nulls=True) + os.linesep
        encoded = command.encode('utf-8')
        self._process.stdin.write(encoded)
        self._process.stdin.flush()
        if self.output:
            print(f'  Passed message to KataGo: {encoded}')

    def next_line(self):
        return self._buffer.pop(0) if self._buffer else None

    def kill(self):
        if self.output:
            print('  KataGo::kill() called...')
        self._process.kill()
        if self.output:
            print('  KataGo::kill() call complete.')


class KataGoPlayer(enum.Enum):
    B = 'B'
    W = 'W'

    @property
    def opposite(self):
        return KataGoPlayer.B if self is KataGoPlayer.W else KataGoPlayer.W

    def __str__(self):
        return 'B' if self is KataGoPlayer.B else 'W'

    def __repr__(self):
        return self.__str__()


class MoveInfo(namedtuple('MoveInfo', 'player location')):
    pass


@dataclass
class SearchFocus:
    player: KataGoPlayer
    moves: List[str]
    untilDepth: int


@dataclass_json
@dataclass(init=False)
class Command:
    id: str

    initialPlayer: KataGoPlayer
    initialStones: List[MoveInfo]
    moves: List[MoveInfo]
    rules: str

    boardXSize: int = 19
    boardYSize: int = 19
    includePolicy: Optional[bool] = True

    allowMoves: Optional[SearchFocus] = None
    analyzeTurns: Optional[List[int]] = None
    avoidMoves: Optional[SearchFocus] = None
    includeMovesOwnership: Optional[bool] = None
    includeOwnership: Optional[bool] = None
    includePVVisits: Optional[bool] = None
    komi: Optional[float] = None
    maxVisits: Optional[int] = None
    overrideSettings: Optional[dict] = None
    priority: Optional[int] = None
    priorities: Optional[List[int]] = None
    reportDuringSearchEvery: Optional[float] = None
    rootPolicyTemperature: Optional[float] = None
    whiteHandicapBonus: Optional[str] = None


@dataclass_json
@dataclass()
class RootAnalysis:
    scoreSelfplay: float
    scoreLead: float
    utility: float
    winrate: float
    visits: int


@dataclass_json
@dataclass()
class MoveAnalysis(RootAnalysis):
    lcb: float
    move: str
    order: int
    prior: float
    pv: List[str]
    scoreMean: float
    scoreStdev: float
    utilityLcb: float

    pvVisits: Optional[List[int]] = None
    ownership: Optional[List[float]] = None


@dataclass_json
@dataclass()
class Response:
    id: str

    turnNumber: int
    rootInfo: RootAnalysis
    moveInfos: List[MoveAnalysis] = field(default_factory=list)

    isDuringSearch: Optional[bool] = None
    ownership: Optional[List[float]] = field(default_factory=list)
    policy: Optional[List[float]] = field(default_factory=list)
