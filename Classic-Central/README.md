# Classic Central Workflows

This repository contains Python based workflows & code samples that utilize [Classic Central's automation capabilities](https://developer.arubanetworks.com/central/docs/aruba-central-extensibility) and the Python SDK [pycentral](https://pypi.org/project/pycentral/)

## Classic Central REST APIs
- [Device Provisioning](/Classic-Central/device_provisioning/)
  - Create a group (Template-based group)
  - Upload Configuration Template to Group
  - Move Devices to the newly created Group.
  - Create a Site
  - Move Devices to the newly created Site.
- [Device Onboarding](/Classic-Central/device_onboarding)
  - Assign Devices to Central Application Instance
  - Provide Devices with Central Subscriptions.
  - Create a template group (Template-based group)
  - Upload Configuration Template to Group
  - Move Devices to the newly created Group.
  - Create a Site
  - Move Devices to the newly created Site.
- [MSP Customer Onboarding](/Classic-Central/msp_customer_onboarding)
  - Create a customer account within the Greenlake MSP account
  - Install an Classic Central instance in the customer account & set the default group.
  - Move & assign subscriptions to devices in the customer's Central Instance
  - Optional Steps
    - Create a Site in the customer's Central instance
    - Move Devices to the newly created Site.
- [MSP Customer Deletion](/Classic-Central/msp_customer_deletion)
  - Unassigns all devices & licenses within the customer's Classic Central Instance. The devices & licenses will be moved back to the MSP's inventory.
  - Uninstall the customer's Classic Central instance
  - Delete the customer's Greenlake Instance
- [Inventory to Excel Workflows](/Classic-Central/inventory_to_excel)\
  This workflow creates excel files populated with device details from devices currently in inventory.
- [AP CLI Workflows](/Classic-Central/ap_config)\
  Access point(AP) config workflows use direct command line interface(CLI) commands to configure APs in an Classic Central group or directly to an AOS10 AP.
- [WLAN Workflows](/Classic-Central/wlan_config)\
  This workflow can be used to create and manage WLANs in groups on an Classic Central.
- [Detailed Central Device Inventory](/Classic-Central/detailed_central_device_inventory/)\
  This workflow can be used to fetch additional details for device inventory in Classic Central & export it as a CSV.
- [Device Inventory Migration](/Classic-Central/device_inventory_migration/)
  This workflow automates the migration of multiple devices between two Classic Central accounts.
- [User Provisioning](/Classic-Central/user_provisioning)\
  This workflow can be used to provision new users to HPE Greenlake and Classic Central.
- [Bulk Renaming of APs (with CSV)](/Classic-Central/renaming_aps)\
  This workflow can be used to rename access points in Classic Central with a custom CSV upload of serial numbers and names.
- [Connected Clients](/Classic-Central/connected_clients)
  - Gather connected client information based on site name and time frame
  - Output csv files are generated and created within workflow folder
- [Classic Central Postman Collection](https://www.postman.com/hpe-aruba-networking/workspace/hpe-aruba-networking-central/overview)\
  Postman is a popular tool used to test HTTP Requests to API endpoints. Classic Central offers a [Postman collection](https://www.postman.com/hpe-aruba-networking/workspace/hpe-aruba-networking-central/collection/32717089-b3b1c3e4-7d04-4af1-be8c-e5c51e2453bb) and [Postman environment](https://www.postman.com/hpe-aruba-networking/workspace/hpe-aruba-networking-central/environment/30369652-60b80c56-ad11-40d3-a4a6-5cde71abf2e4?action=share&creator=32717089&active-environment=30369652-60b80c56-ad11-40d3-a4a6-5cde71abf2e4) that you can use to test REST APIs with Classic Central.

To manage REST APIs in Classic Central, go to `MAINTAIN -> ORGANIZATION -> PLATFORM INTEGRATION -> REST API`.\
Learn more about Classic Central REST APIs [here](https://developer.arubanetworks.com/central/docs/api-getting-started).

## Classic Central Streaming API
- [Streaming API Websocket Client Application](/Classic-Central/streaming-api-client)
The sample script in this section contains sample websocket client application based on python. 
The sample python script would establish a websocket connection and decode the google protobuf message to human readable format.

To manage Streaming APIs in Classic Central, go to `MAINTAIN -> ORGANIZATION -> PLATFORM INTEGRATION -> STREAMING`.\
Learn more about Classic Central Streaming APIs [here](https://developer.arubanetworks.com/central/docs/streaming-api-getting-started).

## Classic Central Webhooks

- [Webhook Client application](/Classic-Central/webhooks)
The sample script in this section would start a HTTP(s) client to receive Alerts from Classic Central via webhooks. 

To manage Webhooks in Classic Central, go to `MAINTAIN -> ORGANIZATION -> PLATFORM INTEGRATION -> WEBHOOKS`.\
Learn more about Classic Central Webhooks [here](https://developer.arubanetworks.com/aruba-central/docs/webhooks-getting-started).

For more information about Classic Central, [refer here](https://www.arubanetworks.com/techdocs/central/latest/content/home.htm)
