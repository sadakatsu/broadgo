import { DOCUMENT } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, Inject, Input, OnDestroy, OnInit } from '@angular/core';
import { concat, Observable, of, Subject, Subscription, timer } from 'rxjs';
import { switchMap, takeWhile, tap } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { CompositeAnalysis } from '../../domain/composite_analysis';
import { Coordinate } from '../../domain/coordinate';
import { GameState } from '../../domain/game_state';
import { NodeData } from '../../domain/node_data';
import { MoveService } from '../../services/move.service';
import { PositionService } from '../../services/position.service';
import { coordinate_to_label, label_to_coordinate } from '../../utils/intersection_helpers';

interface Tree {
    branches: Array<string>;
    continuations: { [propName: string]: Tree };
    createdBy: Coordinate | null;
    data: NodeData;
    parent: Tree | null;
    position: number;
}

@Component({
    selector: 'bg-search',
    templateUrl: './search.component.html',
    styleUrls: [ './search.component.scss' ],
})
export class SearchComponent implements OnInit, OnDestroy {
    @Input()
    root: NodeData;

    analysis$: Observable<any>;
    currentNode: Tree;
    performance$: Observable<any>;
    searchTree: Tree;

    private readonly subject: Subject<GameState>;
    private readonly subscription: Subscription;
    private readonly WGo: any;

    constructor(
        @Inject(DOCUMENT) private document: Document,
        private http: HttpClient,
        private moveService: MoveService,
        private positionService: PositionService
    ) {
        this.WGo = document.defaultView.window['WGo'];
        this.subject = new Subject<GameState>();
        this.subscription = this.moveService.moves$.subscribe(
            coordinate => this.handleMove(coordinate)
        );
    }

    private handleMove(coordinate: Coordinate) {
        if (
            !(
                coordinate &&
                this.currentNode &&
                this.currentNode.data.game &&
                this.currentNode.data.game.isValid(coordinate.x, coordinate.y)
            )
        ) {
            return;
        }

        const label = coordinate_to_label(coordinate);

        if (!(label in this.currentNode.continuations)) {
            this.currentNode.branches.push(label);

            // const next_game = this.currentNode.data.game.play(coordinate.x, coordinate.y);
            const nextGame = this.copyGame(this.currentNode.data.game);
            nextGame.play(coordinate.x, coordinate.y);

            const state = this.currentNode.data.state;
            const nextState = {
                ruleset: state.ruleset,
                komi: state.komi,
                initial_black: state.initial_black ? [...state.initial_black] : undefined,
                initial_white: state.initial_white ? [...state.initial_white] : undefined,
                initial_player: state.initial_player ? state.initial_player : undefined,
                moves: state.moves ? [...state.moves] : []
            };
            nextState.moves.push(label);

            this.currentNode.continuations[label] = {
                branches: [],
                continuations: {},
                createdBy: coordinate,
                data: {
                    game: nextGame,
                    state: nextState
                },
                parent: this.currentNode,
                position: this.currentNode.position + 1,
            };
        }

        this.currentNode = this.currentNode.continuations[label];
        this.publishCurrentPosition();
    }

    private copyGame(currentGame) {
        const nextGame = new this.WGo.Game(currentGame.size, currentGame.repeating);
        nextGame.popPosition();
        nextGame.pushPosition(currentGame.getPosition());
        nextGame.turn = currentGame.turn;
        return nextGame;
    }

    private publishCurrentPosition() {
        setTimeout(
            () => {
                this.positionService.publish({
                    continuations: this.currentNode.branches.map(label_to_coordinate),
                    lastMove: this.currentNode.createdBy,
                    position: this.currentNode.data.game.getPosition()
                });
                this.subject.next(this.currentNode.data.state);
            },
            0
        );
    }

