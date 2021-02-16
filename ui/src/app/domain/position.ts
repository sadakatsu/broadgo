import { Coordinate } from './coordinate';

export interface Position {
    position: {
        capCount: {
            black: number;
            white: number;
        };
        schema: Array<number>;
        size: number;
    };
    lastMove: Coordinate | null;
    continuations?: Array<Coordinate>;
}
