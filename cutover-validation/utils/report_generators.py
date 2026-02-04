"""Report generation orchestration."""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from utils.reports_formatters import generate_device_overview_table, HTML_CSS_TEMPLATE


def parse_troubleshooting_data(output_data: List[Dict]) -> Dict[str, Any]:
    """Parse troubleshooting results from output_data."""
    try:
        if not isinstance(output_data, list) or len(output_data) < 2:
            print("Error: Invalid JSON format")
            return {"summary": None, "devices": {}}

        summary = None
        devices_data = {}

        for item in output_data:
            if item.get("type") == "summary":
                summary = item
            elif item.get("type") == "device_results":
                serial = item.get("device_serial")
                if serial:
                    processed_results = []
                    for result in item.get("troubleshooting_results", []):
                        output = result.get("output", {})
                        processed_results.append(
                            {
                                "command": output.get("command", "N/A"),
                                "response": output.get("response", "N/A"),
                                "status": result.get("status", "UNKNOWN"),
                            }
                        )
                    devices_data[serial] = {
                        "device_info": item.get("device_info", {}),
                        "commands": processed_results,
                    }

        return {"summary": summary, "devices": devices_data}
    except Exception as e:
        print(f"Error loading output_data: {e}")
        return {"summary": None, "devices": {}}


def generate_markdown_report(data: Dict[str, Any], output_file: str) -> None:
    """Generate a Markdown report."""
    summary = data.get("summary")
    devices_data = data.get("devices", {})

    with open(output_file, "w") as f:
        f.write("# Cutover Validation Report\n\n")

        if summary:
            f.write(f"**Generated:** {summary.get('generated_at', 'N/A')}\n\n")
            f.write(f"**Total Devices:** {summary.get('total_devices', 0)}\n\n")
            f.write(
                f"**Total Commands Executed:** {summary.get('total_commands_executed', 0)}\n\n"
            )

        f.write("---\n\n")
        f.write(
            generate_device_overview_table(
                summary.get("devices_overview", []), "markdown"
            )
        )
        f.write("---\n\n")

        # Table of contents
        f.write("## Table of Contents\n\n")
        for idx, serial in enumerate(sorted(devices_data.keys()), 1):
            device_data = devices_data[serial]
            commands_count = len(device_data["commands"])
            f.write(
                f"{idx}. [Device {serial}](#device-{serial.lower()}) ({commands_count} commands)\n"
            )
        f.write("\n---\n\n")

        # Device details
        for serial in sorted(devices_data.keys()):
            device_data = devices_data[serial]
            device_info = device_data["device_info"]
            commands = device_data["commands"]

            f.write(f"## Device {serial}\n\n")
            f.write(f"**Serial Number:** `{serial}`\n\n")
            f.write(f"**Device Name:** {device_info.get('name', 'N/A')}\n\n")
            f.write(f"**Model:** {device_info.get('model', 'N/A')}\n\n")
            f.write(f"**IP Address:** {device_info.get('ip_address', 'N/A')}\n\n")
            f.write(f"**Site:** {device_info.get('site', 'N/A')}\n\n")
            f.write(f"**Commands Executed:** {len(commands)}\n\n")

            for idx, cmd_data in enumerate(commands, 1):
                f.write(f"### Command {idx}: `{cmd_data['command']}`\n\n")
                f.write(f"**Status:** {cmd_data['status']}\n\n")
                f.write("**Response:**\n\n")
                f.write("```\n")
                f.write(cmd_data["response"])
                f.write("\n```\n\n")
                f.write("---\n\n")

    print(f"✓ Markdown report generated: {output_file}")


def generate_html_report(data: Dict[str, Any], output_file: str) -> None:
    """Generate an HTML report with styling."""
    summary = data.get("summary")
    devices_data = data.get("devices", {})

    with open(output_file, "w") as f:
        f.write(HTML_CSS_TEMPLATE)
        f.write("""    <div class="header">
        <h1>🔧 Cutover Validation Report</h1>
        <div class="meta">
""")
        if summary:
            f.write(
                f"            <strong>Generated:</strong> {summary.get('generated_at', 'N/A')}<br>\n"
            )
            f.write(
                f"            <strong>Total Devices:</strong> {summary.get('total_devices', 0)}<br>\n"
            )
            f.write(
                f"            <strong>Total Commands:</strong> {summary.get('total_commands_executed', 0)}\n"
            )
        f.write("""        </div>
    </div>

""")

        f.write(
            generate_device_overview_table(summary.get("devices_overview", []), "html")
        )

        # Device details
        for serial in sorted(devices_data.keys()):
            device_data = devices_data[serial]
            device_info = device_data["device_info"]
            commands = device_data["commands"]

            f.write(f"""
    <div class="device-section" id="device-{serial}">
        <div class="device-header">
            <h2>Device {serial}</h2>
            <div class="device-meta">
                <strong>Serial Number:</strong> <code>{serial}</code> | 
                <strong>Name:</strong> {device_info.get("name", "N/A")} | 
                <strong>Model:</strong> {device_info.get("model", "N/A")} | 
                <strong>IP:</strong> {device_info.get("ip_address", "N/A")} | 
                <strong>Commands Executed:</strong> {len(commands)}
            </div>
        </div>
""")

            for idx, cmd_data in enumerate(commands, 1):
                status_class = (
                    "completed" if cmd_data["status"] == "COMPLETED" else "failed"
                )
                f.write(f"""
        <div class="command-block">
            <div class="command-header">
                <div class="command-title">Command {idx}: {cmd_data["command"]}</div>
                <span class="status {status_class}">{cmd_data["status"]}</span>
            </div>
            <div class="response-box">{cmd_data["response"]}</div>
        </div>
""")

            f.write("    </div>\n")
            if serial != sorted(devices_data.keys())[-1]:
                f.write('    <hr class="separator">\n')

        f.write("""
</body>
</html>
""")

    print(f"✓ HTML report generated: {output_file}")


def generate_json_report(data: Dict[str, Any], output_file: str) -> None:
    """Generate a JSON report."""
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✓ JSON report generated: {output_file}")


def generate_all_reports(output_data: List[Dict]) -> None:
    """Generate all report formats from troubleshooting data."""
    data = parse_troubleshooting_data(output_data)

    if not data.get("devices"):
        print("\nNo valid device data found in output data")
        sys.exit(1)

    devices_data = data.get("devices")
    print(f"Total devices loaded: {len(devices_data)}\n")

    # Create timestamped output folder
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = Path(f"results_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Created output folder: {output_dir}\n")
    print("Generating reports...\n")

    markdown_file = output_dir / f"{timestamp}.md"
    html_file = output_dir / f"{timestamp}.html"
    json_file = output_dir / f"{timestamp}.json"

    generate_html_report(data, str(html_file))
    generate_markdown_report(data, str(markdown_file))
    generate_json_report(data, str(json_file))

    print(f"\n{'=' * 80}")
    print("✅ Report generation completed successfully!")
    print(f"{'=' * 80}")
    print(f"\nReports saved to: {output_dir}")
    print("\nOpen the HTML report for the best viewing experience:")
    print(f"  open {html_file}")
