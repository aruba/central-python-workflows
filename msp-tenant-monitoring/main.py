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

from rich.console import Console

from msp_monitoring.collector import collect_overview
from msp_monitoring.config import ConfigError, resolve_token_yaml
from msp_monitoring.export import write_csv, write_json
from msp_monitoring.interactive import run_interactive
from msp_monitoring.models import TenantSummary
from msp_monitoring.reporter import render_overview
from msp_monitoring.sources.base import GLPSource, TenantDataSource


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


_NOISY_LOGGERS = ("pycentral", "central", "urllib3", "requests", "httpx", "NEW CENTRAL BASE")


def _quiet_third_party() -> None:
    """Re-silence known-noisy loggers.

    Called after MSPBase construction because pycentral's console_logger sets
    the logger level to DEBUG at instantiation time, overriding any earlier
    silencing.
    """
    for _name in _NOISY_LOGGERS:
        logging.getLogger(_name).setLevel(logging.ERROR)


async def _run(args: argparse.Namespace) -> None:
    console = Console()
    one_shot = args.export_json is not None or args.export_csv is not None
    with select_source() as (source, glp_source):
        if not args.verbose:
            # Re-silence after MSPBase.__init__ resets logger levels
            _quiet_third_party()
        if one_shot:
            results = await collect_overview(
                source,
                tenant_filter=args.tenant,
                glp_source=glp_source,
            )
            render_overview(console, results)
            if args.export_json is not None:
                write_json(results, args.export_json)
                console.print(f"[green]✓[/green] JSON exported to {args.export_json}")
            if args.export_csv is not None:
                write_csv(results, args.export_csv)
                console.print(f"[green]✓[/green] CSV exported to {args.export_csv}")
        else:
            await run_interactive(
                source,
                glp_source,
                tenant_filter=args.tenant,
                console=console,
            )


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

    if args.verbose:
        logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.DEBUG)
    else:
        logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.WARNING)
        # Silence known-noisy third-party loggers that may emit below WARNING
        for _noisy in ("pycentral", "central", "urllib3", "requests", "httpx", "NEW CENTRAL BASE"):
            logging.getLogger(_noisy).setLevel(logging.ERROR)

    try:
        asyncio.run(_run(args))
    except ConfigError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
