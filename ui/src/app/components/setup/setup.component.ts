import { DOCUMENT } from '@angular/common';
import { Component, EventEmitter, Inject, OnDestroy, Output } from '@angular/core';
import { Subscription } from 'rxjs';
import { Coordinate } from '../../domain/coordinate';
import { NodeData } from '../../domain/node_data';
import { MoveService } from '../../services/move.service';
import { PositionService } from '../../services/position.service';
import { coordinate_to_label } from '../../utils/intersection_helpers';

@Component({
    selector: 'bg-setup',
    templateUrl: './setup.component.html',
    styleUrls: ['./setup.component.scss']
})
export class SetupComponent implements OnDestroy {
    @Output()
    initialState = new EventEmitter<NodeData>();

    rulesets = [
        { label: 'AGA', value: 'aga' },
        { label: 'AGA Button', value: 'aga-button' },
        { label: 'BGA', value: 'bga' },
        { label: 'Chinese', value: 'chinese' },
        { label: 'Chinese (KGS)', value: 'chinese-kgs' },
        { label: 'Chinese (OGS)', value: 'chinese-ogs' },
        { label: 'Japanese', value: 'japanese' },
        { label: 'Korean', value: 'korean' },
        { label: 'New Zealand', value: 'new-zealand' },
        { label: 'Stone Scoring', value: 'stone-scoring' },
        { label: 'Tromp Taylor', value: 'tromp-taylor' },
    ];

    color = 'b';
    komi = 6.5;
    ruleset = 'japanese';

    private position: Array<number> = new Array(361).fill(0);
    private readonly subscription: Subscription | null = null;
    private WGo: any;

    constructor(
        @Inject(DOCUMENT) private document: Document,
        private positionService: PositionService,
        private moveService: MoveService,
    ) {
        this.WGo = document.defaultView.window['WGo'];
        this.subscription = moveService.moves$.subscribe(
            coordinate => {
                if (coordinate) {
                    this.updateStartingPosition(coordinate);
                }
            }
        );
    }

    private updateStartingPosition(coordinate: Coordinate) {
        // console.log(coordinate);
        const index = coordinate.x * 19 + coordinate.y;
        if (this.position[index] == 2) {
            this.position[index] = 0;
        } else {
            ++this.position[index];
        }

        this.positionService.publish({
            position: {
                capCount: { black: 0, white: 0 },
                schema: [...this.position],
                size: 19,
            },
            lastMove: null
        });
    }

    startGame() {
        const initial_black = [];
        const initial_white = [];

        const game = new this.WGo.Game(
            19,
            this.ruleset === 'japanese' || this.ruleset === 'korean' || this.ruleset == 'chinese' ?
                'KO' :
                'ALL'
        );

        game.turn = this.color === 'b' ? this.WGo.B : this.WGo.W;

        for (let x = 0, i = 0; x < 19; ++x) {
            for (let y = 0; y < 19; ++i, ++y) {
                const code = this.position[i];
                if (code) {
                    const coordinate = coordinate_to_label({ x, y });
                    if (code === 1) {
                        initial_black.push(coordinate);
                        game.addStone(x, y, this.WGo.B);
                    } else {
                        initial_white.push(coordinate);
                        game.addStone(x, y, this.WGo.W);
                    }
                }
            }
        }

        this.initialState.emit({
            game: game,
            state: {
                ruleset: this.ruleset,
                komi: this.komi,
                initial_black,
                initial_white,
                initial_player: this.color,
                moves: [],
            }
        });

        this.moveService.publish(null);
    }

    ngOnDestroy() {
        if (this.subscription) {
            this.subscription.unsubscribe();
        }
    }
}
