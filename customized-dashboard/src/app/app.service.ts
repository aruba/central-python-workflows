import { Injectable } from '@angular/core';
import { HttpManager } from 'central-ui-core';
import { RequestOptions, Headers } from '@angular/http';
import { EnvironmentConfig } from '../config/service.config';

const from = Math.round((new Date().getTime()-(7 * 24 * 60 * 60 * 1000))/1000);
const to = Math.round(new Date().getTime()/1000);

@Injectable()
export class AppService {
    private baseUrl;
    private access_token;


    private storedJson;

    private id = '_' + Date.now();

    constructor(private _http: HttpManager) {
        let cookie = document.cookie.split(';');
        this.baseUrl = cookie[2] && cookie[2].indexOf('apigw_url') > -1 ? 'https://' + cookie[2].split("apigw_url=")[1] + '/':
                EnvironmentConfig.appUrl;
        this.setAccessToken();
    }

    setAccessToken() {
        let cookie = document.cookie.split(';');
        this.access_token = cookie[3] && cookie[3].indexOf('access_token') > -1 ? cookie[3].split("access_token=")[1] :
                EnvironmentConfig.accessToken;
    }

    public getHeaders() {
        let headers = new Headers();
        //headers.set('Access-Control-Allow-Origin', '*');
        headers.set('Authorization: Bearer', this.access_token);
        return  new RequestOptions({ headers: headers });
    }

    public setJson(json) {
        this.storedJson = json;
    }

    public getEventsData(limit, offset) {
        this.setAccessToken();
        return this._http.get(this.baseUrl+'auditlogs/v1/events?limit='+limit+'&offset='+offset+'&access_token='+this.access_token)
    }

    public getDeviceCount() {
        this.setAccessToken();
        return this._http.getBulk([this.baseUrl+'monitoring/v1/aps?calculate_total=true&access_token='+this.access_token, this.baseUrl+'monitoring/v1/switches?calculate_total=true&access_token='+this.access_token, this.baseUrl+'monitoring/v1/mobility_controllers?calculate_total=true&access_token='+this.access_token]);
    }

    public getEventDetails(id) {
        this.setAccessToken();
        return this._http.get(this.baseUrl+'auditlogs/v1/event_details/'+id+'?access_token='+this.access_token)
    }

    getTimeStr(ts) {
        var date = new Date(ts*1000);
        let monthArr = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        let dateStr = monthArr[date.getMonth()] + ' ' + this.validateLength(date.getDate()) + ', ' + date.getFullYear()
            + ', ' + this.validateLength(date.getHours()) + ':' + this.validateLength(date.getMinutes()) + ':' + this.validateLength(date.getSeconds())
        return dateStr
    }

    validateLength(val) {
        return val < 10 ? ('0'+val) : val;
    }

    public getClientCount() {
        this.setAccessToken();
        return this._http.getBulk([this.baseUrl+'monitoring/v1/clients/count?calculate_total=true&access_token='+this.access_token, this.baseUrl+'monitoring/v1/clients/wireless?calculate_total=true&access_token='+this.access_token/*, this.baseUrl+'monitoring/v1/clients/wired?calculate_total=true&access_token='+this.access_token*/]);
    }

    public getConnections() {
        this.setAccessToken();
        return this._http.get(this.baseUrl+'monitoring/v1/networks?calculate_client_count=true&access_token='+this.access_token);
    }

    public getBW(type, network?) {
        this.setAccessToken();
        let url = type === 'WIRELESS' ? this.baseUrl+'monitoring/v1/networks/bandwidth_usage?network='+network : this.baseUrl+'monitoring/v1/switches/bandwidth_usage';
        return this._http.get(url + '&from_timestamp=' + from + '&to_timestamp=' + to + '&access_token='+this.access_token);
    }

    public getRoguAps() {
        this.setAccessToken();
        return this._http.get(this.baseUrl+'rapids/v1/rogue_aps?limit=100&access_token='+this.access_token)
    }

    public getGuestPortalData(limit, offset, type) {
        this.setAccessToken();
        if (type === 'SSIDS')
            return this._http.get(this.baseUrl+'guest/v1/wlans?offset=' + offset + '&limit=' + limit + '&access_token='+this.access_token);
        else
            return this._http.get(this.baseUrl+'guest/v1/portals?sort=%2Bname&offset=' + offset + '&limit=' + limit + '&access_token='+this.access_token)
    }

    public getSecurityInfo(limit, offset, type) {
        this.setAccessToken();
        if (type === 'ROGUEAPS')
            return this._http.get(this.baseUrl+'rapids/v1/rogue_aps?offset=' + offset + '&limit=' + limit + '&access_token='+this.access_token);
        else
            return this._http.get(this.baseUrl+'rapids/v1/interfering_aps?offset=' + offset + '&limit=' + limit + '&access_token='+this.access_token)
    }

