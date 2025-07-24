# Configuration Hierarchy Report

This script simplifies the reporting of the configuration hierarchy from HPE Aruba Networking Central using new Central APIs. It retrieves hierarchical data—including sites, site collections, devices, & device groups and presents it in both a terminal summary table and a CSV file.

By visualizing the configuration hierarchy, network administrators can quickly understand the structure of their Central environment, and locate key attributes such as `scope-id` and `persona`. These attributes are essential for making configuration changes via the New Central APIs.

> [!CAUTION]
> This script uses a beta version of the `pycentral` library and is designed for HPE Aruba New Central, which is also in Public Preview. Expect potential changes and updates to the API and functionality.

## Prerequisites

- Python 3.8 or higher
- API credentials for HPE Aruba Networking Central (JSON or YAML format)
- There should be atleast 1 site created in the account to get new Central configuration attributes

## Setup

1. **Create a virtual environment (recommended):**
    ```sh
    python -m venv env
    source env/bin/activate  # On Windows: env\Scripts\activate
    ```

2. **Install required packages:**
    ```sh
    pip install -r requirements.txt
    ```

## Input Files

**Credentials File**: Contains Central API credentials in JSON or YAML format.
Example (YAML):
```yaml
central:
    # Either `base_url` or `cluster_name` should be provided:
    # 
    # base_url: <central-api-base-url>
    # cluster_name: <central-cluster-name>
    client_id: <central-client-id>
    client_secret: <central-client-secret>
```
> [!TIP]
> To obtain your API credentials, please refer to: [Generating and Managing Access Tokens](https://developer.arubanetworks.com/new-central/docs/generating-and-managing-access-tokens) and to locate the `cluster_name`(E.g. **EU-1**) or `base_url`(E.g. **de1.api.central.arubanetworks.com**) of your New Central cluster refer to [API Gateway Base URLs on our Developer Hub](https://developer.arubanetworks.com/new-central/docs/getting-started-with-rest-apis#api-gateway-base-urls).

## Usage

Run the script with the required arguments:

```sh
python hierarchy_report.py -c account_credentials.yaml
```

**Optional arguments:**
- `-o`, `--output-file-name`: Specify the output CSV file name (default: `hierarchy_report.csv`).

Example:
```sh
python hierarchy_report.py -c account_credentials.yaml -o my_hierarchy.csv
```

## Output
The script generates configuration hierarchy information in two formats:

- **Terminal Table**: Displays the hierarchy in a formatted table for immediate viewing
- **CSV File**: Saves the complete report to the specified CSV file (default: `hierarchy_report.csv`)

### Understanding the Output Table

Each row in the output(terminal table or csv file) represents a scope component in your Central configuration hierarchy. The table contains the following columns:

- **Type**: The hierarchical level - Global (top-level), Site Collection, Site, Device, or Device Group
- **Name**: The display name of the scope element as it appears in Central
- **Scope-ID**: The ID of the scope element. This is the unique identifier needed to identify the scope element for any new Central APIs.
- **Serial**: Device serial number (only for Devices)
- **Device Function (Persona)**: Role of the device along with it's configuration persona in parentheses, which is needed for new Central APIs (only for Devices)

**Sample Output**: ![Sample Output](configuration_hierarchy.gif)

## Troubleshooting

- Ensure your credentials file is valid and in JSON or YAML format.
- Make sure all required dependencies are installed.
- If you encounter issues, please reach out to [Aruba Automation](mailto:aruba-automation@hpe.com)
