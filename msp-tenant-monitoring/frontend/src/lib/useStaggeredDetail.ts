import React from 'react'
import useSWR, { useSWRConfig } from 'swr'
import { getTenantDetail } from '@/lib/api'
import type { IncludeType, Site, Device, Client, Alert } from '@/lib/api'
import { detailKey, projectDetail } from '@/lib/detailKeys'

type TabName = 'sites' | 'devices' | 'clients' | 'alerts'

// Stagger offsets (ms after page land) for the non-gating types.
// Sites is always fetched immediately (and is usually pre-warmed by the
// exchange modal, which navigates only once sites data is in hand).
const STAGGER: Record<Exclude<TabName, 'sites'>, number> = {
  devices: 0,
  clients: 400,
  alerts: 800,
}

export interface DetailResult {
  sites: Site[] | undefined | null
  devices: Device[] | undefined | null
  clients: Client[] | undefined | null
  alerts: Alert[] | undefined | null
  errors: { sites: unknown; devices: unknown; clients: unknown; alerts: unknown }
  fetching: Record<TabName, boolean>
  fetchNow: (type: IncludeType) => void
}

// ---- useStaggeredDetail ----
// Sites fires immediately; devices/clients/alerts fire on staggered timers
// (selected types only). Activating a tab whose fetch hasn't fired yet
// queue-jumps it. Returns per-type tri-state values (undefined=loading,
// null=not-selected, T[]=data) and per-type errors so a single failure
// doesn't poison all tabs.

export function useStaggeredDetail(
  id: string | undefined,
  selected: IncludeType[],
  activeTab: TabName,
): DetailResult {
  const { mutate } = useSWRConfig()

  // "fired" = this type's SWR key may become non-null. Sites is always fired.
  const [fired, setFired] = React.useState<Set<TabName>>(() => new Set(['sites']))

  // Reset when navigating to a different tenant
  React.useEffect(() => {
    setFired(new Set(['sites']))
  }, [id])

  const fire = React.useCallback((type: TabName) => {
    setFired((prev) => (prev.has(type) ? prev : new Set(prev).add(type)))
  }, [])

  // Stable dep key — avoids re-arming timers on array identity churn
  const selectedKey = selected.join(',')

  // Stagger timers for selected non-sites types; cleanup clears pending timers
  React.useEffect(() => {
    if (!id) return
    const timers = (Object.keys(STAGGER) as (keyof typeof STAGGER)[])
      .filter((t) => selected.includes(t))
      .map((t) => window.setTimeout(() => fire(t), STAGGER[t]))
    return () => timers.forEach((h) => window.clearTimeout(h))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, selectedKey, fire])

  // Queue-jump: activating a selected, not-yet-fired tab fires it immediately
  React.useEffect(() => {
    if (id && selected.includes(activeTab)) fire(activeTab)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, activeTab, selectedKey, fire])

  const keyFor = (type: TabName) =>
    id != null && fired.has(type) ? detailKey(id, type) : null

  const sitesKey = keyFor('sites')
  const devicesKey = keyFor('devices')
  const clientsKey = keyFor('clients')
  const alertsKey = keyFor('alerts')

  // Four hooks in fixed order — stable hook count across renders
  const { data: sitesData, error: sitesErr, isValidating: sitesBusy } = useSWR<Site[]>(
    sitesKey,
    () => getTenantDetail(id!, ['sites']).then((d) => d.sites ?? []),
  )
  const { data: devicesData, error: devicesErr, isValidating: devicesBusy } = useSWR<Device[]>(
    devicesKey,
    () => getTenantDetail(id!, ['devices']).then((d) => d.devices ?? []),
  )
  const { data: clientsData, error: clientsErr, isValidating: clientsBusy } = useSWR<Client[]>(
    clientsKey,
    () => getTenantDetail(id!, ['clients']).then((d) => d.clients ?? []),
  )
  const { data: alertsData, error: alertsErr, isValidating: alertsBusy } = useSWR<Alert[]>(
    alertsKey,
    () => getTenantDetail(id!, ['alerts']).then((d) => d.alerts ?? []),
  )

  // Manual fetch: fires an unfired type (FetchNow on deselected types) or
  // revalidates a fired one (retry after error).
  const fetchNow = React.useCallback(
    (type: IncludeType) => {
      if (!id) return
      if (fired.has(type)) {
        mutate(detailKey(id, type))
      } else {
        fire(type)
      }
    },
    [id, fired, fire, mutate],
  )

  return {
    sites: projectDetail({ fired: fired.has('sites'), selected: selected.includes('sites' as IncludeType), data: sitesData, error: sitesErr }),
    devices: projectDetail({ fired: fired.has('devices'), selected: selected.includes('devices' as IncludeType), data: devicesData, error: devicesErr }),
    clients: projectDetail({ fired: fired.has('clients'), selected: selected.includes('clients' as IncludeType), data: clientsData, error: clientsErr }),
    alerts: projectDetail({ fired: fired.has('alerts'), selected: selected.includes('alerts' as IncludeType), data: alertsData, error: alertsErr }),
    errors: { sites: sitesErr, devices: devicesErr, clients: clientsErr, alerts: alertsErr },
    fetching: {
      sites: sitesBusy,
      devices: devicesBusy,
      clients: clientsBusy,
      alerts: alertsBusy,
    },
    fetchNow,
  }
}
