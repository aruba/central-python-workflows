"""Report formatters for different output formats."""

from typing import List, Dict, Any


def generate_device_overview_table(
    devices_overview: List[Dict[str, Any]], format_type: str
) -> str:
    """Generate device overview table in specified format.

    Args:
        devices_overview: List of device overview dictionaries
        format_type: 'markdown' or 'html'
    """
    if not devices_overview:
        return ""

    if format_type == "markdown":
        return _generate_markdown_table(devices_overview)
    elif format_type == "html":
        return _generate_html_table(devices_overview)
    else:
        raise ValueError(f"Unsupported format type: {format_type}")


def _generate_markdown_table(devices: List[Dict[str, Any]]) -> str:
    """Generate Markdown table."""
    table = "## Device Overview\n\n"
    table += "| # | Serial | Device Name | Model | IP Address | Firmware | Site | Status | Commands |\n"
    table += "|---|--------|-------------|-------|------------|----------|------|--------|----------|\n"

    for idx, device in enumerate(devices, 1):
        table += (
            f"| {idx} | {device.get('serial', 'N/A')} | {device.get('name', 'N/A')} | "
            f"{device.get('model', 'N/A')} | {device.get('ip_address', 'N/A')} | "
            f"{device.get('firmware', 'N/A')} | {device.get('site', 'N/A')} | "
            f"{device.get('status', 'N/A')} | {device.get('commands_executed', 0)} |\n"
        )

    return table + "\n"


def _generate_html_table(devices: List[Dict[str, Any]]) -> str:
    """Generate HTML table."""
    html = """    <div class="device-overview">
        <h2>Device Overview</h2>
        <table class="overview-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Serial</th>
                    <th>Device Name</th>
                    <th>Model</th>
                    <th>IP Address</th>
                    <th>Firmware</th>
                    <th>Site</th>
                    <th>Status</th>
                    <th>Commands</th>
                </tr>
            </thead>
            <tbody>
"""

    for idx, device in enumerate(devices, 1):
        status_class = (
            "status-online" if device.get("status") == "ONLINE" else "status-offline"
        )
        serial = device.get("serial", "N/A")
        html += f'''                <tr>
                    <td>{idx}</td>
                    <td><a href="#device-{serial}">{serial}</a></td>
                    <td>{device.get("name", "N/A")}</td>
                    <td>{device.get("model", "N/A")}</td>
                    <td>{device.get("ip_address", "N/A")}</td>
                    <td>{device.get("firmware", "N/A")}</td>
                    <td>{device.get("site", "N/A")}</td>
                    <td><span class="{status_class}">{device.get("status", "N/A")}</span></td>
                    <td>{device.get("commands_executed", 0)}</td>
                </tr>
'''

    html += """            </tbody>
        </table>
    </div>

"""
    return html


# HTML CSS template (extracted as constant to avoid duplication)
HTML_CSS_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cutover Validation Report</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header h1 { margin: 0 0 10px 0; }
        .header .meta { opacity: 0.9; font-size: 14px; }
        .device-overview {
            background: white;
            padding: 20px 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .device-overview h2 { margin-top: 0; color: #667eea; }
        .overview-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        .overview-table th, .overview-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        .overview-table th {
            background-color: #f8f9fa;
            font-weight: 600;
            color: #333;
        }
        .overview-table tr:hover { background-color: #f8f9fa; }
        .overview-table a { color: #667eea; text-decoration: none; font-weight: 500; }
        .overview-table a:hover { text-decoration: underline; }
        .status-online { color: #28a745; font-weight: bold; }
        .status-offline { color: #dc3545; font-weight: bold; }
        .toc {
            background: white;
            padding: 20px 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .toc h2 { margin-top: 0; color: #667eea; }
        .toc ul { list-style: none; padding-left: 0; }
        .toc li { padding: 8px 0; border-bottom: 1px solid #eee; }
        .toc li:last-child { border-bottom: none; }
        .toc a { color: #667eea; text-decoration: none; font-weight: 500; }
        .toc a:hover { text-decoration: underline; }
        .device-section {
            background: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .device-header {
            border-bottom: 3px solid #667eea;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }
        .device-header h2 { margin: 0 0 10px 0; color: #333; }
        .device-meta { color: #666; font-size: 14px; }
        .command-block {
            margin-bottom: 30px;
            border-left: 4px solid #667eea;
            padding-left: 20px;
        }
        .command-header {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 15px;
        }
        .command-title {
            font-family: 'Courier New', monospace;
            font-size: 16px;
            color: #667eea;
            font-weight: bold;
            margin-bottom: 8px;
        }
        .status {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }
        .status.completed { background-color: #d4edda; color: #155724; }
        .status.failed { background-color: #f8d7da; color: #721c24; }
        .response-box {
            background-color: #1e1e1e;
            color: #d4d4d4;
            padding: 20px;
            border-radius: 5px;
            overflow-x: auto;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            line-height: 1.5;
            white-space: pre;
            word-wrap: normal;
            max-width: 100%;
        }
        .separator {
            border: 0;
            height: 2px;
            background: linear-gradient(to right, transparent, #667eea, transparent);
            margin: 40px 0;
        }
        @media print {
            body { background-color: white; }
            .device-section, .toc, .device-overview {
                box-shadow: none;
                border: 1px solid #ddd;
            }
        }
    </style>
</head>
<body>
"""