    public getPresenceAnalytics(limit, offset, type) {
        this.setAccessToken();
        if (type === 'AGGREGATES') {
            return this._http.get(this.baseUrl+'presence/v1/analytics/aggregates&start_time=' + from + '&end_time=' + to + '&access_token='+this.access_token)
        }
        else {
            return this._http.get(this.baseUrl+'presence/v1/analytics/trends&start_time=' + from + '&end_time=' + to + '&access_token='+this.access_token)
        }
    }

    public getOnboardingAnalyticsDetails() {
        this.setAccessToken();
        return this._http.getBulk([this.baseUrl+'clarity/v1/overview/healthscore?start_time=' + from + '&end_time=' + to + '&access_token='+this.access_token, this.baseUrl+'clarity/v1/overview/network_stats&access_token='+this.access_token]);
    }

    public getClientGraph(queryParam) {
        this.setAccessToken();
        let to = new Date(); 
        var hours_3 = 3 * 60 * 60 * 1000;
        let from = new Date(new Date().getTime() - hours_3);
        return this._http.get(this.baseUrl+'monitoring/v1/clients/count?calculate_client_count=true' + (queryParam ? '&' + queryParam : '') + '&access_token='+this.access_token)
    }

    public getAps() {
        this.setAccessToken();
        return this._http.get(this.baseUrl+'monitoring/v1/aps?access_token='+this.access_token);
    }

    public getFirmwareCompliance(device) {
        this.setAccessToken();
        return this._http.get(this.baseUrl+'firmware/v1/upgrade/compliance_version?device_type=' + device + '&access_token='+this.access_token);
    }

    public getStoredJson() {
        let storedJson = window.localStorage.getItem('dashboardJson');
        if (!this.storedJson && storedJson) {
            this.storedJson = JSON.parse(storedJson);
        }
        return this.storedJson;
    }

    public clearCachedJson() {
        window.localStorage.removeItem('dashboardJson');
        this.storedJson = '';
    }

    public getJson(name) {
        return {
            "name": name,
            "id": this.id,
            "color": "",
            "rowCount": 1,
            "columSize": 2,
            "timePeriod": "3 Hours",
            /*"rows": [{
                "name": "Row 1",
                "id": 0,
                "columns": [{
                    "name": "Column 1",
                    "id": 0,
                    "widget": {
                        "name": "",
                        "key": "",
                        "type": ""
                    }
                }]
            }]*/
            widgets: [{}]
        };
    }

    public getWidget(){
        return [
            {
                name: 'Device Count',
                key: 'device_count',
                description: 'This widget shows the total device count of all devices - Instant Access Points, Switches, Gateways - managed through Central',
                type: 'DonutChart',
                typeStr: 'Donut Chart'
            }, {
                name: 'Client Count Summary',
                key: 'total_client_count',
                description: 'This widget shows the total count of all devices - Wired, Wireless connecting to the network',
                type: 'PieChart',
                typeStr: 'Pie Chart'
            }, {
                name: 'Total Connections',
                key: 'connection_count',
                description: 'This widget shows the total count of all connections on the network',
                type: 'PieChart',
                typeStr: 'Pie Chart'
            }, {
                name: 'Bandwidth Usage',
                key: 'bandwidth_usage',
                description: 'This widget captures the Bandwidth usage on the network - Wired and Wireless',
                type: 'AreaChart',
                typeStr: 'Area Chart'
            }, {
                name: 'Client Count Filterable Summary',
                key: 'client_count_filter_summary',
                description: 'This widget details the clients on the network by Band, Device Type, Label, Network etc.',
                type: 'LineChart',
                typeStr: 'Line Chart'
            }, {
                name: 'Security Info',
                key: 'security_info',
                description: 'This widget offers a summarized representation of the security information on the wireless network',
                type: 'Grid',
                typeStr: 'Grid'
            }, {
                name: 'Event Count',
                key: 'events',
                description: 'This widget offers a tabular listing of the various events ocuring on the network',
                type: 'Grid',
                typeStr: 'Grid'
            }, {
                name: 'Firmware Version',
                key: 'firmware_version',
                description: 'This widget offers details on the firmware compliance version for all the devices on the network',
                type: 'Grid',
                typeStr: 'Grid'
            }, {
                name: 'Guest Portal Analytics',
                key: 'guest-portal-analytics',
                description: 'This widget provides a aggregated view of Guest Portal Visitors',
                type: 'Grid',
                typeStr: 'Grid'
            }, /*{
                name: 'Presence Analytics',
                key: 'presence-analytics',
                description: 'This widget offers details and anayltics into the Client presence around the network',
                type: 'BubbleChart',
                typeStr: 'Bubble Chart'
            },*/ {
                name: 'Client Onboarding Analytics (Clarity)',
                key: 'onboarding-analytics',
                description: 'This widget summarizes client onboarding statistics',
                type: 'Grid',
                typeStr: 'Grid'
            }
        ];
    }
}