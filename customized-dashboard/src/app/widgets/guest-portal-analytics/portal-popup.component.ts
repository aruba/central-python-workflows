import { Component, OnInit, Inject, ViewChild, ViewEncapsulation } from '@angular/core';
import { ICellRendererAngularComp } from 'ag-grid-angular';
import { MatDialog, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material';
import { AppService } from '../../app.service';

@Component({
  selector: 'portal-popup',
  templateUrl: './portal-popup.component.html'
})
export class PortalPopupComponent implements  ICellRendererAngularComp {
  public params: any;

  constructor(public dialog: MatDialog) { }

  agInit(params: any): void {
      this.params = params;
  }

  refresh(): boolean {
    return false;
  }

  openDetailsPopup() {
    let dialogRef = this.dialog.open(PortalMessagePopup, {
        width: '600px',
        disableClose : true,
        data: this.params.data,
        autoFocus: false
    });
  }
}

@Component({
    selector: 'portal-message-popup',
    template: `
        <div class="popup-wrapper">
        <span (click)="closeDialog()" class="aruba-icon-close popup"></span>
        <span *ngIf="!response" class="loader"><img width="170" height="100" src="/assets/images/loader.gif" alt="Loading..."><div>Loading...</div></span>    
        <div class="popup-container" *ngIf="response && response.total">
            <h5>{{response.data.header}}</h5>
            <ul *ngFor="let item of response.data.body">
                <li>{{item}}</li>
            </ul>
        </div>
        <b *ngIf="response && !response.total">No Data Available./b>
        <div>`,
    encapsulation: ViewEncapsulation.None
})

export class PortalMessagePopup implements OnInit {

    constructor(public dialogRef: MatDialogRef<PortalMessagePopup>,
      @Inject(MAT_DIALOG_DATA) public data: any, private appService: AppService) {}
  
    response;

    ngOnInit() {
        this.appService.getEventDetails(this.data.id).subscribe(resp => {
            resp = {"data":{"body":["no rf dot11g-radio-profile sanjay"],"header":"Configuration Updated"},"total":1}
            this.response = resp;
        })
    }

    closeDialog() {
        this.dialogRef.close();
    }
}