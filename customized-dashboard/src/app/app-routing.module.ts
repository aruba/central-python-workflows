import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { HomeComponent } from './home/home.component';
import { WidgetComponent } from './widget-preview/widget.component';
import { TestChartComponent } from './test-chart/test-chart.component';
import { MultiColumnComponent } from './multi-column/multi-column.component';

const routes: Routes = [
  { path: '',  redirectTo: '/home', pathMatch: 'full' },
  { path: 'home', pathMatch: 'full', component: HomeComponent},
  { path: 'selectWidgets', pathMatch: 'full', component: WidgetComponent},
  { path: 'dashboard', pathMatch: 'full', component: WidgetComponent},
  { path: 'charts', pathMatch: 'full', component: TestChartComponent},
  { path: 'multiColumn', pathMatch: 'full', component: MultiColumnComponent}
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
