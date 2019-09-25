import {Component, Inject} from '@angular/core';
import {MAT_SNACK_BAR_DATA} from '@angular/material/snack-bar';

@Component({
  selector: 'snack-bar',
  templateUrl: './snack-bar.component.html',
})
export class SnackBarComponent {
  constructor(@Inject(MAT_SNACK_BAR_DATA) public data: any) {

  }

  saveChanges(flag?) {
    if (!this.data.isWidgetRendered)
        this.data.renderWidgets(this.data.__this);
    if (this.data.isWidgetRendered)
        this.data.saveWidgets(this.data.__this, flag);
  }
}