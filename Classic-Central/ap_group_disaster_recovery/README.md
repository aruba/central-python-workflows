# Disaster Recovery

This is a Python script that uses the [PyCentral](https://pypi.org/project/pycentral/) library to create and restore an external backup of your HPE Aruba Networking Classic Central configuration. It is designed so that, in the event of a network outage or accidental group configuration loss, a customer can quickly recover their environment.

## What This Script Does

The script runs in two modes:

**Backup Mode** — Connects to Central and exports:
1. Every AP's serial number, hostname, and group membership saved to `ap_hostnames.csv`
2. Per-AP CLI settings (hostname, radio overrides, etc.) saved as individual `.json` files

> **Note:** Classic Central UI groups do not expose a single group-level configuration endpoint. AP settings are therefore pulled directly from each individual AP using the per-AP settings API.

**Restore Mode** — Pushes every AP's full backed-up CLI configuration back to Central, returning the environment to exactly the state it was in at the time of the backup. Hostnames are included automatically as part of the CLI configuration — no separate step needed.

## Backup Output Structure

```
backup_2024-04-07_10-30-00/
├── ap_hostnames.csv              ← serial_number, hostname, group_name, model
└── ap_settings/
    ├── CNXXXXX.json              ← per-AP CLI settings for serial CNXXXXX
    └── CNYYYYY.json
```

## Prerequisites

1. All Access Points have valid Classic Central licenses
2. Your Central API token has read access to groups and APs (backup) and write access (restore)

## Installation Steps

1. Clone this repository and `cd` into the workflow directory:
    ```bash
    git clone https://github.com/aruba/central-python-workflows
    cd central-python-workflows/Classic-Central/disaster_recovery
    ```

2. Install a virtual environment (Python 3 required):
    ```bash
    python -m venv env
    ```

3. Activate the virtual environment:

    macOS / Linux:
    ```bash
    source env/bin/activate
    ```
    Windows:
    ```bash
    env\Scripts\activate.bat
    ```

4. Install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

5. Fill in your Central API credentials in [central_token.json](central_token.json):
    ```json
    {
        "central_info": {
            "base_url": "<api-gateway-domain-url>",
            "token": {
                "access_token": "<api-gateway-access-token>"
            }
        },
        "ssl_verify": true
    }
    ```
    > **Note**
    > - [Base URLs for Aruba Central clusters](https://developer.arubanetworks.com/aruba-central/docs/api-oauth-access-token#table-domain-urls-for-api-gateway-access)
    > - [Generating an access token from Central UI](https://developer.arubanetworks.com/aruba-central/docs/api-gateway-creating-application-token)
    > - [Generating an access token using OAuth APIs](https://developer.arubanetworks.com/aruba-central/docs/api-oauth-access-token)

## Executing the Workflow

### Backup

Run a full backup of all groups and AP hostnames:
```bash
python disaster_recovery.py --mode backup --central_auth central_token.json
```

The backup will be saved to a timestamped folder (e.g. `backup_2024-04-07_10-30-00/`). You can specify a custom output directory with `--output_dir`:
```bash
python disaster_recovery.py --mode backup --central_auth central_token.json --output_dir my_backup
```

The script automatically scales the number of concurrent worker threads based on the total AP count in your Central instance (formula: `min(30, max(5, total_aps // 100))`). No manual tuning is needed.

### Restore

> [!WARNING]
> **Restore operations make immediate, live configuration changes to your Access Points in HPE Aruba Networking Central.**
> Every AP's full CLI settings will be overwritten with the backed-up version. These changes cannot be undone by this script. Always verify that the backup reflects a **known-good configuration state** before proceeding.

Restore from the **most recent backup** (auto-selected):
```bash
python disaster_recovery.py --mode restore --central_auth central_token.json
```

Restore from a **specific** backup directory:
```bash
python disaster_recovery.py --mode restore \
  --central_auth central_token.json \
  --backup_dir backup_2024-04-07_10-30-00
```

## Documentation

- PyCentral package documentation: [pycentral module documentation](https://pycentral.readthedocs.io/en/latest/)
- Get per-AP setting API: [GET /configuration/v1/ap_settings_cli/{serial}](https://developer.arubanetworks.com/aruba-central/reference/apiap_clisget_ap_settings_clis)
- Replace per-AP setting API: [POST /configuration/v1/ap_settings_cli/{serial}](https://developer.arubanetworks.com/aruba-central/reference/apiap_clisupdate_ap_settings_clis)
- Aruba Developer Hub: [developer.arubanetworks.com](https://developer.arubanetworks.com/aruba-central)

## Troubleshooting

- **Module import errors** — Make sure the virtual environment is activated and `pip install -r requirements.txt` has been run
- **HTTP 401 / 403** — Verify that the access token in `central_token.json` is valid and has not expired
- **HTTP 400 on restore** — The AP serial number in the backup file must exist in Central; the API cannot push settings to an AP that is not registered
- **AP restore skipped** — The AP must be online and reachable in Central at the time of restore

## Known Issues

- **Restore is destructive** — every AP's full CLI settings are replaced verbatim with the backed-up version. There is no partial restore.
- APs on operating systems older than AOS 10.x may not support serial number as a target for `ap_settings_cli`.
- Central API rate limiting (HTTP 429) may occur on very large deployments. The worker count is capped at 30 to stay within typical Central rate limits.
