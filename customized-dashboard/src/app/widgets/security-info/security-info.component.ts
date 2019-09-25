import { Component, ViewEncapsulation, Input, OnInit, ViewChild, OnChanges } from '@angular/core';
import { AppService } from '../../app.service';
import { CentralGridUtilitiesService } from 'central-ui-component';

@Component({
    selector: 'security-info',
    encapsulation: ViewEncapsulation.None,
    templateUrl: './security-info.component.html'
})
export class SecurityInfoComponent implements OnInit, OnChanges {
    
    @Input() config;
    @Input() langLabels;
    @Input() refresh;
    selectedFilter = 'ROGUEAPS';
    gridConfigRogueAps;
    gridConfigIAps;
    id_1 = '_' + Date.now();
    id_2 = '_' + Date.now();
    gridRogueApsParamObj;
    gridRogueApsConfigObj;
    gridIApsConfigObj;
    gridIApsParamObj;
    gridRogueApsOffset;
    gridIApsOffset;

    constructor(private appService: AppService, private tableService: CentralGridUtilitiesService) {}

    ngOnInit() {
        this.setConfig();
    }

    ngOnChanges(changes) {
        if (changes.refresh && !changes.refresh.firstChange) {
            if (this.selectedFilter === 'ROGUEAPS')
                this.gridRogueApsConfigObj.loadGridData(this.gridRogueApsParamObj, this.gridRogueApsConfigObj);
            else
                this.gridIApsConfigObj.loadGridData(this.gridIApsParamObj, this.gridIApsConfigObj);
        }
    }

    setgridConfigRogueAps() {
        this.gridConfigRogueAps = {
            'showHeaderView': false,
            "id": this.id_1,
            "total_count": 0,
            //"title": this.config.title,
            'gridOptions': {
                'rowModelType': 'infinite',
                "rowSelection": "single",
                "rowDeselection": true,
                'columnDefs' : [{
                    headerName: 'id',
                    field: 'id',
                    sortable: false,
                    tooltipField: 'id'
                }, {
                    headerName: 'lan_mac',
                    field: 'lan_mac',
                    sortable: false,
                    tooltipField: 'lan_mac'
                }, {
                    headerName: 'mac_vendor',
                    field: 'mac_vendor',
                    sortable: false,
                    width: 260,
                    tooltipField: 'mac_vendor'
                }, {
                    headerName: 'ssid',
                    field: 'ssid',
                    sortable: false,
                    tooltipField: 'ssid'
                }, {
                    headerName: 'name',
                    field: 'name',
                    sortable: false,
                    tooltipField: 'name'
                }, {
                    headerName: 'containment_status',
                    field: 'containment_status',
                    width: 450,
                    sortable: false,
                    tooltipField: 'containment_status'
                }, {
                    headerName: 'device_name',
                    field: 'last_det_device_name',
                    width: 300,
                    sortable: false,
                    tooltipField: 'device_name'
                }]
            },
            'gridStyle': this.config.gridStyle || { height: '210px', width: '100%'},
            'loadGridData': (params, config) => {
                this.gridRogueApsParamObj = params;
                this.gridRogueApsConfigObj = config;
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

    setgridConfigIAps() {
        this.gridConfigIAps = {
            'showHeaderView': false,
            "id": this.id_2,
            "total_count": 0,
            //"title": this.config.title,
            'gridOptions': {
                'rowModelType': 'infinite',
                "rowSelection": "single",
                "rowDeselection": true,
                suppressHorizontalScroll: false,
                'columnDefs' : [{
                    headerName: 'id',
                    field: 'id',
                    sortable: false,
                    tooltipField: 'id'
                }, {
                    headerName: 'lan_mac',
                    field: 'lan_mac',
                    sortable: false,
                    tooltipField: 'lan_mac'
                }, {
                    headerName: 'mac_vendor',
                    field: 'mac_vendor',
                    sortable: false,
                    width: 260,
                    tooltipField: 'mac_vendor'
                }, {
                    headerName: 'ssid',
                    field: 'ssid',
                    sortable: false,
                    tooltipField: 'ssid'
                }, {
                    headerName: 'name',
                    field: 'name',
                    sortable: false,
                    tooltipField: 'name'
                }, {
                    headerName: 'containment_status',
                    field: 'containment_status',
                    width: 450,
                    sortable: false,
                    tooltipField: 'containment_status'
                }, {
                    headerName: 'device_name',
                    field: 'last_det_device_name',
                    width: 300,
                    sortable: false,
                    tooltipField: 'device_name'
                }]
            },
            'gridStyle': this.config.gridStyle || { height: '210px', width: '100%'},
            'loadGridData': (params, config) => {
                this.gridIApsParamObj = params;
                this.gridIApsConfigObj = config;
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
        this.setgridConfigRogueAps();
        this.setgridConfigIAps();
    }

    getPortalData(params, config) {
        if (this.selectedFilter === 'ROGUEAPS') {
            this.gridRogueApsOffset = isNaN(this.gridRogueApsOffset) ? 0 : this.gridRogueApsOffset + 1;
            this.appService.getSecurityInfo(20, this.gridRogueApsOffset, this.selectedFilter).subscribe((resp:any) => {
                let key = 'rogue_aps';
                if (resp && resp[key] && resp[key].length) {
                    this.gridConfigRogueAps.total_count = resp.total;
                    this.tableService.setData(resp[key], params, config);
                } else {
                    this.gridConfigRogueAps.total_count = 0;
                    this.tableService.setData([], params, config);
                }
            }, error => {
                this.gridConfigRogueAps.total_count = 0;
                this.tableService.setData([], params, config);
            })
        } else {
            this.gridIApsOffset = isNaN(this.gridIApsOffset) ? 0 : this.gridIApsOffset + 1;
            this.appService.getSecurityInfo(20, this.gridIApsOffset, this.selectedFilter).subscribe((resp:any) => {
                let key = 'interfering_aps';
                if (resp && resp[key] && resp[key].length) {
                    this.gridConfigIAps.total_count = resp.total;
                    this.tableService.setData(resp[key], params, config);
                } else {
                    this.gridConfigIAps.total_count = 0;
                    this.tableService.setData([], params, config);
                }
            }, error => {
                this.gridConfigIAps.total_count = 0;
                this.tableService.setData([], params, config);
            })
        }
    }

    onFilterChange(val) {
        this.selectedFilter = val;
        if (val === 'ROGUEAPS' && this.gridRogueApsConfigObj) {
            this.gridConfigRogueAps = undefined;
            this.gridRogueApsOffset = undefined;
            this.getPortalData(this.gridRogueApsParamObj, this.gridRogueApsConfigObj);
            this.setgridConfigRogueAps();
        } else if (this.gridIApsConfigObj) {
            this.gridConfigIAps = undefined;
            this.gridIApsOffset = undefined;
            this.getPortalData(this.gridIApsParamObj, this.gridIApsConfigObj);
            this.setgridConfigIAps();
        }
    }
}