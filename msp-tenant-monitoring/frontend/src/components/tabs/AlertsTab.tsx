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
import { severityBadgeClass, severityOrder } from '@/lib/severity'
import { useTableFilter, uniqueValues } from '@/lib/useTableFilter'
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

function AlertExpandedRow({ alert }: { alert: Alert }) {
  const fields: Array<[string, string | null | undefined]> = [
    ['Priority', alert.priority],
    ['Category', alert.category],
    ['Key', alert.key],
    ['Status', alert.status],
    ['Cleared reason', alert.clearedReason],
    ['Created', alert.createdAt ? new Date(alert.createdAt).toLocaleString() : undefined],
    ['Updated', alert.updatedAt ? new Date(alert.updatedAt).toLocaleString() : undefined],
  ]

  return (
    <div className="flex flex-col gap-3 py-3 px-4">
      <div className="flex flex-col gap-0.5">
        <div className="text-xs text-muted-foreground">Summary</div>
        <div className="text-sm">{alert.summary || '—'}</div>
      </div>
      <dl className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-2">
        {fields.map(([label, val]) =>
          val ? (
            <div key={label} className="flex flex-col gap-0.5">
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="text-sm break-all">{val}</dd>
            </div>
          ) : null,
        )}
      </dl>
    </div>
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
    { paramKey: 'severity', predicate: (a, v) => a.severity?.toUpperCase() === v.toUpperCase() },
    { paramKey: 'alertStatus', predicate: (a, v) => a.status?.toUpperCase() === v.toUpperCase() },
    { paramKey: 'alertDeviceType', predicate: (a, v) => a.deviceType?.toUpperCase() === v.toUpperCase() },
  ],
}

export function AlertsTab({ alerts }: AlertsTabProps) {
  const [searchParams, setParam] = useParamSetter()

  const severityFilter = searchParams.get('severity') ?? 'ALL'
  const statusFilter = searchParams.get('alertStatus') ?? 'ALL'
  const deviceTypeFilter = searchParams.get('alertDeviceType') ?? 'ALL'

  const uniqueSeverities = useMemo(
    () => uniqueValues(alerts, (a) => a.severity, severityOrder),
    [alerts],
  )
  const uniqueStatuses = useMemo(
    () => uniqueValues(alerts, (a) => a.status),
    [alerts],
  )
  const uniqueDeviceTypes = useMemo(
    () => uniqueValues(alerts, (a) => a.deviceType),
    [alerts],
  )

  const { filtered } = useTableFilter(alerts, ALERTS_SPEC)

  const toolbar = (
    <>
      {/* Severity filter */}
      {uniqueSeverities.length > 0 && (
        <Select value={severityFilter} onValueChange={(v) => setParam('severity', v)}>
          <SelectTrigger className="h-8 w-36 text-xs">
            <SelectValue placeholder="Severity" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">All severities</SelectItem>
            {uniqueSeverities.map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {/* Status filter */}
      {uniqueStatuses.length > 0 && (
        <Select value={statusFilter} onValueChange={(v) => setParam('alertStatus', v)}>
          <SelectTrigger className="h-8 w-36 text-xs">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">All statuses</SelectItem>
            {uniqueStatuses.map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

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
      expandedRow={(a) => <AlertExpandedRow alert={a} />}
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
