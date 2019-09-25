import { Component, ViewEncapsulation, Input, OnInit, ViewChild } from '@angular/core';
import { AppService } from '../../app.service';
import { CentralGridUtilitiesService } from 'central-ui-component';

@Component({
    selector: 'presence-analytics',
    encapsulation: ViewEncapsulation.None,
    templateUrl: './presence-analytics.component.html'
})
export class PresenceAnalyticsComponent implements OnInit {
    
    @Input() config;
    @Input() langLabels;
    analyticsConfig;

    selectedFilter = 'AGGREGATES';

    constructor(private appService: AppService, private tableService: CentralGridUtilitiesService) {}

    ngOnInit() {
        this.getAnalyticsData();
    }

    getAnalyticsData() {
        // if (this.selectedFilter === 'AGGREGATES') {
        //     let data = [];
        //     this.appService.getGuestPortalData(this.selectedFilter).subscribe((resp:any) => {
        //         if (resp && resp && resp.length) {
        //         } else {
        //         }
        //     }, error => {
        //         let resp = {"stats":[{"category":"passerby","field_value":{"unit":"secs","value":20},"rate":1}],"conversionRate":{"valid_data":"true","passerby_to_visitor":20,"visitor_to_engaged":40}};
        //         if (resp && resp.stats && resp.stats.length) {
        //             resp.stats.forEach(stat => {
        //                 data.push({key: stat.category, values: []})
        //             });
        //         } else {
        //             this.analyticsConfig = Object.assign({}, this.config, {data: data});
        //         }
        //     })
        // } else {
        //     this.appService.getGuestPortalData(this.selectedFilter).subscribe((resp:any) => {
        //         if (resp && resp && resp.length) {
        //         } else {
        //         }
        //     }, error => {
                
        //     })
        // }
    }

    onFilterChange(val) {
        this.selectedFilter = val;
        this.getAnalyticsData()
    }
}