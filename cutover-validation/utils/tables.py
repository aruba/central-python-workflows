"""Unified table rendering for terminal output."""

from typing import List
from tabulate import tabulate
from utils.models import Device, DeviceFetchResult
from utils.config import TABLE_FORMAT, WIDE_SEPARATOR_WIDTH


def display_device_table(
    devices: List[Device], title: str = "Devices", show_header: bool = True
) -> None:
    """Display devices in a formatted table."""
    if not devices:
        print("No devices to display.")
        return

    table_data = [
        [
            idx,
            device.name,
            device.mac_address,
            device.serial,
            device.model,
            device.ip_address,
            device.firmware,
            device.site,
            device.status,
        ]
        for idx, device in enumerate(devices, 1)
    ]

    headers = [
        "#",
        "Device Name",
        "MAC Address",
        "Serial",
        "Model",
        "IP Address",
        "Firmware",
        "Site",
        "Status",
    ]

    if show_header:
        print(f"\n{title} ({len(devices)})")
        print("-" * WIDE_SEPARATOR_WIDTH)
    print(tabulate(table_data, headers=headers, tablefmt=TABLE_FORMAT))


def display_site_table(sites_data: dict) -> None:
    """Display sites in a formatted table."""
    if not sites_data:
        print("No sites found in the account.")
        return

    # Sort sites by online AP count (descending)
    sorted_sites = sorted(
        sites_data.items(), key=lambda x: x[1]["online_count"], reverse=True
    )

    table_data = [
        [
            idx,
            data["name"],
            data["total_devices"],
            data["online_count"],
            data["offline_count"],
        ]
        for idx, (_, data) in enumerate(sorted_sites, 1)
    ]

    headers = ["#", "Site Name", "Total Devices", "APs Online", "APs Offline"]

    print(f"\n{'=' * WIDE_SEPARATOR_WIDTH}")
    print("Available Sites:")
    print(f"{'=' * WIDE_SEPARATOR_WIDTH}")
    print(tabulate(table_data, headers=headers, tablefmt=TABLE_FORMAT))
    print(f"{'=' * WIDE_SEPARATOR_WIDTH}\n")


def display_device_status_summary(result: DeviceFetchResult) -> None:
    """Display summary of device statuses with clear visual hierarchy."""

    summary_data = [
        ["Total Devices Processed", result.total, ""],
        ["✓ Online", len(result.online), "Ready for troubleshooting"],
        ["? Unassigned (no site)", len(result.unassigned), "Status unknown, requires site assignment"],
        ["✗ Offline", len(result.offline), "Cannot execute commands"],
        ["? Not Found", len(result.not_found), "Not in account"],
    ]
    summary_headers = ["Status", "Count", "Details"]

    print(f"\n{'=' * WIDE_SEPARATOR_WIDTH}")
    print("DEVICE STATUS SUMMARY")
    print(f"{'=' * WIDE_SEPARATOR_WIDTH}")
    print(tabulate(summary_data, headers=summary_headers, tablefmt=TABLE_FORMAT))

    # Display online devices (ready for troubleshooting)
    if result.online:
        print(f"\n{'=' * WIDE_SEPARATOR_WIDTH}")
        print("✓ ONLINE DEVICES - Ready for Troubleshooting")
        print(f"{'=' * WIDE_SEPARATOR_WIDTH}")
        display_device_table(result.online, show_header=False)

    # Display unassigned devices (status unknown - no site)
    if result.unassigned:
        print(f"\n{'=' * WIDE_SEPARATOR_WIDTH}")
        print("? WARNING: DEVICES NOT ASSIGNED TO SITE")
        print(f"{'=' * WIDE_SEPARATOR_WIDTH}")
        print("  These devices are not assigned to a site.")
        print("  Cannot determine online/offline status without site assignment.")
        print("  → Action Required: Assign devices to a site in Central before troubleshooting.")
        display_device_table(result.unassigned, show_header=False)

    # Display offline devices with warning
    if result.offline:
        print(f"\n{'=' * WIDE_SEPARATOR_WIDTH}")
        print("✗ WARNING: OFFLINE DEVICES")
        print(f"{'=' * WIDE_SEPARATOR_WIDTH}")
        print("  Cannot run troubleshooting commands on offline devices.")
        display_device_table(result.offline, show_header=False)

    # Display not found devices
    if result.not_found:
        print(f"\n{'=' * WIDE_SEPARATOR_WIDTH}")
        print("? WARNING: DEVICES NOT FOUND")
        print(f"{'=' * WIDE_SEPARATOR_WIDTH}")
        print("  The following serial numbers were not found in the account:")
        print()
        for idx, serial in enumerate(result.not_found, 1):
            print(f"    {idx}. {serial}")
        print()

    print(f"{'=' * WIDE_SEPARATOR_WIDTH}\n")
