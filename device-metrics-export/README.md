# Device Metrics Export

This workflow retrieves comprehensive device information from both HPE Aruba Networking Central and GreenLake Platform (GLP) APIs. It consolidates device attributes, monitoring data, connectivity status, subscription details, and optional AP floorplan location data into CSV and JSON files for analysis, automation, and reporting.

## Prerequisites

- Python 3.8 or higher
- API credentials for HPE Aruba Networking Central and GLP (JSON or YAML format)

## Installation

1. Clone the repository and navigate to this workflow folder
```bash
git clone -b v2 https://github.com/aruba/central-python-workflows.git
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

This workflow is tested on the `pycentral` SDK (version: `v2.0a22`). Please check compatibility before executing on older/newer versions as there may be changes.

## Configuration

#### Credentials (account_credentials.yaml)

This workflow requires API credentials generated for GLP platform as the script makes API calls to GLP & Central. 

```yaml
unified:
  cluster_name: <cluster-name> # e.g. EU-1, or use base_url: <central-api-base-url>
  workspace_id: <glp-workspace-id>
  client_id: <glp-client-id>
  client_secret: <glp-client-secret>
```

**Sample Input:** See [`account_credentials.yaml`](./account_credentials.yaml) in this repository for an example credential file.

> [!TIP]
> **Where to find these:**
> - [Finding your Central API Gateway Base URL](https://developer.arubanetworks.com/new-central/docs/getting-started-with-rest-apis#finding-your-base-url) 
> - [Generating & Managing Access Token](https://developer.arubanetworks.com/new-central/docs/generating-and-managing-access-tokens)

## Execution

This workflow is executed by the script device_metrics_export.py and covers the following:
- Loads and validates the credentials file (JSON/YAML) & establishes a connection to Central & GLP
- Runs API calls - 
  - GLP
    - [Get Devices managed in a workspace](https://developer.greenlake.hpe.com/docs/greenlake/services/device-management/public/openapi/nbapi-inventory-latest/openapi/devices-v1/getdevicesv1)
    - [Get subscriptions of a workspace](https://developer.greenlake.hpe.com/docs/greenlake/services/subscription-management/public/openapi/nbapi-subscription/subscriptions-v1/getsubscriptionsv1)
  - New Central 
    - [Get a list of devices](https://developer.arubanetworks.com/new-central/reference/getdevices)
    - [Get a device inventory list](https://developer.arubanetworks.com/new-central/reference/getdeviceinventory)
    - Optionally, [List devices with location information](https://developer.arubanetworks.com/new-central/reference/getdevicelocationsv1)
Processes results from the above mentioned APIs and outputs the result in CSV and structured JSON formats.

Example usage:

```bash
python device_metrics_export.py -c <credentials_file> --output <output_file.csv> [--output-json <output_file.json>] [--include-floorplan] [--include-raw-location]
```


### Command Line Options

The script accepts the following command line arguments

| Name             | Type   | Description                                                                 | Required |
|------------------|--------|-----------------------------------------------------------------------------|----------|
| credentials_file | string | Path to credentials (JSON or YAML). Must end in .json, .yaml, or .yml. | Yes      |
| output           | string | Path to output CSV file. Defaults to device_data.csv.                      | No       |
| --output-json    | string | Optional path to write structured JSON output (single array). Defaults to same name as CSV with .json extension. | No |
| --include-floorplan | flag | If set, fetch per-site device locations from the Central and include location fields in output. | No |
| --include-raw-location | flag | If set, include the Raw Location column in the CSV and JSON output, and also fetch per-site device locations (implies `--include-floorplan`). | No |

## Output 

This workflow emits both a CSV (traditional tabular output) and a structured JSON file (single JSON array of device objects).

- CSV (default: device_data.csv): tabular rows where missing values are empty strings. The CSV includes a Raw Location column which contains a JSON string (serialized) when location details are present.
- JSON (default: device_data.json alongside CSV unless overridden): a single JSON array of device objects. Fields with no data are serialized as null in JSON. Location data (Raw Location) is kept as a nested object when available.

CSV / JSON fields (ordered for CSV; JSON objects contain the same keys):

| Field | Description |
|-------|-------------|
| Serial Number | Device serial number from Central inventory. |
| Mac Address | Device MAC address. |
| Device Name | Device name configured in Central. |
| Device Type | Device category, such as access point, switch, or gateway. |
| Device Model | Device hardware model. |
| Deployment | Deployment mode reported by Central inventory. |
| IPv4 | Device IPv4 address. |
| Firmware Version | Software or firmware version reported for the device. |
| Site | Central site name associated with the device. |
| Device Group | Central compatible device group name. |
| Status | Device status from Central inventory. |
| Uptime | Device uptime converted to a human-readable duration. |
| Last Seen At | Last time the device was seen, converted to UTC. |
| Config Status | Device configuration status from monitoring data. |
| Config Last Modified At | Last configuration update time, converted to UTC. |
| Subscription Key | GLP subscription key assigned to the device. |
| Subscription Tier | GLP subscription tier. |
| Subscription Type | Derived subscription type, such as Foundation or Advanced. |
| Subscription End Time | GLP subscription end time, converted to UTC. |
| Floorplan ID | Floorplan identifier from Central device-location data. |
| Building ID | Building identifier from Central device-location data. |
| X Coordinate | Device's X coordinate on the floorplan. |
| Y Coordinate | Device's Y coordinate on the floorplan. |
| Floor Coordinate Unit | Unit used for floorplan's X/Y coordinates. |
| Latitude | Device's latitude from location data. |
| Longitude | Device's longitude from location data. |
| Raw Location | Full normalized location payload. In CSV this is serialized as a JSON string; in JSON this remains a nested object. |

> [!TIP]
> The Device Group field will only be populated for groups that are Central compatible device groups. Classic Central groups will not appear in this export.

> Location fields from Floorplan ID through Longitude are only added to the CSV/JSON when `--include-floorplan` (or `--include-raw-location`) is provided. The Raw Location column is additionally gated behind `--include-raw-location`; passing this flag also implies `--include-floorplan`. When neither flag is provided, location columns are omitted entirely from outputs.


If no data is returned from the APIs or post-processing yields an empty list, the script prints "No data to save." 

## Troubleshooting

- Authentication / tokens: Ensure your credentials file contains a top-level `unified` section with `workspace_id`, `client_id`, `client_secret`, and `cluster_name` or `base_url`.
- Empty output: Confirm that devices exist in Central inventory and that GLP subscriptions/devices exist for the account.
-- Missing location fields: Confirm APs have `siteId` values and floorplan/device-location data exists for the site. If you want location columns in the output, run with `--include-floorplan` (or `--include-raw-location`).
- SDK compatibility: If API calls fail unexpectedly, confirm the installed pycentral version matches tested versions (v2.0a22) or update helpers accordingly.

## Support

- **Automation Team**: [aruba-automation@hpe.com](mailto:aruba-automation@hpe.com)
- **Workflow Issues**: [GitHub Issues](https://github.com/aruba/central-python-workflows/issues)
- **PyCentral Library**: [PyCentral Issues](https://github.com/aruba/pycentral/issues)
