/**
 * KpiCard — unified KPI display tile used in KpiStrip (Overview) and TenantDetail.
 *
 * Supports two visual shapes via `variant`:
 *   "strip"  — used in KpiStrip: larger text (text-2xl), eyebrow label, accent coloring.
 *   "tile"   — compact tile with bg/border, icon inline in label.
 *   "detail" — used in TenantDetail: medium text (text-xl), icon beside value, tri-state value.
 *
 * The `value` tri-state (undefined | null | number) is only relevant for "detail" variant:
 *   undefined → skeleton (data loading)
 *   null      → dash (data not fetched)
 *   number    → formatted count
 */

import React from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { formatNumber } from '@/lib/format'

// ---- Strip variant (KpiStrip / Overview page) ----

export interface KpiCardStripProps {
  variant: 'strip'
  label: string
  /** undefined → skeleton; number → rendered */
  value: number | undefined
  icon: React.ReactNode
  sub?: React.ReactNode
  accent?: 'default' | 'destructive'
}

// ---- Tile variant ----

export interface KpiCardTileProps {
  variant: 'tile'
  /** Icon rendered inline before the label */
  icon: React.ReactNode
  label: string
  value: number
  sub?: React.ReactNode
}

// ---- Detail variant (TenantDetail page KPI row) ----

export interface KpiCardDetailProps {
  variant: 'detail'
  label: string
  /** undefined → skeleton; null → dash (not fetched); number → count */
  value: number | undefined | null
  icon: React.ReactNode
}

export type KpiCardProps = KpiCardStripProps | KpiCardTileProps | KpiCardDetailProps

export function KpiCard(props: KpiCardProps) {
  if (props.variant === 'tile') {
    const { icon, label, value, sub } = props
    return (
      <div className="flex flex-col gap-1 rounded-md bg-background/60 border border-border px-3 py-2.5">
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          {icon}
          {label}
        </span>
        <span className="text-2xl font-semibold tabular-nums leading-none">
          {formatNumber(value)}
        </span>
        {sub && <div className="mt-1">{sub}</div>}
      </div>
    )
  }

  if (props.variant === 'detail') {
    const { label, value, icon } = props
    return (
      <Card className="flex-1 min-w-0">
        <CardContent className="flex items-center gap-3 p-4">
          <div className="flex-shrink-0 text-muted-foreground">{icon}</div>
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">{label}</p>
            {value === undefined ? (
              <Skeleton className="h-6 w-12 mt-0.5" />
            ) : value === null ? (
              <p className="text-xl font-semibold tabular-nums text-muted-foreground">—</p>
            ) : (
              <p className="text-xl font-semibold tabular-nums">{formatNumber(value)}</p>
            )}
          </div>
        </CardContent>
      </Card>
    )
  }

  // variant === 'strip'
  const { label, value, icon, sub, accent = 'default' } = props
  return (
    <Card className="flex-1 min-w-0">
      <CardContent className="flex items-center gap-3 p-4">
        <div
          className={`flex-shrink-0 ${
            accent === 'destructive' && value && value > 0
              ? 'text-destructive'
              : 'text-muted-foreground'
          }`}
        >
          {icon}
        </div>
        <div className="min-w-0">
          <p className="eyebrow leading-none">{label}</p>
          {value === undefined ? (
            <Skeleton className="h-7 w-16 mt-1.5" />
          ) : (
            <p className="text-2xl font-semibold tabular-nums tracking-display-md mt-1 leading-none">
              {formatNumber(value)}
            </p>
          )}
          {sub && <div className="mt-1.5">{sub}</div>}
        </div>
      </CardContent>
    </Card>
  )
}
