import { Component, ViewEncapsulation, AfterViewInit, Input, OnInit, OnChanges } from '@angular/core';
import { AppService } from '../../app.service';

// import * as d3 from 'd3-selection';
// import * as d3Scale from 'd3-scale';
// import * as d3Shape from 'd3-shape';

@Component({
    selector: 'pie-chart',
    encapsulation: ViewEncapsulation.None,
    templateUrl: './pie-chart.component.html',
    styleUrls: ['./pie-chart.component.scss']
})
export class PieChartComponent implements OnInit, OnChanges {

    @Input() config;
    @Input() refresh;
    public options;
    public data;
    constructor(private appService: AppService) {}

    ngOnChanges(changes) {
        if (changes.refresh && !changes.refresh.firstChange) {
            this.data = '';
            this.getData()
        }
    }

    ngOnInit() {
        this.options = {
            chart: {
                type: 'pieChart',
                height: 250,
                width: this.config.width,
                donut: this.config.isDonut,
                x: function(d){return d.key;},
                y: function(d){return Math.round(d.y);},
                showLabels: true,
                duration: 500,
                labelThreshold: 0.01,
                labelSunbeamLayout: false,
                donutLabelsOutside: true,
                legend: {
                    margin: {
                        top: 1,
                        right: 0,
                        bottom: 5,
                        left: 0
                    }
                },
                valueFormat: function(d) {
                    return d;
                },
                noData: "No data to display"
            }
        };
        this.getData();
    }

    getData() {
        if (this.config.key === "device_count") {
            this.appService.getDeviceCount().subscribe((resp:any) => {
                this.data = resp[0].total && !resp[1].total && !resp[2].total ? [] : [{
                    key: 'IAP',
                    y: resp[0].total || 0
                }, {
                    key: 'Switch',
                    y: resp[1].total || 0
                }, {
                    key: 'Gateway',
                    y: resp[2].total || 0
                }]
            }, error => {
                this.data = []
            })
        }
        if (this.config.key === "total_client_count") {
            this.appService.getClientCount().subscribe((resp:any) => {
                this.data = !resp[0].count && !resp[1].total ? [] : [{
                    key: 'Total',
                    y: resp[0].count || 0
                }, {
                    key: 'Wireless',
                    y: resp[1].total || 0
                }, {
                    key: 'Wired',
                    y: resp[0].count - resp[1].total || 0
                }]
            }, error => {
                this.data = []
            })
        }
        if (this.config.key === "connection_count") {
            this.appService.getConnections().subscribe((resp:any) => {
                let devices = [];
                let ref = [];
                let hasClients = false;
                resp.networks.forEach(network => {
                    let index = ref.indexOf(network.security);
                    if (index === -1) {
                        devices.push({key: network.security, y: network.client_count});
                        ref.push(network.security);
                    }
                    else
                        devices[index]['y'] += network.client_count;
                    //hasClients = hasClients || network.client_count ? true : false;
                });
                this.data = devices;
            }, error => {
                this.data = []
            })
        }
    }

}
