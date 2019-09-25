import { BrowserModule } from '@angular/platform-browser';
import { CommonModule } from '@angular/common';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { NgModule } from '@angular/core';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatButtonModule, MatSnackBarModule, MatDialogModule, MatSidenavModule, MatCheckboxModule, MatCardModule, MatDividerModule, MatInputModule, MatIconModule } from '@angular/material';
import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { HomeComponent } from './home/home.component';
import { WidgetComponent } from './widget-preview/widget.component';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { AppService } from './app.service';
import { DragDropModule } from '@angular/cdk/drag-drop';
import { PieChartComponent } from './widgets/pie-chart/pie-chart.component';
import { LineChartComponent } from './widgets/line-chart/line-chart.component';
import { ScatterChartComponent } from './widgets/scatter-chart/scatter-chart.component';
import { GridWrapperComponent } from './widgets/grid-wrapper/grid-wrapper.component';
import { BandwidthUsageComponent } from './widgets/bandwidth/bandwidth.component';
import { ClientCountComponent } from './widgets/client-count/client-count.component';
import { EventsComponent } from './widgets/events/events.component';
import { GuestPortalAnalyticsComponent } from './widgets/guest-portal-analytics/guest-portal-analytics.component';
import { OnboardingAnalyticsComponent } from './widgets/onboarding-analytics/onboarding-analytics.component';
import { PresenceAnalyticsComponent } from './widgets/presence-analytics/presence-analytics.component';
import { SecurityInfoComponent } from './widgets/security-info/security-info.component';
import { FirmwareComponent } from './widgets/firmware/firmware.component';
import { EventPopupComponent } from './widgets/events/event-popup.component';
import { EventsMessagePopup } from './widgets/events/event-popup.component';
import { PortalPopupComponent } from './widgets/guest-portal-analytics/portal-popup.component';
import { PortalMessagePopup } from './widgets/guest-portal-analytics/portal-popup.component';
import { SnackBarComponent } from './widget-preview/snack-bar.component';
import { CentralUiComponentAppModule } from 'central-ui-component';
import { AgGridModule } from 'ag-grid-angular';
import { HttpManager } from 'central-ui-core';
import { HttpModule } from '@angular/http';
import { MultiColumnComponent } from './multi-column/multi-column.component';
import { TestChartComponent } from './test-chart/test-chart.component';
import { MultiBarChartComponent } from './widgets/multi-bar-chart/multi-bar-chart.component';
import { StackedAreaChartComponent } from './widgets/stacked-area-chart/stacked-area-chart.component';
import { NvD3Module } from 'ng2-nvd3';
import 'd3';
import 'nvd3';

@NgModule({
  declarations: [
    AppComponent,
    HomeComponent,
    WidgetComponent,
    PieChartComponent,
    SnackBarComponent,
    LineChartComponent,
    ScatterChartComponent,
    GridWrapperComponent,
    MultiColumnComponent,
    TestChartComponent,
    MultiBarChartComponent,
    StackedAreaChartComponent,
    BandwidthUsageComponent,
    ClientCountComponent,
    EventsComponent,
    FirmwareComponent,
    EventPopupComponent,
    EventsMessagePopup,
    GuestPortalAnalyticsComponent,
    OnboardingAnalyticsComponent,
    PresenceAnalyticsComponent,
    SecurityInfoComponent,
    PortalMessagePopup,
    PortalPopupComponent
  ],
  imports: [
    HttpModule,
    BrowserModule,
    AppRoutingModule,
    MatButtonModule,
    MatSidenavModule,
    MatSnackBarModule,
    MatButtonToggleModule,
    BrowserAnimationsModule,
    FormsModule,
    ReactiveFormsModule,
    MatCheckboxModule,
    MatDividerModule,
    MatInputModule,
    MatIconModule,
    DragDropModule,
    MatCardModule,
    CommonModule,
    CentralUiComponentAppModule,
    AgGridModule,
    NvD3Module,
    MatDialogModule
  ],
  providers: [
    AppService,
    HttpManager
  ],
  bootstrap: [AppComponent],
  entryComponents: [
    SnackBarComponent,
    EventPopupComponent,
    EventsMessagePopup,
    PortalMessagePopup,
    PortalPopupComponent
  ]
})
export class AppModule { }
