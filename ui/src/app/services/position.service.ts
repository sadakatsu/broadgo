import { Injectable } from '@angular/core';
import { Observable, ReplaySubject, Subject } from 'rxjs';
import { Position } from '../domain/position';

@Injectable({
    providedIn: 'root'
})
export class PositionService {
    private positions: Subject<Position>;

    constructor() {
        this.positions = new ReplaySubject();
    }

    get positions$(): Observable<Position> {
        return this.positions.asObservable();
    }

    publish(position: Position) {
        this.positions.next(position);
    }
}
