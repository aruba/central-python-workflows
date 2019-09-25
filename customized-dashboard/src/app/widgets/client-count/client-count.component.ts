import { Component, ViewEncapsulation, Input, OnInit, ViewChild, OnChanges } from '@angular/core';
import { AppService } from '../../app.service';

@Component({
    selector: 'client-count',
    encapsulation: ViewEncapsulation.None,
    templateUrl: './client-count.component.html'
})
export class ClientCountComponent implements OnInit, OnChanges {
    
    @Input() config;
    @Input() refresh;
    chartConfig;
    filterBy = [{name: 'Select Filter', value: ''}, {name: 'By Band', value: 'band'}, {name: 'By Device Type', value: 'device_type'}, {name: 'By Label', value: 'label'}, {name: 'By Network', value: 'network'}, {name: 'By Config Group', value: 'group'}];
    bandTypes = [];
    aps = [{name: 'AP', value: ''}];
    filterValue = "";
    filterByValue = "";
    bandTypeValue = '2.4';
    apSerial;


    constructor(private appService: AppService) {}

    ngOnChanges(changes) {
        if (changes.refresh && !changes.refresh.firstChange) {
            this.ngOnInit();
        }
    }
    ngOnInit() {
        this.chartConfig = '';
        this.filterByValue = "";
        this.getClientCount();
        this.getAps();
    }

    getAps() {
        this.appService.getAps().subscribe((resp:any) => {
            resp.aps.forEach(ap => {
                this.aps.push({name: ap.name, value: ap.serial});
            });
            this.apSerial = this.aps[1] ? this.aps[1].value : '';
        });
    }

    getClientCount() {
        let queryParam = "";
        if (this.filterByValue) {
            if (this.filterByValue === 'band') {
                queryParam = this.filterByValue + '=' + this.bandTypeValue + '&serial=' + this.apSerial;
            }
            else if (this.filterByValue === 'device_type') {
                queryParam = this.filterByValue + '=' + this.bandTypeValue;
            }
            else {
                queryParam = this.filterValue && this.filterValue.length ? this.filterByValue + '=' + this.filterValue : '';
            }
        }
        this.appService.getClientGraph(queryParam).subscribe((resp:any) => {
            var response = [{"key": 'Clients', values: [], color: '#9FDCF6'}];
            resp.samples.forEach(sample => {
                response[0].values.push({'x': new Date(sample.timestamp*1000), 'y': sample.client_count})
            });
            this.chartConfig = Object.assign({}, this.config, {data: response});
        }, error => {
            this.chartConfig = Object.assign({}, this.config, {data: []});
        })
    }

    onFilterChange(val) {
        if (val === 'band') {
            this.bandTypes = [{name: '2.4', value: '2.4'}, {name: '5', value: '5'}]
            this.bandTypeValue = this.bandTypes[0].value;
            this.apSerial = this.aps[1] ? this.aps[1].value : '';
            this.getClientCount();
        }
        else if (val === 'device_type') {
            this.bandTypes = [{name: 'AP', value: 'AP'}, {name: 'Switch', value: 'Switch'}]
            this.bandTypeValue = this.bandTypes[0].value;
            this.getClientCount();
        }
        else {
            this.filterValue = '';
        }
    }
}