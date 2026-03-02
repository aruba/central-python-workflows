"""Unified table rendering for terminal output."""

from typing import List
from tabulate import tabulate
from utils.models import Device
from utils.config import TABLE_FORMAT, WIDE_SEPARATOR_WIDTH


def display_device_table(devices: List[Device], title: str = "Devices") -> None:
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

    print(f"\n{'=' * WIDE_SEPARATOR_WIDTH}")
    print(f"{title} ({len(devices)})")
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


def display_device_status_summary(
    online_devices: List[Device],
    offline_devices: List[Device],
    not_found_serials: List[str],
) -> None:
    """Display summary of device statuses with warnings."""

    # Display online devices
    if online_devices:
        display_device_table(
            online_devices, "ONLINE DEVICES - Ready for Troubleshooting"
        )

    # Display offline devices with warning
    if offline_devices:
        print(f"\n{'=' * WIDE_SEPARATOR_WIDTH}")
        print(
            f"WARNING: OFFLINE DEVICES ({len(offline_devices)}) - Cannot run troubleshooting commands:"
        )
        display_device_table(offline_devices)

    # Display not found devices
    if not_found_serials:
        print(f"\n{'!' * WIDE_SEPARATOR_WIDTH}")
        print(
            f"WARNING: DEVICES NOT FOUND ({len(not_found_serials)}) - Not found in account:"
        )
        for idx, serial in enumerate(not_found_serials, 1):
            print(f"  {idx}. {serial}")
        print(f"\n{'!' * WIDE_SEPARATOR_WIDTH}\n")
