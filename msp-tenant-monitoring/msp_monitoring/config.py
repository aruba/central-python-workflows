from __future__ import annotations

from pathlib import Path


class ConfigError(RuntimeError):
    """Raised when token.yaml cannot be located."""


def resolve_token_yaml() -> Path:
    """Return the path to token.yaml in the current directory.

    Raises ConfigError if the file does not exist. token.yaml is the only
    supported credential source for the CLI (pycentral ``unified:`` format).
    """
    p = Path("token.yaml")
    if not p.exists():
        raise ConfigError(
            "token.yaml not found in the current directory. "
            "Copy token.yaml.example and fill in credentials."
        )
    return p
