# Device Onboarding Workflow

This script automates the complete onboarding journey of factory-default devices in HPE Aruba Networking Central. It takes devices from an **unassigned state in GreenLake Platform (GLP)** through both GLP onboarding and Central onboarding to make them ready for configuration via **New Central**.

> [!CAUTION]
> This script uses a beta version of the `pycentral` library and is designed for HPE Aruba New Central, which is also in Public Preview. Expect potential changes and updates to the API and functionality.

## Overview

This script does the following - 

**Phase 1: GLP (GreenLake Platform) Onboarding** *(Optional)*
- Takes unassigned devices in GLP and assigns them to HPE Aruba Networking Central application instances
- Applies subscription licenses using subscription keys to enable Central management

**Phase 2: Central Onboarding** *(Required)*
- Site creation and device assignment
- Device persona configuration
- Device group management and assignment
- Provisioning verification

> [!IMPORTANT]
> **For Central-only onboarding** (when skipping GLP onboarding): Devices must already be assigned to your Central application with valid subscriptions. They will typically be in the "default" group and should not be assigned to any site.

## Prerequisites

- Python 3.8+
- Factory-default devices added to your GreenLake Platform account
- API credentials for both New Central and Classic Central
- Network connectivity between devices and Central

## Installation

1. Create and activate a virtual environment:
```bash
python3 -m venv env
source env/bin/activate  # Windows: env\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

### Credentials Configuration

#### New Central Credentials (account_credentials.yaml)

For New Central APIs and GLP operations:

```yaml
new_central:
    cluster_name: <cluster-name>  # or base_url: <central-api-base-url>
    client_id: <new-central-client-id>
    client_secret: <new-central-client-secret>

# Only include if you need GLP onboarding
glp:
    client_id: <glp-client-id>
    client_secret: <glp-client-secret>
```

> [!NOTE]
> **Where to find these:**
> - [New Central API Gateway Base URLs](https://developer.arubanetworks.com/new-hpe-anw-central/docs/getting-started-with-rest-apis#api-gateway-base-urls) 
> - [How to get New Central API Credentials](https://developer.arubanetworks.com/new-hpe-anw-central/docs/generating-and-managing-access-tokens) 

#### Classic Central Credentials (classic_central_credentials.yaml)

For some operations that still require Classic Central:

```yaml
central_info:
  base_url: <classic_central_base_url>
  token:
    access_token: <classic_central_access_token>
  ssl_verify: true
```

> [!NOTE]
> **Where to find these:**
> - [Classic Central API Gateway Base URLs](https://developer.arubanetworks.com/central/docs/api-oauth-access-token#table-domain-urls-for-api-gateway-access) 
> - [How to get a Classic Central Access Token](https://developer.arubanetworks.com/central/docs/access-token-management#obtain-access-token-via-web-ui)

### Device Variables

#### Device Configuration (workflow_variables.yaml)

```yaml
devices:
  - serial_number: <device-serial>
    # GLP Variables (Optional - only if GLP onboarding is required)
    application_assignment:
      name: <central-application-name>
      region: <region>
    subscription_assignment:
      key: <subscription-key>
    # Central Variables (Required)
    device_type: ACCESS_POINT  # or SWITCH, GATEWAY
    persona: Campus AP  # Device function
    device_group: <group-name>
    site: <site-name>

# Site details (optional - only if you need to create new sites)
sites:
  - name: <site-name>
    address: <address>
    city: <city>
    state: <state>
    country: <country>
    zipcode: "<zipcode>"
    timezone: <timezone>

# Device group details (optional - only if you need to create new groups)
device_groups:
  - group: <group-name>
    group_attributes:
      template_info:
        Wired: false
      group_properties:
        AllowedDevTypes:
          - AccessPoints
          - Switches
          - Gateways
        Architecture: AOS10
        ApNetworkRole: Standard
        GwNetworkRole: BranchGateway
        AllowedSwitchTypes:
          - AOS_CX
        NewCentral: true  # Required for New Central compatibility
```

### Configuration Reference

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `serial_number` | string | Yes | Device serial number |
| `device_type` | enum | Yes | `ACCESS_POINT`, `SWITCH`, or `GATEWAY` |
| `persona` | string | Yes | Device role (Campus AP, Access Switch, etc.) |
| `device_group` | string | Yes | Target configuration group |
| `site` | string | Yes | Site assignment |
| `application_assignment` | object | No | GLP application details |
| `subscription_assignment` | object | No | GLP subscription details |

**Persona Options by Device Type:**
- **ACCESS_POINT**: Campus AP
- **SWITCH**: Access Switch, Core Switch, Aggregation Switch
- **GATEWAY**: Mobility Gateway

### Sample Configuration Files

The following example files are available in the [`sample-input/`](sample-input/) directory:

- **[`complete_onboarding_variables.yaml`](sample-input/complete_onboarding_variables.yaml)** - Full example with GLP and Central onboarding for multiple devices
- **[`central_only_onboarding_variables.yaml`](sample-input/central_only_onboarding_variables.yaml)** - Central-only onboarding example (no GLP assignment)

Use these as templates for your own configuration files.

## Usage

Execute the onboarding workflow:

```bash
python3 onboarding.py \
  -c new_central_credentials.yaml \
  -cc classic_central_credentials.yaml \
  -vars workflow_variables.yaml
```

### Command Line Options

| Flag | Description | Required |
|------|-------------|----------|
| `-c, --credentials` | New Central API credentials | Yes |
| `-cc, --classic_credentials` | Classic Central API credentials | Yes |
| `-vars, --variables_file` | Device workflow configuration | Yes |

## How It Works

The script processes each device through these steps:

1. **Input Validation** - Validates configuration file structure
2. **GLP Onboarding** - Application and subscription assignment (if configured)
3. **Central Onboarding** - Site → Device Assignment → Persona → Group Management
4. **Verification** - Confirms provisioning status

**If something fails:** The script skips remaining steps for that device to avoid problems.

## Results

**On Screen:**
- Shows progress for each device and step
- Color-coded success/failure indicators
- Summary table at the end

**CSV File:**
Results saved to `onboarding_results_<timestamp>.csv` with:
- What happened for each device and step
- When each step completed
- Error details if something failed

## Common Issues

| Problem | Fix |
|---------|-----|
| **Bad credentials** | Check your API tokens and permissions |
| **GLP errors** | Only include GLP credentials if you need them |
| **Device not responding** | Make sure device can reach Central |
| **File errors** | Check YAML syntax in your configuration files |

## Support

- **Automation Team**: [aruba-automation@hpe.com](mailto:aruba-automation@hpe.com)
- **Workflow Issues**: [GitHub Issues](https://github.com/aruba/central-python-workflows/issues)
- **PyCentral Library**: [PyCentral Issues](https://github.com/aruba/pycentral/issues)