# WPA3 PSK Workflow

This Python script automates the configuration of a WPA3 PSK (Wi-Fi Protected Access 3 - Pre-Shared Key) in New HPE Aruba Networking Central. It creates configuration profiles such as roles and policies in New Central, modifies policy groups and associates policies with them, and generates WPA3 PSK configurations with associated roles. Additionally, it assigns these configurations to the appropriate scopes, whether site or global, and moves devices into the site with the WPA3 PSK configuration to ensure they inherit the profile.

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

This file contains the credentials required to authenticate with New Central.

```yaml
new_central:
  base_url: <your_base_url>
  client_id: <your_client_id>
  client_secret: <your_client_secret>
```

### 

#### classic_account_credentials.yaml

This file contains the credentials required to authenticate with the Classic Central API.

```yaml
central_info:
  base_url: <your_classic_central_base_url>
  token:
    access_token: <your_classic_central_token>
ssl_verify: true
```

### 

#### wlan_overlay_profiles.yaml

This file contains the configuration details for the WPA3 PSK workflow.

> [!IMPORTANT]
>Ensure that the `site_details` section is properly configured. The `ssid` variable is the name of your wlan ssid profile. The `default-role` should match the name of the `role_details` role name so that the role created in this workflow is correctly applied to the wlan ssid profile when it is created. A WPA3 PSK must have the `enable` parameter set to true in order to enable the SSID profile. The `opmode` or operation mode must be set to WPA3_PSK: Wi-Fi Protected Access 3 with Pre-Shared Key authentication.

```yaml
site_details:
  name: "WPA3-PSK-Site"
  address: "6280 America Center Dr"
  city: "San Jose"
  state: "California"
  country: "United States"
  zipcode: "95002"
  timezone: "America/Los_Angeles"

role_details:
  role:
    - name: "wpa3-psk-role"
      description: "wpa3-psk-role description"

policy_details:
  policy:
    - name: "wpa3-psk-policy"
      type: "POLICY_TYPE_SECURITY"
      description: "wpa3-psk-policy description"
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
                role: "wpa3-psk-role"
              destination:
                type: "ADDRESS_ANY"
            action:
              type: "ACTION_ALLOW"

policy_group_details:
  policy-group:
    policy-group-list:
      - name: "wpa3-psk-policy"
        position: 4
        description: "wpa3-psk-policy description"

ssid_details:
  wlan-ssid:
    - ssid: "wpa3-psk-wlan"
      enable: true
      forward-mode: "FORWARD_MODE_BRIDGE"
      opmode: "WPA3_PSK"
      default-role: "wpa3-psk-role"
```

### 

#### inventory.yaml

This file contains the mapping of devices to the site. It specifies the device type and serial numbers of devices to be moved to the site.

```yaml
WPA3-PSK-Site:
    - device_type: IAP
      devices:
          - PHQSLBN5HB
```

### 

#### new_passphrase.yaml (Optional)

This file contains the new passphrase details for updating the WPA3 PSK.

> [!IMPORTANT]
> Ensure that the `ssid` matches the name of the WLAN SSID profile you want to update. The `new_passphrase` should be a secure and valid passphrase. The passphrase must be between 8 and 63 characters long and can include letters, numbers, and special characters.

```yaml
ssid: "wpa3-psk-wlan"
new_passphrase: "<your_new_passphrase>"
```

---

## Workflow Steps

This workflow automates the configuration of a WPA3 PSK in HPE Aruba Networking Central, including site creation, role and policy assignment, and device management. Ensure that all configuration files are properly set up before running the script.

> [!NOTE]
> **Please make sure the device is provisioned to New Central before assigning it to a site.**
>
> The script currently supports assigning devices managed by both Classic and New Central, but only devices in New Central can inherit site-level configurations. Since the goal of the script is to apply these inherited profiles, devices should be in New Central before site assignment.

1. #### **Create a Site** <span style="font-weight: normal"> - The script creates a site in HPE Aruba Networking Central using the details provided in the `site_details` section of the configuration file.</span>
2. #### **Get Site ID** <span style="font-weight: normal"> - The script retrieves the site ID for the newly created site.</span>
3. #### **Create Role** <span style="font-weight: normal"> - The script creates a role in HPE Aruba Networking Central using the details provided in the `role_details` section of the configuration file.</span>
4. #### **Assign Role to Site** <span style="font-weight: normal"> - The script assigns the created role to the site.</span>
5. #### **Create Role-Based Policy** <span style="font-weight: normal"> - The script creates a role-based policy using the details provided in the `policy_details` section of the configuration file.</span>
6. #### **Add Policy to Group** <span style="font-weight: normal"> - The script adds the created policy to a policy group for easier management.</span>
7. #### **Assign Role-Based Policy to Site** <span style="font-weight: normal"> - The script assigns the role-based policy to the site.</span>
8. #### **Create WPA3 PSK** <span style="font-weight: normal"> - The script creates a WPA3 PSK (WLAN Profile) using the details provided in the `ssid_details` section of the configuration file.</span>
9. #### **Assign WPA3 PSK to Site** <span style="font-weight: normal"> - The script assigns the WPA3 PSK to the site.</span>
10. #### **Get Devices** <span style="font-weight: normal"> - The script retrieves the list of devices associated with the site.</span>
11. #### **Move Devices to Site** <span style="font-weight: normal"> - The script moves devices to the newly created site using the inventory details provided in the `inventory.yaml` file. This ensures that devices are properly associated with the site and inherit the configurations applied to the site.</span>
12. #### **Change WPA3 PSK Passphrase (Optional)** <span style="font-weight: normal"> - The script updates the passphrase for the WPA3 PSK using the details provided in the `new_passphrase.yaml` file.</span>
13. #### **Generate and Change WPA3 PSK Passphrase (Optional)** <span style="font-weight: normal"> - The script generates a new passphrase for the WPA3 PSK and updates it in Central if no passphrase is provided in `new_passphrase.yaml`.</span>

