// ---- Domain types (mirror Python dataclasses) ----

export const DOCS_URL = 'https://developer.arubanetworks.com/new-central/docs/msp-token-exchange'
export const AUTH_URL = 'https://developer.arubanetworks.com/new-central/docs/msp-token-exchange#one-time-setup'
export interface TenantSummary {
  tenant_id: string
  tenant_name: string
  total_sites: number
  degraded_sites: number
  device_health: { total: number; good: number; fair: number; poor: number }
  alerts: { total: number; critical: number; major: number; minor: number }
  last_updated_time: number
  glp_workspace_id?: string | null
  device_ownership?: string | null
}

export interface SiteAddress {
  country?: string
  address?: string
  city?: string
  state?: string
  zipCode?: string
  [k: string]: unknown
}

export interface SiteReason {
  health?: string
  reason?: string
  data?: Record<string, unknown>
}

export interface Site {
  id: string
  siteName: string
  address: SiteAddress
  alerts: { totalCount: number; groups: Array<{ name: string; count: number }> }
  health: { groups: Array<{ name: string; value: number }> }
  devices: { count: number; health: { groups: Array<{ name: string; value: number }> } }
  clients: { count: number; health: { groups: Array<{ name: string; value: number }> } }
  reasons?: SiteReason[]
}

export interface Device {
  id: string
  deviceName: string
  deviceType: string
  model: string
  serialNumber: string
  macAddress: string
  ipv4: string
  siteId: string | null
  siteName: string
  status: string
  firmwareVersion: string
  role: string
  deviceFunction: string
  deviceGroupName: string
  isProvisioned: string
  deployment: string
}

export interface Client {
  id: string
  clientName: string
  hostName: string
  macAddress: string
  ipv4: string
  status: string
  connectedDeviceType: string
  clientConnectionType: string
  connectedDeviceSerial: string
  siteId: string | number
  siteName: string
  vlanId: string
  vlanName: string
  wlanName: string
  userName: string
  clientManufacturer: string
  clientFunction: string
  clientOperatingSystem: string
  snr: number
  wirelessBand: string
  wirelessChannel: number
  wirelessSecurity: string
}

export interface Alert {
  id: string
  key: string
  name: string
  summary: string
  severity: string
  status: string
  priority: string
  category: string
  deviceType: string
  createdAt: string
  updatedAt: string
  clearedReason: string | null
}

export interface Tenant {
  summary: TenantSummary
}

export interface Totals {
  tenants: number
  sites: number
  degraded_sites: number
  devices: number
  alerts: { total: number; critical: number; major: number; minor: number }
}

export interface Overview {
  tenants: Tenant[]
  totals: Totals
  last_refresh_ts: number | null
}

export interface StatusResponse {
  authenticated: boolean
  workspace_id_masked?: string
  last_refresh_ts: number | null
  next_refresh_ts: number | null
  refresh_interval_s: number
  demo?: boolean
}

export interface MspCredentials {
  client_id: string
  client_secret: string
  workspace_id: string
  base_url: string
}

export interface LoginResponse {
  ok: boolean
  tenant_count: number
}

export interface ExchangeInfo {
  cached: boolean
  workspace_id: string
  grant_type: string
  token_url: string
  msp_token_masked: string
  tenant_token_masked: string | null
  duration_ms: number
  error: string | null
  simulated?: boolean
}

// ---- Fetch helpers ----

async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init)
  if (!r.ok) {
    let detail: string = `API error ${r.status}: ${r.statusText}`
    try {
      const body = await r.json()
      if (body && typeof body.detail === 'string') detail = body.detail
    } catch {
      // body isn't JSON — keep the default message
    }
    throw new Error(detail)
  }
  return r.json() as Promise<T>
}

export async function getOverview(): Promise<Overview> {
  return apiFetch<Overview>('/api/overview')
}

export async function getStatus(): Promise<StatusResponse> {
  return apiFetch<StatusResponse>('/api/status')
}

export async function postRefresh(): Promise<Overview> {
  return apiFetch<Overview>('/api/refresh', { method: 'POST' })
}

export type IncludeType = 'sites' | 'devices' | 'clients' | 'alerts'

export interface TenantDetail {
  sites: Site[] | null
  devices: Device[] | null
  clients: Client[] | null
  alerts: Alert[] | null
}

export async function getTenantDetail(id: string, include?: IncludeType[]): Promise<TenantDetail> {
  const qs = include && include.length ? `?include=${include.join(',')}` : ''
  return apiFetch<TenantDetail>(`/api/tenants/${id}${qs}`)
}

export async function login(creds: MspCredentials): Promise<LoginResponse> {
  return apiFetch<LoginResponse>('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds),
  })
}

export async function logout(): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>('/api/auth/logout', { method: 'POST' })
}

export async function loginDemo(): Promise<{ ok: boolean; tenant_count: number; demo: boolean }> {
  return apiFetch('/api/auth/demo', { method: 'POST' })
}

export async function exchangeTenant(id: string): Promise<ExchangeInfo> {
  return apiFetch<ExchangeInfo>(`/api/tenants/${id}/exchange`, { method: 'POST' })
}
