import { Component, ViewEncapsulation, Input, OnInit } from '@angular/core';

@Component({
        selector: 'multi-bar-chart',
        encapsulation: ViewEncapsulation.None,
        templateUrl: './multi-bar-chart.component.html',
        styleUrls: ['./multi-bar-chart.component.scss']
    })
export class MultiBarChartComponent implements OnInit {

    @Input() config;
    public options: any;
    public data: any;
  
    constructor() {}
  
    ngOnInit() {
      this.setMultibarChartOptions();
      this.fetchData();
    }
  
    setMultibarChartOptions() {
      this.options = {
        chart: {
          type: 'multiBarChart',
          height: 250,
          margin : {
            top: 30,
            right: 20,
            bottom: 20,
            left: 65
          },
          width: this.config.width,
          clipEdge: true,
          duration: 500,
          stacked: true,
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

    streamLayers(n, m, o) {
      if (arguments.length < 3) { o = 0; }
      function bump(a) {
        let x = 1 / (.1 + Math.random());
        let y = 2 * Math.random() - .5;
        let z = 10 / (.1 + Math.random());
        for (var i = 0; i < m; i++) {
          var w = (i / m - y) * z;
          a[i] += x * Math.exp(-w * w);
        }
      }
      return d3.range(n).map(function() {
        let a = [];
        let i;
        for (i = 0; i < m; i++) a[i] = o + o * Math.random();
        for (i = 0; i < 5; i++) bump(a);
        return a.map(function(val, idx){
          return {x: idx, y: Math.max(0, val)};
        });
      });
    }
  
  
    fetchData() {
      this.data = this.streamLayers(3, 50 + Math.random() * 50, .1).map(function(data, i) {
        return {
          key: 'Stream' + i,
          values: data
        };
      });
    }
}