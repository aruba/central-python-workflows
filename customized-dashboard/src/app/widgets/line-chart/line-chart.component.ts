import { Component, ViewEncapsulation, AfterViewInit, Input, OnInit } from '@angular/core';

// import * as d3 from 'd3-selection';
// import * as d3Scale from 'd3-scale';
// import * as d3ScaleChromatic from 'd3-scale-chromatic';
// import * as d3Shape from 'd3-shape';
// import * as d3Array from 'd3-array';
// import * as d3Axis from 'd3-axis';

@Component({
    selector: 'line-chart',
    encapsulation: ViewEncapsulation.None,
    templateUrl: './line-chart.component.html',
    styleUrls: ['./line-chart.component.scss']
})
export class LineChartComponent implements OnInit {

    @Input() config;
    public options;

    constructor() {}

    ngOnInit() {
        this.setConfig();
        this.fetchData();
    }

    fetchData() {
        this.config.data = this.config.data.map(data => {
          data.values = data.values.map(value => {
            return {x: new Date(value.x), y: value.y};
          })
          return data;
        })
    }

    setConfig() {
        this.options = {
            chart: {
                type: 'lineChart',
                height: 280,
                width: this.config.width,
                x: function(d){ return d.x; },
                y: function(d){ return d.y; },
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
                    axisLabel: this.config.yAxisLabel ? this.config.yAxisLabel : 'Usage (Bytes)',
                    axisLabelDistance: -5,
                    tickFormat: (d, i) => {
                        return !this.config.yAxisLabel ? this.yValueFormatter(d) : d;
                    }
                },
                noData: "No data to display"
            }
        }
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
    // id = '_' + Date.now();

    // data: any;

    // svg: any;
    // totalWidth = document.getElementsByClassName('example-box')[0] ? document.getElementsByClassName('example-box')[0]['offsetWidth'] : document.getElementsByClassName('drop-box')[0]['offsetWidth'];
    // margin = {top: 30, right: 65, bottom: 30, left: 70};
    // g: any;
    // width: number;
    // height: number;
    // x;
    // y;
    // z;
    // line;
    // tooltip = <any>{};

    // constructor() {

    // }

    // ngAfterViewInit() {

    //     this.data = this.config.data.map((v) => v.values.map((v) => v.date ))[0];
    //     //.reduce((a, b) => a.concat(b), []);

    //     this.initChart();
    //     this.drawAxis();
    //     this.drawPath();
    // }

    // private initChart(): void {
    //     this.svg = d3.select('#' + this.id);

    //     this.width = this.svg.attr('width') - this.margin.left - this.margin.right;
    //     this.height = this.svg.attr('height') - this.margin.top - this.margin.bottom;

    //     this.g = this.svg.append('g').attr('transform', 'translate(' + this.margin.left + ',' + this.margin.top + ')');

    //     this.x = d3Scale.scaleTime().range([0, this.width]);
    //     this.y = d3Scale.scaleLinear().range([this.height, 0]);
    //     this.z = d3Scale.scaleOrdinal(d3ScaleChromatic.schemeCategory10);

    //     this.line = d3Shape.line()
    //         .curve(d3Shape.curveBasis)
    //         .x( (d: any) => {
    //             d.date = new Date(d.date);
    //             return this.x(d.date)
    //         })
    //         .y( (d: any) => this.y(d.usage) );

    //     this.x.domain(d3Array.extent(this.data, (d: Date) => {
    //         return new Date(d);
    //     }));

    //     this.y.domain([
    //         d3Array.min(this.config.data, function(c) { return d3Array.min(c.values, function(d) { return d.usage; }); }),
    //         d3Array.max(this.config.data, function(c) { return d3Array.max(c.values, function(d) { return d.usage; }); })
    //     ]);

    //     this.z.domain(this.config.data.map(function(c) { return c.id; }));
    // }

    // private drawAxis(): void {
    //     this.g.append('g')
    //         .attr('class', 'axis axis--x')
    //         .attr('transform', 'translate(0,' + this.height + ')')
    //         .call(d3Axis.axisBottom(this.x));

    //     this.g.append('g')
    //         .attr('class', 'axis axis--y')
    //         .call(d3Axis.axisLeft(this.y))
    //         .append('text')
    //         //.attr('transform', 'rotate(-90)')
    //         .attr('y', -15)
    //         .attr('x', 30)
    //         .attr('dy', '0.71em')
    //         .attr('fill', '#000')
    //         .text('USAGE (bps)');
    // }


    // private drawPath(): void {
    //     let city = this.g.selectAll('.city')
    //         .data(this.config.data)
    //         .enter().append('g')
    //         .attr('class', 'city')
    //         .on("mousemove", (d) => {
    //             console.log(d)
    //             this.tooltip.label = d.data.id;
    //             tooltip.innerHTML = 'Value : ' + d.value;
        
    //             var left = d3.event.pageX;
    //             var tooltipWidth =  parseInt(tooltip.style.width, 10);
    //             var screenWidth = document.documentElement.clientWidth;
    //             if ((left + tooltipWidth) > screenWidth) {
    //                 left = screenWidth - tooltipWidth - 20;
    //             }
    //             tooltip.style.left = left + 'px';
    //             tooltip.style.top = (d3.event.pageY + 20) + 'px';
                
    //             tooltip.style.opacity = "1";
    //         })
    //         .on("mouseout", () => {
    //             tooltip.style.opacity = "0";
    //         });

    //     var tooltip = d3.select("#" + this.id + 'tooltip');
    //     city.append('path')
    //         .attr('class', 'line')
    //         .attr('d', (d) => this.line(d.values) )
    //         .style('stroke', (d) => this.z(d.id) )

    //     city.append('text')
    //         .datum(function(d) { return {id: d.id, value: d.values[d.values.length - 1]}; })
    //         .attr('transform', (d) => 'translate(' + this.x(d.value.date) + ',' + this.y(d.value.usage) + ')' )
    //         .attr('x', 3)
    //         .attr('dy', '0.35em')
    //         .style('font', '10px sans-serif')
    //         .text(function(d) { return d.id; });
    // }

}
