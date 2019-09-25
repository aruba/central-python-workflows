import { Component, ViewEncapsulation, Input, OnInit } from '@angular/core';
import { CentralGridUtilitiesService } from 'central-ui-component';

@Component({
    selector: 'grid-wrapper',
    encapsulation: ViewEncapsulation.None,
    templateUrl: './grid-wrapper.component.html'
})
export class GridWrapperComponent implements OnInit {
    @Input() config;
    @Input() langLabels;
    id = '_' + Date.now();
    gridConfig;
    resp;

    constructor(private tableService: CentralGridUtilitiesService) {}

    ngOnInit() {
        this.gridConfig = {
            "id": this.id,
            "total_count":0,
            "title": this.config.title,
            'gridOptions': {
                'suppressRowHoverHighlight': true,
                'suppressRowClickSelection': true,
                'columnDefs' : this.getColumns()
            },
            'gridStyle': this.config.gridStyle || { height: '210px', width: '100%'},
            'loadGridData': (params, config) => {
                this.tableService.setData(this.config.data, params, config);
            },
            'options': {
                'pagination': {
                'limit': 10,
                'offset': 0
                }
            }
        }
    }

    getColumns() {
        let columns = [];
        this.config.columns.forEach(column => {
            columns.push(Object.assign({}, column));
        })
        return columns;
    }
}