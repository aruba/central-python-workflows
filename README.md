# central-python-workflows
This repository contains Python-based workflows, code samples, and where applicable, Postman collections to help automate and integrate with New Central and HPE GreenLake Platform (GLP) APIs.
It leverages the [pycentral SDK](https://pypi.org/project/pycentral/) to interact with Central’s APIs and extensibility features.

Each folder represents a self-contained workflow. Inside each, you’ll find:
- A dedicated README.md explaining the purpose and usage of the workflow
- All required scripts, data files (like CSVs), and Postman collections (if applicable)
- Clear setup and execution instructions

> [!NOTE]
> If you’re looking for Classic Central workflows, please click [here](/Classic-Central/)


## New Central Workflows
> [!CAUTION]
> The workflows in this section use pre-release versions of the **pycentral** library and are intended primarily for New Central, currently in Public Preview.
> Please note:
> - APIs and SDK behavior may change as the new Central platform evolves with each release.
> - Some workflows may break or require updates with future SDK changes.\
> 
>We will make every effort to keep these workflows up to date. If you encounter any issues or inconsistencies, please open an issue in this repository.

### [Onboarding](/central-device-onboarding/)
This script automates onboarding of devices in HPE Aruba Networking Central to make them ready for configuration via **New Central**. It simplifies and sequences key onboarding steps needed after a device is assigned & subscribed to the Central application.
- Assign Device to Site
  - Site Creation(Optional)
- Set Device Persona
- Assign Device to Device Group
  - Device Group Creation (Optional)
- Set Device Name (Optional)

### [Tunnelled SSID Workflow](/tunneled-ssid-overlays/)
This workflow can:
- Creates config profiles such as roles and policies in New Central
- Creates SSID configurations with associated roles
- Modify policy group and create overlay WLAN profiles
- Assigns these configurations to the appropriate scopes (global or group)
- Associates devices with sites based on the inventory configuration

### [Configuration Hierarchy Report](/configuration-hierarchy/)
This script simplifies the visualization of the configuration hierarchy in New Central via APIs. It retrieves and displays hierarchical data such as:
 - Global
 - Site collections
 - Sites
 - Devices 
You’ll get this data in a terminal-friendly summary as well as in a CSV file, with key attributes like scope-id and persona which are required for configuration and monitoring APIs.

### [Rename Hostnames](/rename-hostnames/)
This script can help you rename the hostname of devices. You can provide a CSV file containing device serial numbers and their corresponding new hostnames. The script reads this file and updates each device's hostname in Central accordingly, automating the renaming process at scale.

## HPE Greenlake Platform Workflows

### [Onboarding](/glp-device-onboarding/)
This workflow can automate the following onboarding steps:
- Assign Devices to Application
- Apply Subscription to Devices
Along with the Python script, there is also a [Postman collection](/glp-device-onboarding/Postman-Collection/) for the same workflow which is available in the folder.

## Classic Central Workflows
- [Device Provisioning](/Classic-Central/device_provisioning/)
- [Device Onboarding](/Classic-Central/device_onboarding/)
- [MSP Customer Onboarding](/Classic-Central/msp_customer_onboarding/)
- [MSP Customer Deletion](/Classic-Central/msp_customer_deletion/)
- [Inventory to Excel Workflows](/Classic-Central/inventory_to_excel/)
- [AP CLI Workflows](/Classic-Central/ap_config/)
- [WLAN Workflows](/Classic-Central/wlan_config/)
- [Detailed Central Device Inventory](/Classic-Central/detailed_central_device_inventory/)
- [Device Inventory Migration](/Classic-Central/device_inventory_migration/)
- [User Provisioning](/Classic-Central/user_provisioning/)
- [Bulk Renaming of APs (with CSV)](/Classic-Central/renaming_aps/)
- [Connected Clients](/Classic-Central/connected_clients/)
- [Classic Central Postman Collection](https://www.postman.com/hpe-aruba-networking/workspace/hpe-aruba-networking-central/overview)
- [Streaming API Websocket Client Application](/Classic-Central/streaming-api-client/)
- [Webhook Client application](/Classic-Central/webhooks/)