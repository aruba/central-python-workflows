"""Pure rich renderers for the MSP monitoring CLI.

Every function takes a ``rich.console.Console`` as first arg so callers
(one-shot CLI, interactive REPL, and tests) can inject a fixed-width console
or capture output to a StringIO.

No ``input()``, no network calls.
"""
from __future__ import annotations

import datetime
from typing import Sequence

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from msp_monitoring.collector import aggregate_totals
from msp_monitoring.models import Alert, Client, Device, Site, TenantSummary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _health_buckets(groups: list[dict]) -> dict[str, int]:
    """Extract good/fair/poor counts from a health groups list.

    Each element is expected to be ``{"name": str, "value": int}``.
    """
    def _get(name: str) -> int:
        for g in groups:
            if isinstance(g, dict) and g.get("name", "").lower() == name:
                return int(g.get("value", 0))
        return 0

    return {"good": _get("good"), "fair": _get("fair"), "poor": _get("poor")}


def _health_dominant(groups: list[dict]) -> str:
    """Return the name of the health group with the highest value."""
    if not groups:
        return ""
    best = max(groups, key=lambda g: int(g.get("value", 0)) if isinstance(g, dict) else 0)
    return best.get("name", "") if isinstance(best, dict) else ""


def _health_bar(good: int, fair: int, poor: int, width: int = 10) -> Text:
    """Render a proportional health bar as Rich Text.

    Uses block characters: green for good, yellow for fair, red for poor.
    """
    total = good + fair + poor
    if total == 0:
        return Text("—", style="dim")

    bar = Text()
    segments = [
        (good, "green"),
        (fair, "yellow"),
        (poor, "red"),
    ]
    filled = 0
    for i, (count, color) in enumerate(segments):
        # last segment gets any rounding remainder
        if i == len(segments) - 1:
            blocks = width - filled
        else:
            blocks = round(count / total * width)
        if blocks > 0:
            bar.append("█" * blocks, style=color)
        filled += blocks

    # Append numeric summary
    bar.append(f" {good}g/{fair}f/{poor}p", style="dim")
    return bar


def _short_location(address: dict) -> str:
    """Return 'City, State' from an address dict."""
    parts = []
    if address and address.get("city"):
        parts.append(str(address["city"]))
    if address and address.get("state"):
        parts.append(str(address["state"]))
    return ", ".join(parts)


def _full_address(address: dict) -> str:
    """Return a full address string from an address dict."""
    if not address:
        return ""
    parts = []
    if address.get("address"):
        parts.append(str(address["address"]))
    if address.get("city"):
        parts.append(str(address["city"]))
    if address.get("state"):
        parts.append(str(address["state"]))
    if address.get("zipCode"):
        parts.append(str(address["zipCode"]))
    if address.get("country"):
        parts.append(str(address["country"]))
    return ", ".join(parts)


def _fmt_ts(ts: str | int | None) -> str:
    """Format a timestamp (ISO string or epoch ms int) to a human-readable string."""
    if ts is None:
        return "—"
    if isinstance(ts, int):
        if ts == 0:
            return "—"
        # epoch ms
        try:
            dt = datetime.datetime.fromtimestamp(ts / 1000, tz=datetime.timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        except (OSError, OverflowError, ValueError):
            return str(ts)
    # ISO string
    try:
        dt = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError):
        return str(ts)


def render_error(console: Console, message: str) -> None:
    """Render a red error panel."""
    console.print(Panel(message, title="Error", border_style="red"))


# ---------------------------------------------------------------------------
# Overview renderers
# ---------------------------------------------------------------------------


def render_totals_panel(console: Console, results: list[TenantSummary]) -> None:
    """Render only the fleet-wide MSP totals panel (no per-tenant table)."""
    totals = aggregate_totals(results)
    summary_lines = [
        f"[bold]Total tenants:[/bold] {totals['tenants']}",
        f"[bold]Total sites:[/bold]   {totals['sites']}",
        f"[bold]Total devices:[/bold] {totals['devices']}",
        f"[bold]Critical alerts:[/bold] {totals['alerts']['critical']}",
    ]
    console.print(
        Panel(
            "\n".join(summary_lines),
            title="[bold cyan]MSP Overview — Cross-Tenant Network Overview[/bold cyan]",
            border_style="cyan",
        )
    )


def render_overview(console: Console, results: list[TenantSummary]) -> None:
    """Render the MSP-level totals panel and per-tenant summary table.

    Replaces the old ``main._print_overview``.
    """
    render_totals_panel(console, results)

    if not results:
        console.print("[dim]No tenants found.[/dim]")
        return

    # Per-tenant summary table
    table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 1))
    table.add_column("Tenant", style="bold")
    table.add_column("Sites", justify="right")
    table.add_column("Devices", justify="right")
    table.add_column("Critical Alerts", justify="right")

    for item in results:
        crit = item.alerts.get("critical", 0)
        crit_str = Text(str(crit), style="red bold" if crit > 0 else "")
        table.add_row(
            item.tenant_name,
            str(item.total_sites),
            str(item.device_health.get("total", 0)),
            crit_str,
        )

    console.print(table)


