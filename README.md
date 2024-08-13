# central-python-workflows

This repository contains Python based workflows & code samples that utilize [Aruba Central's automation capabilities](https://developer.arubanetworks.com/aruba-central/docs/aruba-central-extensibility) and the Python SDK [pycentral](https://pypi.org/project/pycentral/)

## Aruba Central REST APIs
- [Device Provisioning](https://github.com/aruba/central-python-workflows/tree/main/device_provisioning) 
  - Create a group (Template-based group)
  - Upload Configuration Template to Group
  - Move Devices to the newly created Group.
  - Create a Site
  - Move Devices to the newly created Site.
- [Device Onboarding](https://github.com/aruba/central-python-workflows/tree/main/device_onboarding)
  - Assign Devices to Central Application Instance
  - Provide Devices with Central Subscriptions.
  - Create a template group (Template-based group)
  - Upload Configuration Template to Group
  - Move Devices to the newly created Group.
  - Create a Site
  - Move Devices to the newly created Site.
- [MSP Customer Onboarding](https://github.com/aruba/central-python-workflows/tree/main/msp_customer_onboarding)
  - Create a customer account within the Greenlake MSP account
  - Install an Aruba Central instance in the customer account & set the default group.
  - Move & assign subscriptions to devices in the customer's Central Instance
  - Optional Steps
    - Create a Site in the customer's Central instance
    - Move Devices to the newly created Site.
- [MSP Customer Deletion](https://github.com/aruba/central-python-workflows/tree/main/msp_customer_deletion)
  - Unassigns all devices & licenses within the customer's Aruba Central Instance. The devices & licenses will be moved back to the MSP's inventory.
  - Uninstall the customer's Aruba Central instance
  - Delete the customer's Greenlake Instance
- [Inventory to Excel Workflows](https://github.com/aruba/central-python-workflows/tree/main/inventory_to_excel)\
  This workflow creates excel files populated with device details from devices currently in inventory.
- [AP CLI Workflows](https://github.com/aruba/central-python-workflows/tree/main/ap_config)\
  Access point(AP) config workflows use direct command line interface(CLI) commands to configure APs in an Aruba Central group or directly to an AOS10 AP.
- [WLAN Workflows](https://github.com/aruba/central-python-workflows/tree/main/wlan_config)\
  This workflow can be used to create and manage WLANs in groups on an Aruba Central.
- [Detailed Central Device Inventory](https://github.com/aruba/central-python-workflows/tree/main/detailed_central_device_inventory/)\
  This workflow can be used to fetch additional details for device inventory in Aruba Central & export it as a CSV.
- [Device Inventory Migration](https://github.com/aruba/central-python-workflows/tree/main/device_inventory_migration/)
  This workflow automates the migration of multiple devices between two Aruba Central accounts.
- [User Provisioning](https://github.com/aruba/central-python-workflows/tree/main/user_provisioning)\
  This workflow can be used to provision new users to HPE Greenlake and Aruba Central.
- [Bulk Renaming of APs (with CSV)](https://github.com/aruba/central-python-workflows/tree/main/renaming_aps)\
  This workflow can be used to rename access points in Aruba Central with a custom CSV upload of serial numbers and names.
- [Connected Clients](https://github.com/aruba/central-python-workflows/tree/main/connected_clients)
  - Gather connected client information based on site name and time frame
  - Output csv files are generated and created within workflow folder
- [Aruba Central Postman Collection](https://www.postman.com/hpe-aruba-networking/workspace/hpe-aruba-networking-central/overview)\
  Postman is a popular tool used to test HTTP Requests to API endpoints. Aruba Central offers a [Postman collection](https://www.postman.com/hpe-aruba-networking/workspace/hpe-aruba-networking-central/collection/32717089-b3b1c3e4-7d04-4af1-be8c-e5c51e2453bb) and [Postman environment](https://www.postman.com/hpe-aruba-networking/workspace/hpe-aruba-networking-central/environment/30369652-60b80c56-ad11-40d3-a4a6-5cde71abf2e4?action=share&creator=32717089&active-environment=30369652-60b80c56-ad11-40d3-a4a6-5cde71abf2e4) that you can use to test REST APIs with Aruba Central.

To manage REST APIs in Aruba Central, go to `MAINTAIN -> ORGANIZATION -> PLATFORM INTEGRATION -> REST API`.\
Learn more about Aruba Central REST APIs [here](https://developer.arubanetworks.com/aruba-central/docs/api-getting-started).

## Aruba Central Streaming API
- [Streaming API Websocket Client Application](https://github.com/aruba/central-python-workflows/tree/main/streaming-api-client)
The sample script in this section contains sample websocket client application based on python. 
The sample python script would establish a websocket connection and decode the google protobuf message to human readable format.

To manage Streaming APIs in Aruba Central, go to `MAINTAIN -> ORGANIZATION -> PLATFORM INTEGRATION -> STREAMING`.\
Learn more about Aruba Central Streaming APIs [here](https://developer.arubanetworks.com/aruba-central/docs/streaming-api-getting-started).

## Aruba Central Webhooks

- [Webhook Client application](https://github.com/aruba/central-python-workflows/tree/main/webhooks)
The sample script in this section would start a HTTP(s) client to receive Alerts from Aruba Central via webhooks. 

To manage Webhooks in Aruba Central, go to `MAINTAIN -> ORGANIZATION -> PLATFORM INTEGRATION -> WEBHOOKS`.\
Learn more about Aruba Central Webhooks [here](https://developer.arubanetworks.com/aruba-central/docs/webhooks-getting-started).

For more information about Aruba Central, [refer here](https://www.arubanetworks.com/techdocs/central/latest/content/home.htm)
