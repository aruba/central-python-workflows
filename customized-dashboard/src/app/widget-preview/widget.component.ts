import { Component, AfterViewInit, OnDestroy, ViewChild } from '@angular/core';
import { AppService } from '../app.service';
import { CdkDragDrop, transferArrayItem } from '@angular/cdk/drag-drop';
import { MatSnackBar } from '@angular/material/snack-bar';
import { SnackBarComponent } from './snack-bar.component';
import { ViewportRuler } from "@angular/cdk/overlay";
import { HttpManager } from 'central-ui-core';

import {
    CdkDrag,
    CdkDragStart,
    CdkDropList, CdkDropListGroup, CdkDragMove, CdkDragEnter,
    moveItemInArray
  } from "@angular/cdk/drag-drop";
declare var require;

@Component({
    selector: 'select-widget',
    templateUrl: './widget.component.html',
    styleUrls: ['./widget.component.scss'],
})
export class WidgetComponent implements AfterViewInit, OnDestroy {

    @ViewChild(CdkDropListGroup, {static: false}) listGroup: CdkDropListGroup<CdkDropList>;
    @ViewChild(CdkDropList, {static: false}) placeholder: CdkDropList;

    refreshCounter = '_' + Date.now();
    public opened = true;
    public isWidgetRendered = false;
    private snackBarRef;
    public areWidgetsSaved;
    public langLabels;
    private isSnackBarOpen;
    widgetWidth;
    public target: CdkDropList;
    public targetIndex: number;
    public source: CdkDropList;
    public sourceIndex: number;
    public dragIndex: number;
    public activeContainer;
    public closeConfirmClearSection = false;
    public isSwitchEnabled;
    dashboardList;
    widgetList;
    private lang = require('../../assets/language_ui/monitoring_en_US.json');
    public widgets = [];
    public dashboardJson;
    logIn = '';
    constructor(private appService: AppService, private httpManager: HttpManager, private _snackBar: MatSnackBar, private viewportRuler: ViewportRuler) {
        this.widgets = this.appService.getWidget();
        let storedJson = this.appService.getStoredJson();
        if (storedJson && storedJson.hasOwnProperty('name')) {
            this.dashboardJson = storedJson;
            this.isWidgetRendered = true;
            this.opened = false;
            this.areWidgetsSaved = true;
        } else
            this.dashboardJson = this.appService.getJson('My Dashboard');
        for (var labelObj in this.lang.custom_db) {
            this.lang.custom_db[labelObj] = this.lang.custom_db[labelObj]['label'];
        }
        this.langLabels = this.lang.custom_db;
        this.target = null;
        this.source = null;
        this.getLoginCreds();
    }

    syncManually() {
        this.httpManager.get('refresh_token').subscribe(resp => {
            this.refreshCounter = '_' + Date.now();
        })
    }

    drop(event: CdkDragDrop<string[]>) {
        if (event.previousContainer === event.container) {
            moveItemInArray(event.container.data, event.previousIndex, event.currentIndex);
        } else {
            if (!this.dashboardJson.widgets[0]['name'])  this.dashboardJson.widgets.splice(0, 1);
            transferArrayItem(event.previousContainer.data, event.container.data, event.previousIndex, event.currentIndex);
            if (!this.dashboardJson.widgets.length)   this.dashboardJson.widgets.push({});
            else if (!this.isSnackBarOpen) {
                this.snackBarRef = this._snackBar.openFromComponent(SnackBarComponent, {data: {isWidgetRendered: this.isWidgetRendered, renderWidgets: this.renderWidgets, saveWidgets: this.saveWidgets, __this: this}});
                this.isSnackBarOpen = true
            }
        }
    }

    switchToTwoColumn(flag) {
        if ((flag && this.dashboardJson.columSize == 2) || (!flag && this.dashboardJson.columSize == 1))
            return;
        if (flag) {
            this.dashboardJson.columSize = 2;
            //this.dashboardJson.widgets.shift();
            this.dashboardJson.widgets = [{}];
        } else {
            this.dashboardJson.columSize = 1;
            this.dashboardJson.widgets = [{}];
            this.isSwitchEnabled = true;
        }
        this.widgets = this.appService.getWidget();
    }

