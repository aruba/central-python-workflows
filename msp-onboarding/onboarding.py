#!/usr/bin/env python3
"""Command-line entry point for MSP onboarding."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
import sys

from msp_onboarding.adapter import AdapterError
from msp_onboarding.demo_adapter import DemoAdapter
from msp_onboarding.engine import OnboardingEngine
from msp_onboarding.parser import ParseError, parse_yaml_manifest
from msp_onboarding.pycentral_adapter import PycentralAdapter
from msp_onboarding.store import MemoryStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MSP onboarding workflow")
    parser.add_argument("--demo", action="store_true", help="Use deterministic demo data")
    commands = parser.add_subparsers(dest="command", required=True)
    list_parser = commands.add_parser("list")
    list_parser.add_argument(
        "selector", choices=("tenants", "services", "devices", "subscriptions")
    )
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("manifest")
    run_parser = commands.add_parser("run")
    run_parser.add_argument("manifest")
    run_parser.add_argument("--yes", action="store_true", help="Confirm execution")
    return parser


def _adapter(demo: bool):
    if demo:
        return DemoAdapter()
    if not os.path.isfile("token.yaml"):
        raise FileNotFoundError("Live mode requires token.yaml in the current directory")
    return PycentralAdapter("token.yaml")


def _print(value: object) -> None:
    print(json.dumps(value, sort_keys=True))


def _list(adapter, selector: str) -> list[dict]:
    if selector == "tenants":
        return [asdict(item) for item in adapter.list_tenants()]
    if selector == "services":
        return [asdict(item) for item in adapter.list_eligible_services(None)]
    if selector == "devices":
        return [asdict(item) for item in adapter.list_available_devices()]
    subscriptions = [asdict(item) for item in adapter.list_subscriptions()]
    for subscription in subscriptions:
        subscription["key"] = "***"
    return subscriptions


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        adapter = _adapter(args.demo)
        if args.command == "list":
            _print(_list(adapter, args.selector))
            return 0
        with MemoryStore() as store:
            engine = OnboardingEngine(adapter, store)
            if args.command == "plan":
                with open(args.manifest, encoding="utf-8") as manifest_file:
                    plan = engine.plan(parse_yaml_manifest(manifest_file.read()))
                _print(plan.to_dict())
                return 0
            if args.command == "run":
                with open(args.manifest, encoding="utf-8") as manifest_file:
                    plan = engine.plan(parse_yaml_manifest(manifest_file.read()))
                if not args.yes:
                    try:
                        print(
                            f"Run onboarding job {plan.job_id}? [y/N] ",
                            end="",
                            file=sys.stderr,
                            flush=True,
                        )
                        confirmed = input()
                    except EOFError:
                        confirmed = ""
                    if confirmed.lower() not in ("y", "yes"):
                        print("Run requires confirmation.", file=sys.stderr)
                        return 1
                engine.start(plan.job_id)
                engine.drain()
                call_stats = getattr(adapter, "call_stats", None)
                if callable(call_stats):
                    print(
                        "GLP call summary: "
                        + json.dumps(call_stats(), sort_keys=True),
                        file=sys.stderr,
                    )
                _print(engine.get(plan.job_id))
                return 0
    except (AdapterError, FileNotFoundError, KeyError, ParseError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
