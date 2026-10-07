# MSP Tenant Monitoring

This workflow has been absorbed into [MSP Workbench](../msp-workbench/), which now covers tenant monitoring through its Observe journeys: Monitor tenants and Subscription burndown. See the [MSP Workbench README](../msp-workbench/README.md) for setup and usage.

## What changed

MSP Workbench replaces the `main.py` CLI with `workbench.py`. These Control Tower features were not carried over:

- The interactive terminal view (`main.py` with no export flag: numbered overview, `/search`, row expand, `r` refresh); use `workbench.py monitor overview` and `monitor tenant` instead
- `--tenant` filtering on export; `monitor export` always exports every tenant
- Default export paths under `output/`; pass `--out FILE` instead
- The 15-minute background refresh in the dashboard; data is read once per session, and **Refresh** re-reads it
- The frontend source in `frontend/`; the UI now ships prebuilt, and the source is available on request from [network-automation@hpe.com](mailto:network-automation@hpe.com)
