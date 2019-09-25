import { Component, ViewEncapsulation, Input, OnInit, ViewChild, OnChanges } from '@angular/core';
import { AppService } from '../../app.service';
import { CentralGridUtilitiesService } from 'central-ui-component';

@Component({
    selector: 'onboarding-analytics',
    encapsulation: ViewEncapsulation.None,
    templateUrl: './onboarding-analytics.component.html'
})
export class OnboardingAnalyticsComponent implements OnInit, OnChanges {

    @Input() config;
    @Input() langLabels;
    @Input() refresh;
    gridConfig;
    id = '_' + Date.now();

    gridParamsObj;
    gridConfigObj;

    constructor(private appService: AppService, private tableService: CentralGridUtilitiesService) {}

    ngOnInit() {
        this.setConfig();
    }

    ngOnChanges(changes) {
        if (changes.refresh && !changes.refresh.firstChange) {
            this.gridConfig.loadGridData(this.gridParamsObj, this.gridConfigObj)
        }
    }

    setConfig() {
        this.gridConfig = {
            'showHeaderView': false,
            "id": this.id,
            "total_count": 0,
            'gridOptions': {
                'rowModelType': 'infinite',
                'columnDefs' : [{
                    headerName: 'score',
                    field: 'score',
                    tooltipField: 'score',
                    sortable: false
                }, {
                    headerName: 'stage',
                    field: 'stage',
                    tooltipField: 'stage',
                    sortable: false
                }, {
                    headerName: 'cch_score',
                    field: 'cch_score',
                    tooltipField: 'cch_score',
                    sortable: false
                }, {
                    headerName: 'onboarding_count',
                    field: 'onboarding_count',
                    tooltipField: 'onboarding_count',
                    width: 270,
                    sortable: false
                }, {
                    headerName: 'success_rate',
                    field: 'success_rate',
                    tooltipField: 'success_rate',
                    sortable: false
                }]
            },
            'gridStyle': this.config.gridStyle || { height: '230px', width: '100%'},
            'loadGridData': (params, config) => {
                this.gridParamsObj = params;
                this.gridConfigObj = config;
                this.getOnboardingAnalyticsDetails(params, config);  
            },
            options: {
                'pagination': {
                    'limit': 20,
                    'offset': 0
                }
            }
        }
    }
    getOnboardingAnalyticsDetails(params, config) {
        this.appService.getOnboardingAnalyticsDetails().subscribe((resp:any) => {
            if (resp && resp[0] && resp[1]) {
                this.gridConfig.total_count = 1;
                this.tableService.setData([{score: resp[0].score, stage: resp[0].stage, cch_score: resp[1].cch_score, onboarding_count: resp[1].onboarding_count, success_rate: resp[1].success_rate}], params, config);
            } else {
                this.gridConfig.total_count = 0;
                this.getOnboardingAnalyticsDetails(params, config);  
            }
        }, error => {
            this.gridConfig.total_count = 0;
            this.tableService.setData([], params, config);
        })
    }
}