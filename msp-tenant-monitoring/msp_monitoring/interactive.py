"""Interactive REPL loop and navigation state machine for the MSP monitoring CLI.

Provides:
  - prompt()          async wrapper around blocking input()
  - get_detail()      async lazy fetch with session cache
  - evict()           remove a cache entry so 'r' forces re-fetch
  - _filter_rows()    case-insensitive search per tab
  - run_interactive() top-level entry point (called from main._run)
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from rich.console import Console

from msp_monitoring import reporter
from msp_monitoring.collector import collect_overview
from msp_monitoring.models import TenantDetail, TenantSummary

if TYPE_CHECKING:
    from msp_monitoring.sources.base import GLPSource, TenantDataSource

# ---------------------------------------------------------------------------
# Sentinel for propagating quit through nested loops
# ---------------------------------------------------------------------------

_QUIT = object()


# ---------------------------------------------------------------------------
# Async prompt helper
# ---------------------------------------------------------------------------


async def prompt(message: str) -> str:
    """Read a line from stdin off the event loop thread."""
    return (await asyncio.to_thread(input, message)).strip()


# ---------------------------------------------------------------------------
# Session cache helpers
# ---------------------------------------------------------------------------

# Cache type: dict[tuple[tenant_id, frozenset[str]], TenantDetail]
Cache = dict[tuple[str, frozenset], TenantDetail]


async def get_detail(
    source: "TenantDataSource",
    cache: Cache,
    tenant: TenantSummary,
    include: frozenset,
) -> TenantDetail:
    """Return a cached TenantDetail or lazily fetch and store it."""
    key = (tenant.tenant_id, include)
    if key in cache:
        return cache[key]
    detail = await source.fetch_detail(tenant.glp_workspace_id, set(include))
    cache[key] = detail
    return detail


def evict(cache: Cache, tenant: TenantSummary, include: frozenset) -> None:
    """Remove a cache entry so the next get_detail call re-fetches."""
    key = (tenant.tenant_id, include)
    cache.pop(key, None)


# ---------------------------------------------------------------------------
# Per-tab row filter
# ---------------------------------------------------------------------------


def _filter_rows(tab: str, rows: list, term: str) -> list:
    """Return rows whose relevant fields contain *term* (case-insensitive)."""
    if not term:
        return list(rows)
    t = term.lower()

    def _match_site(s) -> bool:
        # address sub-fields live in s.address dict
        addr = s.address or {}
        return (
            t in (s.siteName or "").lower()
            or t in str(addr.get("city", "")).lower()
            or t in str(addr.get("state", "")).lower()
            or t in str(addr.get("country", "")).lower()
            or t in str(addr.get("zipCode", "")).lower()
        )

    def _match_device(d) -> bool:
        return (
            t in (d.deviceName or "").lower()
            or t in (d.model or "").lower()
            or t in (d.ipv4 or "").lower()
            or t in (d.macAddress or "").lower()
            or t in (d.serialNumber or "").lower()
        )

    def _match_client(c) -> bool:
        return (
            t in (c.clientName or "").lower()
            or t in (c.hostName or "").lower()
            or t in (c.macAddress or "").lower()
            or t in (c.ipv4 or "").lower()
            or t in (c.userName or "").lower()
        )

    def _match_alert(a) -> bool:
        return (
            t in (a.name or "").lower()
            or t in (a.summary or "").lower()
            or t in (a.category or "").lower()
        )

    matchers = {
        "sites": _match_site,
        "devices": _match_device,
        "clients": _match_client,
        "alerts": _match_alert,
    }
    matcher = matchers.get(tab)
    if matcher is None:
        return list(rows)
    return [r for r in rows if matcher(r)]


# ---------------------------------------------------------------------------
# Tab-level REPL loop
# ---------------------------------------------------------------------------

_TAB_INCLUDE = {
    "s": frozenset({"sites"}),
    "d": frozenset({"devices"}),
    "c": frozenset({"clients"}),
    "a": frozenset({"alerts"}),
}
_TAB_NAME = {
    "s": "sites",
    "d": "devices",
    "c": "clients",
    "a": "alerts",
}
_TABLE_RENDERERS = {
    "sites": reporter.render_sites_table,
    "devices": reporter.render_devices_table,
    "clients": reporter.render_clients_table,
    "alerts": reporter.render_alerts_table,
}
_DETAIL_RENDERERS = {
    "sites": reporter.render_site_detail,
    "devices": reporter.render_device_detail,
    "clients": reporter.render_client_detail,
    # alerts: no detail renderer
}


async def _tab_loop(
    console: Console,
    source: "TenantDataSource",
    cache: Cache,
    tenant: TenantSummary,
    tab_key: str,
) -> object:
    """Run the tab-level REPL. Returns _QUIT or None (back to tenant menu)."""
    tab = _TAB_NAME[tab_key]
    include = _TAB_INCLUDE[tab_key]
    search_term = ""
    render_table = _TABLE_RENDERERS[tab]

    # Initial fetch
    try:
        detail = await get_detail(source, cache, tenant, include)
    except Exception as exc:
        reporter.render_error(console, f"Failed to load {tab}: {exc}")
        return None  # back to tenant menu

    all_rows: list = getattr(detail, tab) or []
    visible = _filter_rows(tab, all_rows, search_term)
    render_table(console, visible)

    # Hint: shown once on tab entry
    if tab == "alerts":
        console.print("[dim]Commands: /text = search · r = refresh · b = back · q = quit  (alerts have no detail view)[/dim]")
    else:
        console.print("[dim]Commands: /text = search · <number> = expand row · r = refresh · b = back · q = quit[/dim]")

    while True:
        try:
            raw = await prompt(f"  {tenant.tenant_name} / {tab} > ")
        except (EOFError, KeyboardInterrupt):
            console.print()
            return _QUIT  # overview loop prints the single "Bye." on _QUIT

        cmd = raw.strip()

        # "/" or "/term" — set/clear search
        if cmd.startswith("/"):
            search_term = cmd[1:]
            visible = _filter_rows(tab, all_rows, search_term)
            render_table(console, visible)
            continue

        if cmd == "r":
            # Evict and re-fetch
            evict(cache, tenant, include)
            try:
                detail = await get_detail(source, cache, tenant, include)
            except Exception as exc:
                reporter.render_error(console, f"Failed to refresh {tab}: {exc}")
                return None  # back to tenant menu
            all_rows = getattr(detail, tab) or []
            visible = _filter_rows(tab, all_rows, search_term)
            render_table(console, visible)
            continue

        if cmd == "b":
            return None  # back to tenant menu

        if cmd == "q":
            return _QUIT

        # Numeric: expand row
        if cmd.isdigit():
            idx = int(cmd) - 1  # 1-based -> 0-based
            if idx < 0 or idx >= len(visible):
                reporter.render_error(console, f"Row {cmd} is out of range (1–{len(visible)}).")
                continue
            if tab == "alerts":
                console.print("[dim]Alerts have no detail view.[/dim]")
            else:
                detail_renderer = _DETAIL_RENDERERS[tab]
                detail_renderer(console, visible[idx])
            continue

        reporter.render_error(console, f"Unknown command: {cmd!r}. Use /term, r, b, q, or a row number.")


# ---------------------------------------------------------------------------
# Tenant-level menu loop
# ---------------------------------------------------------------------------


async def _tenant_loop(
    console: Console,
    source: "TenantDataSource",
    cache: Cache,
    tenant: TenantSummary,
) -> object:
    """Run the tenant-level menu. Returns _QUIT or None (back to overview)."""
    # Print tenant header
    crit = tenant.alerts.get("critical", 0)
    console.print(
        f"\n[bold cyan]{tenant.tenant_name}[/bold cyan]  "
        f"sites={tenant.total_sites}  "
        f"devices={tenant.device_health.get('total', 0)}  "
        f"critical_alerts={crit}"
    )

    while True:
        # Escape the brackets so rich renders them literally (e.g. "[s]ites")
        # rather than parsing [s], [d]… as markup tags and stripping them.
        console.print("[dim]  \\[s]ites  \\[d]evices  \\[c]lients  \\[a]lerts  \\[b]ack  \\[q]uit[/dim]")
        try:
            cmd = await prompt("  tenant > ")
        except (EOFError, KeyboardInterrupt):
            console.print()
            return _QUIT  # overview loop prints the single "Bye." on _QUIT

        cmd = cmd.lower()

        if cmd in ("s", "d", "c", "a"):
            result = await _tab_loop(console, source, cache, tenant, cmd)
            if result is _QUIT:
                return _QUIT
            # Otherwise stay in tenant menu (re-print header)
            console.print(
                f"\n[bold cyan]{tenant.tenant_name}[/bold cyan]  "
                f"sites={tenant.total_sites}  "
                f"devices={tenant.device_health.get('total', 0)}  "
                f"critical_alerts={crit}"
            )
        elif cmd == "b":
            return None  # back to overview
        elif cmd == "q":
            return _QUIT
        else:
            reporter.render_error(console, f"Unknown option: {cmd!r}. Use s, d, c, a, b, or q.")


# ---------------------------------------------------------------------------
# Overview loop
# ---------------------------------------------------------------------------


async def _overview_loop(
    console: Console,
    source: "TenantDataSource",
    cache: Cache,
    results: list[TenantSummary],
) -> None:
    """Run the overview REPL loop (select a tenant by number)."""
    reporter.render_tenant_list(console, results)
    console.print("[dim]Type a tenant number to drill in, or q to quit.[/dim]")

    while True:
        try:
            raw = await prompt("Select tenant # (q to quit): ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye.[/dim]")
            return

        cmd = raw.strip()

        if cmd.lower() == "q":
            console.print("[dim]Bye.[/dim]")
            return

        if not cmd.isdigit():
            reporter.render_error(console, f"Enter a number (1–{len(results)}) or q to quit.")
            reporter.render_tenant_list(console, results)
            continue

        idx = int(cmd) - 1  # 1-based -> 0-based
        if idx < 0 or idx >= len(results):
            reporter.render_error(console, f"Row {cmd} is out of range (1–{len(results)}).")
            reporter.render_tenant_list(console, results)
            continue

        tenant = results[idx]
        result = await _tenant_loop(console, source, cache, tenant)
        if result is _QUIT:
            console.print("[dim]Bye.[/dim]")
            return

        # Back from tenant menu — reprint tenant list
        reporter.render_tenant_list(console, results)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_interactive(
    source: "TenantDataSource",
    glp_source: "GLPSource | None",
    *,
    tenant_filter: str | None = None,
    console: Console | None = None,
) -> None:
    """Collect overview then run the interactive REPL.

    Must be called inside the ``with select_source()`` block so MSPBase
    stays open for on-demand ``fetch_detail`` calls throughout the session.
    """
    if console is None:
        console = Console()

    try:
        results = await collect_overview(
            source,
            tenant_filter=tenant_filter,
            glp_source=glp_source,
        )
    except Exception as exc:
        reporter.render_error(console, f"Failed to load tenant overview: {exc}")
        return

    # Show the fleet totals panel once; the numbered tenant list (rendered by
    # the overview loop) is the single selectable table — avoids printing the
    # tenant rows twice.
    reporter.render_totals_panel(console, results)

    if not results:
        console.print("[dim]No tenants found.[/dim]")
        return

    cache: Cache = {}
    await _overview_loop(console, source, cache, results)
