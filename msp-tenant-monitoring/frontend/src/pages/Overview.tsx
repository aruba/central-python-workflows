import { useMemo, useState } from 'react'
import useSWR from 'swr'
import { Search, X } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { KpiStrip } from '@/components/KpiStrip'
import { TenantCard } from '@/components/TenantCard'
import { getOverview, type Tenant } from '@/lib/api'
import { useAutoEnabled } from '@/lib/autoRefresh'
import { AUTO_INTERVAL_MS } from '@/lib/constants'

type OwnershipFilter = 'all' | 'MSP' | 'TENANT'

function SkeletonCard() {
  return (
    <Card>
      <CardContent className="p-4 flex flex-col gap-3">
        <div className="flex items-start justify-between gap-2">
          <Skeleton className="h-5 w-36" />
          <Skeleton className="h-5 w-10" />
        </div>
        <div className="flex items-center gap-4">
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-4 w-12" />
        </div>
        <div className="flex flex-col gap-1">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-1.5 w-full rounded-full" />
        </div>
      </CardContent>
    </Card>
  )
}

interface OwnershipToggleProps {
  value: OwnershipFilter
  onChange: (next: OwnershipFilter) => void
}

function OwnershipToggle({ value, onChange }: OwnershipToggleProps) {
  const items: Array<{ key: OwnershipFilter; label: string }> = [
    { key: 'all', label: 'All' },
    { key: 'MSP', label: 'MSP owned' },
    { key: 'TENANT', label: 'Tenant owned' },
  ]
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium text-muted-foreground">
        Inventory Owner
      </span>
      <div
        role="radiogroup"
        aria-label="Filter by inventory ownership"
        className="inline-flex items-center rounded-full border border-border bg-card p-0.5 shadow-stack-1"
      >
        {items.map(({ key, label }) => {
          const active = value === key
          return (
            <button
              key={key}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(key)}
              className={`px-3.5 h-7 text-[13px] font-medium rounded-full transition-colors ${
                active
                  ? 'bg-foreground text-background'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function tenantMatches(
  t: Tenant,
  query: string,
  ownership: OwnershipFilter,
): boolean {
  if (ownership !== 'all' && t.summary.device_ownership !== ownership) {
    return false
  }
  if (query.length > 0) {
    const haystack = t.summary.tenant_name.toLowerCase()
    if (!haystack.includes(query)) return false
  }
  return true
}

export function Overview() {
  const autoEnabled = useAutoEnabled()

  const { data: overview, isLoading, isValidating } = useSWR(
    ['overview'],
    () => getOverview(),
    { refreshInterval: autoEnabled ? AUTO_INTERVAL_MS : 0 },
  )

  const isRevalidating = isValidating && !isLoading

  const [query, setQuery] = useState('')
  const [ownership, setOwnership] = useState<OwnershipFilter>('all')

  const filterActive = query.trim().length > 0 || ownership !== 'all'

  const filteredTenants = useMemo(() => {
    if (!overview) return []
    const q = query.trim().toLowerCase()
    return overview.tenants.filter((t) => tenantMatches(t, q, ownership))
  }, [overview, query, ownership])

  function clearFilters() {
    setQuery('')
    setOwnership('all')
  }

  return (
    <div className="flex flex-col gap-8">
      <KpiStrip
        tenants={overview?.totals.tenants}
        sites={overview?.totals.sites}
        devices={overview?.totals.devices}
        alerts={overview?.totals.alerts}
      />

      {/* Filter bar */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <Input
            type="search"
            placeholder="Search tenants…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-8"
            aria-label="Search tenants by name"
          />
        </div>
        <OwnershipToggle value={ownership} onChange={setOwnership} />
        {filterActive && overview && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="tabular-nums">
              Showing {filteredTenants.length} of {overview.tenants.length} tenants
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={clearFilters}
              className="h-7 px-2 text-xs"
            >
              <X className="h-3 w-3 mr-1" />
              Clear
            </Button>
          </div>
        )}
      </div>

      {/* Tenant grid */}
      {isLoading && !overview ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : overview && overview.tenants.length === 0 ? (
        <div className="flex justify-center py-16">
          <Card className="max-w-sm w-full text-center">
            <CardContent className="p-8 flex flex-col gap-2">
              <p className="font-semibold text-lg">No tenants discovered</p>
              <p className="text-sm text-muted-foreground">
                Try refreshing or check your credentials.
              </p>
            </CardContent>
          </Card>
        </div>
      ) : filteredTenants.length === 0 ? (
        <div className="flex justify-center py-16">
          <Card className="max-w-sm w-full text-center">
            <CardContent className="p-8 flex flex-col gap-3">
              <p className="font-semibold text-lg">No tenants match these filters</p>
              <p className="text-sm text-muted-foreground">
                Try a different search or ownership selection.
              </p>
              <div>
                <Button variant="outline" size="sm" onClick={clearFilters}>
                  Clear filters
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : (
        <div
          className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 transition-opacity duration-300${isRevalidating ? ' opacity-90' : ''}`}
        >
          {filteredTenants.map((tenant) => (
            <TenantCard
              key={tenant.summary.tenant_id}
              tenant={tenant}
            />
          ))}
        </div>
      )}
    </div>
  )
}