def render_tenant_list(console: Console, results: list[TenantSummary]) -> None:
    """Render a numbered selectable tenant list for the overview REPL state."""
    if not results:
        console.print("[dim]No tenants found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 1))
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Tenant", style="bold")
    table.add_column("Sites", justify="right")
    table.add_column("Devices", justify="right")
    table.add_column("Critical Alerts", justify="right")

    for i, item in enumerate(results, start=1):
        crit = item.alerts.get("critical", 0)
        crit_str = Text(str(crit), style="red bold" if crit > 0 else "dim")
        table.add_row(
            str(i),
            item.tenant_name,
            str(item.total_sites),
            str(item.device_health.get("total", 0)),
            crit_str,
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Per-tab table renderers
# ---------------------------------------------------------------------------


def render_sites_table(console: Console, rows: Sequence[Site]) -> None:
    """Render a Sites table with a leading 1-based # column."""
    if not rows:
        console.print("[dim]No sites…[/dim]")
        return

    table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 1))
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Site", style="bold")
    table.add_column("Location")
    table.add_column("Health")
    table.add_column("Devices", justify="right")
    table.add_column("Clients", justify="right")
    table.add_column("Alerts", justify="right")

    for i, site in enumerate(rows, start=1):
        health_groups = (site.health or {}).get("groups", [])
        dominant = _health_dominant(health_groups)
        dev_groups = ((site.devices or {}).get("health") or {}).get("groups", [])
        buckets = _health_buckets(dev_groups)
        bar = _health_bar(buckets["good"], buckets["fair"], buckets["poor"])

        health_cell = Text()
        if dominant:
            color = {"good": "green", "fair": "yellow", "poor": "red"}.get(dominant.lower(), "white")
            health_cell.append(f"[{dominant}] ", style=color)
        health_cell.append_text(bar)

        alert_count = (site.alerts or {}).get("totalCount", 0)
        alert_str = Text(str(alert_count), style="red bold" if alert_count > 0 else "dim")

        table.add_row(
            str(i),
            site.siteName or "—",
            _short_location(site.address or {}) or "—",
            health_cell,
            str((site.devices or {}).get("count", 0)),
            str((site.clients or {}).get("count", 0)),
            alert_str,
        )

    console.print(table)


def render_devices_table(console: Console, rows: Sequence[Device]) -> None:
    """Render a Devices table with a leading 1-based # column."""
    if not rows:
        console.print("[dim]No devices…[/dim]")
        return

    table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 1))
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Model")
    table.add_column("Site")
    table.add_column("Status")
    table.add_column("Firmware")
    table.add_column("IPv4")

    for i, dev in enumerate(rows, start=1):
        # Match the UI (DevicesTab): ONLINE green, OFFLINE red.
        dev_status = (dev.status or "").lower()
        status_style = "green" if dev_status == "online" else "red" if dev_status == "offline" else ""
        table.add_row(
            str(i),
            dev.deviceName or "—",
            dev.deviceType or "—",
            dev.model or "—",
            dev.siteName or "—",
            Text(dev.status or "—", style=status_style),
            dev.firmwareVersion or "—",
            dev.ipv4 or "—",
        )

    console.print(table)


def render_clients_table(console: Console, rows: Sequence[Client]) -> None:
    """Render a Clients table with a leading 1-based # column."""
    if not rows:
        console.print("[dim]No clients…[/dim]")
        return

    table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 1))
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Name", style="bold")
    table.add_column("Host")
    table.add_column("MAC")
    table.add_column("IP")
    table.add_column("Site")
    table.add_column("Type")
    table.add_column("VLAN")
    table.add_column("SNR", justify="right")

    for i, client in enumerate(rows, start=1):
        snr_val = client.snr
        # Match the UI (ClientsTab SnrBar): <20 poor, <40 fair, else good.
        snr_style = "red" if snr_val < 20 else "yellow" if snr_val < 40 else "green"
        table.add_row(
            str(i),
            client.clientName or "—",
            client.hostName or "—",
            client.macAddress or "—",
            client.ipv4 or "—",
            client.siteName or "—",
            client.connectedDeviceType or "—",
            client.vlanName or client.vlanId or "—",
            Text(str(snr_val), style=snr_style),
        )

    console.print(table)


