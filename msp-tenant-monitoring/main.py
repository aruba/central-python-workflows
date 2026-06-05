from __future__ import annotations
import sys

if sys.version_info < (3, 10):
    sys.exit(
        f"MSP Monitoring requires Python 3.10+. "
        f"Detected {sys.version.split()[0]}. "
        f"Please upgrade or activate a suitable virtualenv."
    )

import argparse
import asyncio
import logging
from contextlib import contextmanager
from typing import Iterator

from msp_monitoring.collector import aggregate_totals, collect_overview
from msp_monitoring.config import ConfigError, resolve_token_yaml
from msp_monitoring.export import write_csv, write_json
from msp_monitoring.models import TenantSummary
from msp_monitoring.sources.base import GLPSource, TenantDataSource


def _print_overview(results: list[TenantSummary]) -> None:
    totals = aggregate_totals(results)
    print("MSP Overview - Cross-Tenant Network Overview\n")
    print("Summary:")
    print(f"- Total tenants: {totals['tenants']}")
    print(f"- Total sites: {totals['sites']}")
    print(f"- Total devices: {totals['devices']}")
    for item in results:
        print()
        print(f"Tenant: {item.tenant_name}")
        print(f"- Sites: {item.total_sites}")
        print(f"- Devices: {item.device_health.get('total', 0)}")
        print(f"- Alerts (critical): {item.alerts.get('critical', 0)}")

log = logging.getLogger(__name__)


@contextmanager
def select_source() -> Iterator[tuple[TenantDataSource, GLPSource]]:
    """Yield (tenant_source, glp_source). Owns the shared MSPBase lifecycle.

    Constructs one shared MSPBase, injects it into both real sources, and
    closes it on exit.
    """
    from pycentral import MSPBase  # type: ignore[import]
    from msp_monitoring.sources.pycentral_source import PyCentralSource
    from msp_monitoring.sources.glp_source import GLPWorkspaceSource

    token_yaml = resolve_token_yaml()
    msp = MSPBase(token_info=str(token_yaml))
    with msp:
        yield PyCentralSource(msp), GLPWorkspaceSource(msp)


async def _run(args: argparse.Namespace) -> None:
    with select_source() as (source, glp_source):
        results = await collect_overview(
            source,
            tenant_filter=args.tenant,
            glp_source=glp_source,
        )
    _print_overview(results)
    if args.export_json is not None:
        write_json(results, args.export_json)
        logging.getLogger(__name__).info("JSON exported to %s", args.export_json)
    if args.export_csv is not None:
        write_csv(results, args.export_csv)
        logging.getLogger(__name__).info("CSV exported to %s", args.export_csv)


def main() -> None:
    parser = argparse.ArgumentParser(description="MSP cross-tenant network overview")
    parser.add_argument("--tenant", metavar="NAME_OR_ID", help="Filter to a single tenant")
    parser.add_argument("--verbose", action="store_true", help="Enable DEBUG logging")
    parser.add_argument(
        "--export-json",
        nargs="?",
        const="output/sample_output.json",
        metavar="PATH",
        help="Export results to JSON (default: output/sample_output.json)",
    )
    parser.add_argument(
        "--export-csv",
        nargs="?",
        const="output/sample_output.csv",
        metavar="PATH",
        help="Export results to CSV (default: output/sample_output.csv)",
    )
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=level)

    try:
        asyncio.run(_run(args))
    except ConfigError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
