"""Data models for device troubleshooting."""

from dataclasses import dataclass, field
from typing import Optional


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
            serial=ap.serial,
            name=getattr(ap, "name", "N/A"),
            model=getattr(ap, "model", "N/A"),
            ip_address=getattr(ap, "ipv4", "N/A"),
            mac_address=getattr(ap, "mac", "N/A"),
            firmware=getattr(ap, "software-version", "N/A"),
            status=getattr(ap, "status", "N/A"),
            site=getattr(ap, "site_name", "N/A"),
        )

    def is_online(self) -> bool:
        """Check if device is online."""
        return self.status.upper() == "ONLINE"

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