def render_alerts_table(console: Console, rows: Sequence[Alert]) -> None:
    """Render an Alerts table with a leading 1-based # column.

    The summary column uses ellipsis overflow (truncated to 50 chars).
    """
    if not rows:
        console.print("[dim]No alerts…[/dim]")
        return

    table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 1))
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Severity")
    table.add_column("Name", style="bold")
    table.add_column("Summary", max_width=50, overflow="ellipsis")
    table.add_column("Device Type")
    table.add_column("Status")
    table.add_column("Created")

    severity_styles = {
        "critical": "red bold",
        "major": "yellow",
        "minor": "cyan",
    }

    for i, alert in enumerate(rows, start=1):
        sev = (alert.severity or "").lower()
        sev_style = severity_styles.get(sev, "")
        status_style = "green" if (alert.status or "").lower() == "open" else "dim"
        table.add_row(
            str(i),
            Text(alert.severity or "—", style=sev_style),
            alert.name or "—",
            alert.summary or "—",
            alert.deviceType or "—",
            Text(alert.status or "—", style=status_style),
            _fmt_ts(alert.createdAt),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Detail / expanded-row renderers
# ---------------------------------------------------------------------------


def render_site_detail(console: Console, site: Site) -> None:
    """Render an expanded panel for a single Site row."""
    address = site.address or {}
    health_groups = (site.health or {}).get("groups", [])
    dev_groups = ((site.devices or {}).get("health") or {}).get("groups", [])
    cli_groups = ((site.clients or {}).get("health") or {}).get("groups", [])
    dev_buckets = _health_buckets(dev_groups)
    cli_buckets = _health_buckets(cli_groups)

    lines: list[str] = []

    # Address
    full_addr = _full_address(address)
    lines.append(f"[bold]Address:[/bold]  {full_addr or '—'}")
    if address.get("country"):
        lines.append(f"[bold]Country:[/bold]  {address['country']}")

    lines.append("")

    # Devices health breakdown
    dev_count = (site.devices or {}).get("count", 0)
    lines.append(f"[bold]Devices ({dev_count}):[/bold]")
    lines.append(f"  Good: {dev_buckets['good']}  Fair: {dev_buckets['fair']}  Poor: {dev_buckets['poor']}")

    # Clients health breakdown
    cli_count = (site.clients or {}).get("count", 0)
    lines.append(f"[bold]Clients ({cli_count}):[/bold]")
    lines.append(f"  Good: {cli_buckets['good']}  Fair: {cli_buckets['fair']}  Poor: {cli_buckets['poor']}")

    # Alert groups
    alerts = site.alerts or {}
    alert_total = alerts.get("totalCount", 0)
    if alert_total > 0:
        lines.append("")
        lines.append(f"[bold]Alerts ({alert_total}):[/bold]")
        for g in (alerts.get("groups") or []):
            lines.append(f"  {g.get('name', '?')}: {g.get('count', 0)}")

    # Reasons
    reasons = site.reasons or []
    if reasons:
        lines.append("")
        lines.append("[bold]Reasons:[/bold]")
        for r in reasons:
            health = r.get("health", "")
            reason = r.get("reason", "")
            count = (r.get("data") or {}).get("count")
            suffix = f" ×{count}" if count is not None else ""
            lines.append(f"  [{health}] {reason}{suffix}")

    console.print(
        Panel(
            "\n".join(lines),
            title=f"[bold cyan]{site.siteName or site.id}[/bold cyan]",
            border_style="cyan",
        )
    )


def render_device_detail(console: Console, device: Device) -> None:
    """Render an expanded panel for a single Device row."""
    lines = [
        f"[bold]Serial:[/bold]      {device.serialNumber or '—'}",
        f"[bold]MAC:[/bold]         {device.macAddress or '—'}",
        f"[bold]Role:[/bold]        {device.role or '—'}",
        f"[bold]Function:[/bold]    {device.deviceFunction or '—'}",
        f"[bold]Group:[/bold]       {device.deviceGroupName or '—'}",
        f"[bold]Provisioned:[/bold] {device.isProvisioned or '—'}",
        f"[bold]Deployment:[/bold]  {device.deployment or '—'}",
    ]
    console.print(
        Panel(
            "\n".join(lines),
            title=f"[bold cyan]{device.deviceName or device.id}[/bold cyan]",
            border_style="cyan",
        )
    )


def render_client_detail(console: Console, client: Client) -> None:
    """Render an expanded panel for a single Client row."""
    lines = [
        f"[bold]Manufacturer:[/bold]  {client.clientManufacturer or '—'}",
        f"[bold]OS:[/bold]            {client.clientOperatingSystem or '—'}",
        f"[bold]Function:[/bold]      {client.clientFunction or '—'}",
        f"[bold]Security:[/bold]      {client.wirelessSecurity or '—'}",
        f"[bold]Band:[/bold]          {client.wirelessBand or '—'}",
        f"[bold]Channel:[/bold]       {client.wirelessChannel if client.wirelessChannel else '—'}",
        f"[bold]WLAN Name:[/bold]     {client.wlanName or '—'}",
    ]
    console.print(
        Panel(
            "\n".join(lines),
            title=f"[bold cyan]{client.clientName or client.id}[/bold cyan]",
            border_style="cyan",
        )
    )
