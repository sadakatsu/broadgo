import { PositionAnalysis } from './position_analysis';
import { RootAnalysis } from './root_analysis';

export interface CompositeAnalysis {
    complete: boolean;
    moves: number;
    movesComplete: number;
    analyses: {
        [propName: string]: RootAnalysis;
    };
    direct: PositionAnalysis;
}