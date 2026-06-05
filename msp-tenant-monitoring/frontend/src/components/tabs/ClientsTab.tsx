import { useMemo } from 'react'
import { Wifi, Network, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { DataTable, useParamSetter } from '@/components/DataTable'
import type { Column } from '@/components/DataTable'
import type { Client } from '@/lib/api'
import { useTableFilter, siteFilter } from '@/lib/useTableFilter'
import type { FilterSpec } from '@/lib/useTableFilter'

interface ClientsTabProps {
  clients: Client[]
}

type ConnectionTypeFilter = 'ALL' | 'WIRELESS' | 'WIRED'

function SnrBar({ snr }: { snr: number }) {
  if (!snr && snr !== 0) {
    return <span className="text-muted-foreground text-xs">—</span>
  }

  const clamped = Math.min(Math.max(snr, 0), 70)
  const pct = (clamped / 70) * 100

  let barColor: string
  let label: string
  if (snr < 20) {
    barColor = 'bg-danger'
    label = 'Poor'
  } else if (snr < 40) {
    barColor = 'bg-warning'
    label = 'Fair'
  } else {
    barColor = 'bg-success'
    label = 'Good'
  }

  return (
    <div className="flex items-center gap-2">
      <div
        className="relative h-2 w-[60px] rounded-full bg-muted overflow-hidden flex-shrink-0"
        title={`SNR: ${snr} dB`}
      >
        <div
          className={`absolute inset-y-0 left-0 ${barColor} rounded-full`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-muted-foreground">
        {snr}
        <span className="text-[10px] ml-0.5 text-muted-foreground/70"> dB</span>
      </span>
      <span
        className={`text-[10px] ${
          snr < 20
            ? 'text-danger'
            : snr < 40
              ? 'text-warning'
              : 'text-success'
        }`}
      >
        {label}
      </span>
    </div>
  )
}

function ClientExpandedRow({ client }: { client: Client }) {
  const fields: Array<[string, string | number | null | undefined]> = [
    ['Manufacturer', client.clientManufacturer],
    ['OS', client.clientOperatingSystem],
    ['Function', client.clientFunction],
    ['Security', client.wirelessSecurity],
    ['Band', client.wirelessBand],
    ['Channel', client.wirelessChannel ? String(client.wirelessChannel) : undefined],
    ['WLAN Name', client.wlanName],
  ]

  return (
    <dl className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-2 py-3 px-4">
      {fields.map(([label, val]) =>
        val !== undefined && val !== null && val !== '' ? (
          <div key={label} className="flex flex-col gap-0.5">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="text-sm break-all">{val}</dd>
          </div>
        ) : null,
      )}
    </dl>
  )
}

const CONN_TYPE_BUTTONS: Array<{
  value: ConnectionTypeFilter
  label: string
  icon: React.ReactNode
}> = [
  { value: 'ALL', label: 'All', icon: null },
  { value: 'WIRELESS', label: 'Wireless', icon: <Wifi className="h-3.5 w-3.5" /> },
  { value: 'WIRED', label: 'Wired', icon: <Network className="h-3.5 w-3.5" /> },
]

const COLUMNS: Column<Client>[] = [
  {
    id: 'name',
    header: 'Name',
    cell: (c) => <span className="font-medium">{c.clientName || '—'}</span>,
  },
  {
    id: 'host',
    header: 'Host',
    cellClassName: 'text-xs text-muted-foreground',
    cell: (c) => c.hostName || '—',
  },
  {
    id: 'mac',
    header: 'MAC',
    cellClassName: 'text-xs font-mono tabular-nums',
    cell: (c) => c.macAddress || '—',
  },
  {
    id: 'ip',
    header: 'IP',
    cellClassName: 'text-xs font-mono tabular-nums',
    cell: (c) => c.ipv4 || '—',
  },
  {
    id: 'site',
    header: 'Site',
    cellClassName: 'text-xs',
    cell: (c) => c.siteName || '—',
  },
  {
    id: 'type',
    header: 'Type',
    cell: (c) => (
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        {c.connectedDeviceType?.toUpperCase() === 'WIRELESS' ||
        c.clientConnectionType?.toUpperCase() === 'WIRELESS' ? (
          <Wifi className="h-3.5 w-3.5" />
        ) : (
          <Network className="h-3.5 w-3.5" />
        )}
        {c.connectedDeviceType || c.clientConnectionType || '—'}
      </span>
    ),
  },
  {
    id: 'vlan',
    header: 'VLAN',
    cellClassName: 'text-xs tabular-nums',
    cell: (c) => c.vlanId || c.vlanName || '—',
  },
  {
    id: 'snr',
    header: 'SNR',
    cell: (c) => <SnrBar snr={c.snr} />,
  },
]

const CLIENTS_SPEC: FilterSpec<Client> = {
  search: {
    paramKey: 'q',
    fields: (c) => [c.clientName, c.hostName, c.macAddress, c.ipv4, c.userName],
  },
  filters: [
    {
      paramKey: 'connType',
      predicate: (c, v) => {
        const isWireless = c.clientConnectionType?.toUpperCase() === 'WIRELESS'
        if (v === 'WIRELESS') return isWireless
        if (v === 'WIRED') return !isWireless
        return true
      },
    },
    siteFilter<Client>(),
  ],
}

export function ClientsTab({ clients }: ClientsTabProps) {
  const [searchParams, setParam] = useParamSetter()

  const connTypeFilter = (searchParams.get('connType') ?? 'ALL') as ConnectionTypeFilter
  const siteFilterValue = searchParams.get('site') ?? 'ALL'

  const uniqueSites = useMemo(
    () =>
      Array.from(new Set(clients.map((c) => c.siteName).filter(Boolean))).sort(),
    [clients],
  )

  const { filtered } = useTableFilter(clients, CLIENTS_SPEC)

  const toolbar = (
    <>
      {/* Connection type segmented control */}
      <div className="flex items-center gap-1 rounded-md border p-0.5">
        {CONN_TYPE_BUTTONS.map((btn) => (
          <Button
            key={btn.value}
            variant={connTypeFilter === btn.value ? 'secondary' : 'ghost'}
            size="sm"
            className="h-7 px-2 text-xs gap-1"
            onClick={() => setParam('connType', btn.value)}
          >
            {btn.icon}
            {btn.label}
          </Button>
        ))}
      </div>

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

  return (
    <DataTable
      rows={clients}
      filtered={filtered}
      rowKey={(c) => c.id}
      columns={COLUMNS}
      expandedRow={(c) => <ClientExpandedRow client={c} />}
      toolbar={toolbar}
      search={{
        paramKey: 'q',
        placeholder: 'Search name, host, MAC, IP, user…',
      }}
      emptyData={{
        icon: <Users className="h-8 w-8" />,
        title: 'No clients match the current filters',
      }}
      emptyFiltered="No clients match the current filters"
    />
  )
}
