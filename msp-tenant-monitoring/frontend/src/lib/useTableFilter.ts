import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

// ─── Public types ─────────────────────────────────────────────────────────────

export type Filter<T> = { paramKey: string; predicate: (row: T, value: string) => boolean }
export type SearchSpec<T> = { paramKey?: string; fields: (row: T) => unknown[] }
export type FilterSpec<T> = { search?: SearchSpec<T>; filters?: Filter<T>[] }

// ─── Pure filter engine ───────────────────────────────────────────────────────

/**
 * PURE — no hooks, no router. Pass a real URLSearchParams.
 *
 * Active-value rule: a filter is INACTIVE (predicate skipped) when its param
 * value is null, '' or 'ALL'. Only active values invoke the predicate.
 *
 * Search bug fix: fields are run through .filter(Boolean) before joining so
 * null/undefined values do NOT coerce to the literal string "null".
 */
export function applyTableFilter<T>(
  rows: T[],
  spec: FilterSpec<T>,
  params: URLSearchParams,
): T[] {
  return rows.filter((row) => {
    // --- search ---
    if (spec.search) {
      const key = spec.search.paramKey ?? 'q'
      const raw = params.get(key) ?? ''
      if (raw !== '') {
        const q = raw.toLowerCase()
        const haystack = spec.search
          .fields(row)
          .filter(Boolean)
          .map(String)
          .join(' ')
          .toLowerCase()
        if (!haystack.includes(q)) return false
      }
    }

    // --- discrete filters ---
    if (spec.filters) {
      for (const filter of spec.filters) {
        const value = params.get(filter.paramKey)
        // inactive when absent, empty, or 'ALL'
        if (value === null || value === '' || value === 'ALL') continue
        if (!filter.predicate(row, value)) return false
      }
    }

    return true
  })
}

// ─── Shared site predicate ────────────────────────────────────────────────────

/**
 * Shared filter for site-name columns used by both DevicesTab and ClientsTab.
 * 'unassigned' matches rows where siteName is falsy; any other value matches exactly.
 */
export function siteFilter<T extends { siteName?: string }>(): Filter<T> {
  return {
    paramKey: 'site',
    predicate: (row, value) =>
      value === 'unassigned' ? !row.siteName : row.siteName === value,
  }
}

// ─── Hook wrapper ─────────────────────────────────────────────────────────────

/**
 * Thin hook that reads useSearchParams() and delegates to applyTableFilter.
 * Memoised on rows identity + params.toString().
 */
export function useTableFilter<T>(
  rows: T[],
  spec: FilterSpec<T>,
): { filtered: T[] } {
  const [searchParams] = useSearchParams()
  const paramsKey = searchParams.toString()

  const filtered = useMemo(
    () => applyTableFilter(rows, spec, searchParams),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rows, paramsKey],
  )

  return { filtered }
}
