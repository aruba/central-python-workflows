# central-examples-only

This repository contains code samples for Aruba Central. 
- [Custom Dashboard](customized-dashboard/)

- [REST API Python Libraries and Scripts](rest-api-python-scripts/)

- [Streaming API Websocket Client Application](streaming-api-client/)

- [Webhook Client application](webhooks/)

## Aruba Central Custom Dashboard

This folder contains a sample code for building your own Aruba Central Dashboard using the API Gateways
[Aruba Central Custom Dashboard](customized-dashboard/)


### Instructions for using the "customized-dashboard" folder

1. Clone the repo
2. `cd customized-dashboard/`
3. `npm install`
4. `ng serve`. This should have your web-app up and running
5. Edit the file `vi src/config/service.config.ts` and provide a valid App URL and access token. Save this file.
6. Open 'localhost:4200' in your browser to see the home page

## Aruba Central REST API Python Sample Scripts

[rest-api-python-scripts/](rest-api-python-scripts/)

This folder contains sample python libraries and scripts to make API Requests to Aruba Central. REST APIs are based on request-response model.
Refer to the Aruba Central's API Swagger documentation page (under `ACCOUNT HOME -> GLOBAL SETTINGS -> API GATEWAY -> APIs`) for the list of available APIs.

## Aruba Central Streaming API

[streaming-api-client/](streaming-api-client/)

This folder contains sample websocket client application based on python programming language. 
The sample python script would establish a websocket connection and decode the google protobuf message to human readable format.

## Aruba Central Webhooks

[webhooks/](webhooks/)

This folder contains sample scripts and documentation for Aruba Central Webhooks and Alerts. The sample script in this section would start a HTTP(s) client to receive Alerts from Aruba Central via webhooks. To manage Webhooks in Aruba Central, go to `ACCOUNT HOME -> GLOBAL SETTINGS -> WEBHOOKS`.

For more information about Aruba Central, [refer here](https://help.central.arubanetworks.com/latest/documentation/online_help/content/home.htm)
