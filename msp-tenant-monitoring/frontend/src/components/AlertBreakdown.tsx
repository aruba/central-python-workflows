/**
 * AlertBreakdown — inline severity chip row for Alert totals.
 *
 * Shows "N critical · N major · N minor" chips (zero-value severities are omitted).
 * Renders "All clear" when every count is zero.
 *
 * Used in:
 *   - KpiStrip (Overview) as the `sub` of the Alerts KpiCard
 */

import { severityTextClass } from '@/lib/severity'

export interface AlertTotals {
  total: number
  critical: number
  major: number
  minor: number
}

interface AlertBreakdownProps {
  alerts: AlertTotals
}

const CHIPS: Array<{ key: keyof AlertTotals; label: string }> = [
  { key: 'critical', label: 'critical' },
  { key: 'major', label: 'major' },
  { key: 'minor', label: 'minor' },
]

export function AlertBreakdown({ alerts }: AlertBreakdownProps) {
  const visible = CHIPS.filter((c) => (alerts[c.key] as number) > 0)

  if (visible.length === 0) {
    return <span className="text-[11px] text-muted-foreground">All clear</span>
  }

  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[11px] tabular-nums">
      {visible.map((c) => (
        <span key={c.key} className={severityTextClass(c.key)}>
          {alerts[c.key]} {c.label}
        </span>
      ))}
    </div>
  )
}
