"""Customer-facing Classic Central alert extraction command."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from alert_inventory.extraction_command import (
    ExtractionCommandError,
    ExtractionSummary,
    extract_to_file,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract Classic Central alerts."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser(
        "extract",
        help="retrieve enabled alert settings into a JSON file",
    )
    extract.add_argument(
        "--output",
        type=Path,
        metavar="PATH",
        help="write to PATH instead of the timestamped file in this directory",
    )
    extract.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing --output file",
    )
    return parser


def _print_summary(summary: ExtractionSummary) -> None:
    print(f"Created: {summary.output_path}")
    print(f"Schema version: {summary.schema_version}")
    print(f"Reported total: {summary.reported_total}")
    print(f"Retrieved: {summary.retrieved}")
    print(f"Enabled: {summary.enabled}")
    print(f"Disabled: {summary.disabled}")
    for alert_type in summary.enabled_types:
        print(f"Enabled type: {alert_type}")
    print(
        "Warning: The JSON contains sensitive customer configuration "
        "and is not safe for public sharing."
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested Alert Inventory command."""

    parser = _build_parser()
    arguments = parser.parse_args(argv)
    if arguments.overwrite and arguments.output is None:
        parser.error("--overwrite requires --output")

    try:
        summary = extract_to_file(
            output=arguments.output,
            overwrite=arguments.overwrite,
        )
    except ExtractionCommandError:
        print("Extraction failed.", file=sys.stderr)
        return 1

    _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
