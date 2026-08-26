#!/usr/bin/env python3
"""Print read-only plans and bounded execution scenarios using DemoAdapter.

Run from the msp-onboarding/ directory:
    python run_samples.py
    python run_samples.py --execute-demo
"""
from __future__ import annotations

import os
import sys

# Ensure the package is importable when run directly
sys.path.insert(0, os.path.dirname(__file__))

from msp_onboarding.demo_adapter import (
    DemoAdapter, SERVICE_S1_ID, TENANT_CLEAN_ID, TENANT_EUROPE_ID,
    TENANT_NORTH_ID, TENANT_SOUTH_ID, TENANT_T1_ID,
)
from msp_onboarding.engine import OnboardingEngine
from msp_onboarding.models import (
    Manifest,
    ManifestDevice,
    Plan,
    ServiceRef,
    TenantExisting,
)
from msp_onboarding.parser import parse_csv_devices, parse_yaml_manifest
from msp_onboarding.store import MemoryStore

SAMPLES = os.path.join(os.path.dirname(__file__), "samples")


def _print_plan(label: str, plan: Plan) -> None:
    d = plan.to_dict()
    print(f"\n{'=' * 62}")
    print(f"  {label}")
    print(f"{'=' * 62}")
    print(f"  job_id          : {d['job_id']}")
    print(f"  mode            : {d['mode']}")
    print(f"  tenant groups ({len(d['tenant_groups'])}):")
    for group in d["tenant_groups"]:
        print(
            f"    {group['tenant_name']}: {group['status']}  "
            f"tenant_id={group['tenant_workspace_id']}  "
            f"service={group['service_manager_id']} [{group['service_region']}]"
        )
    print(f"  manifest_hash   : {d['manifest_hash'][:16]}…")
    print(f"  plan_hash       : {d['plan_hash'][:16]}…")
    print(f"  created_at      : {d['created_at']}")
    print(f"  devices         : {len(d['devices'])} (identifiers redacted)")
    if d["errors"]:
        print(f"  errors ({len(d['errors'])}):")
        for err in d["errors"]:
            print(f"    [{err['code']}] {err['path']}: {err['message']}")
    else:
        print("  errors          : none — plan is ready")


def _read(filename: str) -> str:
    with open(os.path.join(SAMPLES, filename)) as f:
        return f.read()

def _execution_manifest() -> Manifest:
    return Manifest(
        version=2,
        mode="existing",
        tenants=[TenantExisting(
            name="Acme Corp",
            workspace_id=TENANT_T1_ID,
            service=ServiceRef(SERVICE_S1_ID, "us-west"),
        )],
        devices=[
            ManifestDevice(tenant="Acme Corp", serial_number="CNXA001", subscription_key="KEY_A"),
            ManifestDevice(tenant="Acme Corp", serial_number="CNXA002", subscription_key="KEY_A"),
        ],
    )


def _bulk_partial_manifest(adapter: DemoAdapter) -> Manifest:
    names = (
        "Demo North Tenant",
        "Demo South Tenant",
        "Demo Europe Tenant",
        "Demo Clean Tenant",
    )
    ids = (TENANT_NORTH_ID, TENANT_SOUTH_ID, TENANT_EUROPE_ID, TENANT_CLEAN_ID)
    service = ServiceRef(SERVICE_S1_ID, "us-west")
    for name in names:
        tenant = adapter.ensure_tenant("new", None, name)
        adapter.submit_service_provisioning(
            tenant.workspace_id, SERVICE_S1_ID, "us-west"
        )
        adapter.observe_service_provisioning(
            tenant.workspace_id, SERVICE_S1_ID, "us-west"
        )
    return Manifest(
        version=2,
        mode="existing",
        tenants=[TenantExisting(name, workspace_id, service) for name, workspace_id in zip(names, ids)],
        devices=[
            *(
                ManifestDevice("Demo North Tenant", "KEY_SHARED", serial_number=serial)
                for serial in ("CNXA001", "CNXA002", "CNXA003")
            ),
            *(
                ManifestDevice("Demo South Tenant", "KEY_SHARED", serial_number=serial)
                for serial in ("CNXA005", "CNXA006")
            ),
            *(
                ManifestDevice("Demo Europe Tenant", "KEY_B", serial_number=serial)
                for serial in ("CNXA007", "CNXA008")
            ),
            ManifestDevice("Demo Clean Tenant", "KEY_B", serial_number="CNXA009"),
        ],
    )


def _run_execution_demo() -> None:
    with MemoryStore() as store:
        adapter = DemoAdapter()
        engine = OnboardingEngine(adapter, store)
        job_id = engine.plan(_execution_manifest()).job_id
        engine.confirm(job_id)
        engine.drain()
        print(f"success: {engine.get(job_id)['status']}")

    with MemoryStore() as store:
        adapter = DemoAdapter("bulk-partial")
        engine = OnboardingEngine(adapter, store)
        job_id = engine.plan(_bulk_partial_manifest(adapter)).job_id
        engine.confirm(job_id)
        engine.drain()
        print(f"bulk partial: {engine.get(job_id)['status']}")

    with MemoryStore() as store:
        adapter = DemoAdapter("ambiguous-write")
        engine = OnboardingEngine(adapter, store)
        job_id = engine.plan(_execution_manifest()).job_id
        engine.confirm(job_id)
        engine.drain()
        print(f"ambiguous inline: {engine.get(job_id)['status']}")


def main() -> None:
    if sys.argv[1:] == ["--execute-demo"]:
        _run_execution_demo()
        return
    adapter = DemoAdapter()

    # ── new-tenant plan ────────────────────────────────────────────────
    with MemoryStore() as store:
        manifest1 = parse_yaml_manifest(_read("new_tenant.yaml"))
        plan1 = OnboardingEngine(adapter, store).plan(manifest1)
    _print_plan("new_tenant.yaml → new-tenant-success", plan1)

    # ── existing-tenant plan ───────────────────────────────────────────
    with MemoryStore() as store:
        manifest2 = parse_yaml_manifest(_read("existing_tenant.yaml"))
        plan2 = OnboardingEngine(adapter, store).plan(manifest2)
    _print_plan("existing_tenant.yaml → existing-tenant-success", plan2)

    # ── CSV devices → plan ─────────────────────────────────────────────
    csv_devices = parse_csv_devices(_read("devices.csv"))
    manifest3 = Manifest(
        version=2,
        mode="existing",
        tenants=[TenantExisting(
            name="Demo West Tenant",
            workspace_id=TENANT_T1_ID,
            service=ServiceRef(SERVICE_S1_ID, "us-west"),
        )],
        devices=csv_devices,
    )
    with MemoryStore() as store:
        plan3 = OnboardingEngine(adapter, store).plan(manifest3)
    _print_plan("devices.csv → csv-devices-plan (existing T1, S1)", plan3)

    print()


if __name__ == "__main__":
    main()
