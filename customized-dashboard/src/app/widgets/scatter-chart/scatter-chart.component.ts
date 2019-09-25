import { Component, ViewEncapsulation, Input, AfterViewInit, OnInit } from '@angular/core';

// import * as d3 from 'd3-selection';
// import * as d3Scale from 'd3-scale';
// import * as d3Array from 'd3-array';
// import * as d3Axis from 'd3-axis';

@Component({
    selector: 'scatter-chart',
    encapsulation: ViewEncapsulation.None,
    templateUrl: './scatter-chart.component.html',
    styleUrls: ['./scatter-chart.component.scss']
})
export class ScatterChartComponent implements OnInit {

    @Input() config;
    public options;
    public data;

    constructor() {}

    ngOnInit() {
        this.setScatterChartOptions();
        this.fetchData();
      }
    
      setScatterChartOptions() {
        this.options = {
          chart: {
            type: 'scatterChart',
            height: 270,
            width: this.config.width-5,
            color: d3.scale.category10().range(),
            scatter: {
              onlyCircles: false
            },
            showDistX: true,
            showDistY: true,
            tooltipContent: function(key) {
              return '<h3>' + key + '</h3>';
            },
            duration: 350,
            xAxis: {
              axisLabel: 'X Axis',
              tickFormat: function(d){
                return d3.format('.02f')(d);
              }
            },
            yAxis: {
              axisLabel: 'Y Axis',
              tickFormat: function(d){
                return d3.format('.02f')(d);
              },
              axisLabelDistance: -5
            }
          }
        };
      }
    
      fetchData() {
        const groups = 1;
        const points = 100;
        this.data = [];
        const shapes = ['circle'];
        const random = d3.random.normal();
        for (let i = 0; i < groups; i++) {
          this.data.push({
            key: 'Group ' + i,
            values: []
          });
    
          for (let j = 0; j < points; j++) {
            this.data[i].values.push({
              x: random()
              , y: random()
              , size: Math.random()
              , shape: shapes[j % 6]
            });
          }
        }
        console.log(this.data, 'this.data');
      }  
    // id = '_' + Date.now();

    // title = 'Bar Chart';
    // totalWidth = document.getElementsByClassName('example-box')[0] ? document.getElementsByClassName('example-box')[0]['offsetWidth'] : document.getElementsByClassName('drop-box')[0]['offsetWidth'];
    // private width: number;
    // private height: number;
    // private margin = {top: 30, right: 20, bottom: 17, left: 50};

    // private x: any;
    // private y: any;
    // private svg: any;
    // private g: any;

    // constructor() {}

    // ngAfterViewInit() {
    //     this.initSvg();
    //     this.initAxis();
    //     this.drawAxis();
    //     this.drawBars();
    // }

    // private initSvg() {
    //     this.svg = d3.select('#' + this.id);
    //     this.width = +this.svg.attr('width') - this.margin.left - this.margin.right;
    //     this.height = +this.svg.attr('height') - this.margin.top - this.margin.bottom;
    //     this.g = this.svg.append('g')
    //         .attr('transform', 'translate(' + this.margin.left + ',' + this.margin.top + ')');
    // }

    // private initAxis() {
    //     this.x = d3Scale.scaleBand().rangeRound([0, this.width]).padding(0.522);
    //     this.y = d3Scale.scaleLinear().rangeRound([this.height, 0]);
    //     this.x.domain(this.config.data.map((d) => d.date));
    //     this.y.domain([0, d3Array.max(this.config.data, (d) => d.value)]);
    // }

    // private drawAxis() {
    //     this.g.append('g')
    //         .attr('class', 'axis axis--x')
    //         .attr('transform', 'translate(0,' + this.height + ')')
    //         .call(d3Axis.axisBottom(this.x).tickFormat((d, i) => {
    //             if (i%3===0)    return d;
    //             return '';
    //         }));
    //     this.g.append('g')
    //         .attr('class', 'axis axis--y')
    //         .call(d3Axis.axisLeft(this.y).ticks(10, ''))
    //         .append('text')
    //         .attr('class', 'axis-title')
    //         //.attr('transform', 'rotate(180)')
    //         .attr('fill', '#000')
    //         .attr('y', -15)
    //         .attr('x', 20)
    //         .attr('dy', '0.71em')
    //         .attr('text-anchor', 'end')
    //         .text('CLIENTS');
    // }

    // private drawBars() {
    //     this.g.selectAll('.bar')
    //         .data(this.config.data)
    //         .enter().append('rect')
    //         .attr('class', 'bar')
    //         .attr('x', (d) => this.x(d.date) )
    //         .attr('y', (d) => this.y(d.value) )
    //         .attr('width', this.x.bandwidth())
    //         .attr('height', (d) => this.height - this.y(d.value) );
    // }

}
