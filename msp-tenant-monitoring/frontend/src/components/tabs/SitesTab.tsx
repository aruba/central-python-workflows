import {
  Building2,
  MapPin,
  AlertTriangle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { HealthBar } from '@/components/HealthBar'
import { formatNumber } from '@/lib/format'
import { DataTable } from '@/components/DataTable'
import type { Column } from '@/components/DataTable'
import type { Site } from '@/lib/api'
import { useTableFilter } from '@/lib/useTableFilter'
import type { FilterSpec } from '@/lib/useTableFilter'

interface SitesTabProps {
  sites: Site[]
}

function dominantHealth(site: Site): string {
  const groups = site.health?.groups ?? []
  if (groups.length === 0) return ''
  return groups.reduce((a, b) => (b.value > a.value ? b : a)).name
}

function healthBuckets(groups: Array<{ name: string; value: number }>) {
  const get = (n: string) =>
    groups.find((g) => g.name?.toLowerCase() === n)?.value ?? 0
  return { good: get('good'), fair: get('fair'), poor: get('poor') }
}

function formatAddress(addr: Site['address']): string {
  const parts: string[] = []
  if (addr?.address) parts.push(String(addr.address))
  if (addr?.city) parts.push(String(addr.city))
  if (addr?.state) parts.push(String(addr.state))
  if (addr?.zipCode) parts.push(String(addr.zipCode))
  if (addr?.country) parts.push(String(addr.country))
  return parts.join(', ')
}

function shortLocation(addr: Site['address']): string {
  const parts: string[] = []
  if (addr?.city) parts.push(String(addr.city))
  if (addr?.state) parts.push(String(addr.state))
  return parts.join(', ')
}

function healthBadgeClass(name: string): string {
  switch (name.toLowerCase()) {
    case 'good':
      return 'bg-success/15 text-success border-transparent'
    case 'fair':
      return 'bg-warning/15 text-warning border-transparent'
    case 'poor':
      return 'bg-danger/15 text-danger border-transparent'
    default:
      return ''
  }
}

function SiteExpandedRow({ site }: { site: Site }) {
  const fullAddress = formatAddress(site.address)
  const devBuckets = healthBuckets(site.devices?.health?.groups ?? [])
  const cliBuckets = healthBuckets(site.clients?.health?.groups ?? [])

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 py-4 px-4">
      {/* Address */}
      <div className="flex flex-col gap-1">
        <div className="text-xs text-muted-foreground flex items-center gap-1">
          <MapPin className="h-3 w-3" /> Address
        </div>
        <div className="text-sm">{fullAddress || '—'}</div>
        {site.address?.country && (
          <div className="text-xs text-muted-foreground">
            {String(site.address.country)}
          </div>
        )}
      </div>

      {/* Devices health breakdown */}
      <div className="flex flex-col gap-1.5">
        <div className="text-xs text-muted-foreground">
          Devices ({formatNumber(site.devices?.count ?? 0)})
        </div>
        <HealthBar
          good={devBuckets.good}
          fair={devBuckets.fair}
          poor={devBuckets.poor}
        />
        <div className="text-xs tabular-nums text-muted-foreground">
          Good {devBuckets.good} · Fair {devBuckets.fair} · Poor {devBuckets.poor}
        </div>
      </div>

      {/* Clients health breakdown */}
      <div className="flex flex-col gap-1.5">
        <div className="text-xs text-muted-foreground">
          Clients ({formatNumber(site.clients?.count ?? 0)})
        </div>
        <HealthBar
          good={cliBuckets.good}
          fair={cliBuckets.fair}
          poor={cliBuckets.poor}
        />
        <div className="text-xs tabular-nums text-muted-foreground">
          Good {cliBuckets.good} · Fair {cliBuckets.fair} · Poor {cliBuckets.poor}
        </div>
      </div>

      {/* Alerts breakdown */}
      {site.alerts?.totalCount > 0 && (
        <div className="flex flex-col gap-1 lg:col-span-1">
          <div className="text-xs text-muted-foreground flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" /> Alerts ({site.alerts.totalCount})
          </div>
          <div className="flex flex-wrap gap-1.5">
            {site.alerts.groups?.map((g) => (
              <Badge
                key={g.name}
                variant="outline"
                className={`text-xs tabular-nums ${
                  g.name.toLowerCase() === 'critical'
                    ? 'bg-danger/15 text-danger border-transparent'
                    : g.name.toLowerCase() === 'major'
                      ? 'bg-warning/15 text-warning border-transparent'
                      : ''
                }`}
              >
                {g.name}: {g.count}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Reasons */}
      {site.reasons && site.reasons.length > 0 && (
        <div className="flex flex-col gap-1 lg:col-span-2">
          <div className="text-xs text-muted-foreground">Reasons</div>
          <div className="flex flex-col gap-1">
            {site.reasons.map((r, i) => {
              const count = (r.data as { count?: number } | undefined)?.count
              return (
                <div key={i} className="text-xs flex items-center gap-2">
                  {r.health && (
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${healthBadgeClass(r.health)}`}
                    >
                      {r.health}
                    </Badge>
                  )}
                  <span className="font-mono text-muted-foreground">
                    {r.reason}
                  </span>
                  {count !== undefined && (
                    <span className="tabular-nums">×{count}</span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

const COLUMNS: Column<Site>[] = [
  {
    id: 'site',
    header: 'Site',
    cell: (s) => <span className="font-medium">{s.siteName || '—'}</span>,
  },
  {
    id: 'location',
    header: 'Location',
    cell: (s) => (
      <span className="text-xs text-muted-foreground">
        {shortLocation(s.address) || '—'}
      </span>
    ),
  },
  {
    id: 'health',
    header: 'Health',
    headerClassName: 'min-w-40',
    cell: (s) => {
      const dominant = dominantHealth(s)
      const devBuckets = healthBuckets(s.devices?.health?.groups ?? [])
      return (
        <div className="flex flex-col gap-1">
          {dominant ? (
            <Badge
              variant="outline"
              className={`w-fit text-[10px] ${healthBadgeClass(dominant)}`}
            >
              {dominant}
            </Badge>
          ) : (
            <span className="text-muted-foreground text-xs">—</span>
          )}
          <HealthBar
            good={devBuckets.good}
            fair={devBuckets.fair}
            poor={devBuckets.poor}
          />
        </div>
      )
    },
  },
  {
    id: 'devices',
    header: 'Devices',
    headerClassName: 'text-right',
    cellClassName: 'text-right tabular-nums',
    cell: (s) => formatNumber(s.devices?.count ?? 0),
  },
  {
    id: 'clients',
    header: 'Clients',
    headerClassName: 'text-right',
    cellClassName: 'text-right tabular-nums',
    cell: (s) => formatNumber(s.clients?.count ?? 0),
  },
  {
    id: 'alerts',
    header: 'Alerts',
    headerClassName: 'text-right',
    cellClassName: 'text-right',
    cell: (s) =>
      s.alerts?.totalCount > 0 ? (
        <Badge variant="destructive" className="tabular-nums text-xs">
          {s.alerts.totalCount}
        </Badge>
      ) : (
        <span className="text-muted-foreground text-xs">0</span>
      ),
  },
]

const SITES_SPEC: FilterSpec<Site> = {
  search: {
    paramKey: 'q',
    fields: (s) => [
      s.siteName,
      s.address?.city,
      s.address?.state,
      s.address?.country,
      s.address?.address,
      s.address?.zipCode,
    ],
  },
}

export function SitesTab({ sites }: SitesTabProps) {
  const { filtered } = useTableFilter(sites, SITES_SPEC)

  return (
    <DataTable
      rows={sites}
      filtered={filtered}
      rowKey={(s) => s.id}
      columns={COLUMNS}
      expandedRow={(s) => <SiteExpandedRow site={s} />}
      search={{
        paramKey: 'q',
        placeholder: 'Search name, city, state, country…',
      }}
      emptyData={{
        icon: <Building2 className="h-8 w-8" />,
        title: 'No sites configured',
      }}
      emptyFiltered="No sites match the current filters"
    />
  )
}

