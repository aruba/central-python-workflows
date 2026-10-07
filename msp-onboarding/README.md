# MSP Onboarding

This workflow has been renamed to [MSP Workbench](../msp-workbench/), which covers tenant creation, inventory assignment, and adding devices to MSP inventory through its Onboard journeys. See the [MSP Workbench README](../msp-workbench/README.md) for setup and usage.

## What changed

MSP Workbench replaces `onboarding.py` with `workbench.py` (`plan` and `run` take the same YAML manifests). These demo scenarios were removed: `bulk-success`, `bulk-partial`, `tenant-name-conflict`, `tenant-creation-systemic`, and `partial-add`. The remaining scenarios are `success`, `partial-device-write`, and `ambiguous-write`.
