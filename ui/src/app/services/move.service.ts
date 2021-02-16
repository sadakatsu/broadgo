import { Injectable } from '@angular/core';
import { Observable, ReplaySubject, Subject } from 'rxjs';
import { Coordinate } from '../domain/coordinate';

@Injectable({
    providedIn: 'root'
})
export class MoveService {
    private moves: Subject<Coordinate>;

    constructor() {
        this.moves = new ReplaySubject();
    }

    get moves$(): Observable<Coordinate> {
        return this.moves.asObservable();
    }

    publish(move: Coordinate | null) {
        this.moves.next(move);
    }
}