     renderWidgets(__this) {
        __this.opened = false;
        __this.isWidgetRendered = true;
        __this.snackBarRef = __this._snackBar.openFromComponent(SnackBarComponent, {data: {isWidgetRendered: __this.isWidgetRendered, renderWidgets: __this.renderWidgets, saveWidgets: __this.saveWidgets, __this: this}});
        __this.isSnackBarOpen = true;
        setTimeout(() => {__this.setColumnConfig();}, 1000)
    }

    setColumnConfig() {
        let widthRef = this.dashboardJson.columSize === 1 ? document.getElementsByClassName('widget-list-container')[0] : document.getElementsByClassName('example-box')[0];
        this.widgetWidth = widthRef['offsetWidth'];
        this.dashboardJson.widgets.forEach((widget) => {
            if (widget.key == 'device_count') {
                widget.config = {
                    name: widget.name,
                    key: widget.key,
                    isDonut: true,
                    width: this.widgetWidth
                }
            }
            if (widget.key == 'total_client_count') {
                widget.config = {
                    name: widget.name,
                    key: widget.key,
                    //isDonut: true,
                    width: this.widgetWidth
                }
            }
            if (widget.key == 'connection_count') {
                widget.config = {
                    name: widget.name,
                    isDonut: true,
                    key: 'connection_count',
                    width: this.widgetWidth
                }
            }
            if (widget.key === 'bandwidth_usage') {
                widget.config = {
                    name: widget.name,
                    width: this.widgetWidth
                }
            }
            if (widget.key === 'client_count_filter_summary') {
                // var response = [{"key": 'client 1', values: [], color: '#9FDCF6'}];
                // let resp = {"count":36,"interval":"5minutes","samples":[{"client_count":5,"timestamp":1566801300},{"client_count":12,"timestamp":1566801600},{"client_count":10,"timestamp":1566801900},{"client_count":15,"timestamp":1566802200},{"client_count":5,"timestamp":1566802500},{"client_count":15,"timestamp":1566802800},{"client_count":2,"timestamp":1566803100},{"client_count":15,"timestamp":1566803400},{"client_count":1,"timestamp":1566803700},{"client_count":15,"timestamp":1566804000},{"client_count":15,"timestamp":1566804300},{"client_count":15,"timestamp":1566804600},{"client_count":15,"timestamp":1566804900},{"client_count":15,"timestamp":1566805200},{"client_count":15,"timestamp":1566805500},{"client_count":15,"timestamp":1566805800},{"client_count":15,"timestamp":1566806100},{"client_count":15,"timestamp":1566806400},{"client_count":15,"timestamp":1566806700},{"client_count":7,"timestamp":1566807000},{"client_count":40,"timestamp":1566807300},{"client_count":15,"timestamp":1566807600},{"client_count":15,"timestamp":1566807900},{"client_count":3,"timestamp":1566808200},{"client_count":15,"timestamp":1566808500},{"client_count":15,"timestamp":1566808800},{"client_count":15,"timestamp":1566809100},{"client_count":15,"timestamp":1566809400},{"client_count":15,"timestamp":1566809700},{"client_count":15,"timestamp":1566810000},{"client_count":15,"timestamp":1566810300},{"client_count":15,"timestamp":1566810600},{"client_count":15,"timestamp":1566810900},{"client_count":15,"timestamp":1566811200},{"client_count":15,"timestamp":1566811500},{"client_count":15,"timestamp":1566811800}]};
                // resp.samples.forEach(sample => {
                //     response[0].values.push({'x': new Date(sample.timestamp*1000), 'y': sample.client_count})
                // });
                widget.config = {
                    name: widget.name,
                    width: this.widgetWidth,
                    yAxisLabel: 'Count'
                }
            }
            if (widget.key === 'security_info') {
                widget.config = {
                    name: widget.name,
                    //title: 'events',
                    key: 'security_info',
                    gridStyle: { height: '240px', width: (this.widgetWidth-30)+'px'}
                }
            }
            if (widget.key === 'guest-portal-analytics') {
                widget.config = {
                    name: widget.name,
                    //title: 'events',
                    key: 'guest_portal_visitors',
                    gridStyle: { height: '240px', width: (this.widgetWidth-30)+'px'}
                }
            }
            if (widget.key === 'onboarding-analytics') {
                widget.config = {
                    name: widget.name,
                    //title: 'events',
                    key: 'guest_portal_visitors',
                    gridStyle: { height: '240px', width: (this.widgetWidth-30)+'px'}
                }
            }
            if (widget.key === 'events') {
                widget.config = {
                    name: widget.name,
                    title: 'events',
                    key: 'events',
                    gridStyle: { height: '240px', width: (this.widgetWidth-30)+'px'}
                }
            }
            if (widget.key === 'presence-analytics') {
                widget.config = {
                    name: widget.name,
                    width: this.widgetWidth,
                    key: 'presence-analytics'
                }
            }
            if (widget.key === 'firmware_version') {
                widget.config = {
                    name: widget.name,
                    key: 'firmware_version',
                    gridStyle: { height: '240px', width: (this.widgetWidth-30)+'px'}
                }
            }
        });
    }


