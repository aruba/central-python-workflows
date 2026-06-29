"""Data models for device troubleshooting."""

from dataclasses import dataclass, field
from typing import Optional


def _safe_value(value, default: str = "N/A") -> str:
    return default if value in (None, "") else value


@dataclass
class Device:
    """Device information model."""

    serial: str
    name: str = "N/A"
    model: str = "N/A"
    ip_address: str = "N/A"
    mac_address: str = "N/A"
    firmware: str = "N/A"
    status: str = "N/A"
    site: str = "N/A"

    @classmethod
    def from_api_object(cls, ap) -> "Device":
        """Create Device from API object."""
        return cls(
            serial=_safe_value(getattr(ap, "serial", None)),
            name=_safe_value(getattr(ap, "name", None)),
            model=_safe_value(getattr(ap, "model", None)),
            ip_address=_safe_value(getattr(ap, "ipv4", None)),
            mac_address=_safe_value(getattr(ap, "mac", None)),
            firmware=_safe_value(getattr(ap, "software-version", None)),
            status=_safe_value(getattr(ap, "status", None)),
            site=_safe_value(getattr(ap, "site_name", None)),
        )

    def is_online(self) -> bool:
        """Check if device is online."""
        return (self.status or "").upper() == "ONLINE"

    def is_assigned_to_site(self) -> bool:
        """Check if device has a site assignment."""
        return self.site != "N/A"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "serial": self.serial,
            "name": self.name,
            "model": self.model,
            "ip_address": self.ip_address,
            "mac_address": self.mac_address,
            "firmware": self.firmware,
            "status": self.status,
            "site": self.site,
        }


@dataclass
class CommandResult:
    """Command execution result model."""

    command: str
    status: str
    response: str = ""
    error: Optional[str] = None
    device_serial: Optional[str] = None
    raw_response: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status,
            "error": self.error,
            "output": {"command": self.command, "response": self.response},
            "device_serial": self.device_serial,
            "raw_response": self.raw_response,
        }
