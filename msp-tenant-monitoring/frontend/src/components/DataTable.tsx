/**
 * DataTable — generic table shell shared by SitesTab, DevicesTab, ClientsTab, AlertsTab.
 *
 * Responsibilities owned here (so individual tabs don't repeat them):
 *   • URL search-param sync  (setParam: 'ALL'/''/delete semantics)
 *   • Expand/collapse row state (Set<string> toggle)
 *   • Sticky toolbar markup + classes
 *   • Table/TableHeader/TableBody scaffold + border wrapper
 *   • Empty-state (no data) and filtered-empty-state rendering
 *
 * Responsibilities left in individual tab files:
 *   • Column definitions + header labels
 *   • Row cell renderers
 *   • Expanded-row content (or none)
 *   • Toolbar filter controls (passed as ReactNode children via `toolbar` prop)
 *   • All per-tab presentational helpers (badges, bars, icons)
 *   • The filtering / useMemo logic (tabs keep their own `filtered` array)
 */

import { Fragment, useState, type ReactNode } from 'react'
import { ChevronRight, ChevronDown, Search } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

// ─── Public types ────────────────────────────────────────────────────────────

/** One column in the table. */
export interface Column<T> {
  /** Unique key used as React key. */
  id: string
  /** Header cell content. */
  header: ReactNode
  /** Cell content for a given row. */
  cell: (row: T) => ReactNode
  /** Extra className applied to <TableHead>. */
  headerClassName?: string
  /** Extra className applied to <TableCell>. */
  cellClassName?: string
  /**
   * When true this column may be hidden. DataTable does NOT manage visibility
   * itself — pass `visible: false` to exclude the column from the rendered set.
   * The tab controls visibility externally via its own local state.
   */
  visible?: boolean
}

/** Describes the search box in the toolbar. */
export interface SearchSpec {
  /** URL param key for the search query (default: 'q'). */
  paramKey?: string
  placeholder?: string
}

/**
 * What to show when rows === [] (data arrived but empty).
 * The `filtered` empty state (data exist but filters zeroed the list) uses
 * the simpler text variant; you only need to supply `emptyData` for the
 * true-no-data case.
 */
export interface EmptySpec {
  /** Icon element, e.g. <Building2 className="h-8 w-8 …" /> */
  icon?: ReactNode
  title: string
  /** Extra hint line shown below the title. */
  hint?: string
}

export interface DataTableProps<T> {
  /** Full (unfiltered) row array — used only for the no-data empty state. */
  rows: T[]
  /** Filtered rows to actually render. */
  filtered: T[]
  /** Stable string key for a row (used as React key + expand id). */
  rowKey: (row: T) => string
  /** Column definitions. Columns with visible===false are skipped. */
  columns: Column<T>[]
  /**
   * When provided, each row becomes expandable.  The returned node is rendered
   * in a full-width <TableCell colSpan={N}> below the primary row.
   */
  expandedRow?: (row: T) => ReactNode
  /**
   * Filter controls rendered inside the sticky toolbar, before the search box.
   * Pass your <Select>, button groups, etc. as children.
   */
  toolbar?: ReactNode
  /**
   * Additional controls appended after the search box (e.g. Columns toggle).
   */
  toolbarSuffix?: ReactNode
  /** Search box config (omit to hide the search box). */
  search?: SearchSpec
  /** Empty-state config shown when `rows` is empty (no data at all). */
  emptyData?: EmptySpec
  /**
   * Text shown when `filtered` is empty but `rows` is not.
   * Defaults to "No items match the current filters".
   */
  emptyFiltered?: string
}

// ─── Exported helper: setParam ────────────────────────────────────────────────
// Tabs that need to read URL params for their useMemo still call useSearchParams
// themselves; this hook just gives them the setter with the shared semantics.

/**
 * Returns a setter that writes URL search params, deleting the key when the
 * value is 'ALL' or ''.  Consume in tab files like:
 *
 *   const [searchParams, setParam] = useParamSetter()
 */
export function useParamSetter(): [
  URLSearchParams,
  (key: string, value: string) => void,
] {
  const [searchParams, setSearchParams] = useSearchParams()

  function setParam(key: string, value: string) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value === 'ALL' || value === '') {
        next.delete(key)
      } else {
        next.set(key, value)
      }
      return next
    })
  }

  return [searchParams, setParam]
}

// ─── DataTable component ──────────────────────────────────────────────────────

export function DataTable<T>({
  rows,
  filtered,
  rowKey,
  columns,
  expandedRow,
  toolbar,
  toolbarSuffix,
  search,
  emptyData,
  emptyFiltered = 'No items match the current filters',
}: DataTableProps<T>) {
  const [searchParams, setParam] = useParamSetter()
  const [expandedSet, setExpandedSet] = useState<Set<string>>(new Set())

  const searchParamKey = search?.paramKey ?? 'q'
  const searchQuery = searchParams.get(searchParamKey) ?? ''

  function toggleExpand(id: string) {
    setExpandedSet((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  // Columns that should actually be rendered
  const visibleColumns = columns.filter((c) => c.visible !== false)
  // +1 for the chevron column when expandedRow is provided
  const totalCols = visibleColumns.length + (expandedRow ? 1 : 0)

  // ── No data at all ──
  if (rows.length === 0) {
    if (!emptyData) {
      return (
        <div className="py-12 text-center text-sm text-muted-foreground">
          {emptyFiltered}
        </div>
      )
    }
    return (
      <div className="flex justify-center py-16">
        <div className="text-center">
          {emptyData.icon && (
            <div className="text-muted-foreground mx-auto mb-2">
              {emptyData.icon}
            </div>
          )}
          <p className="text-sm text-muted-foreground">{emptyData.title}</p>
          {emptyData.hint && (
            <p className="text-xs text-muted-foreground mt-1">{emptyData.hint}</p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Sticky toolbar */}
      <div className="sticky top-0 z-10 bg-background pb-2 pt-1 flex flex-wrap items-center gap-2 border-b">
        {toolbar}

        {search && (
          <div className="relative flex-1 min-w-48">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              className="h-8 pl-7 text-xs"
              placeholder={search.placeholder ?? 'Search…'}
              value={searchQuery}
              onChange={(e) => setParam(searchParamKey, e.target.value)}
            />
          </div>
        )}

        {toolbarSuffix}
      </div>

      {/* Table or filtered-empty state */}
      {filtered.length === 0 ? (
        <div className="py-12 text-center text-sm text-muted-foreground">
          {emptyFiltered}
        </div>
      ) : (
        <div className="rounded-md border overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                {expandedRow && <TableHead className="w-8" />}
                {visibleColumns.map((col) => (
                  <TableHead
                    key={col.id}
                    className={col.headerClassName}
                  >
                    {col.header}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((row) => {
                const key = rowKey(row)
                const isExpanded = expandedSet.has(key)
                return (
                  <Fragment key={key}>
                    <TableRow
                      className={expandedRow ? 'cursor-pointer hover:bg-muted/50' : undefined}
                      onClick={expandedRow ? () => toggleExpand(key) : undefined}
                    >
                      {expandedRow && (
                        <TableCell className="w-8 p-2">
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          )}
                        </TableCell>
                      )}
                      {visibleColumns.map((col) => (
                        <TableCell
                          key={col.id}
                          className={col.cellClassName}
                        >
                          {col.cell(row)}
                        </TableCell>
                      ))}
                    </TableRow>
                    {expandedRow && isExpanded && (
                      <TableRow className="bg-muted/40 hover:bg-muted/40">
                        <TableCell colSpan={totalCols} className="p-0">
                          {expandedRow(row)}
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
