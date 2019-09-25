import { Component, ViewEncapsulation, Input, OnInit, ViewChild, OnChanges } from '@angular/core';
import { AppService } from '../../app.service';
import { REFERENCE_PREFIX } from '@angular/compiler/src/render3/view/util';

@Component({
    selector: 'bandwidth-usage',
    encapsulation: ViewEncapsulation.None,
    templateUrl: './bandwidth.component.html'
})
export class BandwidthUsageComponent implements OnInit, OnChanges {
    
    @Input() config;
    @Input() refresh;
    public chartConfig;
    selectedFilter = 'WIRED';
    allNetworks = [{name: 'Select Network'}];
    selectedNetwork = "Select Network";

    constructor(private appService: AppService) {}

    ngOnChanges(changes) {
        if (changes.refresh && !changes.refresh.firstChange) {
            this.ngOnInit();
        }
    }

    ngOnInit() {
        this.chartConfig = undefined;
        this.getBWUsage(this.selectedFilter);
        this.getAllNetworks();
    }

    getAllNetworks() {
        this.selectedNetwork = this.allNetworks.length ? this.allNetworks[0].name : ''
        this.appService.getConnections().subscribe((resp:any) => {
            resp.networks.forEach(network => {
                this.allNetworks.push({name: network.essid});
            })
            this.selectedNetwork = this.allNetworks.length ? this.allNetworks[0].name : ''
        })
    }

    getBWUsage(filter) {
        var response = [{"key": 'Received', values: [], color: '#9FDCF6'}, {"key": "Sent", values: [], color: '#FD9A69'}];
        this.appService.getBW(this.selectedFilter, this.selectedNetwork ? this.selectedNetwork : '').subscribe((resp:any) => {
            resp.samples.forEach(sample => {
                response[0].values.push([new Date(sample.timestamp*1000), sample.rx_data_bytes])
                response[1].values.push([new Date(sample.timestamp*1000), sample.tx_data_bytes]);
            });
            this.chartConfig = Object.assign({}, this.config, {data: response})
        }, error => {
            let resp = {"count":36,"interval":"5minutes","samples":[{"rx_data_bytes":184625880,"timestamp":1566870900,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566871200,"tx_data_bytes":318585520},{"rx_data_bytes":165698520,"timestamp":1566871500,"tx_data_bytes":303877380},{"rx_data_bytes":39754278,"timestamp":1566871800,"tx_data_bytes":33885076},{"rx_data_bytes":33885076,"timestamp":1566872100,"tx_data_bytes":290815798},{"rx_data_bytes":51085856,"timestamp":1566872400,"tx_data_bytes":104221078},{"rx_data_bytes":144701366,"timestamp":1566872700,"tx_data_bytes":254826164},{"rx_data_bytes":184625880,"timestamp":1566873000,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566873300,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566873600,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566873900,"tx_data_bytes":318585520},{"rx_data_bytes":275370180,"timestamp":1566874200,"tx_data_bytes":493758658},{"rx_data_bytes":184625880,"timestamp":1566874500,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566874800,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566875100,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566875400,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566875700,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566876000,"tx_data_bytes":318585520},{"rx_data_bytes":181257618,"timestamp":1566876300,"tx_data_bytes":317915314},{"rx_data_bytes":184625880,"timestamp":1566876600,"tx_data_bytes":318585520},{"rx_data_bytes":318585520,"timestamp":1566876900,"tx_data_bytes":275267818},{"rx_data_bytes":184625880,"timestamp":1566877200,"tx_data_bytes":318585520},{"rx_data_bytes":183709254,"timestamp":1566877500,"tx_data_bytes":314918998},{"rx_data_bytes":104776854,"timestamp":1566877800,"tx_data_bytes":191066812},{"rx_data_bytes":184625880,"timestamp":1566878100,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566878400,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566878700,"tx_data_bytes":318585520},{"rx_data_bytes":52455720,"timestamp":1566879000,"tx_data_bytes":106416350},{"rx_data_bytes":184625880,"timestamp":1566879300,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566879600,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566879900,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566880200,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566880500,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566880800,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566881100,"tx_data_bytes":318585520},{"rx_data_bytes":184625880,"timestamp":1566881400,"tx_data_bytes":318585520}]};
            resp.samples.forEach(sample => {
                response[0].values.push([new Date(sample.timestamp*1000), sample.rx_data_bytes])
                response[1].values.push([new Date(sample.timestamp*1000), sample.tx_data_bytes]);
            });
            this.chartConfig = Object.assign({}, this.config, {data: response})
        })
    }

    onFilterChange(val) {
        this.selectedFilter = val;
        this.config.data = [];
        if (this.selectedFilter === 'WIRELESS' && this.selectedNetwork === 'Select Network') return
            this.getBWUsage(val);
    }
}