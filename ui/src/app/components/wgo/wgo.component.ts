import { DOCUMENT } from '@angular/common';
import { AfterViewInit, Component, ElementRef, Inject, OnDestroy, ViewChild } from '@angular/core';
import { Subscription } from 'rxjs';
import { Position } from '../../domain/position';
import { MoveService } from '../../services/move.service';
import { PositionService } from '../../services/position.service';

@Component({
    selector: 'gr-wgo',
    templateUrl: './wgo.component.html',
    styleUrls: [ './wgo.component.scss' ],
})
export class WgoComponent implements AfterViewInit, OnDestroy {
    @ViewChild('board')
    boardReference: ElementRef;

    board: any;
    subscription: Subscription | null = null;
    WGo: any;

    constructor(
        @Inject(DOCUMENT) private document: Document,
        private elementReference: ElementRef,
        private moveService: MoveService,
        private positionService: PositionService,
    ) {
        this.WGo = document.defaultView.window['WGo'];
    }

    ngAfterViewInit() {
        const el = this.boardReference.nativeElement;
        this.board = new this.WGo.Board(
            el,
            {
                background: 'assets/images/board-final.svg',
                section: {
                    bottom: -0.5,
                    left: -0.5,
                    right: -0.5,
                    top: -0.5,
                }
            },
        );

        const performResize = () => {
            setTimeout(
                () => {
                    let selected = Math.min(
                        el.clientHeight,
                        el.clientWidth,
                    );
                    if (selected < 64) {
                        selected = Math.max(el.clientHeight, el.clientWidth);
                    }
                    this.board.setDimensions(selected, selected);
                },
                0
            );
        }
        performResize();

        var coordinates = {
            // draw on grid layer
            grid: {
                draw: function (args, board) {
                    var ch, t, xright, xleft, ytop, ybottom;

                    this.fillStyle = 'rgba(0,0,0,0.7)';
                    this.textBaseline = 'middle';
                    this.textAlign = 'center';
                    this.font =
                        board.stoneRadius +
                        'px ' +
                        (
                            board.font || ''
                        );

                    xright = board.getX(-0.75);
                    xleft = board.getX(board.size - 0.25);
                    ytop = board.getY(-0.75);
                    ybottom = board.getY(board.size - 0.25);

                    for (var i = 0; i < board.size; i++) {
                        ch = i + 'A'.charCodeAt(0);
                        if (ch >= 'I'.charCodeAt(0)) {
                            ch++;
                        }

                        t = board.getY(i);
                        this.fillText(board.size - i, xright, t);
                        this.fillText(board.size - i, xleft, t);

                        t = board.getX(i);
                        this.fillText(String.fromCharCode(ch), t, ytop);
                        this.fillText(String.fromCharCode(ch), t, ybottom);
                    }

                    this.fillStyle = 'black';
                },
            },
        };
        this.board.addCustomObject(coordinates);

        this.document.defaultView.window.addEventListener(
            'resize',
            (event) => performResize()
        );

        this.board.addEventListener(
            'click',
            (x, y) => this.moveService.publish({ x, y })
        );

        this.subscription = this.positionService.positions$.subscribe(
            position => this.handlePosition(position)
        );
    }

    private handlePosition(position: Position) {
        this.board.removeAllObjects();

        for (let i = 0; i < position.position.schema.length; ++i) {
            const code = position.position.schema[i];
            if (!code) {
                continue;
            }
            const x = Math.floor(i / 19);
            const y = i % 19;
            this.board.addObject({ x, y, c: code === 1 ? this.WGo.B : this.WGo.W });
        }

        if (position.lastMove) {
            this.board.addObject({ x: position.lastMove.x, y: position.lastMove.y, type: 'CR'});
        }

        if (position.continuations) {
            let count = 1;
            const total = position.continuations.length;
            for (const continuation of position.continuations) {
                const boardObject = { x: continuation.x, y: continuation.y };
                if (total > 1) {
                    boardObject['type'] = 'LB';
                    boardObject['text'] = '' + count;
                } else {
                    boardObject['type'] = 'SQ';
                }
                this.board.addObject(boardObject);
                ++count;
            }
        }
    }

    ngOnDestroy() {
        if (this.subscription) {
            this.subscription.unsubscribe();
        }
    }
}