    clearStorage(flag) {
        if (flag) {
            this.isWidgetRendered = false;
            this.opened = true;
            this.appService.clearCachedJson();
            this.dashboardJson = this.appService.getJson('My Dashboard');
            this.widgets = this.appService.getWidget();
            this.areWidgetsSaved = false;
        } else {
            this.closeConfirmClearSection = true;
        }
    }

    editDB() {
        this.isWidgetRendered = false;
        this.opened = true;
        this.dashboardJson = this.appService.getStoredJson();
        this.widgets = this.widgets.filter(widget => {
            let hasWidget = this.dashboardJson.widgets.filter(storedWidget => {
                return storedWidget.name === widget.name;
            })
            return !hasWidget || !hasWidget.length;
        })
        this.appService.clearCachedJson();
        this.areWidgetsSaved = false;
        this.snackBarRef = this._snackBar.openFromComponent(SnackBarComponent, {data: {isWidgetRendered: this.isWidgetRendered, renderWidgets: this.renderWidgets, saveWidgets: this.saveWidgets, __this: this}});
        this.isSnackBarOpen = true
    }

    getLoginCreds() {
        let cookie = document.cookie.split(';');
        this.logIn = cookie[1] && cookie[1].indexOf('email') > -1 ? cookie[1].split('email=')[1] : '';
    }

    getTime(ts) {
        var hours:any;
        let dateVal = new Date(ts*1000);
        hours = dateVal.getHours();
        var timeZone = 'AM';
        if (hours > 12) {
            hours -= 12;
            timeZone = 'PM';
        } else if (hours === 0) {
            hours = 12;
        }
        let minutes = dateVal.getMinutes();
        return hours + ':' + (minutes<10?'0'+minutes:minutes) + timeZone;
    }

    saveWidgets(__this, flag) {
        var _this = __this.__this;
        if (!flag) {
            _this.isWidgetRendered = false;
            _this.opened = true;
            _this.snackBarRef = _this._snackBar.openFromComponent(SnackBarComponent, {data: {isWidgetRendered: _this.isWidgetRendered, renderWidgets: _this.renderWidgets, saveWidgets: _this.saveWidgets, __this: _this}});
            _this.isSnackBarOpen = true
        }
        else {
            window.localStorage.setItem('dashboardJson', JSON.stringify(_this.dashboardJson));
            _this.snackBarRef.dismiss();
            _this.isSnackBarOpen = false;
            _this.areWidgetsSaved = true;
            _this.closeConfirmClearSection = false;
        }
        console.log('save widgets called', flag);
    }

    addWidget(index) {
        if (this.dashboardJson.widgets[0] && !this.dashboardJson.widgets[0]['name'])  this.dashboardJson.widgets.splice(0, 1);
        let widget = this.widgets.splice(index, 1);
        this.dashboardJson.widgets = this.dashboardJson.widgets.concat(widget);
        if (!this.isSnackBarOpen) {
            this.snackBarRef = this._snackBar.openFromComponent(SnackBarComponent, {data: {isWidgetRendered: this.isWidgetRendered, renderWidgets: this.renderWidgets, saveWidgets: this.saveWidgets, __this: this}});
            this.isSnackBarOpen = true;
        }
    }

