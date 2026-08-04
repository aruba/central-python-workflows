from tabulate import tabulate

from utils.base_tracker import BaseTracker
from utils.csv_export import write_csv
from utils.print_helpers import colorize_status, error, info, phase_header, subheader


class NetworkSetupTracker(BaseTracker):
    """Tracks site creation, group creation/verification, and profile binding outcomes."""

    def __init__(self, sites, groups, configuration_profiles=None, site_collections=None, on_event=None):
        self._on_event = on_event or (lambda _evt: None)
        self.site_results = {
            site["name"]: {
                "name": site["name"],
                "create_status": None,
                "create_error": None,
                "overall_status": "In Progress",
            }
            for site in sites
        }

        self.site_collection_results = {
            sc["name"]: {
                "name": sc["name"],
                "sites": sc.get("sites") or [],
                "create_status": None,
                "create_error": None,
                "overall_status": "In Progress",
            }
            for sc in (site_collections or [])
        }

        self.group_results = {
            group["group"]: {
                "name": group["group"],
                "create_status": None,
                "create_error": None,
                "verify_attributes_status": None,
                "verify_attributes_error": None,
                "overall_status": "In Progress",
                "failed_step": None,
                "error_details": None,
            }
            for group in groups
        }

        self.profile_results = {}
        for binding in (configuration_profiles or []):
            target_type = "site_collection" if "site_collection" in binding else "site"
            target_name = binding.get("site_collection") or binding.get("site")
            for profile in binding.get("profiles", []):
                pname = profile.get("profile_name") or profile.get("name")
                key = f"{target_type}:{target_name}:{pname}"
                self.profile_results[key] = {
                    "target_type": target_type,
                    "target": target_name,
                    "profile_type": profile.get("profile_type") or "",
                    "profile": pname,
                    "bind_status": None,
                    "bind_error": None,
                    "overall_status": "In Progress",
                }

    def has_failures(self):
        return (
            self._any_failed(self.site_results)
            or self._any_failed(self.site_collection_results)
            or self._any_failed(self.group_results)
            or self._any_failed(self.profile_results)
        )

    def mark_site(self, site_name, step, status, error=None):
        r = self.site_results[site_name]
        r[f"{step}_status"] = status
        if error:
            r[f"{step}_error"] = error
            r["overall_status"] = "Failed"
        elif r["overall_status"] != "Failed":
            r["overall_status"] = status
        self._on_event({"type": "site", "name": site_name, "step": step, "status": status, "error": error})

    def mark_site_collection(self, sc_name, step, status, error=None):
        r = self.site_collection_results[sc_name]
        r[f"{step}_status"] = status
        if error:
            r[f"{step}_error"] = error
            r["overall_status"] = "Failed"
        elif r["overall_status"] != "Failed":
            r["overall_status"] = status
        self._on_event({"type": "site_collection", "name": sc_name, "step": step, "status": status, "error": error})

    def mark_group(self, group_name, step, status, error=None):
        r = self.group_results[group_name]
        r[f"{step}_status"] = status
        if error:
            r[f"{step}_error"] = error
            if r["overall_status"] != "Failed":
                r["overall_status"] = "Failed"
                r["failed_step"] = step
                r["error_details"] = error
        self._on_event({"type": "group", "name": group_name, "step": step, "status": status, "error": error})

    def finalize_group(self, group_name):
        r = self.group_results[group_name]
        if r["overall_status"] not in ("Failed",):
            r["overall_status"] = "Success"
        self._on_event({"type": "group_done", "name": group_name, "overall": self.group_results[group_name]["overall_status"]})

    def mark_profile(self, target_type, target_name, profile_name, status, error=None):
        key = f"{target_type}:{target_name}:{profile_name}"
        r = self.profile_results[key]
        r["bind_status"] = status
        if error:
            r["bind_error"] = error
        if status == "Failed" or (error and status != "Skipped"):
            r["overall_status"] = "Failed"
        elif r["overall_status"] != "Failed":
            r["overall_status"] = status
        self._on_event({"type": "profile", "target_type": target_type, "target": target_name, "profile": profile_name, "status": status, "error": error})

    def generate_summary(self):
        phase_header("NETWORK SETUP SUMMARY")

        if self.site_results:
            subheader("Sites")
            rows = [
                [
                    r["name"],
                    colorize_status(r["create_status"]),
                    colorize_status(r["overall_status"]),
                    r.get("create_error") or "",
                ]
                for r in self.site_results.values()
            ]
            print(tabulate(rows, headers=["Site", "Create", "Status", "Error"], tablefmt="grid"))

        if self.site_collection_results:
            subheader("Site Collections")
            rows = [
                [
                    r["name"],
                    ", ".join(r["sites"]),
                    colorize_status(r["create_status"]),
                    colorize_status(r["overall_status"]),
                    r.get("create_error") or "",
                ]
                for r in self.site_collection_results.values()
            ]
            print(
                tabulate(
                    rows,
                    headers=["Collection", "Sites", "Create", "Status", "Error"],
                    tablefmt="grid",
                )
            )

        if self.group_results:
            subheader("Groups")
            rows = [
                [
                    r["name"],
                    colorize_status(r["create_status"]),
                    colorize_status(r["verify_attributes_status"]),
                    colorize_status(r["overall_status"]),
                    r.get("error_details") or "",
                ]
                for r in self.group_results.values()
            ]
            print(
                tabulate(
                    rows,
                    headers=["Group", "Create", "Attributes", "Status", "Error"],
                    tablefmt="grid",
                )
            )

        if self.profile_results:
            subheader("Profile Bindings")
            rows = [
                [
                    r["target_type"],
                    r["target"],
                    r.get("profile_type") or "",
                    r["profile"],
                    colorize_status(r["bind_status"]),
                    colorize_status(r["overall_status"]),
                    r.get("bind_error") or "",
                ]
                for r in self.profile_results.values()
            ]
            print(
                tabulate(
                    rows,
                    headers=["Target Type", "Target", "Profile Type", "Instance", "Bind", "Status", "Error"],
                    tablefmt="grid",
                )
            )

        self._export_to_csv()
        self._print_statistics()

    def _print_statistics(self):
        subheader("SUMMARY STATISTICS")

        def stats(results):
            total = len(results)
            success = sum(1 for r in results.values() if r["overall_status"] == "Success")
            skipped = sum(1 for r in results.values() if r["overall_status"] == "Skipped")
            failed = sum(1 for r in results.values() if r["overall_status"] == "Failed")
            return total, success, skipped, failed

        if self.site_results:
            t, s, sk, f = stats(self.site_results)
            print(f"Sites            — Total: {t}  Success/Existing: {s}  Skipped: {sk}  Failed: {f}")
        if self.site_collection_results:
            t, s, sk, f = stats(self.site_collection_results)
            print(f"Site Collections — Total: {t}  Success/Existing: {s}  Skipped: {sk}  Failed: {f}")
        if self.group_results:
            t, s, sk, f = stats(self.group_results)
            print(f"Groups           — Total: {t}  Success/Existing: {s}  Skipped: {sk}  Failed: {f}")
        if self.profile_results:
            t, s, sk, f = stats(self.profile_results)
            print(f"Profiles         — Total: {t}  Bound: {s}  Skipped: {sk}  Failed: {f}")

    def _export_to_csv(self):
        try:
            folder_path, export_time = self._make_results_dir()
            files_written = []

            if self.site_results:
                rows = [
                    {
                        "Export_Date_Time": export_time,
                        "Site": r["name"],
                        "Create_Status": r["create_status"] or "",
                        "Create_Error": r.get("create_error") or "",
                        "Overall_Status": r["overall_status"],
                    }
                    for r in self.site_results.values()
                ]
                files_written.append(write_csv(folder_path, "network_setup_sites.csv", rows))

            if self.site_collection_results:
                rows = [
                    {
                        "Export_Date_Time": export_time,
                        "Site_Collection": r["name"],
                        "Sites": ", ".join(r["sites"]),
                        "Create_Status": r["create_status"] or "",
                        "Create_Error": r.get("create_error") or "",
                        "Overall_Status": r["overall_status"],
                    }
                    for r in self.site_collection_results.values()
                ]
                files_written.append(write_csv(folder_path, "network_setup_site_collections.csv", rows))

            if self.group_results:
                rows = [
                    {
                        "Export_Date_Time": export_time,
                        "Group": r["name"],
                        "Create_Status": r["create_status"] or "",
                        "Create_Error": r.get("create_error") or "",
                        "Verify_Attributes_Status": r["verify_attributes_status"] or "",
                        "Verify_Attributes_Error": r.get("verify_attributes_error") or "",
                        "Overall_Status": r["overall_status"],
                        "Failed_Step": r.get("failed_step") or "",
                        "Error_Details": r.get("error_details") or "",
                    }
                    for r in self.group_results.values()
                ]
                files_written.append(write_csv(folder_path, "network_setup_groups.csv", rows))

            if self.profile_results:
                rows = [
                    {
                        "Export_Date_Time": export_time,
                        "Target_Type": r["target_type"],
                        "Target": r["target"],
                        "Profile_Type": r.get("profile_type") or "",
                        "Profile_Instance": r["profile"],
                        "Bind_Status": r["bind_status"] or "",
                        "Bind_Error": r.get("bind_error") or "",
                        "Overall_Status": r["overall_status"],
                    }
                    for r in self.profile_results.values()
                ]
                files_written.append(write_csv(folder_path, "network_setup_profiles.csv", rows))

            if files_written:
                info(f"results exported to {folder_path}")
                for f in files_written:
                    info(f"  - {f.split('/')[-1]}")
                info(f"export date/time: {export_time}")
            else:
                info("no CSV exported (no resources to report)")
        except Exception as e:
            error(f"failed to export CSV: {e}")
