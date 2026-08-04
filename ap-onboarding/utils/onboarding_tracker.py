from tabulate import tabulate

from steps import STEPS
from utils.base_tracker import BaseTracker
from utils.csv_export import write_csv
from utils.print_helpers import colorize_status, error, info, phase_header, subheader


class OnboardingTracker(BaseTracker):
    """Track core onboarding state for each access point."""

    def __init__(self, devices_data, on_event=None):
        self._on_event = on_event or (lambda _event: None)
        self._device_done = set()
        self.results = {
            device["serial_number"]: {
                "serial_number": device["serial_number"],
                "glp_application_status": None,
                "glp_application_error": None,
                "glp_subscription_status": None,
                "glp_subscription_error": None,
                "firmware_check_status": None,
                "firmware_check_error": None,
                "discovered_firmware": None,
                "minimum_firmware": None,
                "site_assoc_status": None,
                "site_assoc_error": None,
                "device_function_status": None,
                "device_function_error": None,
                "group_assign_status": None,
                "group_assign_error": None,
                "provision_status": None,
                "provision_error": None,
                **{
                    field_name: None
                    for step in STEPS
                    for field_name in (
                        f"{step.key}_status",
                        f"{step.key}_error",
                    )
                },
                "overall_status": "In Progress",
                "failed_step": None,
                "error_details": None,
                "warning_steps": [],
                "warning_details": [],
            }
            for device in devices_data
        }

    def has_failures(self):
        return self._any_failed(self.results)

    def has_warnings(self):
        return any(
            result["overall_status"] == "WARNING"
            for result in self.results.values()
        )

    def mark_step(self, serial, step, status, error=None, add_on=False, **details):
        record = self.results[serial]
        record[f"{step}_status"] = status
        if error:
            record[f"{step}_error"] = error
            if add_on:
                record["warning_steps"].append(step)
                record["warning_details"].append(error)
                if record["overall_status"] != "Failed":
                    record["overall_status"] = "WARNING"
            else:
                record["failed_step"] = step
                record["error_details"] = error
                record["overall_status"] = "Failed"

        event = {
            "type": "step",
            "serial": serial,
            "step": step,
            "status": status,
            "error": error,
            **details,
        }
        self._on_event(event)
        if error and not add_on and serial not in self._device_done:
            self._device_done.add(serial)
            self._on_event(
                {"type": "device_done", "serial": serial, "overall": "Failed"}
            )

    def mark_firmware_checked(self, serial, current, minimum, message):
        record = self.results[serial]
        record["discovered_firmware"] = current
        record["minimum_firmware"] = minimum
        self.mark_step(
            serial,
            "firmware_check",
            "Success",
            current_version=current,
            minimum_version=minimum,
            message=message,
        )

    def mark_firmware_skipped(self, serial, current, minimum, message):
        record = self.results[serial]
        record["firmware_check_status"] = "Skipped"
        record["discovered_firmware"] = current
        record["minimum_firmware"] = minimum
        record["overall_status"] = "Skipped (firmware)"
        self._on_event(
            {
                "type": "step",
                "serial": serial,
                "step": "firmware_check",
                "status": "Skipped",
                "current_version": current,
                "minimum_version": minimum,
                "message": message,
            }
        )
        if serial not in self._device_done:
            self._device_done.add(serial)
            self._on_event(
                {
                    "type": "device_done",
                    "serial": serial,
                    "overall": "Skipped (firmware)",
                }
            )

    def mark_success(self, serial):
        record = self.results[serial]
        if record["overall_status"] not in ("Failed", "WARNING"):
            record["overall_status"] = "Success"
        if serial not in self._device_done:
            self._device_done.add(serial)
            self._on_event(
                {
                    "type": "device_done",
                    "serial": serial,
                    "overall": record["overall_status"],
                }
            )

    def is_failed(self, serial):
        return self.results[serial]["overall_status"] == "Failed"

    def eligible(self, devices):
        return [device for device in devices if not self.is_failed(device["serial_number"])]

    def generate_summary(self):
        phase_header("DEVICE ONBOARDING SUMMARY")
        any_issue = any(
            result["overall_status"] in ("Failed", "WARNING")
            for result in self.results.values()
        )
        active_add_ons = [
            step
            for step in STEPS
            if any(
                result[f"{step.key}_status"] is not None
                for result in self.results.values()
            )
        ]

        headers = [
            "Serial Number",
            "GLP App",
            "GLP Sub",
            "Firmware Gate",
            "Discovered Firmware",
            "Site Assoc",
            "Device Function",
            "Group Assign",
            "Provision",
        ]
        headers.extend(f"{step.label} (Optional)" for step in active_add_ons)
        headers.append("Status")
        if any_issue:
            headers += ["Issue Step", "Error Details"]

        rows = []
        for result in self.results.values():
            row = [
                result["serial_number"],
                colorize_status(result["glp_application_status"]),
                colorize_status(result["glp_subscription_status"]),
                colorize_status(result["firmware_check_status"]),
                result["discovered_firmware"] or "",
                colorize_status(result["site_assoc_status"]),
                colorize_status(result["device_function_status"]),
                colorize_status(result["group_assign_status"]),
                colorize_status(result["provision_status"]),
            ]
            row.extend(
                colorize_status(result[f"{step.key}_status"])
                for step in active_add_ons
            )
            row.append(colorize_status(result["overall_status"]))
            if any_issue:
                if result["overall_status"] == "WARNING":
                    row += [
                        ", ".join(result["warning_steps"]),
                        "; ".join(result["warning_details"]),
                    ]
                else:
                    row += [
                        result["failed_step"] or "",
                        result["error_details"] or "",
                    ]
            rows.append(row)

        print(
            tabulate(
                rows,
                headers=headers,
                tablefmt="grid",
                colalign=("left",) * len(headers),
                stralign="left",
                numalign="left",
                maxcolwidths=[None] * len(headers),
            )
        )
        self._export_to_csv()
        self._print_statistics()

    def _base_csv_row(self, result, export_time):
        row = {
            "Export_Date_Time": export_time,
            "Serial_Number": result["serial_number"],
            "GLP_Application_Status": result["glp_application_status"] or "",
            "GLP_Subscription_Status": result["glp_subscription_status"] or "",
            "Firmware_Check_Status": result["firmware_check_status"] or "",
            "Discovered_Firmware": result["discovered_firmware"] or "",
            "Minimum_Firmware": result["minimum_firmware"] or "",
            "Site_Assoc_Status": result["site_assoc_status"] or "",
            "Device_Function_Status": result["device_function_status"] or "",
            "Group_Assign_Status": result["group_assign_status"] or "",
            "Provision_Status": result["provision_status"] or "",
            "Overall_Status": result["overall_status"],
        }
        for step in STEPS:
            column = "_".join(part.capitalize() for part in step.key.split("_"))
            row[f"{column}_Status"] = result[f"{step.key}_status"] or ""
            row[f"{column}_Error"] = result[f"{step.key}_error"] or ""
        return row

    def _export_to_csv(self):
        try:
            folder_path, export_time = self._make_results_dir()
            files_written = []

            categories = (
                ("successful_devices.csv", "Success"),
                ("warning_devices.csv", "WARNING"),
                ("skipped_devices.csv", "Skipped (firmware)"),
                ("failed_devices.csv", "Failed"),
            )
            for filename, overall_status in categories:
                selected = [
                    result
                    for result in self.results.values()
                    if result["overall_status"] == overall_status
                ]
                if not selected:
                    continue
                rows = [self._base_csv_row(result, export_time) for result in selected]
                if overall_status == "Failed":
                    for row, result in zip(rows, selected):
                        row["Failed_Step"] = result["failed_step"] or ""
                        row["Error_Details"] = result["error_details"] or ""
                elif overall_status == "WARNING":
                    for row, result in zip(rows, selected):
                        row["Warning_Steps"] = ", ".join(result["warning_steps"])
                        row["Warning_Details"] = "; ".join(
                            result["warning_details"]
                        )
                files_written.append(write_csv(folder_path, filename, rows))

            if files_written:
                info(f"results exported to {folder_path}")
                for filepath in files_written:
                    info(f"  - {filepath.split('/')[-1]}")
                info(f"export date/time: {export_time}")
            else:
                info("no CSV exported (no completed devices)")
        except Exception as exc:
            error(f"failed to export CSV: {exc}")

    def _print_statistics(self):
        subheader("SUMMARY STATISTICS")
        total = len(self.results)
        success = sum(
            result["overall_status"] == "Success"
            for result in self.results.values()
        )
        skipped = sum(
            result["overall_status"] == "Skipped (firmware)"
            for result in self.results.values()
        )
        failed = sum(
            result["overall_status"] == "Failed"
            for result in self.results.values()
        )
        warnings = sum(
            result["overall_status"] == "WARNING"
            for result in self.results.values()
        )
        print(f"Total Devices: {total}")
        print(f"Successful: {success}")
        print(f"Onboarded with warnings: {warnings}")
        print(f"Skipped (firmware): {skipped}")
        print(f"Failed: {failed}")
