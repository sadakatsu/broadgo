import {Component, EventEmitter, Input, OnInit, Output} from '@angular/core';

@Component({
  selector: 'bg-toggle',
  templateUrl: './toggle.component.html',
  styleUrls: ['./toggle.component.scss']
})
export class ToggleComponent implements OnInit {
  @Input('false')
  falseLabel: string;

  @Input('true')
  trueLabel: string;

  label: string;
  value: boolean = true;


  @Output()
  toggle = new EventEmitter<boolean>();

  ngOnInit() {
    this.toggle.emit(true);
    this.label = this.trueLabel;
  }

  onClick() {
    this.value = !this.value;
    this.label = this.value ? this.trueLabel : this.falseLabel;
    this.toggle.emit(this.value);
  }
}
