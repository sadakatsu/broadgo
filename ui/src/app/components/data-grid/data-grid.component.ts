import {ChangeDetectorRef, Component, Input} from '@angular/core';
import {Observable, Subject} from 'rxjs';
import { map } from 'rxjs/operators';
import { CompositeAnalysis } from '../../domain/composite_analysis';
import { Coordinate } from '../../domain/coordinate';
import { RootAnalysis } from '../../domain/root_analysis';
import { Position } from '../../domain/position';
import { PositionService } from '../../services/position.service';
import { label_to_coordinate } from '../../utils/intersection_helpers';

interface SimplePosition {
    black: Array<Coordinate>;
    white: Array<Coordinate>;
}

interface Representation {
    x: number;
    y: number;
    color: string;
    loss: number;
    opposite: string;
    score: number;
}

@Component({
  selector: 'bg-data-grid',
  templateUrl: './data-grid.component.html',
  styleUrls: [ './data-grid.component.scss' ],
})
export class DataGridComponent {
    @Input('data')
    data: CompositeAnalysis;

    position$: Observable<SimplePosition>;
    toggle: boolean = true;
    percentage: number = 100;

    private readonly colorCodes = [
        '#00FF00', // 0
        '#33FF00', // 1
        '#66FF00', // 2
        '#99FF00', // 3
        '#CCFF00', // 4
        '#FFFF00', // 5
        '#FFCC00', // 6
        '#FF9900', // 7
        '#FF6600', // 8
        '#FF3300', // 9
        '#FF0000', // 10
        '#FF0033', // 11
        '#FF0066', // 12
        '#FF0099', // 13
        '#FF00CC', // 14
        '#FF00FF', // 15
        '#CC00FF', // 16
        '#9900FF', // 17
        '#6600FF', // 18
        '#3300FF', // 19
        '#0000FF', // 20
    ];

    constructor(positionService: PositionService, private changeDetectorRef: ChangeDetectorRef) {
        this.position$ = positionService.positions$
            .pipe(
                map(position => this.transformPosition(position))
            );
    }

    private transformPosition(position: Position) {
        const black: Array<Coordinate> = [];
        const white: Array<Coordinate> = [];

        for (let i = 0, x = 0; x < 19; ++x) {
            for (let y = 0; y < 19; ++y, ++i) {
                const code = position.position.schema[i];
                if (code == 1) {
                    black.push({ x, y });
                } else if (code == -1) {
                    white.push({ x, y });
                }
            }
        }

        return { black, white };
    }

    transformData(useLoss: boolean, percentage: number) {
        const transformation: Array<Representation> = [];

        let worst = Infinity;
        let best = -Infinity;

        let worstSimplicity = -Infinity;
        let bestSimplicity = Infinity;

        for (const value of Object.values(this.data.analyses)) {
            const score = (value as RootAnalysis).scoreLead;
            if (score < worst) {
                worst = score;
            }
            if (score > best) {
                best = score;
            }

            const simplicity = (value as RootAnalysis).simplicity;
            if (simplicity > worstSimplicity) {
                worstSimplicity = simplicity;
            }
            if (simplicity < bestSimplicity) {
                bestSimplicity = simplicity;
            }
        }

        let threshold = Infinity;
        if (percentage < 100) {
            let losses: Array<number> = [];
            for (const value of Object.values(this.data.analyses)) {
                const cast = value as RootAnalysis;
                losses.push(best - cast.scoreLead);
            }
            losses.sort((a, b) => a - b);
            const rawIndex = (losses.length - 1) * (percentage / 100.);
            const floorIndex = Math.floor(rawIndex);

            if (Math.abs(rawIndex - floorIndex) < 1e-6) {
                threshold = losses[floorIndex];
            } else {
                const ceilingIndex = Math.ceil(rawIndex);
                const proportion = rawIndex - floorIndex;
                threshold = losses[floorIndex] * proportion + losses[ceilingIndex] * (1. - proportion);
            }
        }

        for (const [key, value] of Object.entries(this.data.analyses)) {
            const coordinate = label_to_coordinate(key);
            const cast = value as RootAnalysis;
            const pointLoss = best - cast.scoreLead;
            if (pointLoss > threshold) {
                continue;
            }

            const simplicityLoss = cast.simplicity - bestSimplicity;

            let score: number;
            let loss: number;
            if (useLoss) {
                score = cast.scoreLead;
                loss = pointLoss;
            } else {
                score = cast.simplicity;
                loss = simplicityLoss;
            }

            let color: string;
            const simplified = Math.floor(loss);
            if (simplified <= 20) {
                color = this.colorCodes[simplified];
            } else {
                const contribution = 255 - Math.round(255 * (loss - 20) / 707);
                color = `rgb(0, 0, ${contribution})`;
            }

            transformation.push({
                x: coordinate ? coordinate.x * 100 + 150 : -Infinity,
                y: coordinate ? coordinate.y * 100 + 150 : -Infinity,
                color,
                loss: Math.round(loss),
                opposite: `white - ${color}`,
                score: Math.round(score * 10) / 10
            })
        }

        return transformation;
    }

    getPass(transformed) {
        const found = transformed.filter(e => !Number.isFinite(e.x));
        return found ? found[0] : null;
    }

    onDisplayToggle(value: boolean) {
        this.toggle = value;
        this.changeDetectorRef.markForCheck();
    }
}
