import { useParams, Link, useSearchParams } from 'react-router-dom'
import useSWR from 'swr'
import { ChevronLeft, Building2, Server, Users, BellRing, Loader2 } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { SitesTab } from '@/components/tabs/SitesTab'
import { DevicesTab } from '@/components/tabs/DevicesTab'
import { ClientsTab } from '@/components/tabs/ClientsTab'
import { AlertsTab } from '@/components/tabs/AlertsTab'
import { KpiCard } from '@/components/KpiCard'
import { DrilldownPanel } from '@/components/DrilldownPanel'
import { getOverview } from '@/lib/api'
import { useSelectedTypes } from '@/lib/selection'
import { useStaggeredDetail } from '@/lib/useStaggeredDetail'
import type { Overview } from '@/lib/api'

type TabName = 'sites' | 'devices' | 'clients' | 'alerts'
const VALID_TABS: TabName[] = ['sites', 'devices', 'clients', 'alerts']

function isValidTab(v: string | null): v is TabName {
  return VALID_TABS.includes(v as TabName)
}

// ---- TenantDetail page ----

export function TenantDetail() {
  const { id } = useParams<{ id: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const selected = useSelectedTypes()

  const rawTab = searchParams.get('tab')
  const activeTab: TabName = isValidTab(rawTab) ? rawTab : 'sites'

  const { data: overview, isLoading } = useSWR<Overview>(['overview'], () => getOverview())

  const { sites, devices, clients, alerts, errors, fetching, fetchNow } = useStaggeredDetail(
    id,
    selected,
    activeTab,
  )

  function setActiveTab(tab: TabName) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('tab', tab)
      return next
    })
  }

  if (isLoading && !overview) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-8 w-48" />
        <div className="flex gap-4">
          <Skeleton className="h-16 flex-1" />
          <Skeleton className="h-16 flex-1" />
          <Skeleton className="h-16 flex-1" />
          <Skeleton className="h-16 flex-1" />
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  const tenant = overview?.tenants.find((t) => t.summary.tenant_id === id)

  if (!tenant) {
    return (
      <div className="flex justify-center py-16">
        <Card className="max-w-sm w-full text-center">
          <CardContent className="p-8 flex flex-col gap-4">
            <p className="font-semibold text-lg">Tenant not found</p>
            <p className="text-sm text-muted-foreground">
              No tenant with ID{' '}
              <span className="font-mono text-xs bg-muted px-1 py-0.5 rounded">{id}</span>{' '}
              was found in the current overview.
            </p>
            <Button asChild variant="outline">
              <Link to="/">Back to Overview</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  const { summary } = tenant

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link
          to="/"
          className="flex items-center gap-0.5 text-sm text-muted-foreground hover:text-foreground transition-colors w-fit"
        >
          <ChevronLeft className="h-4 w-4" />
          Back to Overview
        </Link>
        <h1 className="text-2xl font-semibold">{summary.tenant_name}</h1>
      </div>

      <div className="flex gap-4">
        <KpiCard
          variant="detail"
          label="Sites"
          value={sites === undefined ? undefined : sites === null ? null : sites.length}
          icon={<Building2 className="h-5 w-5" />}
        />
        <KpiCard
          variant="detail"
          label="Devices"
          value={devices === undefined ? undefined : devices === null ? null : devices.length}
          icon={<Server className="h-5 w-5" />}
        />
        <KpiCard
          variant="detail"
          label="Clients"
          value={clients === undefined ? undefined : clients === null ? null : clients.length}
          icon={<Users className="h-5 w-5" />}
        />
        <KpiCard
          variant="detail"
          label="Alerts"
          value={alerts === undefined ? undefined : alerts === null ? null : alerts.length}
          icon={<BellRing className="h-5 w-5" />}
        />
      </div>

      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as TabName)}
        className="w-full"
      >
        <TabsList className="mb-4">
          <TabsTrigger value="sites" className={sites === null ? 'text-muted-foreground' : ''}>
            Sites
            {sites === undefined ? (
              <Loader2 className="ml-1.5 h-3 w-3 animate-spin" />
            ) : sites && sites.length > 0 ? (
              <span className="ml-1.5 text-xs tabular-nums text-muted-foreground">
                {sites.length}
              </span>
            ) : null}
          </TabsTrigger>
          <TabsTrigger value="devices" className={devices === null ? 'text-muted-foreground' : ''}>
            Devices
            {devices === undefined ? (
              <Loader2 className="ml-1.5 h-3 w-3 animate-spin" />
            ) : devices && devices.length > 0 ? (
              <span className="ml-1.5 text-xs tabular-nums text-muted-foreground">
                {devices.length}
              </span>
            ) : null}
          </TabsTrigger>
          <TabsTrigger value="clients" className={clients === null ? 'text-muted-foreground' : ''}>
            Clients
            {clients === undefined ? (
              <Loader2 className="ml-1.5 h-3 w-3 animate-spin" />
            ) : clients && clients.length > 0 ? (
              <span className="ml-1.5 text-xs tabular-nums text-muted-foreground">
                {clients.length}
              </span>
            ) : null}
          </TabsTrigger>
          <TabsTrigger value="alerts" className={alerts === null ? 'text-muted-foreground' : ''}>
            Alerts
            {alerts === undefined ? (
              <Loader2 className="ml-1.5 h-3 w-3 animate-spin" />
            ) : alerts && alerts.length > 0 ? (
              <span className="ml-1.5 text-xs tabular-nums text-muted-foreground">
                {alerts.length}
              </span>
            ) : null}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="sites">
          <DrilldownPanel
            value={sites}
            error={errors.sites}
            type="sites"
            onFetch={() => fetchNow('sites')}
            fetching={fetching.sites}
          >
            <SitesTab sites={sites!} />
          </DrilldownPanel>
        </TabsContent>

        <TabsContent value="devices">
          <DrilldownPanel
            value={devices}
            error={errors.devices}
            type="devices"
            onFetch={() => fetchNow('devices')}
            fetching={fetching.devices}
          >
            <DevicesTab devices={devices!} />
          </DrilldownPanel>
        </TabsContent>

        <TabsContent value="clients">
          <DrilldownPanel
            value={clients}
            error={errors.clients}
            type="clients"
            onFetch={() => fetchNow('clients')}
            fetching={fetching.clients}
          >
            <ClientsTab clients={clients!} />
          </DrilldownPanel>
        </TabsContent>

        <TabsContent value="alerts">
          <DrilldownPanel
            value={alerts}
            error={errors.alerts}
            type="alerts"
            onFetch={() => fetchNow('alerts')}
            fetching={fetching.alerts}
          >
            <AlertsTab alerts={alerts!} />
          </DrilldownPanel>
        </TabsContent>
      </Tabs>
    </div>
  )
}
