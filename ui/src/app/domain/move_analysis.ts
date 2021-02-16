import { RootAnalysis } from './root_analysis';

export interface MoveAnalysis extends RootAnalysis {
    lcb: number;
    move: string;
    order: number;
    prior: number;
    pv: Array<string>;
    scoreMean: number;
    scoreStdev: number;
    utilityLcb: number;

    pvVisits?: Array<number>;
    ownership?: Array<number>;
}
