#!/usr/bin/env python3
"""Agent-friendly command-line entry point for MSP Workbench."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from difflib import get_close_matches
from io import StringIO
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any

from msp_workbench.adapter import AdapterError, AuthenticationRequiredError
from msp_workbench.demo_adapter import DemoAdapter
from msp_workbench.engine import OnboardingEngine
from msp_workbench.monitor import (
    export_fieldnames,
    export_rows,
    find_monitored_tenant,
    overview as monitor_overview,
    parse_include,
    tenant_detail,
)
from msp_workbench.models import strip_subscription_ids
from msp_workbench.parser import ParseError, parse_yaml_manifest
from msp_workbench.pycentral_adapter import PycentralAdapter
from msp_workbench.burndown_snapshot import BurndownUsageError, load_snapshot
from msp_workbench.burndown_projection import (
    HORIZON_MONTHS,
    export_csv as burndown_csv,
    listing as list_burndown,
    project as project_burndown,
    public as public_burndown,
    validate_filters as validate_burndown_filters,
)
from msp_workbench.store import MemoryStore


JSON_OPTIONS = {"sort_keys": True, "separators": (",", ":")}
MONITOR_SECTIONS = ("sites", "monitored_devices", "clients", "alerts")


class CliError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        hint: str | None = None,
        *,
        errors: list[dict] | None = None,
    ):
        self.status = status
        self.code = code
        self.message = message
        self.hint = hint
        self.errors = errors
        super().__init__(message)


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliError(2, "usage_error", message, f"Run '{self.prog} --help'.")


def _command(commands, name: str, description: str, output: str, example: str):
    return commands.add_parser(
        name,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=f"{description}\n\nOutput keys: {output}",
        epilog=f"Example:\n  {example}",
    )


def _parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(
        description="MSP Workbench CLI. Reads token.yaml from the current directory unless --demo is used.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--demo", action="store_true", help="Use deterministic demo data")
    parser.add_argument("--verbose", action="store_true", help="Show pycentral INFO logs on stderr")
    parser.add_argument("--format", choices=("json", "table"), default="json")
    parser.add_argument("--fields", help="Comma-separated dotted paths within each list item, e.g. workspace_name,address.city")
    parser.add_argument(
        "--limit",
        action="append",
        default=[],
        metavar="N|SECTION=N",
        help="Cap every list or one named list section; repeatable",
    )
    parser.add_argument("--out", help="Write output to this path and print a receipt")
    commands = parser.add_subparsers(dest="command", required=True)

    list_parser = _command(
        commands, "list", "Reads one discovery collection from GLP.",
        "the selected collection", "workbench.py --demo list tenants",
    )
    list_parser.add_argument(
        "selector", choices=("tenants", "services", "devices", "subscriptions")
    )
    plan_parser = _command(
        commands, "plan", "Reads and validates a YAML manifest without writing to GLP.",
        "job_id, manifest_hash, plan_hash, mode, tenant_groups, devices, errors, created_at",
        "workbench.py --demo plan samples/new_tenant.yaml",
    )
    plan_parser.add_argument("manifest")
    run_parser = _command(
        commands, "run", "Reads a YAML manifest, plans it, and executes the confirmed job.",
        "activity, created_at, devices, ended_at, id, last_error, manifest_hash, mode, plan, plan_hash, started_at, status, steps, stop_requested, tenant_groups, updated_at",
        "workbench.py --demo run samples/new_tenant.yaml --yes",
    )
    run_parser.add_argument("manifest")
    run_parser.add_argument("--yes", action="store_true", help="Confirm execution")

    monitor_parser = _command(
        commands, "monitor", "Reads the merged read-only tenant monitoring backend.",
        "depends on the monitor subcommand", "workbench.py --demo monitor overview",
    )
    monitor_commands = monitor_parser.add_subparsers(dest="monitor_command", required=True)
    _command(
        monitor_commands, "overview", "Reads the monitored tenant overview.",
        "tenants, totals, fetched_at", "workbench.py --demo monitor overview",
    )
    tenant_parser = _command(
        monitor_commands, "tenant",
        "Reads live monitoring detail for an exact tenant name or workspace ID.",
        "workspace_id, workspace_name, sites, monitored_devices, clients, alerts",
        "workbench.py --demo monitor tenant 'Acme Corp' --sites --alerts",
    )
    tenant_parser.add_argument("tenant")
    for flag in MONITOR_SECTIONS:
        tenant_parser.add_argument(f"--{flag.replace('_', '-')}", action="store_true")
    export_parser = _command(
        monitor_commands, "export",
        "Freshly reads the monitored tenant overview for JSON or CSV export.",
        "JSON: tenants, totals, fetched_at; CSV: tenant, sites, degraded_sites, total_devices, critical_alerts",
        "workbench.py --demo monitor export --format csv --out tenants.csv",
    )
    export_parser.add_argument("--format", choices=("csv", "json"), dest="export_format")
    export_parser.add_argument("--out", dest="export_out")
    subscriptions = _command(
        commands, "subscriptions", "Reads subscription coverage and utilization.",
        "data and snapshot/call metadata", "workbench.py --demo subscriptions burndown",
    )
    subscription_commands = subscriptions.add_subparsers(dest="subscriptions_command", required=True)
    burndown_parser = _command(
        subscription_commands, "burndown", "Reads a single source snapshot and projects burndown scope.",
        "horizon_months, months, kpis, tenant_options, fetched_at", "workbench.py --demo subscriptions burndown --scope msp",
    )
    burndown_parser.add_argument("--scope", choices=("msp", "tenant", "tenants", "all"))
    burndown_parser.add_argument("--tenant", action="append", default=[])
    burndown_parser.add_argument("--months", type=int, choices=HORIZON_MONTHS, default=12)
    burndown_parser.add_argument("--view", choices=("losing_cover", "unused", "evaluations"), default="losing_cover")
    burndown_parser.add_argument("--lifecycle", choices=("current", "expired", "all"), default="current")
    burndown_parser.add_argument("--search", default="")
    burndown_parser.add_argument("--month")
    burndown_parser.add_argument("--format", choices=("json", "csv"), dest="burndown_format", default="json")
    burndown_parser.add_argument("--out", dest="burndown_out")
    return parser


def _configure_logging(verbose: bool) -> None:
    # ponytail: pycentral installs its own stderr handlers with explicit levels, so global disable is the only reliable switch; revisit if the CLI ever wants its own logging.
    logging.disable(logging.NOTSET if verbose else logging.WARNING)


def _adapter(demo: bool):
    if demo:
        return DemoAdapter()
    if not os.path.isfile("token.yaml"):
        raise CliError(
            1,
            "token_not_found",
            "Live mode requires token.yaml in the current directory",
            "Create token.yaml (see msp-workbench/token.yaml.example) or pass --demo.",
        )
    return PycentralAdapter("token.yaml")


def _list(adapter, selector: str) -> list[dict]:
    if selector == "tenants":
        values = adapter.list_tenants()
    elif selector == "services":
        values = adapter.list_eligible_services(None)
    elif selector == "devices":
        values = adapter.list_available_devices()
    else:
        values = adapter.list_subscriptions()
    return [asdict(item) for item in values]


def _limits(values: list[str], sections: set[str]) -> tuple[int | None, dict[str, int]]:
    default = None
    overrides = {}
    for value in values:
        section, separator, raw_limit = value.partition("=")
        if not separator:
            raw_limit, section = section, ""
        try:
            limit = int(raw_limit)
        except ValueError:
            raise CliError(2, "invalid_limit", f"Invalid limit: {value}", "Use N or section=N.")
        if limit < 0:
            raise CliError(2, "invalid_limit", "Limits cannot be negative", "Use zero or a positive integer.")
        if section and section not in sections:
            raise CliError(
                2, "invalid_limit", f"Unknown list section: {section}",
                "Valid sections: " + ", ".join(sorted(sections)),
            )
        if section:
            overrides[section] = limit
        else:
            default = limit
    return default, overrides


def _cap_lists(
    data: dict[str, Any], values: list[str], required: tuple[str, ...] = (),
) -> tuple[dict[str, Any], dict[str, dict[str, int | bool]]]:
    sections = {key for key, value in data.items() if isinstance(value, list)} | set(required)
    default, overrides = _limits(values, sections)
    meta = {}
    for section in sections:
        rows = data.get(section)
        total = len(rows) if isinstance(rows, list) else 0
        limit = overrides.get(section, default)
        returned = total if limit is None else min(total, limit)
        if isinstance(rows, list) and limit is not None:
            data[section] = rows[:limit]
        meta[section] = {"total": total, "returned": returned, "truncated": returned < total}
    return data, meta


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(value, dict):
        return {prefix: value}
    flattened = {}
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(child, dict):
            flattened.update(_flatten(child, path))
        else:
            flattened[path] = child
    return flattened


def _lookup(value: dict[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _assign(target: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def _project(value: dict[str, Any], paths: list[str]) -> dict[str, Any]:
    result = {}
    for path in paths:
        found, selected = _lookup(value, path)
        if found:
            _assign(result, path, selected)
    return result


def _fields(data: dict[str, Any], raw: str | None) -> dict[str, Any]:
    if not raw:
        return data
    paths = [path.strip() for path in raw.split(",") if path.strip()]
    valid = set(data)
    for key, value in data.items():
        if isinstance(value, dict):
            valid.update(_flatten(value, key))
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            valid.update(_flatten(value[0]))
    unknown = [path for path in paths if path not in valid]
    if unknown:
        raise CliError(
            2, "unknown_field", "Unknown field path: " + ", ".join(unknown),
            "Valid keys: " + ", ".join(sorted(valid)),
        )
    result = _project(data, paths)
    for section, rows in data.items():
        if not isinstance(rows, list):
            continue
        if section in paths:
            result[section] = rows
            continue
        row_paths = [
            path for path in paths
            if any(_lookup(row, path)[0] for row in rows if isinstance(row, dict))
        ]
        if row_paths:
            result[section] = [
                _project(row, row_paths) if isinstance(row, dict) else row for row in rows
            ]
    return result


def _cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, **JSON_OPTIONS)
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _table(data: dict[str, Any]) -> str:
    blocks = []
    scalars = {key: value for key, value in data.items() if not isinstance(value, list)}
    if scalars:
        pairs = list(_flatten(scalars).items())
        width = max(len(key) for key, _ in pairs)
        blocks.append("\n".join(f"{key:<{width}}  {_cell(value)}" for key, value in pairs))
    for section, rows in data.items():
        if not isinstance(rows, list):
            continue
        flat_rows = [_flatten(row) if isinstance(row, dict) else {"value": row} for row in rows]
        headers = list(dict.fromkeys(key for row in flat_rows for key in row))
        lines = [f"[{section}]"]
        if headers:
            widths = [
                max(len(header), *[len(_cell(row.get(header))) for row in flat_rows])
                for header in headers
            ]
            lines.append("  ".join(f"{header:<{width}}" for header, width in zip(headers, widths)))
            lines.extend(
                "  ".join(
                    f"{_cell(row.get(header)):<{width}}"
                    for header, width in zip(headers, widths)
                )
                for row in flat_rows
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _json(value: Any) -> str:
    return json.dumps(value, **JSON_OPTIONS)


def _write(document: str, path: str, rows: int) -> None:
    content = document + ("" if document.endswith("\n") else "\n")
    try:
        Path(path).write_text(content, encoding="utf-8")
    except OSError as exc:
        raise CliError(
            1,
            "output_not_writable",
            f"Cannot write {path}: {exc.strerror or exc}",
            "Check the parent directory exists and is writable.",
        )
    print(_json({"bytes": len(content.encode()), "path": path, "rows": rows}))


def _render(data: dict[str, Any], meta: dict[str, Any], args) -> None:
    rows = sum(len(value) for value in data.values() if isinstance(value, list))
    if (args.format or "json") == "json":
        document = _json({"data": data, "meta": meta})
    else:
        document = _table(data)
    if args.out:
        _write(document, args.out, rows)
    else:
        print(document)
    if args.format == "table":
        print(_json(meta), file=sys.stderr)


def _error(exc: Exception) -> tuple[int, dict[str, Any]]:
    if isinstance(exc, CliError):
        error = {"code": exc.code, "message": exc.message, "hint": exc.hint}
        if exc.errors is not None:
            error["errors"] = exc.errors
        return exc.status, error
    if isinstance(exc, ParseError):
        return 1, {
            "code": "manifest_invalid",
            "message": str(exc),
            "hint": "See samples/*.yaml for the schema-v2 manifest shape.",
            "errors": [asdict(error) for error in exc.errors],
        }
    if isinstance(exc, AdapterError):
        hint = "Check token.yaml and MSP credentials." if isinstance(exc, AuthenticationRequiredError) else None
        return 4, {"code": exc.code, "message": exc.message, "hint": hint}
    if isinstance(exc, LookupError):
        return 3, {"code": "not_found", "message": str(exc), "hint": "Check the exact GLP tenant name or ID."}
    if isinstance(exc, BurndownUsageError):
        return 2, {"code": "usage_error", "message": str(exc), "hint": "Check subscriptions burndown flags."}
    return 1, {"code": exc.__class__.__name__.lower(), "message": str(exc), "hint": None}


def _manifest(engine: OnboardingEngine, path: str):
    try:
        with open(path, encoding="utf-8") as manifest_file:
            content = manifest_file.read()
    except (FileNotFoundError, IsADirectoryError):
        raise CliError(
            1,
            "manifest_not_found",
            f"Manifest not found: {path}",
            "Pass the path to a version 2 YAML manifest; see samples/.",
        )
    except OSError as exc:
        raise CliError(
            1,
            "manifest_not_readable",
            f"Cannot read manifest {path}: {exc.strerror or exc}",
            "Check the file permissions.",
        )
    return engine.plan(parse_yaml_manifest(content))


def _confirm(plan, yes: bool) -> None:
    if yes:
        return
    print(f"Run onboarding job {plan.job_id}? [y/N] ", end="", file=sys.stderr, flush=True)
    if input().lower() not in ("y", "yes"):
        print(file=sys.stderr)
        raise CliError(2, "confirmation_refused", "Run was not confirmed.", "Pass --yes to confirm execution.")


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        _configure_logging(args.verbose)
        if args.command == "run" and not args.yes and not sys.stdin.isatty():
            raise CliError(
                2, "confirmation_required", "Run requires confirmation.",
                "Pass --yes to confirm execution.",
            )
        adapter = _adapter(args.demo)
        fetched_at = adapter.now().isoformat()
        command_meta: dict[str, Any] = {}

        if args.command == "subscriptions":
            scope = args.scope or ("tenant" if len(set(args.tenant)) == 1 else "tenants" if args.tenant else "msp")
            validate_burndown_filters(view=args.view, lifecycle_value=args.lifecycle, month=args.month, q=args.search)
            current = project_burndown(load_snapshot(adapter, 1), scope=scope, tenants=args.tenant, months=args.months, cache="miss")
            fetched_at = current["fetched_at"]
            command_meta = dict(current["meta"])
            if args.burndown_format == "csv":
                args.out = args.burndown_out or args.out
                raw_document = burndown_csv(current, args.view, month=args.month, lifecycle_value=args.lifecycle, q=args.search)
                reader = csv.DictReader(StringIO(raw_document))
                csv_rows, sections = _cap_lists({"rows": list(reader)}, args.limit)
                fieldnames = list(reader.fieldnames or [])
                if args.fields:
                    requested = [field.strip().removeprefix("rows.") for field in args.fields.split(",") if field.strip()]
                    unknown = [field for field in requested if field not in fieldnames]
                    if unknown:
                        raise CliError(2, "unknown_field", "Unknown CSV field: " + ", ".join(unknown), "Valid fields: " + ", ".join(fieldnames))
                    fieldnames = requested
                output = StringIO()
                writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
                writer.writeheader()
                writer.writerows(csv_rows["rows"])
                document = output.getvalue()
                rows = len(csv_rows["rows"])
                if args.out: _write(document, args.out, rows)
                else: print(document, end="")
                print(_json({"demo": args.demo, **command_meta, **sections}), file=sys.stderr)
                return 0
            if args.view == "losing_cover":
                data = public_burndown(current)
                data.pop("meta", None)
            else: data = list_burndown(current, args.view, args.lifecycle, args.search, full=True)
            if args.view != "losing_cover":
                command_meta = dict(data.pop("meta"))
            data, sections = _cap_lists(data, args.limit)
            if args.view != "losing_cover" and "rows" in sections:
                command_meta.update(sections["rows"])
            args.out = args.burndown_out or args.out
        elif args.command == "list":
            data, sections = _cap_lists(
                strip_subscription_ids({args.selector: _list(adapter, args.selector)}),
                args.limit,
            )
        elif args.command == "monitor" and args.monitor_command == "overview":
            current = monitor_overview(adapter)
            fetched_at = current.fetched_at
            data, sections = _cap_lists(asdict(current), args.limit)
        elif args.command == "monitor" and args.monitor_command == "tenant":
            current = monitor_overview(adapter)
            tenant = find_monitored_tenant(current, args.tenant, by_name=True)
            if tenant is None:
                names = [row.workspace_name for row in current.tenants]
                suggestions = get_close_matches(args.tenant, names) or names
                raise CliError(
                    3, "tenant_not_found", f"Monitored tenant not found: {args.tenant}",
                    "Try: " + ", ".join(suggestions),
                )
            selected = [section for section in MONITOR_SECTIONS if getattr(args, section)]
            include = parse_include(",".join(selected))
            data = asdict(tenant_detail(adapter, tenant.workspace_id, include))
            data.update(workspace_id=tenant.workspace_id, workspace_name=tenant.workspace_name)
            data, sections = _cap_lists(data, args.limit, MONITOR_SECTIONS)
        elif args.command == "monitor" and args.monitor_command == "export":
            current = monitor_overview(adapter, fresh=True)
            fetched_at = current.fetched_at
            export_format = args.export_format or "json"
            args.out = args.export_out or args.out
            if export_format == "csv":
                csv_data, sections = _cap_lists({"tenants": export_rows(current)}, args.limit)
                csv_data = _fields(csv_data, args.fields)
                fieldnames = export_fieldnames
                if args.fields:
                    requested = {field.strip() for field in args.fields.split(",")}
                    if "tenants" not in requested:
                        fieldnames = tuple(field for field in export_fieldnames if field in requested)
                output = StringIO()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_data["tenants"])
                meta = {"demo": args.demo, "fetched_at": fetched_at, **command_meta, **sections}
                document = output.getvalue()
                if args.out:
                    _write(document, args.out, sections["tenants"]["returned"])
                else:
                    print(document, end="")
                print(_json(meta), file=sys.stderr)
                return 0
            args.format = "json"
            data, sections = _cap_lists(asdict(current), args.limit)
        else:
            with MemoryStore() as store:
                engine = OnboardingEngine(adapter, store)
                plan = _manifest(engine, args.manifest)
                if args.command == "run":
                    _confirm(plan, args.yes)
                    engine.start(plan.job_id)
                    engine.drain()
                    data = engine.get(plan.job_id)
                else:
                    data = plan.to_dict()
                data, sections = _cap_lists(strip_subscription_ids(data), args.limit)

        data = _fields(data, args.fields)
        meta = {"demo": args.demo, "fetched_at": fetched_at, **command_meta, **sections}
        _render(data, meta, args)
        return 0
    except Exception as exc:
        status, error = _error(exc)
        print(_json(error), file=sys.stderr)
        return status


if __name__ == "__main__":
    raise SystemExit(main())
