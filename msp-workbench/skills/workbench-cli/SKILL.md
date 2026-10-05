---
name: workbench-cli
description: Use the MSP Workbench CLI for agent-safe discovery, monitoring, planning, and confirmed onboarding runs.
---

# Workbench CLI

Use `workbench.py` when an agent needs structured MSP discovery, read-only tenant
monitoring, manifest validation, or an explicitly confirmed onboarding run. Run it
from `msp-workbench/`; live mode reads `token.yaml` in that directory, while
`--demo` uses deterministic fixtures.

## Commands

```text
workbench.py [--demo] [--verbose] [--format json|table] [--fields PATHS]
              [--limit N|SECTION=N] [--out PATH]
              list {tenants,services,devices,subscriptions}
workbench.py [global flags] plan MANIFEST
workbench.py [global flags] run MANIFEST [--yes]
workbench.py [global flags] monitor overview
workbench.py [global flags] monitor tenant NAME_OR_ID
              [--sites] [--monitored-devices] [--clients] [--alerts]
workbench.py [global flags] monitor export [--format csv|json] [--out PATH]
workbench.py [global flags] subscriptions burndown
              [--scope msp|tenant|tenants|all] [--tenant NAME_OR_ID]...
              [--months 12|24|36|48|60] [--view losing_cover|unused|evaluations]
              [--lifecycle current|expired|all] [--search TEXT] [--month YYYY-MM]
              [--format json|csv] [--out PATH]
```

`monitor export --format` is subcommand-local and accepts `csv` or `json`.
Every other `--format` accepts `json` or `table`. `--fields` uses comma-separated
dotted paths relative to each list item (`workspace_name`, `address.city`), never prefixed by the section name. A bare `--limit N` caps every list; repeatable
`--limit SECTION=N` values override individual sections.

JSON stdout is one compact `{"data":...,"meta":...}` envelope. `meta` includes
`demo`, `fetched_at`, and counts for every returned list section. Table and CSV
write metadata as one JSON line on stderr. With `--out`, the document is written
to the path and stdout becomes a compact `bytes`, `path`, and `rows` receipt.

Errors are one JSON line on stderr with `code`, `message`, and nullable `hint`.
They may include `errors`: `{path, code, message}` entries for each
`manifest_invalid` problem; fix every `path` and re-run `plan`. Stable exit-1
codes are `manifest_invalid`, `manifest_not_found`, `manifest_not_readable`,
`output_not_writable`, and `token_not_found`. Exit `2` means usage or
confirmation is required, `3` means not found, `4` means authentication or
upstream failure, and `1` means another local failure. Never run a write command
without inspecting its plan; non-interactive runs require `run MANIFEST --yes`.
stderr carries only the documented JSON line(s); pycentral INFO logs are suppressed
unless `--verbose` is passed (library errors still surface).

## End-to-end recipe

1. Run `.venv/bin/python3 workbench.py --demo monitor overview` and choose an exact tenant name.
2. Run `.venv/bin/python3 workbench.py --demo monitor tenant "Acme Corp"` for live detail.
3. Run `.venv/bin/python3 workbench.py --demo subscriptions burndown` to inspect
   expiring coverage. Repeat `--tenant`; one tenant implies `tenant`, several imply
   `tenants`. MSP/mixed selections require explicit `--scope`. CSV exports all
   matching rows and never exposes internal subscription IDs.
4. Write a version 2 YAML manifest using discovered tenant, device, service, and subscription keys; copy the shape of `samples/existing_tenant.yaml` (`mode: existing`), `samples/new_tenant.yaml` (`mode: new`), or `samples/add_devices.yaml` (`mode: add`).
5. Run `.venv/bin/python3 workbench.py --demo plan manifest.yaml` and inspect `data.errors` and the planned lists; a non-zero exit prints manifest `errors` on stderr.
6. After explicit authorization, run `.venv/bin/python3 workbench.py --demo run manifest.yaml --yes` and inspect the terminal job envelope.