    removeWidget(index) {
        let widget = this.dashboardJson.widgets.splice(index, 1);
        if (!this.dashboardJson.widgets.length) {
            this.dashboardJson.widgets.push({});
            this.snackBarRef.dismiss();
            this.isSnackBarOpen = false
        }
        this.widgets = this.widgets.concat(widget);
    }

    ngAfterViewInit() {
        let phElement = this.placeholder.element.nativeElement;
        phElement.style.display = 'none';
        phElement.parentElement.removeChild(phElement);
    }

    ngOnDestroy() {
        if (this.isSnackBarOpen) {
            this.snackBarRef.dismiss();
            this.isSnackBarOpen = false;
        }
    }
    
      dragMoved(e: CdkDragMove) {
        let point = this.getPointerPositionOnPage(e.event);
    
        this.listGroup._items.forEach(dropList => {
          if (__isInsideDropListClientRect(dropList, point.x, point.y)) {
            this.activeContainer = dropList;
            return;
          }
        });
      }
    
      dropListDropped(e) {
        if (!this.target)
          return;
    
        let phElement = this.placeholder.element.nativeElement;
        let parent = phElement.parentElement;
    
        phElement.style.display = 'none';
    
        parent.removeChild(phElement);
        parent.appendChild(phElement);
        parent.insertBefore(this.source.element.nativeElement, parent.children[this.sourceIndex]);
    
        this.target = null;
        this.source = null;
    
        if (this.sourceIndex != this.targetIndex)
          moveItemInArray(this.dashboardJson.widgets, this.sourceIndex, this.targetIndex);
      }
    
      dropListEnterPredicate = (drag: CdkDrag, drop: CdkDropList) => {
        if (drop == this.placeholder)
          return true;
    
        if (drop != this.activeContainer)
          return false;
    
        let phElement = this.placeholder.element.nativeElement;
        let sourceElement = drag.dropContainer.element.nativeElement;
        let dropElement = drop.element.nativeElement;
    
        let dragIndex = __indexOf(dropElement.parentElement.children, (this.source ? phElement : sourceElement));
        let dropIndex = __indexOf(dropElement.parentElement.children, dropElement);
    
        if (!this.source) {
          this.sourceIndex = dragIndex;
          this.source = drag.dropContainer;
    
          phElement.style.width = sourceElement.clientWidth + 'px';
          phElement.style.height = sourceElement.clientHeight + 'px';
          
          sourceElement.parentElement.removeChild(sourceElement);
        }
    
        this.targetIndex = dropIndex;
        this.target = drop;
    
        phElement.style.display = '';
        dropElement.parentElement.insertBefore(phElement, (dropIndex > dragIndex 
          ? dropElement.nextSibling : dropElement));
    
        this.placeholder.enter(drag, drag.element.nativeElement.offsetLeft, drag.element.nativeElement.offsetTop);
        return false;
      }
      
      /** Determines the point of the page that was touched by the user. */
      getPointerPositionOnPage(event: MouseEvent | TouchEvent) {
        // `touches` will be empty for start/end events so we have to fall back to `changedTouches`.
        const point = __isTouchEvent(event) ? (event.touches[0] || event.changedTouches[0]) : event;
            const scrollPosition = this.viewportRuler.getViewportScrollPosition();
    
            return {
                x: point.pageX - scrollPosition.left,
                y: point.pageY - scrollPosition.top
            };
        }
}

function __indexOf(collection, node) {
    return Array.prototype.indexOf.call(collection, node);
  };
  
  /** Determines whether an event is a touch event. */
  function __isTouchEvent(event: MouseEvent | TouchEvent): event is TouchEvent {
    return event.type.startsWith('touch');
  }
  
  function __isInsideDropListClientRect(dropList: CdkDropList, x: number, y: number) {
    const {top, bottom, left, right} = dropList.element.nativeElement.getBoundingClientRect();
    return y >= top && y <= bottom && x >= left && x <= right; 
  }