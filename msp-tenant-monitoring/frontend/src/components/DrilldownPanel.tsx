/**
 * DrilldownPanel — owns the four-state render ladder for a Drilldown resource tab.
 *
 * The tri-state value follows the TenantDetail convention:
 *   undefined  → still loading (show skeleton)
 *   null       → loaded but resource was not included in the Detail fetch (show FetchNow)
 *   T[]        → data present (render children)
 *
 * If `error` is set the error message is shown instead of skeleton/FetchNow/children.
 *
 * FetchNowPlaceholder is co-located here because it is only used by this panel.
 */

import React from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import type { IncludeType } from '@/lib/api'

// ---- FetchNowPlaceholder (moved from TenantDetail) ----

interface FetchNowPlaceholderProps {
  type: IncludeType
  onFetch: () => void
  loading: boolean
}

function FetchNowPlaceholder({ type, onFetch, loading }: FetchNowPlaceholderProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <p className="text-sm text-muted-foreground">
        No {type} loaded for this tenant yet.
      </p>
      <Button variant="outline" size="sm" onClick={onFetch} disabled={loading}>
        {loading ? 'Fetching…' : 'Fetch now'}
      </Button>
    </div>
  )
}

// ---- Per-type skeleton shapes (preserved from TenantDetail) ----

function SitesSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-28 rounded-xl" />
      ))}
    </div>
  )
}

function RowsSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  )
}

// ---- DrilldownPanel ----

interface DrilldownPanelProps<T> {
  /** The tri-state Drilldown value: undefined=loading, null=not fetched, T[]=data */
  value: T[] | undefined | null
  /** Error from the Detail fetch, if any */
  error: unknown
  /** Which Drilldown resource type this panel is for (used in FetchNow text and error label) */
  type: IncludeType
  /** Called when the user clicks "Fetch now" */
  onFetch: () => void
  /** True while the on-demand fetch is in flight */
  fetching: boolean
  /** Rendered when data is present */
  children: React.ReactNode
}

export function DrilldownPanel<T>({
  value,
  error,
  type,
  onFetch,
  fetching,
  children,
}: DrilldownPanelProps<T>) {
  if (value === undefined) {
    return type === 'sites' ? <SitesSkeleton /> : <RowsSkeleton />
  }

  if (error) {
    return (
      <p className="text-sm text-destructive py-8 text-center capitalize">
        Couldn't load {type}.
      </p>
    )
  }

  if (value === null) {
    return <FetchNowPlaceholder type={type} onFetch={onFetch} loading={fetching} />
  }

  return <>{children}</>
}
