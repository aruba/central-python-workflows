# SSID Tunnel Overlay Workflow

This script automates the configuration of WLAN overlay in new HPE Aruba Networking Central. The script performs the following actions:

![SSID Tunneled Workflow][workflow]

- Creates config profiles such as roles and policies in Central
- Creates SSID configurations with associated roles
- Modify policy group and create overlay WLAN profiles
- Assigns these configurations to the appropriate scopes (global or group)
- Associates devices with sites based on the inventory configuration

## Prerequisites

This script assumes the following regarding your new Central environment:
- Gateways & APs have been added to device groups & are online in new Central
- Underlay is configured with Gateways in established cluster and any VLANs configured & assigned to the appropriate scopes


## Installation

1. Clone the repository and navigate to this workflow folder
   ```bash
   git clone -b "v2(pre-release)" https://github.com/aruba/central-python-workflows.git
   cd central-python-workflows/tunneled-ssid-overlay
   ```

2) Create and activate a virtual environment, then install dependencies
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use: venv\Scripts\activate
    pip install -r requirements.txt
    ```

This workflow is tested on the `pycentral` SDK version `2.0a9`. Please check compatibility before executing on older/newer versions as there may be changes.

## Configuration

### Credentials Configuration

For API operations in new HPE Aruba Networking Central and classic Central:

```yaml
new_central:
  base_url: <new-central-base-url>
  client_id: <your-client-id>
  client_secret: <your-client-secret>
classic:
  base_url: <classic-central-base-url>
  token:
    access_token: <your-access-token>
```

**Sample Input:** See `account_credentials.yaml` in this repository for an example credential file.

> [!TIP]
> **Where to find these:**
> - [Central API Gateway Base URLs](https://developer.arubanetworks.com/new-hpe-anw-central/docs/getting-started-with-rest-apis#api-gateway-base-urls) 
> - [How to get API Credentials for new Central](https://developer.arubanetworks.com/new-hpe-anw-central/docs/generating-and-managing-access-tokens)
> - [classic Central API Gateway Base URLs](https://developer.arubanetworks.com/central/docs/api-oauth-access-token#table-domain-urls-for-api-gateway-access) 
> - [How to get an Access Token for classic Central](https://developer.arubanetworks.com/central/docs/access-token-management#obtain-access-token-via-web-ui)

### Workflow Input Data

#### Profile Configuration (wlan_overlay_profiles.yaml)

The `wlan_overlay_profiles.yaml` file defines the configuration for roles, policies, SSIDs, and WLAN profiles:

```yaml
roles:
  # Role definitions
policies:
  # Policy definitions
ssids:
  # SSID configurations
policy_groups:
  # Policy group configurations
wlan_profiles:
  # WLAN profile configurations
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `roles` | dictionary | Yes | User roles with access permissions |
| `policies` | dictionary | Yes | Security policies and rules |
| `ssids` | dictionary | Yes | WLAN SSID configurations with associated roles |
| `policy_groups` | dictionary | Yes | Policies to apply to global policy |
| `wlan_profiles` | dictionary | Yes | WLAN SSID profile configurations |

**Sample Input:** See `wlan_overlay_profiles.yaml` in this repository for an example configuration file.

#### Inventory Configuration (inventory.yaml)

The `inventory.yaml` file specifies site names and their associated devices:

```yaml
<site_name>:
  - device_type: IAP
    devices:
      - <device-serial>
      - <device-serial>
  - device_type: GATEWAY
    devices:
      - <device-serial>
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `site_name` | string | Yes | Name of the site in Central |
| `device_type` | string | Yes | Type of device (IAP or GATEWAY) |
| `devices` | array | Yes | List of device serial numbers |

**Example Configuration:**
```yaml
Corporate_HQ:
  - device_type: IAP
    devices:
      - PHQSLBN5HB
      - PHQSLBN56K
  - device_type: GATEWAY
    devices:
      - CNSHKLB01W
```

**Sample Input:** See `inventory.yaml` in this repository for an example inventory file.

## Execution

Run the script:

```bash
python ssid_tunnel_overlay_workflow.py
```


## Output

The script provides detailed console output about each step of the process, including:

- Creation status of roles and policies
- Configuration of SSIDs
- Policy group modifications
- Creation of overlay WLAN profiles
- Assignment of configurations to scopes
- Association of devices with sites

Success or failure messages will be displayed for each operation, with colorized output for better visibility.

## Troubleshooting

- **Authentication Issues**: Verify that your API credentials in `account_credentials.yaml` are correct and have not expired
- **Configuration Errors**: Ensure that all YAML files are properly formatted and contain the required API fields.
- **Device Not Found**: Check that the serial numbers in `inventory.yaml` match those in Central
- **Scope Assignment Failures**: Verify that the scopes specified in your configurations exist in Central
- **Pre-existing Configuration**: The script may fail if configurations with the same names already exist; consider renaming or removing them first
- **VLAN Not Found**: Make sure all VLANs referenced in the configurations are already configured and assigned to the appropriate scopes
- **Cluster Issues**: Ensure Gateway clusters are properly established before running the script


## Support

- **Automation Team**: [aruba-automation@hpe.com](mailto:aruba-automation@hpe.com)
- **Workflow Issues**: [GitHub Issues](https://github.com/aruba/central-python-workflows/issues)
- **PyCentral Library**: [PyCentral Issues](https://github.com/aruba/pycentral/issues)

[workflow]: .images/workflow.PNG "Tunneled SSID Workflow"