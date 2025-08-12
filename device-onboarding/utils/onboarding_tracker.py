import csv
from datetime import datetime
import os

# ANSI color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
from tabulate import tabulate


class OnboardingTracker:
    """Tracks onboarding step status and errors for each device."""

    def __init__(self, devices_data):
        self.results = {
            device["serial_number"]: {
                "serial_number": device["serial_number"],
                "glp_status": None,
                "glp_error": None,
                "site_status": None,
                "site_error": None,
                "site_assoc_status": None,
                "site_assoc_error": None,
                "persona_status": None,
                "persona_error": None,
                "group_status": None,
                "group_error": None,
                "group_assign_status": None,
                "group_assign_error": None,
                "local_profiles_success": None,  # List of successful profiles
                "local_profiles_failed": None,  # List of failed profiles
                "overall_status": "In Progress",
                "failed_step": None,
                "error_details": None,
            }
            for device in devices_data
        }

    def mark_step(
        self,
        serial,
        step,
        status,
        error=None,
        local_profiles_success=None,
        local_profiles_failed=None,
    ):
        """Mark a step as success/failure and record error if any.
        For local_profiles step, also record successful/failed profiles.
        """
        status_field = f"{step}_status"
        error_field = f"{step}_error"
        self.results[serial][status_field] = status
        if step == "local_profiles":
            if local_profiles_success is not None:
                self.results[serial]["local_profiles_success"] = local_profiles_success
            if local_profiles_failed is not None:
                self.results[serial]["local_profiles_failed"] = local_profiles_failed
        if error:
            self.results[serial][error_field] = error
            self.results[serial]["failed_step"] = step
            self.results[serial]["error_details"] = error
            self.results[serial]["overall_status"] = "Failed"

    def mark_success(self, serial):
        self.results[serial]["overall_status"] = "Success"

    def is_failed(self, serial):
        return self.results[serial]["overall_status"] == "Failed"

    def generate_summary(self):
        """Print concise tabular summary with colored status, export CSV, and print stats."""
        print("\n" + "=" * 80)
        print(" " * 25 + "DEVICE ONBOARDING SUMMARY")
        print("=" * 80)
        any_failed = any(r["overall_status"] == "Failed" for r in self.results.values())
        # Add local_profiles columns if any device has local_profiles
        any_local_profiles = any(
            r["local_profiles_success"] or r["local_profiles_failed"]
            for r in self.results.values()
        )
        headers = [
            "Serial Number",
            "GLP",
            "Site",
            "Site Assoc",
            "Persona",
            "Group",
            "Group Assign",
        ]
        if any_local_profiles:
            headers += ["Local Profiles Success", "Local Profiles Failed"]
        headers += [
            "Status",
        ]
        if any_failed:
            headers += ["Failed Step", "Error Details"]

        summary_data = []
        for r in self.results.values():

            def colorize(val):
                if val == "Success":
                    return f"{GREEN}Success{RESET}"
                elif val == "Failed":
                    return f"{RED}Failed{RESET}"
                elif val == "Skipped":
                    return "Skipped"
                else:
                    return val or ""

            row = [
                r["serial_number"],
                colorize(r["glp_status"]),
                colorize(r["site_status"]),
                colorize(r["site_assoc_status"]),
                colorize(r["persona_status"]),
                colorize(r["group_status"]),
                colorize(r["group_assign_status"]),
            ]
            if any_local_profiles:
                row.append(
                    ", ".join(r["local_profiles_success"])
                    if r["local_profiles_success"]
                    else ""
                )
                row.append(
                    ", ".join(r["local_profiles_failed"])
                    if r["local_profiles_failed"]
                    else ""
                )
            row += [
                colorize(r["overall_status"]),
            ]
            if any_failed:
                row += [r["failed_step"] or "", r["error_details"] or ""]
            summary_data.append(row)

        # Adjust column widths for better formatting
        colalign = ("left",) * len(headers)
        print(
            tabulate(
                summary_data,
                headers=headers,
                tablefmt="grid",
                colalign=colalign,
                stralign="left",
                numalign="left",
                maxcolwidths=[18, 10, 10, 12, 10, 10, 12, 20, 20, 10, 19, 19]
                + (
                    [12, None] if any_failed else []
                ),  # None disables truncation for error details
            )
        )

        # Export to CSV
        self._export_to_csv(
            any_failed=any_failed, any_local_profiles=any_local_profiles
        )

        # Print summary statistics
        self._print_statistics()

    def _print_statistics(self):
        print("\n" + "-" * 50)
        print("SUMMARY STATISTICS")
        print("-" * 50)
        total = len(self.results)
        success = sum(
            1 for r in self.results.values() if r["overall_status"] == "Success"
        )
        failed = sum(
            1 for r in self.results.values() if r["overall_status"] == "Failed"
        )
        print(f"Total Devices: {total}")
        print(f"Successful: {success}")
        print(f"Failed: {failed}")
        if total > 0:
            print(f"Success Rate: {(success / total) * 100:.1f}%")

    def _print_failed_devices(self):
        failed = [r for r in self.results.values() if r["overall_status"] == "Failed"]
        if failed:
            print("\n" + "-" * 50)
            print("FAILED DEVICES DETAILS")
            print("-" * 50)
            for r in failed:
                print(f"Device: {r['serial_number']}")
                print(f"Failed Step: {r['failed_step']}")
                print(f"Error: {r.get('error_details', 'Unknown error')}")
                print("-" * 30)

    def _export_to_csv(self, any_failed=False, any_local_profiles=False):
        try:
            now = datetime.now()
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            csv_filename = f"onboarding_results_{timestamp}.csv"
            csv_filepath = os.path.join(os.getcwd(), csv_filename)
            export_time = now.strftime("%Y-%m-%d %H:%M:%S")
            csv_data = []
            for r in self.results.values():
                row = {
                    "Export_Date_Time": export_time,
                    "Serial_Number": r["serial_number"],
                    "GLP_Status": r["glp_status"],
                    "GLP_Error": r["glp_error"],
                    "Site_Status": r["site_status"],
                    "Site_Error": r["site_error"],
                    "Site_Assoc_Status": r["site_assoc_status"],
                    "Site_Assoc_Error": r["site_assoc_error"],
                    "Persona_Status": r["persona_status"],
                    "Persona_Error": r["persona_error"],
                    "Group_Status": r["group_status"],
                    "Group_Error": r["group_error"],
                    "Group_Assign_Status": r["group_assign_status"],
                    "Group_Assign_Error": r["group_assign_error"],
                    "Overall_Status": r["overall_status"],
                    "Failed_Step": r["failed_step"],
                    "Error_Details": r["error_details"],
                }
                if any_local_profiles:
                    row["Local_Profiles_Success"] = (
                        ", ".join(r["local_profiles_success"])
                        if r["local_profiles_success"]
                        else ""
                    )
                    row["Local_Profiles_Failed"] = (
                        ", ".join(r["local_profiles_failed"])
                        if r["local_profiles_failed"]
                        else ""
                    )
                csv_data.append(row)
            if csv_data:
                with open(csv_filepath, "w", newline="", encoding="utf-8") as csvfile:
                    fieldnames = csv_data[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(csv_data)
                print(f"\n📄 Results exported to: {csv_filepath}")
                print(f"📅 Export Date/Time: {export_time}")
            else:
                print("\n⚠️  No data to export to CSV")
        except Exception as e:
            print(f"\n❌ Failed to export CSV: {e}")
