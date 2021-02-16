import { Coordinate } from '../domain/coordinate';

const files = 'ABCDEFGHJKLMNOPQRST';

export function coordinate_to_label(coordinate: Coordinate): string {
    return files[coordinate.x] + (19 - coordinate.y);
}

export function label_to_coordinate(label: string): Coordinate | null {
    let result = null;
    if (label !== 'pass') {
        result = { x: files.indexOf(label[0]), y: 19 - parseInt(label.substr(1)) };
    }
    return result;
}
