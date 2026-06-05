import { useMemo } from 'react'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { DataTable, useParamSetter } from '@/components/DataTable'
import type { Column } from '@/components/DataTable'
import type { Alert } from '@/lib/api'
import { severityBadgeClass } from '@/lib/severity'
import { useTableFilter } from '@/lib/useTableFilter'
import type { FilterSpec } from '@/lib/useTableFilter'

interface AlertsTabProps {
  alerts: Alert[]
}

function SeverityBadge({ severity }: { severity: string }) {
  return (
    <Badge variant="outline" className={`text-xs ${severityBadgeClass(severity)}`}>
      {severity || '—'}
    </Badge>
  )
}

const COLUMNS: Column<Alert>[] = [
  {
    id: 'severity',
    header: 'Severity',
    cell: (a) => <SeverityBadge severity={a.severity} />,
  },
  {
    id: 'name',
    header: 'Name',
    cell: (a) => <span className="font-medium">{a.name || '—'}</span>,
  },
  {
    id: 'summary',
    header: 'Summary',
    cellClassName: 'text-xs text-muted-foreground max-w-xs truncate',
    cell: (a) => a.summary || '—',
  },
  {
    id: 'deviceType',
    header: 'Device Type',
    cellClassName: 'text-xs',
    cell: (a) => a.deviceType || '—',
  },
  {
    id: 'status',
    header: 'Status',
    cellClassName: 'text-xs',
    cell: (a) => a.status || '—',
  },
  {
    id: 'createdAt',
    header: 'Created',
    cellClassName: 'text-xs tabular-nums text-muted-foreground whitespace-nowrap',
    cell: (a) => (a.createdAt ? new Date(a.createdAt).toLocaleString() : '—'),
  },
]

const ALERTS_SPEC: FilterSpec<Alert> = {
  search: {
    paramKey: 'q',
    fields: (a) => [a.name, a.summary, a.category],
  },
  filters: [
    { paramKey: 'severity', predicate: (a, v) => a.severity?.toUpperCase() === v },
    { paramKey: 'alertStatus', predicate: (a, v) => a.status?.toUpperCase() === v },
    { paramKey: 'alertDeviceType', predicate: (a, v) => a.deviceType === v },
  ],
}

export function AlertsTab({ alerts }: AlertsTabProps) {
  const [searchParams, setParam] = useParamSetter()

  const severityFilter = searchParams.get('severity') ?? 'ALL'
  const statusFilter = searchParams.get('alertStatus') ?? 'ALL'
  const deviceTypeFilter = searchParams.get('alertDeviceType') ?? 'ALL'

  const uniqueDeviceTypes = useMemo(
    () =>
      Array.from(new Set(alerts.map((a) => a.deviceType).filter(Boolean))).sort(),
    [alerts],
  )

  const { filtered } = useTableFilter(alerts, ALERTS_SPEC)

  const toolbar = (
    <>
      {/* Severity filter */}
      <Select value={severityFilter} onValueChange={(v) => setParam('severity', v)}>
        <SelectTrigger className="h-8 w-36 text-xs">
          <SelectValue placeholder="Severity" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="ALL">All severities</SelectItem>
          <SelectItem value="CRITICAL">Critical</SelectItem>
          <SelectItem value="MAJOR">Major</SelectItem>
          <SelectItem value="MINOR">Minor</SelectItem>
          <SelectItem value="WARNING">Warning</SelectItem>
        </SelectContent>
      </Select>

      {/* Status filter */}
      <Select value={statusFilter} onValueChange={(v) => setParam('alertStatus', v)}>
        <SelectTrigger className="h-8 w-36 text-xs">
          <SelectValue placeholder="Status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="ALL">All statuses</SelectItem>
          <SelectItem value="OPEN">Open</SelectItem>
          <SelectItem value="CLEARED">Cleared</SelectItem>
          <SelectItem value="ACKNOWLEDGED">Acknowledged</SelectItem>
        </SelectContent>
      </Select>

      {/* Device type filter */}
      {uniqueDeviceTypes.length > 0 && (
        <Select
          value={deviceTypeFilter}
          onValueChange={(v) => setParam('alertDeviceType', v)}
        >
          <SelectTrigger className="h-8 w-40 text-xs">
            <SelectValue placeholder="Device type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">All device types</SelectItem>
            {uniqueDeviceTypes.map((dt) => (
              <SelectItem key={dt} value={dt}>
                {dt}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
    </>
  )

  return (
    <DataTable
      rows={alerts}
      filtered={filtered}
      rowKey={(a) => a.id}
      columns={COLUMNS}
      toolbar={toolbar}
      search={{
        paramKey: 'q',
        placeholder: 'Search name, summary, category…',
      }}
      emptyData={{ title: 'No alerts found.' }}
      emptyFiltered="No alerts match your filters."
    />
  )
}
