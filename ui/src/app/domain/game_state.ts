export interface GameState {
    ruleset: string;
    komi: number;

    initial_black?: Array<string>;
    initial_white?: Array<string>;
    initial_player?: string;

    moves?: Array<string>;
}