    ngOnInit() {
        this.searchTree = {
            branches: [],
            continuations: {},
            createdBy: null,
            data: this.root,
            parent: null,
            position: 1
        };
        this.currentNode = this.searchTree;

        this.analysis$ = this.subject.pipe(
            switchMap(state => this.http.post(environment.positionUrl, state)),
            switchMap(
                id => timer(0, 2500)
                    .pipe(
                        switchMap(
                            () => this.http.get<CompositeAnalysis>(`${environment.positionUrl}/${id}`)
                        ),
                        takeWhile(analysis => !analysis.complete, true)
                    )
            )
        );

        this.performance$ = concat(
            of(
                {
                    active: false,
                    completed: 0,
                    searchTime: 0,
                    secondsPerPosition: 0,
                    submitted: 0,
                    visits: 0,
                    visitsPerSecond: 0
                }
            ),
            timer(0, 2500)
                .pipe(
                    switchMap(() => this.http.get<any>(environment.positionUrl))
                )
        );

        this.publishCurrentPosition();
    }

    getCurrentBranchLength() {
        if (this.currentNode) {
            let current = this.currentNode;
            while (current.branches.length > 0) {
                current = current.continuations[current.branches[0]];
            }
            return current.position;
        } else {
            return 0;
        }
    }

    findNextBranchingPoint() {
        if (this.currentNode) {
            let current = this.currentNode;
            while (current.branches.length === 1) {
                current = current.continuations[current.branches[0]];
            }
            return current !== this.currentNode ? current : null;
        } else {
            return null;
        }
    }

    findPreviousBranchingPoint() {
        if (this.currentNode && this.currentNode.parent) {
            let current = this.currentNode.parent;
            while (current.branches.length === 1 && current.parent !== null) {
                current = current.parent;
            }
            return current;
        } else {
            return null;
        }
    }

    onFirst() {
        if (this.currentNode !== this.searchTree) {
            this.currentNode = this.searchTree;
            this.publishCurrentPosition();
        }
    }

    onPreviousBranch() {
        const target = this.findPreviousBranchingPoint();
        if (target) {
            this.currentNode = target;
            this.publishCurrentPosition();
        }
    }

    onUndo() {
        if (this.currentNode.parent != null) {
            this.currentNode = this.currentNode.parent;
            this.publishCurrentPosition();
        }
    }

    onPass() {
        if (!('pass' in this.currentNode.continuations)) {
            this.currentNode.branches.push('pass');

            const nextGame = this.copyGame(this.currentNode.data.game);
            nextGame.pass();

            const state = this.currentNode.data.state;
            const nextState = {
                ruleset: state.ruleset,
                komi: state.komi,
                initial_black: state.initial_black ? [...state.initial_black] : undefined,
                initial_white: state.initial_white ? [...state.initial_white] : undefined,
                initial_player: state.initial_player ? state.initial_player : undefined,
                moves: state.moves ? [...state.moves] : []
            };
            nextState.moves.push('pass');

            this.currentNode.continuations['pass'] = {
                branches: [],
                continuations: {},
                createdBy: null,
                data: {
                    game: nextGame,
                    state: nextState
                },
                parent: this.currentNode,
                position: this.currentNode.position + 1,
            };
        }

        this.currentNode = this.currentNode.continuations['pass'];
        this.publishCurrentPosition();
    }

    onRedo() {
        if (this.currentNode.branches.length === 1) {
            this.currentNode = this.currentNode.continuations[this.currentNode.branches[0]];
            this.publishCurrentPosition();
        }
    }

    onNextBranch() {
        const target = this.findNextBranchingPoint();
        if (target) {
            this.currentNode = target;
            this.publishCurrentPosition();
        }
    }

    onLast() {
        let current = this.currentNode;
        while (current.branches.length > 0) {
            current = current.continuations[current.branches[0]];
        }
        if (current !== this.currentNode) {
            this.currentNode = current;
            this.publishCurrentPosition();
        }
    }

    ngOnDestroy() {
        if (this.subscription) {
            this.subscription.unsubscribe();
        }

        this.subject.complete();
    }
}
