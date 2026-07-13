import { SlidersHorizontal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { useSelectionContext } from '@/lib/selection'
import type { IncludeType } from '@/lib/api'

const ROWS: { type: IncludeType; label: string; locked?: boolean }[] = [
  // Sites gates the drilldown (fetched before navigation) — always on.
  { type: 'sites', label: 'Sites', locked: true },
  { type: 'devices', label: 'Devices' },
  { type: 'clients', label: 'Clients' },
  { type: 'alerts', label: 'Alerts' },
]

export function DrilldownSettings() {
  const { selectedTypes: selected, setSelectedTypes } = useSelectionContext()

  function toggle(type: IncludeType, on: boolean) {
    const next = on
      ? ([...new Set([...selected, type])] as IncludeType[])
      : selected.filter((t) => t !== type)
    setSelectedTypes(next)
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Drilldown data settings">
          <SlidersHorizontal className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-60">
        <p className="text-sm font-medium">Data to fetch on drilldown</p>
        <p className="text-xs text-muted-foreground mt-0.5 mb-3">
          Applies to the next tenant you open.
        </p>
        <div className="flex flex-col gap-1">
          {ROWS.map(({ type, label, locked }) => (
            <div
              key={type}
              className={`flex items-center justify-between px-1.5 py-1.5 rounded-md transition-colors ${
                locked
                  ? 'opacity-60'
                  : 'hover:bg-muted/50 cursor-pointer'
              }`}
            >
              <Label
                htmlFor={`dd-${type}`}
                className={locked ? 'text-muted-foreground cursor-default' : 'cursor-pointer'}
              >
                {label}
                {locked && (
                  <span className="ml-1.5 text-xs text-muted-foreground">Always on</span>
                )}
              </Label>
              <Switch
                id={`dd-${type}`}
                checked={locked || selected.includes(type)}
                disabled={locked}
                onCheckedChange={(checked) => toggle(type, checked)}
              />
            </div>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}
