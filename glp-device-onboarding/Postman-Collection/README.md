# Device Onboarding Workflow Guide

This workflow is designed to onboard devices to the HPE GreenLake Cloud Platform (GLP) and HPE Aruba Networking Central using GLP API calls. It supports the following steps:
- Adding devices
- Assigning devices to a Central application
- Applying subscriptions to devices

## Prerequisites

This workflow requires that a user has access to the HPE GreenLake Cloud Platform. The first step in executing this workflow is to fill out the Variables section of the Device Onboarding collection. The list of variables is used throughout the workflow to make a series of sequential API requests. Pay attention when filling out these variables. If they are incorrect or not in the proper format, errors may occur.

### Import the Postman Collection

1. Download the [provided Postman Collection](Device-Onboarding.json).
2. Open Postman, click on the "Import" button, and select the collection file.
3. Once imported, you will see all the available API endpoints in the collection.

### Update Variables in the Collection

1. Go to the **Variables** tab in the imported collection.
2. Update the following variables before making any API calls in this collection:

| **Name** | **Description** | **Example** |
| --- | --- | --- |
| glp_client_id | HPE GreenLake Cloud Platform credential client ID | 34a47b6e-1789-435d-bk0f-3bd547art5f8 |
| glp_client_secret | HPE GreenLake Cloud Platform credential client secret | 45ad273a695f12ek83a4360765e04a2e |
| glp_token | HPE GreenLake Cloud Platform token obtained by following the guide below | JWT Bearer Token |
| device_mac | Device MAC Address | xx:xx:xx:xx:xx:xx |
| device_sn | Device Serial Number | SGxxxxxxx |
| central_application_id | Application ID | 373a74a1-xxxx-xxxx-xxxx-xxxxxxxxx |
| central_application_region | Region of Application Deployment | us-west |
| glp_device_id | Device ID | 22206f15-xxxx-xxxx-xxxx-xxxxxxxxx |
| glp_subscription_id | Subscription ID | 73428f10-xxxx-xxxx-xxxx-xxxxxxxxx |

## API Workflow

### Authentication

To obtain API client credentials for GLP, follow [this guide](https://developer.arubanetworks.com/hpe-aruba-networking-central/docs/generating-a-hpe-greenlake-cloud-platform-token) on the HPE Aruba Networking Developer Hub. Fill out the `glp_client_id` and `glp_client_secret` variables, then run **Generate Access Token** to generate a token. If the API call is successful, the generated GLP access token will automatically be saved as the Postman variable `glp_token`. The GLP access token is valid for 15 minutes.

> [!NOTE]
> For each step in the onboarding workflow, all required API calls are organized in folders within the Postman collection. This structure is intended to help guide you through each step of the process.

### 1. Add Devices

The first step of onboarding is to add devices to the GLP workspace. For this step, you need the device's unique Serial Number and MAC Address. The device Serial Number and MAC Address are listed physically on the device itself. Each device type has a slightly different location for this information:

- Access Points: Bottom of the device
- AOS-CX Switch: A tab you can pull out and view
- Gateways: Back of the device

On the CLI of the device, you can also run an equivalent 'show system' command, which differs depending on whether you're on AOS-CX, AOS8, or AOS10.

- AOS-CX Switch CLI: `show system`
- AOS10 CLI: `show inventory`

Once you have identified the device's serial number and MAC address, save these as the `device_sn` and `device_mac` Postman collection variables, respectively. You can then run the **Add Device(s)** API call. 
This is an asynchronous operation. If the add device API call has been accepted, you will receive a 202 API response code. You need to verify the device was added by logging into the GLP workspace. You can now continue with the rest of the onboarding process.

### 2. Assign Devices to Application

After devices have been added to a GLP workspace, they need to be assigned to a Central application. Ensure that the following collection variables are populated:

1. `central_application_id` - The central application ID can be determined by making a **Get Service Manager(s)** API call. The "id" variable in the same array element as the Central application whose name matches the "name" key is the central application ID.
2. `central_application_region` - The central application region that corresponds to the region's deployment can be found in the following [list here](https://developer.greenlake.hpe.com/docs/greenlake/services/service-catalog/public/glossary/#region).
3. `glp_device_id` - This can be found with the **Get Device** API call. For each device, the device's GLP ID will be returned with the 'id' attribute. You need to save the "id" attribute for the device you would like to assign to the application.

The **Assign Device(s) to Application** API call is an asynchronous operation. If the API call has been accepted, you will receive a 202 response with a transaction_id. The transaction ID will automatically be saved to the `device_app_transaction_id` Postman variable.

You can then run the **Get Device Assignment Status** API call to verify that the device assignment operation was successful. The API response will include `status` and `results` attributes, which will indicate if the device assignment to the application was successful or failed.

### 3. Apply Subscription to Devices

The next onboarding step is applying subscriptions to devices. There are two variables needed for this step:

1. `glp_device_id` - This can be found with the **Get Device(s)** API call. For each device, the device's GLP ID will be returned with the 'id' attribute. You need to save the "id" attribute for the device you would like to apply the subscription to.
2. `glp_subscription_id` - This can be found with the **Get Subscription(s)** API call. For each subscription, the subscription's GLP ID will be returned with the 'id' attribute. You need to save the "id" attribute for the subscription you would like to apply to the device.

The **Apply Subscription to Device(s)** API call is an asynchronous operation. If the API call has been accepted, you will receive a 202 response with a transaction_id. The transaction ID will automatically be saved to the `device_sub_transaction_id` Postman variable.

You can then run the **Get Subscription Assignment Status** API call to verify that the subscription assignment operation was successful. The API response will include `status` and `results` attributes, which will indicate if the subscription assignment to the device was successful or failed.

## Conclusion

By following this workflow and utilizing the organized API call folders in the Postman collection, you can efficiently onboard devices to HPE GreenLake Cloud Platform and HPE Aruba Networking Central. Ensure all required variables are set correctly and refer to the documentation links for additional guidance. If you encounter any issues, please contact the [Automation team](mailto:aruba-automation@hpe.com).