---

## Running the Script

To execute the workflow, run the following command:

```bash
python wpa3_psk_overlay_workflow.py -c account_credentials.yaml -cc classic_account_credentials.yaml -i inventory.yaml -p wlan_overlay_profiles.yaml
```

To update the WPA3 PSK passphrase, include the `-np` flag with the `new_passphrase.yaml` file:

```bash
python wpa3_psk_overlay_workflow.py -c account_credentials.yaml -cc classic_account_credentials.yaml -i inventory.yaml -p wlan_overlay_profiles.yaml -np new_passphrase.yaml
```

## Conditional Logic for Passphrase Steps

The script includes logic to handle passphrase updates conditionally based on the `-np` flag and the contents of the `new_passphrase.yaml` file.

### How It Works

1. **Checking the `-np` Flag**:
   - The script checks if the `-np` flag is provided when running the script.
   - If the flag is not provided, the passphrase update steps (Step 13 and Step 14) are skipped entirely.

2. **Checking the `new_passphrase.yaml` File**:
   - If the `-np` flag is provided, the script reads the `new_passphrase.yaml` file.
   - The file must contain the `ssid_name` field (the name of the SSID to update). If this field is missing, the script will terminate with an error.
   - The file may optionally contain the `new_passphrase` field:
     - If `new_passphrase` is present and non-empty, the script executes **Step 13** to update the passphrase for the specified SSID.
     - If `new_passphrase` is missing or empty, the script executes **Step 14** to generate a new passphrase and update the SSID with the generated value.

3. **Confirmation Prompts**:
   - Before executing either Step 13 or Step 14, the script prompts the user for confirmation with a message explaining the action to be taken.
   - The user must confirm by entering `y` to proceed; otherwise, the step is skipped.

### Example Scenarios

#### Scenario 1: Update Passphrase with a Specified Value
- Command:
  ```bash
  python wpa3_psk_overlay_workflow.py -c account_credentials.yaml -cc classic_account_credentials.yaml -i inventory.yaml -p wlan_overlay_profiles.yaml -np new_passphrase.yaml
  ```
- `new_passphrase.yaml`:
  ```yaml
  ssid_name: "wpa3-psk-wlan"
  new_passphrase: "securepassword123"
  ```
- Outcome:
  - The script executes Step 13 to update the passphrase for `wpa3-psk-wlan` to `securepassword123`.

#### Scenario 2: Generate and Update Passphrase
- Command:
  ```bash
  python wpa3_psk_overlay_workflow.py -c account_credentials.yaml -cc classic_account_credentials.yaml -i inventory.yaml -p wlan_overlay_profiles.yaml -np new_passphrase.yaml
  ```
- `new_passphrase.yaml`:
  ```yaml
  ssid_name: "wpa3-psk-wlan"
  new_passphrase: ""
  ```
- Outcome:
  - The script executes Step 14 to generate a new random passphrase and update the SSID `wpa3-psk-wlan` with the generated value.

#### Scenario 3: Skip Passphrase Steps
- Command:
  ```bash
  python wpa3_psk_overlay_workflow.py -c account_credentials.yaml -cc classic_account_credentials.yaml -i inventory.yaml -p wlan_overlay_profiles.yaml
  ```
- Outcome:
  - The script skips both Step 13 and Step 14 since the `-np` flag is not provided.


---

## Troubleshooting

### Common Issues
1. **Authentication Errors**:
   - Ensure that the credentials in account_credentials.yaml and classic_account_credentials.yaml are correct.

2. **Site Creation Fails**:
   - Check the site_details section in wlan_overlay_profiles.yaml for missing or incorrect fields.

3. **Role or Policy Assignment Fails**:
   - Ensure that the role or policy exists before assigning it to a site.

4. **Device Retrieval Fails**:
   - Verify that devices are associated with the site in HPE Aruba Networking Central.

5. **Passphrase Update Fails**:
   - Ensure that the `new_passphrase.yaml` file is properly configured with the correct SSID and a valid passphrase.

---

## Additional Notes

- This workflow is designed for HPE Aruba Networking Central environments and requires the pycentral SDK.
- Ensure that the configuration files listed above are filled out properly before running the script.

---
