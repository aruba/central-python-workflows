"""R1 live-contract prober.

Runs every read/parse the engine relies on against the real workspace and
reports ALL failures at once, instead of one preflight error per UI round
trip. Optionally (--write) performs the single-device assignment probe.

Usage, from msp-onboarding/ with token.yaml present:
    .venv/bin/python3 verify_live_contract.py --tenant test-tenant-1 \
        --serial CNK4K5104W --key AKJHHDX9BD7JHMA7
    ... --write        # phase C: real single-device assignment + poll
    MSP_API_LOG=api-verification.log ...   # keep the raw wire log too
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import asdict

from msp_onboarding.engine import OnboardingEngine
from msp_onboarding.parser import parse_yaml_manifest
from msp_onboarding.pycentral_adapter import PycentralAdapter
from msp_onboarding.store import MemoryStore

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", required=True, help="tenant workspace name")
    ap.add_argument("--serial", required=True, help="device serial number")
    ap.add_argument("--key", required=True, help="subscription key")
    ap.add_argument("--write", action="store_true", help="run the assignment probe")
    args = ap.parse_args()

    adapter = PycentralAdapter("token.yaml")

    print("\n== Phase A: adapter reads, raw vs parsed ==")
    tenants = adapter.list_tenants()
    tenant = next((t for t in tenants if t.workspace_name == args.tenant), None)
    check("tenant found by name", tenant is not None,
          f"{len(tenants)} tenants listed")
    if tenant is None:
        print([t.workspace_name for t in tenants])
        return finish()
    print(f"  tenant: {asdict(tenant)}")
    check("tenant ownership parsed", tenant.ownership == "MSP_OWNED_INVENTORY",
          repr(tenant.ownership))
    check("tenant id is 36-char uuid", len(tenant.workspace_id) == 36,
          tenant.workspace_id)

    device = adapter.resolve_device_by_serial(args.serial)
    print(f"  device: {asdict(device)}")
    check("device serial matches request", device.serial_number == args.serial)
    check("device management parsed", device.management == "MSP",
          repr(device.management))
    check("device assigned_state parsed", device.assigned_state == "UNASSIGNED",
          repr(device.assigned_state))
    check("device refs are str-or-None", all(
        v is None or isinstance(v, str)
        for v in (device.in_use_workspace, device.tenant_workspace_id,
                  device.subscription)))

    subscription = adapter.resolve_subscription(args.key)
    print(f"  subscription: {asdict(subscription)}")
    check("subscription key matches request", subscription.key == args.key)
    check("subscription status parsed", subscription.status == "STARTED",
          repr(subscription.status))
    check("subscription product_type parsed",
          subscription.product_type == "DEVICE", repr(subscription.product_type))
    check("available_quantity is digit string",
          subscription.available_quantity.isdigit(),
          repr(subscription.available_quantity))
    check("quantity is digit string", subscription.quantity.isdigit(),
          repr(subscription.quantity))
    for label, value in (("start_date", subscription.start_date),
                         ("end_date", subscription.end_date)):
        ok = value is None or (len(value) == 10 and value[4] == value[7] == "-")
        check(f"subscription {label} is YYYY-MM-DD or absent", ok, repr(value))

    services = adapter.list_eligible_services(tenant.workspace_id)
    print(f"  services: {[asdict(s) for s in services]}")
    check("at least one eligible service", bool(services))
    if not services:
        return finish()
    service = services[0]

    print("\n== Phase B: engine.plan preflight, all errors at once ==")
    manifest_yaml = f"""
version: 2
mode: existing
tenants:
  - name: {tenant.workspace_name}
    workspace_id: {tenant.workspace_id}
    service:
      service_manager_id: {service.service_manager_id}
      region: {service.region}
devices:
  - serial_number: {args.serial}
    tenant: {tenant.workspace_name}
    subscription_key: {args.key}
"""
    manifest = parse_yaml_manifest(manifest_yaml)
    engine = OnboardingEngine(adapter, MemoryStore())
    plan = engine.plan(manifest)
    for error in plan.errors:
        print(f"  preflight error: {error.path} [{error.code}] {error.message}")
    check("preflight clean", not plan.errors, f"{len(plan.errors)} error(s)")
    statuses = [(g.tenant_name, g.status) for g in plan.tenant_groups]
    check("tenant group runnable",
          all(status == "pending" for _, status in statuses), repr(statuses))

    if args.write and not plan.errors:
        print("\n== Phase C: single-device assignment probe ==")
        transaction = adapter.assign_devices(
            [device.glp_id], tenant.workspace_id, service.service_manager_id,
            service.region,
        )
        print(f"  device transaction accepted: {transaction}")
        result = poll(adapter, transaction)
        check("device assignment succeeded", device.glp_id in result.succeeded_ids,
              f"succeeded={result.succeeded_ids} failed={result.failed_ids}")
        transaction = adapter.assign_subscriptions(
            [(device.glp_id, subscription.subscription_id)],
        )
        print(f"  subscription transaction accepted: {transaction}")
        result = poll(adapter, transaction)
        check("subscription assignment succeeded",
              device.glp_id in result.succeeded_ids,
              f"succeeded={result.succeeded_ids} failed={result.failed_ids}")

    return finish()


def poll(adapter: PycentralAdapter, transaction: str):
    import time

    from msp_onboarding.adapter import AdapterError

    for _ in range(30):
        try:
            return adapter.poll_transaction(transaction)
        except AdapterError as exc:
            if not exc.retryable:
                raise
            time.sleep(2)
    raise RuntimeError("transaction did not complete within 60s")


def finish() -> int:
    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed"
          + (f"; FAILED: {failed}" if failed else " — all green"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
