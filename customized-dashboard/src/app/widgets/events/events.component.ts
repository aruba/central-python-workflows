import { Component, ViewEncapsulation, Input, OnInit, ViewChild, OnChanges } from '@angular/core';
import { AppService } from '../../app.service';
import { CentralGridUtilitiesService } from 'central-ui-component';
import { EventPopupComponent } from './event-popup.component';

@Component({
    selector: 'events',
    encapsulation: ViewEncapsulation.None,
    templateUrl: './events.component.html'
})
export class EventsComponent implements OnInit, OnChanges {

    @Input() config;
    @Input() refresh;
    @Input() langLabels;
    gridConfig;
    id = '_' + Date.now();
    gridOffset;
    gridParamObj;
    gridConfigObj;

    constructor(private appService: AppService, private tableService: CentralGridUtilitiesService) {}

    ngOnChanges(changes) {
        if (changes.refresh && !changes.refresh.firstChange) {
            this.gridConfig.loadGridData(this.gridParamObj, this.gridConfigObj);
        }
    }

    ngOnInit() {
        this.setEventConfig();
    }

    setEventConfig() {
        this.gridConfig = {
            'showHeaderView': false,
            "id": this.id,
            "total_count": 0,
            //"title": this.config.title,
            'gridOptions': {
                'rowModelType': 'infinite',
                "rowSelection": "single",
                "rowDeselection": true,
                'frameworkComponents': {
                    eventPopup: EventPopupComponent
                },
                'columnDefs' : [{
                    headerName: 'id_label',
                    field: 'id',
                    sortable: false,
                    cellRenderer: 'eventPopup'
                }, {
                    headerName: 'classification',
                    field: 'classification',
                    sortable: false,
                    width: 230,
                    tooltipField: 'classification'
                }, {
                    headerName: 'description',
                    field: 'description',
                    sortable: false,
                    width: 330,
                    tooltipField: 'description'
                }, {
                    headerName: 'ip_address',
                    field: 'ip_addr',
                    sortable: false,
                    tooltipField: 'ip_address'
                }, {
                    headerName: 'target',
                    field: 'target',
                    sortable: false,
                    tooltipField: 'target'
                }, {
                    headerName: 'timestamp',
                    field: 'ts',
                    sortable: false,
                    valueFormatter: (params) => {
                        return this.appService.getTimeStr(params.value)
                    },
                    tooltip: (params) => {
                        return params.valueFormatted;
                    }
                }]
            },
            'gridStyle': this.config.gridStyle || { height: '210px', width: '100%'},
            'loadGridData': (params, config) => {
                this.gridParamObj = params;
                this.gridConfigObj = config;
                this.getEvents(params, config);  
            },
            options: {
                'pagination': {
                    'limit': 20,
                    'offset': 0
                }
            }
        }
    }
    getEvents(params, config) {
        this.gridOffset = isNaN(this.gridOffset) ? 0 : this.gridOffset + 1;
        this.appService.getEventsData(20, this.gridOffset).subscribe((resp:any) => {
            if (resp && resp.events && resp.events.length) {
                this.gridConfig.total_count = resp.total;
                this.tableService.setData(resp.events, params, config);
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