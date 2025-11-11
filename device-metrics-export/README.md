# Device Metrics Export

This workflow retrieves comprehensive device information from both HPE Aruba Networking Central and GreenLake Platform (GLP) APIs. It consolidates device attributes, monitoring data, connectivity status, and subscription details into a single CSV file for easy analysis and reporting.

## Prerequisites

- Python 3.8 or higher
- API credentials for HPE Aruba Networking Central & GLP (JSON or YAML format)

## Installation

1. Clone the repository and navigate to this workflow folder
```bash
git clone -b "v2(pre-release)" https://github.com/aruba/central-python-workflows.git
cd central-python-workflows/device-metrics-export
```

2) Create and activate a virtual environment, then install dependencies
- On macOS/Linux: source venv/bin/activate
- On Windows (PowerShell): venv\Scripts\Activate.ps1

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

This workflow is tested on the `pycentral` SDK (version: `v2.0a10`). Please check compatibility before executing on older/newer versions as there may be changes.

## Configuration

#### New HPE Aruba Networking Central & GLP Credentials (account_credentials.yaml)

For API operations in new HPE Aruba Networking Central & GLP:

```yaml
new_central:
    cluster_name: <cluster-name>  # or base_url: <central-api-base-url>
    client_id: <new-central-client-id>
    client_secret: <new-central-client-secret>
glp:
    client_id: <glp-client-id>
    client_secret: <glp-client-secret>
```
**Sample Input:** See [`account_credentials.yaml`](./account_credentials.yaml) in this repository for an example credential file.

> [!TIP]
> **Where to find these:**
> - [New Central API Gateway Base URLs](https://developer.arubanetworks.com/new-hpe-anw-central/docs/getting-started-with-rest-apis#api-gateway-base-urls) 
> - [How to get API Credentials for new Central](https://developer.arubanetworks.com/new-hpe-anw-central/docs/generating-and-managing-access-tokens)
> - [How to get API Credentials for GLP](https://developer.greenlake.hpe.com/docs/greenlake/guides/public/authentication/authentication#creating-a-personal-api-client)

## Execution

This workflow is executed by the script device_metrics_export.py and covers the following:
- Loads and validates the credentials file (JSON/YAML) & establishes a connection to Central & GLP
- Runs API calls - 
    - New Central - [Get a list of devices](https://developer.arubanetworks.com/new-central/reference/getdevices)
    - New Central - [Get a device inventory list](https://developer.arubanetworks.com/new-central/reference/getdeviceinventory)
    - GLP - [Get Devices managed in a workspace](https://developer.greenlake.hpe.com/docs/greenlake/services/device-management/public/openapi/nbapi-inventory-latest/openapi/devices-v1/getdevicesv1)
    - GLP - [Get subscriptions of a workspace](https://developer.greenlake.hpe.com/docs/greenlake/services/subscription-management/public/openapi/nbapi-subscription/subscriptions-v1/getsubscriptionsv1)
- Processes results from the above mentioned APIs and outputs the result in a CSV format for usage.

Example usage:

```bash
python device_metrics_export.py -c <credentials_file> --output <output_file>
```


### Command Line Options

The script accepts the following command line argument

| Name        | Type   | Description           | Required |
|-------------|--------|----------------------|----------|
| credentials_file | string | Path to file with New Central & GLP credentials (JSON or YAML). Must end in .json, .yaml, or .yml. | Yes      |
| output         | string | Path to output CSV file. Defaults to device_data.csv. | No       |

## Output 

A CSV file (default: device_data.csv) containing merged device details from Central and GLP. You can find a sample output file [here](device_data.csv)

CSV column titles (ordered):
- Serial Number
- Mac Address
- Device Name
- Device Type
- Device Model
- Deployment
- IPv4
- Firmware Version
- Site
- Device Group Name
- Status
- Uptime
- Last Seen At
- Config Status
- Config Last Modified At
- Subscription Key
- Subscription End Time

If no data is returned from the APIs or post-processing yields an empty list, the script prints "No data to save." 

## Troubleshooting

- Authentication / tokens: Ensure your credentials file is complete and has valid credentials for GLP & New Central.
- Empty output: Confirm that devices exist in Central inventory and that GLP subscriptions/devices exist for the account.
- SDK compatibility: If API calls fail unexpectedly, confirm the installed pycentral version matches tested versions (v2.0a10) or update helpers accordingly.

## Support

- **Automation Team**: [aruba-automation@hpe.com](mailto:aruba-automation@hpe.com)
- **Workflow Issues**: [GitHub Issues](https://github.com/aruba/central-python-workflows/issues)
- **PyCentral Library**: [PyCentral Issues](https://github.com/aruba/pycentral/issues)
