import { useState, useMemo } from 'react'
import { Wifi, Network, Router, Server } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { DataTable, useParamSetter } from '@/components/DataTable'
import type { Column } from '@/components/DataTable'
import type { Device } from '@/lib/api'
import { useTableFilter, siteFilter } from '@/lib/useTableFilter'
import type { FilterSpec } from '@/lib/useTableFilter'

interface DevicesTabProps {
  devices: Device[]
}

type DeviceTypeFilter = 'ALL' | 'ACCESS_POINT' | 'SWITCH' | 'GATEWAY'

function DeviceTypeIcon({ type }: { type: string }) {
  switch (type?.toUpperCase()) {
    case 'ACCESS_POINT':
      return <Wifi className="h-3.5 w-3.5 inline mr-1" />
    case 'SWITCH':
      return <Network className="h-3.5 w-3.5 inline mr-1" />
    case 'GATEWAY':
      return <Router className="h-3.5 w-3.5 inline mr-1" />
    default:
      return <Server className="h-3.5 w-3.5 inline mr-1" />
  }
}

function DeviceExpandedRow({ device }: { device: Device }) {
  const fields: Array<[string, string | null | undefined]> = [
    ['Serial', device.serialNumber],
    ['MAC Address', device.macAddress],
    ['Role', device.role],
    ['Function', device.deviceFunction],
    ['Group', device.deviceGroupName],
    ['Provisioned', device.isProvisioned],
    ['Deployment', device.deployment],
  ]

  return (
    <dl className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-2 py-3 px-4">
      {fields.map(([label, val]) =>
        val ? (
          <div key={label} className="flex flex-col gap-0.5">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="text-sm font-mono break-all">{val}</dd>
          </div>
        ) : null,
      )}
    </dl>
  )
}

const TYPE_BUTTONS: Array<{
  value: DeviceTypeFilter
  label: string
  icon: React.ReactNode
}> = [
  { value: 'ALL', label: 'All', icon: null },
  { value: 'ACCESS_POINT', label: 'APs', icon: <Wifi className="h-3.5 w-3.5" /> },
  { value: 'SWITCH', label: 'Switches', icon: <Network className="h-3.5 w-3.5" /> },
  { value: 'GATEWAY', label: 'Gateways', icon: <Router className="h-3.5 w-3.5" /> },
]

const DEVICES_SPEC: FilterSpec<Device> = {
  search: {
    paramKey: 'q',
    fields: (d) => [d.deviceName, d.model, d.ipv4, d.macAddress, d.serialNumber],
  },
  filters: [
    { paramKey: 'deviceType', predicate: (d, v) => d.deviceType?.toUpperCase() === v },
    { paramKey: 'status', predicate: (d, v) => d.status?.toUpperCase() === v },
    siteFilter<Device>(),
  ],
}

export function DevicesTab({ devices }: DevicesTabProps) {
  const [searchParams, setParam] = useParamSetter()

  const typeFilter = (searchParams.get('deviceType') ?? 'ALL') as DeviceTypeFilter
  const statusFilter = searchParams.get('status') ?? 'ALL'
  const siteFilterValue = searchParams.get('site') ?? 'ALL'

  const [visibleColumns, setVisibleColumns] = useState({
    model: true,
    firmware: true,
    ipv4: true,
  })

  const uniqueSites = useMemo(
    () =>
      Array.from(new Set(devices.map((d) => d.siteName).filter(Boolean))).sort(),
    [devices],
  )

  const { filtered } = useTableFilter(devices, DEVICES_SPEC)

  const columns: Column<Device>[] = [
    {
      id: 'name',
      header: 'Name',
      cell: (d) => <span className="font-medium">{d.deviceName || '—'}</span>,
    },
    {
      id: 'type',
      header: 'Type',
      cell: (d) => (
        <span className="flex items-center gap-1 text-muted-foreground text-xs">
          <DeviceTypeIcon type={d.deviceType} />
          {d.deviceType || '—'}
        </span>
      ),
    },
    {
      id: 'model',
      header: 'Model',
      cellClassName: 'text-xs text-muted-foreground',
      cell: (d) => d.model || '—',
      visible: visibleColumns.model,
    },
    {
      id: 'site',
      header: 'Site',
      cellClassName: 'text-xs',
      cell: (d) => d.siteName || '—',
    },
    {
      id: 'status',
      header: 'Status',
      cell: (d) =>
        d.status ? (
          <Badge
            variant="outline"
            className={`text-xs tabular-nums border-transparent ${
              d.status.toUpperCase() === 'ONLINE'
                ? 'bg-success/15 text-success'
                : 'bg-danger/15 text-danger'
            }`}
          >
            {d.status}
          </Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      id: 'firmware',
      header: 'Firmware',
      cellClassName: 'text-xs font-mono text-muted-foreground',
      cell: (d) => d.firmwareVersion || '—',
      visible: visibleColumns.firmware,
    },
    {
      id: 'ipv4',
      header: 'IPv4',
      cellClassName: 'text-xs font-mono tabular-nums',
      cell: (d) => d.ipv4 || '—',
      visible: visibleColumns.ipv4,
    },
  ]

  const toolbar = (
    <>
      {/* Type segmented control */}
      <div className="flex items-center gap-1 rounded-md border p-0.5">
        {TYPE_BUTTONS.map((btn) => (
          <Button
            key={btn.value}
            variant={typeFilter === btn.value ? 'secondary' : 'ghost'}
            size="sm"
            className="h-7 px-2 text-xs gap-1"
            onClick={() => setParam('deviceType', btn.value)}
          >
            {btn.icon}
            {btn.label}
          </Button>
        ))}
      </div>

      {/* Status filter */}
      <Select value={statusFilter} onValueChange={(v) => setParam('status', v)}>
        <SelectTrigger className="h-8 w-32 text-xs">
          <SelectValue placeholder="Status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="ALL">All statuses</SelectItem>
          <SelectItem value="ONLINE">Online</SelectItem>
          <SelectItem value="OFFLINE">Offline</SelectItem>
        </SelectContent>
      </Select>

      {/* Site filter */}
      {uniqueSites.length > 0 && (
        <Select value={siteFilterValue} onValueChange={(v) => setParam('site', v)}>
          <SelectTrigger className="h-8 w-40 text-xs">
            <SelectValue placeholder="All sites" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">All sites</SelectItem>
            <SelectItem value="unassigned">Unassigned</SelectItem>
            {uniqueSites.map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
    </>
  )

  const toolbarSuffix = (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 text-xs">
          Columns
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {(
          [
            ['model', 'Model'],
            ['firmware', 'Firmware'],
            ['ipv4', 'IPv4'],
          ] as const
        ).map(([col, label]) => (
          <DropdownMenuCheckboxItem
            key={col}
            checked={visibleColumns[col]}
            onCheckedChange={(checked) =>
              setVisibleColumns((prev) => ({ ...prev, [col]: checked }))
            }
          >
            {label}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )

  return (
    <DataTable
      rows={devices}
      filtered={filtered}
      rowKey={(d) => d.id}
      columns={columns}
      expandedRow={(d) => <DeviceExpandedRow device={d} />}
      toolbar={toolbar}
      toolbarSuffix={toolbarSuffix}
      search={{
        paramKey: 'q',
        placeholder: 'Search name, model, IP, MAC, serial…',
      }}
      emptyFiltered="No devices match the current filters"
    />
  )
}
