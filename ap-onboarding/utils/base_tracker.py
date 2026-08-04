import os
from datetime import datetime


class BaseTracker:
    """Shared infrastructure for OnboardingTracker and NetworkSetupTracker."""

    results_dir = None
    _session_dir: "str | None" = None

    @classmethod
    def set_session_dir(cls, path: "str | None") -> None:
        """Pin all trackers in this process to a shared results folder."""
        cls._session_dir = path

    @staticmethod
    def _any_failed(result_dict):
        return any(r["overall_status"] == "Failed" for r in result_dict.values())

    def _make_results_dir(self):
        """Return (folder_path, export_time_str) and set self.results_dir.

        Reuses BaseTracker._session_dir when set (shared-folder mode used by
        ui_app.py so all runs in one session land in the same directory).
        """
        now = datetime.now()
        export_time = now.strftime("%Y-%m-%d %H:%M:%S")
        if BaseTracker._session_dir:
            self.results_dir = BaseTracker._session_dir
            return BaseTracker._session_dir, export_time
        timestamp = now.strftime("%Y-%m-%dT%H-%M-%S")
        folder_path = os.path.join(os.getcwd(), f"results_{timestamp}")
        self.results_dir = folder_path
        return folder_path, export_time

    def has_failures(self):
        raise NotImplementedError
