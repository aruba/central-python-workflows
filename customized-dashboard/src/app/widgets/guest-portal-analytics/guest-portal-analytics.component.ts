import { Component, ViewEncapsulation, Input, OnInit, ViewChild, OnChanges } from '@angular/core';
import { AppService } from '../../app.service';
import { PortalPopupComponent } from './portal-popup.component';
import { CentralGridUtilitiesService } from 'central-ui-component';

@Component({
    selector: 'guest-portal-analytics',
    encapsulation: ViewEncapsulation.None,
    templateUrl: './guest-portal-analytics.component.html'
})
export class GuestPortalAnalyticsComponent implements OnInit, OnChanges {
    
    @Input() config;
    @Input() langLabels;
    @Input() refresh;
    selectedFilter = 'SSIDS';
    gridConfigSSID;
    gridConfigVisitor;
    id_1 = '_' + Date.now();
    id_2 = '_' + Date.now();
    gridSSIDParamObj;
    gridSSIDConfigObj;
    gridVisitorConfigObj;
    gridVisitorParamObj;
    gridSSIDOffset;
    gridVisitorOffset;

    constructor(private appService: AppService, private tableService: CentralGridUtilitiesService) {}

    ngOnInit() {
        this.setConfig();
    }

    ngOnChanges(changes) {
        if (changes.refresh && !changes.refresh.firstChange) {
            if (this.selectedFilter === 'SSIDS')
                this.gridSSIDConfigObj.loadGridData(this.gridSSIDParamObj, this.gridSSIDConfigObj);
            else
                this.gridVisitorConfigObj.loadGridData(this.gridVisitorParamObj, this.gridVisitorConfigObj);
        }
    }

    setGridConfigSSID() {
        this.gridConfigSSID = {
            'showHeaderView': false,
            "id": this.id_1,
            "total_count": 0,
            //"title": this.config.title,
            'gridOptions': {
                'rowModelType': 'infinite',
                "rowSelection": "single",
                "rowDeselection": true,
                'columnDefs' : [{
                    headerName: 'wlan',
                    field: 'wlan',
                    sortable: false,
                    tooltipField: 'wlan'
                }, {
                    headerName: 'portal_id',
                    field: 'portal_id',
                    sortable: false,
                    tooltipField: 'portal_id'
                }]
            },
            'gridStyle': this.config.gridStyle || { height: '210px', width: '100%'},
            'loadGridData': (params, config) => {
                this.gridSSIDParamObj = params;
                this.gridSSIDConfigObj = config;
                this.getPortalData(params, config);  
            },
            options: {
                'pagination': {
                    'limit': 20,
                    'offset': 0
                }
            }
        };
    }

    setGridConfigVisitor() {
        this.gridConfigVisitor = {
            'showHeaderView': false,
            "id": this.id_2,
            "total_count": 0,
            //"title": this.config.title,
            'gridOptions': {
                'rowModelType': 'infinite',
                "rowSelection": "single",
                "rowDeselection": true,
                'frameworkComponents': {
                    portalPopup: PortalPopupComponent
                },
                'columnDefs' : [{
                    headerName: 'name',
                    field: 'name',
                    sortable: false,
                    //cellRenderer: 'portalPopup'
                }, {
                    headerName: 'auth_type',
                    field: 'auth_type',
                    sortable: false,
                    tooltipField: 'auth_type'
                }, {
                    headerName: 'id',
                    field: 'id',
                    sortable: false,
                    tooltipField: 'id'
                }, {
                    headerName: 'capture_url_val',
                    field: 'capture_url',
                    sortable: false,
                    tooltipField: 'capture_url'
                }]
            },
            'gridStyle': this.config.gridStyle || { height: '210px', width: '100%'},
            'loadGridData': (params, config) => {
                this.gridVisitorParamObj = params;
                this.gridVisitorConfigObj = config;
                this.getPortalData(params, config);  
            },
            options: {
                'pagination': {
                    'limit': 20,
                    'offset': 0
                }
            }
        }
    }

    setConfig() {
        this.setGridConfigSSID();
        this.setGridConfigVisitor();
    }

    getPortalData(params, config) {
        if (this.selectedFilter === 'SSIDS') {
            this.gridSSIDOffset = isNaN(this.gridSSIDOffset) ? 0 : this.gridSSIDOffset + 1;
            this.appService.getGuestPortalData(20, this.gridSSIDOffset, this.selectedFilter).subscribe((resp:any) => {
                let key = this.selectedFilter === 'SSIDS' ? 'wlans' : 'portals';
                if (resp && resp[key] && resp[key].length) {
                    this.gridConfigSSID.total_count = resp.total;
                    this.tableService.setData(resp[key], params, config);
                } else {
                    this.gridConfigSSID.total_count = 0;
                    this.tableService.setData([], params, config);
                }
            }, error => {
                this.gridConfigSSID.total_count = 0;
                this.tableService.setData([], params, config);
            })
        } else {
            this.gridVisitorOffset = isNaN(this.gridVisitorOffset) ? 0 : this.gridVisitorOffset + 1;
            this.appService.getGuestPortalData(20, this.gridVisitorOffset, this.selectedFilter).subscribe((resp:any) => {
                let key = this.selectedFilter === 'SSIDS' ? 'wlans' : 'portals';
                if (resp && resp[key] && resp[key].length) {
                    this.gridConfigVisitor.total_count = resp.total;
                    this.tableService.setData(resp[key], params, config);
                } else {
                    this.gridConfigVisitor.total_count = 0;
                    this.tableService.setData([], params, config);
                }
            }, error => {
                this.gridConfigVisitor.total_count = 0;
                this.tableService.setData([], params, config);
            })
        }
    }

    onFilterChange(val) {
        this.selectedFilter = val;
        if (val === 'SSIDS' && this.gridSSIDConfigObj) {
            this.gridConfigSSID = undefined;
            this.gridSSIDOffset = undefined;
            this.getPortalData(this.gridSSIDParamObj, this.gridSSIDConfigObj);
            this.setGridConfigSSID();
        } else if (this.gridVisitorConfigObj) {
            this.gridConfigVisitor = undefined;
            this.gridVisitorOffset = undefined;
            this.getPortalData(this.gridVisitorParamObj, this.gridVisitorConfigObj);
            this.setGridConfigVisitor();
        }
    }
}