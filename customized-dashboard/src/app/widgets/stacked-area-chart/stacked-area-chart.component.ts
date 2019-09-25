import { Component, ViewEncapsulation, Input, OnInit } from '@angular/core';
import { config } from 'rxjs';

@Component({
        selector: 'stacked-area-chart',
        encapsulation: ViewEncapsulation.None,
        templateUrl: './stacked-area-chart.component.html',
        styleUrls: ['./stacked-area-chart.component.scss']
    })
export class StackedAreaChartComponent implements OnInit {
    @Input() config;
    public options: any;
    public data: any;
  
    constructor() { }
  
    ngOnInit() {
      this.setStackedAreaChartOptions();
      this.fetchData();
    }
  
    setStackedAreaChartOptions() {
      this.options = {
        chart: {
          type: 'stackedAreaChart',
          height: 280,
          width: this.config.width,
          x: function(d){return d[0];},
          y: function(d){return d[1];},
          useVoronoi: false,
          clipEdge: true,
          duration: 100,
          useInteractiveGuideline: true,
          xAxis: {
            showMaxMin: false,
            tickFormat: (d, i) => {
              var date = new Date(d);
              let monthArr = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
              //let dateStr = monthArr[date.getMonth()] + ' ' + this.validateLength(date.getDate()) + ', ' + date.getFullYear()
                  + ', ' + this.validateLength(date.getHours()) + ':' + this.validateLength(date.getMinutes())
              
              return this.validateLength(date.getHours()) + ':' + this.validateLength(date.getMinutes());
            }
          },
          yAxis: {
            axisLabel: 'Usage (Bytes)',
            axisLabelDistance: -5,
            tickFormat: (d, i) => {
                return this.yValueFormatter(d);
            }
          },
          zoom: {
            enabled: true,
            scaleExtent: [1, 10],
            useFixedDomain: false,
            useNiceScale: false,
            horizontalOff: false,
            verticalOff: true,
            unzoomEventType: 'dblclick.zoom'
          },
          noData: "No data to display"
        }
      };
    }
  
    validateLength(val) {
      return val < 10 ? ('0'+val) : val;
    }

    yValueFormatter(val) {
      let numericValue;
      let suffix;
      if (!val) return 0;
      if (val < 1000000 && val >= 1000) {
          numericValue = val / 1000;
          suffix = 'K';
      }
      if (val < 1000000000 && val >= 1000000) {
              numericValue = val / 1000000;
              suffix = 'M';

      }
      if (val < 1000000000000 && val >= 1000000000) {
              numericValue = val / 1000000000;
              suffix = 'G';

      }
      if (val < 1000000000000000 && val >= 1000000000000) {
              numericValue = val / 1000000000000;
              suffix = 'T';
      }
      if (val >= 1000000000000000) {
              numericValue = val / 1000000000000000;
              suffix = 'P';
      }
      return (Math.round(numericValue)) + suffix;
    }

    fetchData() {
      this.config.data = this.config.data.map(data => {
        data.values = data.values.map(value => {
          let mapppedValue = [];
          mapppedValue.push(new Date(value[0]));
          mapppedValue.push(value[1]);
          return mapppedValue;
        })
        return data;
      })
    }

}