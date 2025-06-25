# SSID Tunnel Overlay Workflow

This Python script automates the configuration of WLAN overlay in HPE Aruba New Central. The script performs the following actions:

- Creates config profiles such as roles and policies in New Central
- Creates SSID configurations with associated roles
- Modify policy group and create overlay WLAN profiles
- Assigns these configurations to the appropriate scopes (global or group)
- Associates devices with sites based on the inventory configuration

![SSID Tunneled Workflow][workflow]

## Dependencies

This script assumes the following regarding your New Central environment:
- Gateways & APs have been added to device groups & are online in New Central
- Underlay is configured with Gateways in established cluster

This script relies on the following Python packages:
- `pycentral` - New Central's API client library [(beta version v2.0beta2)](https://github.hpe.com/hpe/pycentral/releases/tag/2.0beta2)
- `PyYAML` - YAML parsing for configuration files
- `termcolor` - For colorized console output

## Installation

Clone this repository and `cd` into the workflow directory:
```bash
  git clone -b "v2(pre-release)" https://github.com/aruba/central-python-workflows.git
  cd central-python-workflows/tunneled-ssid-overlay
```

### Setting up a Virtual Environment

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

> **Note:** This script uses a beta version of the `pycentral` library and is designed for HPE Aruba New Central, which is also in beta. Expect potential changes and updates to the API and functionality.

## Configuration Files

The script requires three YAML configuration files:

1. **account_credentials.yaml** - Contains API credentials for New Central and Classic Central
2. **wlan_overlay_profiles.yaml** - Defines the WLAN profiles, roles, policies, and SSIDs
3. **inventory.yaml** - Specifies device information and site assignments

### Credential Configuration

You'll need to create an `account_credentials.yaml` file with the following structure:

```yaml
new_central:
  base_url: https://apigw-uswest4.central.arubanetworks.com
  client_id: <your_client_id>
  client_secret: <your_client_secret>
classic:
  base_url: https://apigw-uswest4.central.arubanetworks.com
  token:
    access_token: <your_access_token>
```

To obtain your API credentials, please refer to: [Generating and Managing Access Tokens](https://developer.arubanetworks.com/new-hpe-anw-central/docs/generating-and-managing-access-tokens) and to locate the `base_url` of your New Central cluster refer to [API Gateway Base URLs on our Developer Hub](https://developer.arubanetworks.com/new-hpe-anw-central/docs/getting-started-with-rest-apis#api-gateway-base-urls).

### WLAN Overlay Profiles Configuration

Create a `wlan_overlay_profiles.yaml` file that defines:
- Roles and their permissions
- Security policies
- SSID configurations
- Policy groups
- Overlay WLAN profiles

### Inventory Configuration

Create an `inventory.yaml` file that specifies:
- AP Groups
- Site names and their associated devices (with serial numbers)
- Device types

Example:
```yaml
AP_GROUP: "your-ap-group-name"
site_name:
  - device_type: "IAP"
    devices:
      - "SERIAL1"
      - "SERIAL2"
```

## Usage

After configuring the required YAML files, run the script:

```bash
python ssid_tunnel_overlay_workflow.py
```

## Adapting to Your Environment

To adapt this script to your environment:

1. Update `account_credentials.yaml` with your New Central API credentials
2. Modify `wlan_overlay_profiles.yaml` to define your desired wireless network configuration
3. Adjust `inventory.yaml` to match your device inventory and site structure
4. Review the script's output to ensure all operations were successful

## Troubleshooting

- Verify your API credentials are correct and have sufficient permissions
- Ensure all required YAML files are properly formatted
- Check the console output for specific error messages
- Remember that New Central is in beta, so API endpoints may change - submit any issues found within this repository

## Limitations

- This script is designed for HPE Aruba New Central, which is currently in beta
- The `pycentral` library used is also in beta and subject to changes
- Some functions may require adjustments as the New Central API evolves

[workflow]: .images/workflow.PNG "Tunneled SSID Workflow"