#!/usr/bin/env python3
"""
Generate Consolidated Report from Device Command Outputs

This script processes JSON output files from troubleshooting commands
and generates easy-to-read consolidated reports in multiple formats.

Now uses the new modular reports module for cleaner code.
"""

import json
import argparse
from .report_generators import generate_all_reports


def main():
    """Main entry point for standalone report generation."""
    parser = argparse.ArgumentParser(
        description="Generate consolidated reports from device troubleshooting JSON output"
    )
    parser.add_argument(
        "json_file", help="JSON file containing troubleshooting results"
    )
    args = parser.parse_args()

    # Load JSON file
    with open(args.json_file, "r") as f:
        output_data = json.load(f)

    # Generate all reports using the new modular system
    generate_all_reports(output_data)


if __name__ == "__main__":
    main()
