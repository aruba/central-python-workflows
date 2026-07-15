# Configure Hostnames and Location Aliases

This workflow configures device hostnames and optional per-device location aliases in Central. Hostnames are configured with the local System Information profile. Locations are configured through Central local alias objects using the location alias name and each device's requested location value.

The workflow validates all inputs before execution, confirms the planned changes in the terminal, processes valid devices sequentially, and writes timestamped CSV and HTML reports that include every input device.

## Prerequisites

- Python 3.10 or higher
- API credentials for Central
- Target devices must be provisioned, have a persona assigned, and have a site assignment
- For location updates, the AP System Information profile must already be created, assigned, and configured to use the location alias name that will be passed with `--location-alias`

Offline devices are not blocked. The workflow notes offline status in the terminal preview and reports, then still attempts the requested configuration.

## Installation

1. Clone the repository and navigate to this workflow folder.

```bash
git clone -b v2 https://github.com/aruba/central-python-workflows.git
cd central-python-workflows/rename-hostnames
```

2. Create and activate a virtual environment, then install dependencies.

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

_This workflow is tested on the PyCentral SDK (version: 2.0a21). Check compatibility before executing on older or newer versions._

## Credentials Configuration

For API operations in new HPE Aruba Networking Central:

```yaml
new_central:
    cluster_name: <cluster-name>  # or base_url: <central-api-base-url>
    client_id: <central-client-id>
    client_secret: <central-client-secret>
```

**Sample Input:** See [`account_credentials.yaml`](./account_credentials.yaml) for an example credential file.

