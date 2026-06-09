# Development Guide

This guide covers frontend and backend development for the MSP Control Tower. It assumes you have already completed the installation and configuration steps in the [README](../README.md).

---

## Frontend Development

### Prerequisites

- Node.js LTS (v20 or later recommended)
- The Python server must be running separately to serve `/api/*` responses

### Run with Hot Module Replacement (HMR)

```bash
cd frontend
npm install
npm run dev
# open http://localhost:5173/
```

Vite proxies all `/api/*` requests to the FastAPI server on `:8000`, so run both in separate terminals:

```bash
# Terminal 1 — Python backend
python3 server.py

# Terminal 2 — Vite dev server
cd frontend && npm run dev
```

### Rebuild prebuilt assets

After any UI change, rebuild the static assets committed in `static/` so the server can serve them without Node:

```bash
cd frontend && npm run build
```

Output goes to `../static/` (configured in `vite.config.ts`).

### Lint and type-check

```bash
cd frontend
npm run lint          # ESLint
npx tsc --noEmit      # TypeScript type check
```

### Run frontend tests

```bash
cd frontend
npm test              # vitest run (single pass)
npm run test:watch    # vitest watch mode
```

Tests live in `frontend/src/lib/*.test.ts` and `frontend/src/test/`.

### Structure

```
frontend/src/
  pages/          Overview.tsx, TenantDetail.tsx
  components/     Topbar, KpiStrip, TenantCard, HealthBar, DataTable, tabs/*
  lib/            api.ts, polling.ts, theme.tsx, useTableFilter.ts, detailKeys.ts, …
  main.tsx        React entry point
```

The UI uses semantic Tailwind tokens (`bg-background`, `text-foreground`, `border-border`) so dark mode works via the `.dark` class on `<html>`. Theme state is persisted via `localStorage` (see `src/lib/theme.tsx`).

---

## Backend Development

### Prerequisites

- Python ≥ 3.10
- Project virtual environment activated (`.venv/`)

### Run the server

```bash
python3 server.py
```

The server starts on port `8000` and mounts prebuilt UI assets from `static/`. It spawns a background task that refreshes the cross-tenant overview every 15 minutes.

### Package structure

```
msp_monitoring/
  collector.py        collect_overview() — MSP-level overview fetch
  models.py           TenantSummary, TenantDetail, Site, Device, Client, Alert dataclasses
  detail_cache.py     DetailCache — coalesces concurrent fetches, enforces TTL
  export.py           dump_json() / dump_csv()
  config.py           Credential loading (token.yaml or env vars)
  session.py          exchange_metadata() — RFC 8693 introspection for the UI
  sources/
    base.py           TenantDataSource + GLPSource protocols
    pycentral_source.py  Real pycentral 2.0a19 (MSPBase) — overview + per-tenant detail
    glp_source.py        GLP workspace listing; shares the MSPBase instance
    mappers.py           Pure map_* functions: raw API dict → model dataclass
    pagination.py        paginate_cursor / paginate_offset helpers
    demo_source.py       Replay source backed by demo_fixture.json (no credentials)
```

### Key server behaviours

| Behaviour | Detail |
|-----------|--------|
| Background refresh | Runs every 15 minutes via `asyncio` background task; can be forced with `POST /api/refresh` |
| Detail cache | `DetailCache` coalesces concurrent fetches for the same `(tenant_id, include)` key and evicts after 60 s |
| Demo mode | `DemoSource` replays `msp_monitoring/demo_fixture.json`; no MSPBase is created |
| Auth guard | All data endpoints call `_require_auth()` which raises `401` if no source is active |

---

## FastAPI API Endpoints

These are the routes exposed by `server.py` and consumed by the React frontend.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/login` | Authenticate with MSP credentials |
| `POST` | `/api/auth/demo` | Start demo mode (no credentials) |
| `POST` | `/api/auth/logout` | Disconnect and clear session |
| `GET` | `/api/overview` | Latest cached cross-tenant overview |
| `POST` | `/api/refresh` | Force background refresh now |
| `GET` | `/api/tenants/{id}?include=sites,devices,clients,alerts` | Per-tenant detail resources (on-demand) |
| `POST` | `/api/tenants/{id}/exchange` | Token exchange metadata for a tenant |
| `GET` | `/api/status` | Authentication and refresh status |
| `GET` | `/api/export?format=json\|csv` | Export overview data |
