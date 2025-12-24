import { HttpClientModule } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';

import { AppComponent } from './app.component';
import { SetupComponent } from './components/setup/setup.component';
import { WgoComponent } from './components/wgo/wgo.component';
import { SearchComponent } from './components/search/search.component';
import { DataGridComponent } from './components/data-grid/data-grid.component';
import { ToggleComponent } from './components/toggle/toggle.component';
import {SliderModule} from "primeng/slider";

@NgModule({
    declarations: [
        AppComponent,
        SetupComponent,
        WgoComponent,
        SearchComponent,
        DataGridComponent,
        ToggleComponent,
    ],
    imports: [
        BrowserAnimationsModule,
        BrowserModule,
        FormsModule,
        HttpClientModule,
        SliderModule,
    ],
    providers: [],
    bootstrap: [AppComponent]
})
export class AppModule { }