> [!TIP]
> **Where to find these:**
> - [Central API Gateway Base URLs](https://developer.arubanetworks.com/new-hpe-anw-central/docs/getting-started-with-rest-apis#api-gateway-base-urls)
> - [How to get API Credentials for Central](https://developer.arubanetworks.com/new-hpe-anw-central/docs/generating-and-managing-access-tokens)

## Workflow Input Data

### CSV mode

CSV mode is the default. The input CSV must contain these exact headers:

```csv
serial,new_hostname,location
{device1_serial},{device1_new_hostname},{device1_location}
{device2_serial},,{device2_location}
{device3_serial},{device3_new_hostname},
```

Rules:

- `serial`, `new_hostname`, and `location` headers are required.
- `new_hostname` and `location` values are optional per row.
- Each row must include at least one requested change: `new_hostname` or `location`.
- Duplicate serial numbers are rejected before execution.
- If any row includes `location`, provide `--location-alias`.

Run with the default sample CSV:

```bash
python rename_hostnames.py --location-alias <alias_name>
```

Run with a custom CSV:

```bash
python rename_hostnames.py -c <credentials_file> --devices-csv <input_file> --location-alias <alias_name>
```

For hostname-only CSV rows, `--location-alias` is not required:

```bash
python rename_hostnames.py --devices-csv <hostname_only_input_file>
```

### Interactive mode

Interactive mode collects devices one at a time from terminal prompts:

```bash
python rename_hostnames.py --interactive
```

At startup, the workflow asks whether the run will set locations. If yes, it asks for one run-level location alias name and then allows hostname and location to be optional per device, as long as at least one is provided. If no, each device requires a new hostname.

## Command Line Options

| Name | Type | Description | Required | Default |
|------|------|-------------|----------|---------|
| `credential_file` | string | Path to Central credentials YAML | No | `account_credentials.yaml` |
| `devices-csv` | string | CSV file with `serial,new_hostname,location` headers | No, unless replacing the default CSV | `variables_sample.csv` |
| `interactive` | flag | Collect target devices and requested changes from terminal prompts | No | Disabled |
| `location-alias` | string | Run-level Central location alias name used for all requested locations | Required when CSV input includes `location` | None |

## Validation and Confirmation

The workflow rejects input-shape errors before connecting changes to execution:

- Invalid CSV headers
- CSV rows with no requested hostname or location
- Duplicate serial numbers
- Missing serial numbers
- CSV location values without `--location-alias`

After connecting to Central, the workflow validates each device. Device-level validation failures do not block valid devices. The confirmation preview includes both valid and invalid devices with Central details:

- Serial
- Current name or hostname
- Persona
- Site
- Online or offline status
- Requested hostname
- Requested location
- Planned actions or skip reason

Valid devices proceed only after user confirmation. Invalid devices are skipped and included in reports.

## Execution Behavior

Devices are processed sequentially. For each valid device:

1. If `new_hostname` is provided, the workflow creates or updates the local `sys-system-info-profile` hostname.
2. If hostname succeeds or no hostname was requested, and `location` is provided, the workflow creates or updates the user-named local location alias.
3. If hostname fails, the workflow skips the location update for that device and records the reason.

Location updates assume the AP already receives location from a location alias in its assigned System Information profile. The `--location-alias` value is the name of that existing alias reference. For each device with a requested `location`, the workflow writes a device-scoped local override for that alias name, so the profile continues to reference the same alias while each device receives its own location value.

Location alias overrides use the Central alias API shape:

```text
/network-config/v1alpha1/aliases/{alias_name}?object-type=LOCAL&scope-id={device_id}&device-function={persona}
```

Payload:

```json
{
  "type": "ALIAS_LOCATION",
  "name": "<alias_name>",
  "default-value": {
    "location-value": {
      "location": "<location-value>"
    }
  }
}
```

Before each device location update, the workflow fetches the existing local alias. If the existing alias type is `ALIAS_LOCATION`, it updates the alias. If the alias exists with any other type, it fails the location step and does not overwrite the alias.

## Output

Results are saved in timestamped directories:

```text
results_YYYY-MM-DD_HH-MM-SS/
  rename_hostnames_results_YYYY-MM-DD_HH-MM-SS.csv
  rename_hostnames_results_YYYY-MM-DD_HH-MM-SS.html
```

Reports include every input device and these status fields:

- `validation_status`
- `hostname_status`
- `location_status`
- `overall_status`
- `message`

The workflow no longer writes the legacy `output.csv`.

## Accompanying Utility Script: Delete System Info Profiles

### Overview

The `delete_system_info.py` script is a utility for fixing devices stuck in a bugged state due to Central no longer supporting multiple local system-info profiles. Devices follow the same provisioning requirements as laid out previously for configuring hostnames.

**Background:** Devices can no longer have multiple local system-info profiles in Central. Any device with multiple system-info profiles will be unable to create or update these profiles until all extra profiles are removed, leaving zero or one profile. This script cleans up the bugged state by deleting all local system-info profiles for the target devices.

### When to Use

Use this utility when:

- A device fails to update its hostname with errors related to maximum or existing system-info profiles. Example error:

```json
{
    "httpStatusCode": 400,
    "message": "module aruba-system-info can only have single instance per scope",
    "debugId": "axxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "errorCode": "HPE_GL_ERROR_BAD_REQUEST"
}
```

- A device has multiple system-info profiles from legacy configurations.
- You need to reset a device's system-info profile state before re-configuring.

### Input

Create a CSV file with a `serial` column header containing target device serial numbers:

```csv
serial
CNXXXXXXXX
CNXXXXXXX1
```

By default, the script uses `delete_serials.csv`. Update this file or provide a custom CSV.

### Execution

```bash
python delete_system_info.py
```

With arguments:

```bash
python delete_system_info.py -c <credentials_file> --serials_csv <input_file>
```

Or provide serial numbers directly:

```bash
python delete_system_info.py --serials CNXXXXXXXX,CNXXXXXXX1,CNXXXXXXX2
```

### Command Line Options

| Name | Type | Description | Required | Default |
|------|------|-------------|----------|---------|
| `credential_file` | string | Path to file with Central credentials | No | `account_credentials.yaml` |
| `serials_csv` | string | Path to CSV file with serial numbers | No | `delete_serials.csv` |
| `serials` | string | Comma-separated list of serials | No | None |

### Output

Results are saved to `delete_system_info_results.csv`:

```csv
serial_number,device_function,profiles_deleted,status
CNXXXXXXXX,ACCESS_SWITCH,2,success
CNXXXXXXX1,AP,0,no_profiles
```

## Troubleshooting

- Authentication or tokens: Ensure your credentials file is complete and has valid credentials for Central.
- Device validation: Ensure target devices are provisioned, have a persona assigned, and have a site assignment.
- Hostnames: Ensure hostnames use a valid format for the target device type.
- Location alias type mismatch: If a local alias with the requested alias name already exists but is not type `ALIAS_LOCATION`, choose a different alias name or resolve the existing alias in Central before rerunning.
- SDK compatibility: If API calls fail unexpectedly, confirm the installed pycentral version matches tested version 2.0a21 or update helpers accordingly.
- System-info profile errors: If unable to update or create hostnames, review the Delete System Info utility script.

## Support

- **Automation Team**: [aruba-automation@hpe.com](mailto:aruba-automation@hpe.com)
- **Workflow Issues**: [GitHub Issues](https://github.com/aruba/central-python-workflows/issues)
- **PyCentral Library**: [PyCentral Issues](https://github.com/aruba/pycentral/issues)
