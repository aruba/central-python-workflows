# Access Point Onboarding

Onboard **AOS 10 access points** into Central from one batched run. When you bring a new site online or migrate a stack of APs, this workflow assigns devices to GreenLake, applies subscriptions, provisions the access points, and applies optional per-device settings, from a scriptable CLI or a local web UI, both driven by the same engine. This onboarding workflow is for devices that are configured via Central (**not Classic Central**)

Only AOS 10 access points are supported. Other device types and architectures are rejected during validation.

<!-- TODO(ap-onboarding): add workflow/architecture diagram — tracked as a follow-up task -->

## Features

- **AOS 10 AP onboarding** — assign devices to GreenLake, apply subscriptions, provision access points into Central, and record per-device results in a single batched run.
- **Run-time firmware gate** — each AP's model and version are discovered live during the run and compared against a per-model minimum. An AP below its minimum is marked **Skipped (firmware)** and the rest of the batch continues.
- **Central infrastructure prep** — a supporting `network_setup.py` command, creates the sites, device groups, the onboarding run expects. Existing objects are skipped, so it is safe to re-run.
- **Two run surfaces** — a scriptable CLI and a local single-page web UI that share one engine, with the same validation and device limit.
- **Batched and safe** — up to 50 devices per run (configurable), credential files enforced at mode `0600`, and explicit exit codes for automation.

## Prerequisites

Before starting, you need:

- Python 3.10+ or higher
- HPE GreenLake API credentials for your account: client ID, client secret, and workspace ID.
- A Classic Central API access token for the same account.
- Access points present in GreenLake inventory, plus any subscription keys required by your workflow.

## Installation

Clone the workflows repository, move into this workflow, and install the
pinned dependencies into a virtual environment:

```bash
git clone https://github.com/aruba/central-python-workflows.git
cd central-python-workflows/ap-onboarding
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Confirm the entry points load without making API calls:

```bash
.venv/bin/python network_setup.py --help
.venv/bin/python onboarding.py --help
```

## Configuration

### Credentials

The workflow uses two credential systems for Central as some of the onboarding steps require Classic Central today:

| Local file | Used for |
| --- | --- |
| `account_credentials.yaml` | GreenLake platform operations and New Central operations |
| `classic_central_credentials.yaml` | Classic Central site lookup, site association, and group assignment |

Both files must point to the same account. Start from the annotated examples and create the local files with owner-only permissions:

```bash
install -m 600 account_credentials.example.yaml account_credentials.yaml
install -m 600 classic_central_credentials.example.yaml classic_central_credentials.yaml
```

Both files should show `-rw-------`. They are ignored by Git and must never be committed. The workflow enforces mode `0600`; it rejects or warns about unsafe existing files, and CLI runs verify both credential systems before making changes.

> [!TIP]
> The web UI can create the same pair safely: start the UI, select the Central instance chip in the top bar, choose **Manage credentials**, select the cluster, enter both credential groups, and use **Save & verify all**. Secrets are write-only in the browser and the files are saved as `0600`.

### Input data

The annotated input templates live in [`sample-input/`](sample-input/). Create local working copies in the workflow root:

```bash
cp sample-input/network_setup_variables.yaml network_setup_variables.yaml
cp sample-input/onboarding_variables.yaml onboarding_variables.yaml
```

Edit the copies for your cluster. Use `sample-input/onboarding_variables.central_only.yaml` instead when devices already have their GreenLake application and subscription assignments. Root-level `*_variables.yaml` files are ignored by Git.

## Execution

### 1. Prepare Central infrastructure

Configure the sites, device groups you need, then run:

```bash
.venv/bin/python network_setup.py \
  -c account_credentials.yaml \
  -cc classic_central_credentials.yaml \
  -vars network_setup_variables.yaml
```

Existing objects and bindings are skipped where appropriate, so this is also the basic first run for checking that credentials and infrastructure settings are correct.

### 2. Onboard access points

Review each serial number and its target site/group before running:

```bash
.venv/bin/python onboarding.py \
  -c account_credentials.yaml \
  -cc classic_central_credentials.yaml \
  -vars onboarding_variables.yaml
```

### 3. Web UI (optional)

Start the local server:

```bash
.venv/bin/uvicorn ui_app:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. The single-page workflow has three stages:

1. **Configure** — choose the Central instance and configure or verify the target infrastructure.
2. **Devices** — select inventory devices, upload CSV input, or enter serial numbers; then set per-device values.
3. **Run & results** — run preflight and onboarding, follow live progress and logs, and review or export the results.

Credentials are managed from the instance chip → **Manage credentials**.

## Output

The onboarding CLI exit codes are:

- `0` — the run completed without device failures or add-on warnings.
- `1` — one or more devices failed onboarding.
- `2` — core onboarding succeeded, but one or more optional add-on steps need
  attention or retry.

Firmware is discovered during the run, not accepted as input. The first per-device step compares the discovered model and version with the per-model
minimum in `min_firmware.yaml`; an AP below its minimum is marked **Skipped (firmware)** while the rest of the batch continues.

The web UI shows the same run as live progress and logs, then lets you review per-device results and export them.

## Troubleshooting

| Symptom | Cause / Fix |
| --- | --- |
| `pycentral` fails to install | Python is older than 3.10; create the virtual environment with Python 3.10+. |
| Device rejected during validation | Only AOS 10 access points are supported; remove other device types from the run. |
| Device not found / cannot be assigned | The AP is not in GreenLake inventory; add it to inventory before onboarding. |
| `401`/auth error on Classic Central steps | The Classic Central access token has expired; regenerate it and update `classic_central_credentials.yaml`. |
| Credential file rejected as unsafe | The file is not mode `0600`; run `chmod 600` on it. |
| Device marked **Skipped (firmware)** | The AP is below its per-model minimum in `min_firmware.yaml`; upgrade firmware or adjust the minimum. |
| Batch capped below your device count | The run exceeds the device limit; raise `ONBOARDING_MAX_DEVICES`. |

## Support

- **Automation Team**: [aruba-automation@hpe.com](mailto:aruba-automation@hpe.com)
- **Workflow Issues**: [GitHub Issues](https://github.com/aruba/central-python-workflows/issues)
- **PyCentral Library**: [PyCentral Issues](https://github.com/aruba/pycentral/issues)
