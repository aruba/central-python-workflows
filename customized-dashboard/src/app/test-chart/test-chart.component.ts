import { Component, OnInit, ViewEncapsulation } from '@angular/core';


@Component({
  selector: 'test-chart',
  templateUrl: './test-chart.component.html',
  styleUrls: ['./test-chart.component.scss'],
  encapsulation: ViewEncapsulation.None
})

export class TestChartComponent implements OnInit {
    /*public options: any;
    public data: any;

    constructor() { }

    ngOnInit() {
      this.setLineWithFocusChartOptions();
      this.fetchData();
    }

    setLineWithFocusChartOptions() {
      this.options = {
        chart: {
          type: 'lineWithFocusChart',
          height: 450,
          margin: {
            top: 20,
            right: 20,
            bottom: 60,
            left: 40
          },
          duration: 500,
          useInteractiveGuideline: true,
          xAxis: {
            axisLabel: 'X Axis',
            tickFormat: function (d) {
              return d3.format(',f')(d);
            }
          },
          x2Axis: {
            tickFormat: function (d) {
              return d3.format(',f')(d);
            }
          },
          yAxis: {
            axisLabel: 'Y Axis',
            tickFormat: function (d) {
              return d3.format(',.2f')(d);
            },
            rotateYLabel: false
          },
          y2Axis: {
            tickFormat: function (d) {
              return d3.format(',.2f')(d);
            }
          }
        }
      };
    }

    streamLayers(n, m, o) {
      if (arguments.length < 3) {o = 0;}
      function bump(a) {
        let x = 1 / (.1 + Math.random());
        let y = 2 * Math.random() - .5;
        let z = 10 / (.1 + Math.random());
        for (let i = 0; i < m; i++) {
          let w = (i / m - y) * z;
          a[i] += x * Math.exp(-w * w);
        }
      }
      return d3.range(n).map(function() {
        const a = [];
        let i;
        for (i = 0; i < m; i++) a[i] = o + o * Math.random();
        for (i = 0; i < 5; i++) bump(a);
        return a.map(function(val, idx) {
          return {x: idx, y: Math.max(0, val)};
        });
      });
    }

    fetchData() {
      this.data = this.streamLayers(3, 10 + Math.random() * 200, .1).map(function(data, i) {
        return {
          key: 'Stream' + i,
          values: data
        };
      });
    }*/
    /*public options: any;
    public data: any;
  
    constructor() { }
  
    ngOnInit() {
      this.setMultibarChartOptions();
      this.fetchData();
    }
  
    setMultibarChartOptions() {
      this.options = {
        chart: {
          type: 'multiBarChart',
          height: 450,
          margin : {
            top: 20,
            right: 20,
            bottom: 45,
            left: 45
          },
          clipEdge: true,
          duration: 500,
          stacked: true,
          xAxis: {
            axisLabel: 'Time (ms)',
            showMaxMin: false,
            tickFormat: function(d){
              return d3.format(',f')(d);
            }
          },
          yAxis: {
            axisLabel: 'Y Axis',
            axisLabelDistance: -20,
            tickFormat: function(d){
              return d3.format(',.1f')(d);
            }
          }
        }
      };
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
    }*/
    public options = {
        chart: {
            type: 'pieChart',
            height: 500,
            x: function(d){return d.key;},
            y: function(d){return d.y;},
            showLabels: true,
            duration: 500,
            labelThreshold: 0.01,
            labelSunbeamLayout: false,
            donutLabelsOutside: true,
            //donut: true,
            legend: {
                margin: {
                    top: 10,
                    right: 35,
                    bottom: 35,
                    left: 0
                }
            },
            tooltip: {
                contentGenerator: function (d) {
                var html = "dsjghjhasgjhsagdjhsagdhas"
                return html;
              }
            }
        }
    };

    public data = [
        {
            key: "One",
            y: 5
        },
        {
            key: "Two",
            y: 2
        },
        {
            key: "Three",
            y: 9
        },
        {
            key: "Four",
            y: 7
        },
        {
            key: "Five",
            y: 4
        },
        {
            key: "Six",
            y: 3
        },
        {
            key: "Seven",
            y: .5
        }
    ];

    ngOnInit() {}

    constructor() {}
}