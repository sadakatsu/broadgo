import { MoveAnalysis } from './move_analysis';
import { RootAnalysis } from './root_analysis';

export interface PositionAnalysis {
    id: string;

    turnNumber: number;
    rootInfo: RootAnalysis;
    moveInfos: Array<MoveAnalysis>;

    isDuringSearch?: boolean;
    ownership?: Array<number>;
    policy?: Array<number>;
}
