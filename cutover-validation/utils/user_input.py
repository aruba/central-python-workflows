"""User input and interaction utilities."""

import sys
from typing import List
from utils.config import SEPARATOR_WIDTH


def prompt_confirmation(device_serials: List[str], commands: List[str]) -> bool:
    """Display summary and prompt user for confirmation."""
    print(f"\n{'=' * SEPARATOR_WIDTH}")
    print("CONFIRMATION REQUIRED")
    print(f"{'=' * SEPARATOR_WIDTH}")
    print(
        f"\nThe following {len(commands)} troubleshooting command(s) will be executed:"
    )
    for i, cmd in enumerate(commands, 1):
        print(f"  {i}. {cmd}")

    print(f"\nOn {len(device_serials)} device(s):")
    for serial in device_serials:
        print(f"  - {serial}")

    print(f"\n{'=' * SEPARATOR_WIDTH}")

    while True:
        response = input("\nDo you want to proceed? (yes/no or y/n): ").strip().lower()
        if response in ["yes", "y"]:
            return True
        elif response in ["no", "n"]:
            print("Operation cancelled by user.")
            return False
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")


def prompt_site_selection(sites_data: dict) -> List[str]:
    """Prompt user to select a site."""
    if not sites_data:
        print("No sites available to select.")
        return []

    sorted_sites = sorted(
        sites_data.items(), key=lambda x: x[1]["online_count"], reverse=True
    )

    print("Select a site to run troubleshooting commands:")
    print()
    for idx, (site_id, data) in enumerate(sorted_sites, 1):
        print(f"  {idx}. {data['name']} ({data['online_count']} online APs)")

    while True:
        try:
            choice = input("\nEnter choice: ").strip()
            choice_num = int(choice)

            if 1 <= choice_num <= len(sorted_sites):
                selected_site_id, selected_site_data = sorted_sites[choice_num - 1]
                selected_site_name = selected_site_data["name"]

                print(f"\nSelected Site: {selected_site_name}")
                print(
                    f"\nAll Online APs in '{selected_site_name}' will be troubleshot:"
                )

                # Display selected devices
                from utils.tables import display_device_table

                display_device_table(
                    selected_site_data["online_ap_details"],
                    f"Online APs in {selected_site_name}",
                )

                return [selected_site_id]
            else:
                print(f"Invalid choice. Please enter 1-{len(sorted_sites)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            sys.exit(0)
