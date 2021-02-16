import { DOCUMENT } from '@angular/common';
import { Component, Inject } from '@angular/core';
import { NodeData } from './domain/node_data';

@Component({
  selector: 'bg-root',
  templateUrl: 'app.component.html',
  styleUrls: [ 'app.component.scss' ],
})
export class AppComponent {
  root: any = null;

  private WGo: any = null;

  constructor(
      @Inject(DOCUMENT) document: Document,
  ) {
    this.WGo = document.defaultView.window['WGo'];
  }

  onInitialState(event: NodeData) {
    this.root = event;
  }
}
