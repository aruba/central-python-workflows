# Open SSID Workflow

This Python script automates the configuration of an Open SSID (Opportunistic Wireless Encryption) in New HPE Aruba Networking Central. It creates configuration profiles such as roles and policies in New Central, modifies policy groups and associates policies with them, and generates Open SSID configurations with associated roles. Additionally, it assigns these configurations to the appropriate scopes, whether site or global, and moves devices into the site with the Open SSID configuration to ensure they inherit the profile.

---

## Dependencies

This script relies on the following Python packages:

- **pycentral**: Aruba Central's API client library [(beta version v2.0beta2)](https://github.hpe.com/hpe/pycentral/releases/tag/2.0beta6)
- **PyYAML**: YAML parsing for configuration files
- **termcolor**: For colorized console output

---

## Installation

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

---

## Configuration Files

### 

#### account_credentials.yaml

This file contains the credentials required to authenticate with Aruba Central.

```yaml
new_central:
  base_url: <your_base_url>
  client_id: <your_client_id>
  client_secret: <your_client_secret>
classic:
  base_url: <your_base_url>
```

### 

#### classic_account_credentials.yaml

This file contains the credentials required to authenticate with the Classic Aruba Central API.

```yaml
central_info:
  base_url: <your_classic_central_base_url>
  token:
    access_token: <your_classic_central_token>
ssl_verify: true
```

### 

#### wlan_overlay_profiles.yaml

This file contains the configuration details for the Open SSID workflow.

```yaml
site_details:
  name: "Open-SSID-Site"
  address: "6280 America Center Dr"
  city: "San Jose"
  state: "California"
  country: "United States"
  zipcode: "95002"
  timezone: "America/Los_Angeles"

role_details:
  role:
    - name: "open-ssid-role"
      description: "open-ssid-role description"

policy_details:
  policy:
    - name: "open-ssid-policy"
      type: "POLICY_TYPE_SECURITY"
      description: "open-ssid-policy description"
      security-policy:
        type: "SECURITY_POLICY_TYPE_DEFAULT"
        policy-rule:
          - position: 1
            description: "Allow All"
            condition:
              type: "CONDITION_DEFAULT"
              rule-type: "RULE_ANY"
              source:
                type: "ADDRESS_ROLE"
                role: "open-ssid-role"
              destination:
                type: "ADDRESS_ANY"
            action:
              type: "ACTION_ALLOW"

policy_group_details:
  policy-group:
    policy-group-list:
      - name: "open-ssid-policy"
        position: 4
        description: "open-ssid-policy description"

ssid_details:
  wlan-ssid:
    - ssid: "open-ssid-wlan"
      enable: true
      forward-mode: "FORWARD_MODE_BRIDGE"
      opmode: "ENHANCED_OPEN"
      default-role: "open-ssid-role"
```

>**⚠️ Important Note:** Ensure that the `site_details` section is properly configured. The `ssid` variable is the name of your wlan ssid profile. The `default-role` should match the name of the `role_details` role name so that the role created in this workflow is correctly applied to the wlan ssid profile when it is created. An Open SSID must have the `enable` parameter set to true in order to enable the SSID profile. The `opmode` or operation mode must be set to either OPEN: no authentication and encryption or ENHANCED_OPEN: Improved data encryption in open Wi-Fi networks and protects data from sniffing. Enhanced open replaces open system as the default opmode.

### 

#### inventory.yaml

This file contains the mapping of devices to the site. It specifies the device type and serial numbers of devices to be moved to the site.

```yaml
Open-SSID-Site:
    - device_type: IAP
      devices:
          - PHQSLBN5HB
```

---

## Workflow Steps

This workflow automates the configuration of an Open SSID in HPE Aruba Networking Central, including site creation, role and policy assignment, and device management. Ensure that all configuration files are properly set up before running the script.

1. #### **Create a Site** <span style="font-weight: normal"> - The script creates a site in HPE Aruba Networking Central using the details provided in the `site_details` section of the configuration file.</span>
2. #### **Get Site ID** <span style="font-weight: normal"> - The script retrieves the site ID for the newly created site.</span>
3. #### **Create Role** <span style="font-weight: normal"> - The script creates a role in HPE Aruba Networking Central using the details provided in the `role_details` section of the configuration file.</span>
4. #### **Assign Role to Site** <span style="font-weight: normal"> - The script assigns the created role to the site.</span>
5. #### **Create Role-Based Policy** <span style="font-weight: normal"> - The script creates a role-based policy using the details provided in the `policy_details` section of the configuration file.</span>
6. #### **Add Policy to Group** <span style="font-weight: normal"> - The script adds the created policy to a policy group for easier management.</span>
7. #### **Assign Role-Based Policy to Site** <span style="font-weight: normal"> - The script assigns the role-based policy to the site.</span>
8. #### **Create Open SSID** <span style="font-weight: normal"> - The script creates an Open SSID (WLAN Profile) using the details provided in the `ssid_details` section of the configuration file.</span>
9. #### **Assign Open SSID to Site** <span style="font-weight: normal"> - The script assigns the Open SSID to the site.</span>
10. #### **Get Devices** <span style="font-weight: normal"> - The script retrieves the list of devices associated with the site.</span>
11. #### **Move Devices to Site** <span style="font-weight: normal"> - The script moves devices to the newly created site using the inventory details provided in the `inventory.yaml` file. This ensures that devices are properly associated with the site and inherit the configurations applied to the site.</span>

---

## Running the Script

To execute the workflow, run the following command:

```bash
python ssid_open_overlay_workflow.py -c account_credentials.yaml -cc classic_account_credentials.yaml -i inventory.yaml -p wlan_overlay_profiles.yaml
```

---

## Troubleshooting

### Common Issues
1. **Authentication Errors**:
   - Ensure that the credentials in account_credentials.yaml are correct.
   - Verify that the API token has the necessary permissions.

2. **Site Creation Fails**:
   - Check the site_details section in wlan_overlay_profiles.yaml for missing or incorrect fields.

3. **Role or Policy Assignment Fails**:
   - Ensure that the role or policy exists before assigning it to a site.

4. **Device Retrieval Fails**:
   - Verify that devices are associated with the site in HPE Aruba Networking Central.

---

## Additional Notes

- This workflow is designed for HPE Aruba Networking Central environments and requires the pycentral SDK.
- Ensure that the configuration files listed above are filled out properly before running the script.

---
