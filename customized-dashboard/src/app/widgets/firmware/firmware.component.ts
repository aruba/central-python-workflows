import { Component, ViewEncapsulation, Input, OnInit, ViewChild, OnChanges } from '@angular/core';
import { AppService } from '../../app.service';
import { CentralGridUtilitiesService } from 'central-ui-component';

@Component({
    selector: 'firmware',
    encapsulation: ViewEncapsulation.None,
    templateUrl: './firmware.component.html'
})
export class FirmwareComponent implements OnInit, OnChanges {

    @Input() config;
    @Input() langLabels;
    @Input() refresh;
    gridConfig;
    id = '_' + Date.now();
    deviceTypes = [{name: 'IAP'}, {name: 'MAS'}, {name: 'HP'}, {name: 'CONTROLLER'}]
    deviceTypeValue = 'IAP';

    gridParamsObj;
    gridConfigObj;

    constructor(private appService: AppService, private tableService: CentralGridUtilitiesService) {}

    ngOnChanges(changes) {
        if (changes.refresh && !changes.refresh.firstChange) {
            this.gridConfig.loadGridData(this.gridParamsObj, this.gridConfigObj)
        }
    }

    ngOnInit() {
        this.setConfig();
    }

    onFilterChange(val) {
        this.getFirmwareDetails(this.gridParamsObj, this.gridConfigObj);  
    }

    setConfig() {
        this.gridConfig = {
            'showHeaderView': false,
            "id": this.id,
            "total_count": 0,
            'gridOptions': {
                'rowModelType': 'infinite',
                'columnDefs' : [{
                    headerName: 'fm_compliance_version',
                    field: 'firmware_compliance_version',
                    tooltipField: 'firmware_compliance_version',
                    sortable: false
                }, {
                    headerName: 'fm_scheduled_at',
                    field: 'compliance_scheduled_at',
                    sortable: false,
                    width: 230,
                    tooltip: (params) => {
                        return params.valueFormatted
                    },
                    valueFormatter: (params) => {
                        return this.appService.getTimeStr(params.value);
                    }
                }]
            },
            'gridStyle': this.config.gridStyle || { height: '230px', width: '100%'},
            'loadGridData': (params, config) => {
                this.gridParamsObj = params;
                this.gridConfigObj = config;
                this.getFirmwareDetails(params, config);  
            },
            options: {
                'pagination': {
                    'limit': 20,
                    'offset': 0
                }
            }
        }
    }
    getFirmwareDetails(params, config) {
        this.appService.getFirmwareCompliance(this.deviceTypeValue).subscribe((resp:any) => {
            if (resp && resp.firmware_compliance_version) {
                this.gridConfig.total_count = 1;
                this.tableService.setData([{firmware_compliance_version: resp.firmware_compliance_version, compliance_scheduled_at: resp.compliance_scheduled_at}], params, config);
            } else {
                this.gridConfig.total_count = 0;
                this.tableService.setData([], params, config);
            }
        }, error => {
            this.gridConfig.total_count = 0;
            this.tableService.setData([], params, config);
        })
    }
}