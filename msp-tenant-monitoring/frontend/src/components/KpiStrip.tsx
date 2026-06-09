import { AlertTriangle, Building2, Server, Users } from 'lucide-react'
import { KpiCard } from '@/components/KpiCard'
import { AlertBreakdown } from '@/components/AlertBreakdown'
import type { AlertTotals } from '@/components/AlertBreakdown'

interface KpiStripProps {
  tenants: number | undefined
  sites: number | undefined
  devices: number | undefined
  alerts: AlertTotals | undefined
}

export function KpiStrip({ tenants, sites, devices, alerts }: KpiStripProps) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 w-full">
      <KpiCard
        variant="strip"
        label="Tenants"
        value={tenants}
        icon={<Users className="h-5 w-5" />}
      />
      <KpiCard
        variant="strip"
        label="Sites"
        value={sites}
        icon={<Building2 className="h-5 w-5" />}
      />
      <KpiCard
        variant="strip"
        label="Devices"
        value={devices}
        icon={<Server className="h-5 w-5" />}
      />
      <KpiCard
        variant="strip"
        label="Alerts"
        value={alerts?.total}
        icon={<AlertTriangle className="h-5 w-5" />}
        accent="destructive"
        sub={alerts ? <AlertBreakdown alerts={alerts} /> : undefined}
      />
    </div>
  )
}
