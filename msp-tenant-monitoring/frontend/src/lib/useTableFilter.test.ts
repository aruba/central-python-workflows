import { describe, it, expect } from 'vitest'
import { applyTableFilter, siteFilter, uniqueValues } from './useTableFilter'
import type { FilterSpec } from './useTableFilter'
import { severityOrder } from './severity'

// ─── Helper row types ─────────────────────────────────────────────────────────

interface Row {
  name: string | null | undefined
  tag: string | null | undefined
  siteName?: string
}

const ROW_A: Row = { name: 'Alpha', tag: 'blue', siteName: 'HQ' }
const ROW_B: Row = { name: 'Beta', tag: 'red', siteName: 'Branch' }
const ROW_C: Row = { name: 'Gamma', tag: 'blue', siteName: undefined }
const ROW_D: Row = { name: 'Delta', tag: null, siteName: '' }

const ROWS = [ROW_A, ROW_B, ROW_C, ROW_D]

// ─── Basic passthrough ────────────────────────────────────────────────────────

describe('applyTableFilter – empty params', () => {
  it('returns all rows when no params are set', () => {
    const spec: FilterSpec<Row> = {
      search: { fields: (r) => [r.name] },
      filters: [{ paramKey: 'tag', predicate: (r, v) => r.tag === v }],
    }
    const result = applyTableFilter(ROWS, spec, new URLSearchParams(''))
    expect(result).toHaveLength(ROWS.length)
  })

  it('returns all rows when spec has no search or filters', () => {
    const result = applyTableFilter(ROWS, {}, new URLSearchParams(''))
    expect(result).toHaveLength(ROWS.length)
  })
})

// ─── Active-value rule ────────────────────────────────────────────────────────

describe('applyTableFilter – active-value rule', () => {
  const spec: FilterSpec<Row> = {
    filters: [{ paramKey: 'tag', predicate: (r, v) => r.tag === v }],
  }

  it('filter with value ALL is inactive → all rows returned', () => {
    const result = applyTableFilter(ROWS, spec, new URLSearchParams('tag=ALL'))
    expect(result).toHaveLength(ROWS.length)
  })

  it('filter with empty string value is inactive → all rows returned', () => {
    const result = applyTableFilter(ROWS, spec, new URLSearchParams('tag='))
    expect(result).toHaveLength(ROWS.length)
  })

  it('absent key is inactive → all rows returned', () => {
    const result = applyTableFilter(ROWS, spec, new URLSearchParams(''))
    expect(result).toHaveLength(ROWS.length)
  })

  it('active filter with value "blue" narrows to matching rows', () => {
    const result = applyTableFilter(ROWS, spec, new URLSearchParams('tag=blue'))
    expect(result).toEqual([ROW_A, ROW_C])
  })

  it('active filter with value "red" returns only ROW_B', () => {
    const result = applyTableFilter(ROWS, spec, new URLSearchParams('tag=red'))
    expect(result).toEqual([ROW_B])
  })
})

// ─── Search ───────────────────────────────────────────────────────────────────

describe('applyTableFilter – search', () => {
  const spec: FilterSpec<Row> = {
    search: { fields: (r) => [r.name, r.tag] },
  }

  it('search is case-insensitive', () => {
    const result = applyTableFilter(ROWS, spec, new URLSearchParams('q=alpha'))
    expect(result).toEqual([ROW_A])
  })

  it('search is substring', () => {
    const result = applyTableFilter(ROWS, spec, new URLSearchParams('q=et'))
    // "Beta" contains "et"
    expect(result).toEqual([ROW_B])
  })

  it('empty q is inactive → all rows', () => {
    const result = applyTableFilter(ROWS, spec, new URLSearchParams('q='))
    expect(result).toHaveLength(ROWS.length)
  })

  it('absent q is inactive → all rows', () => {
    const result = applyTableFilter(ROWS, spec, new URLSearchParams(''))
    expect(result).toHaveLength(ROWS.length)
  })

  // ── Null-coercion regression ──────────────────────────────────────────────
  it('null/undefined fields do NOT match the literal string "null"', () => {
    // ROW_C has tag=undefined, ROW_D has tag=null.
    // Without .filter(Boolean), joining would produce "... null" which matches.
    const result = applyTableFilter(ROWS, spec, new URLSearchParams('q=null'))
    expect(result).toHaveLength(0)
  })

  it('null/undefined fields do NOT match the literal string "undefined"', () => {
    const result = applyTableFilter(ROWS, spec, new URLSearchParams('q=undefined'))
    expect(result).toHaveLength(0)
  })

  it('uses custom paramKey when specified', () => {
    const customSpec: FilterSpec<Row> = {
      search: { paramKey: 'search', fields: (r) => [r.name] },
    }
    const result = applyTableFilter(ROWS, customSpec, new URLSearchParams('search=alpha'))
    expect(result).toEqual([ROW_A])
    // plain 'q' should not trigger it
    const resultQ = applyTableFilter(ROWS, customSpec, new URLSearchParams('q=alpha'))
    expect(resultQ).toHaveLength(ROWS.length)
  })
})

// ─── siteFilter ───────────────────────────────────────────────────────────────

describe('siteFilter', () => {
  const spec: FilterSpec<Row> = {
    filters: [siteFilter<Row>()],
  }

  it('"unassigned" keeps only rows with falsy siteName', () => {
    const result = applyTableFilter(ROWS, spec, new URLSearchParams('site=unassigned'))
    // ROW_C (undefined) and ROW_D (empty string '')
    expect(result).toEqual([ROW_C, ROW_D])
  })

  it('a literal site name matches exactly', () => {
    const result = applyTableFilter(ROWS, spec, new URLSearchParams('site=HQ'))
    expect(result).toEqual([ROW_A])
  })

  it('"ALL" is inactive → all rows', () => {
    const result = applyTableFilter(ROWS, spec, new URLSearchParams('site=ALL'))
    expect(result).toHaveLength(ROWS.length)
  })

  it('absent site param is inactive → all rows', () => {
    const result = applyTableFilter(ROWS, spec, new URLSearchParams(''))
    expect(result).toHaveLength(ROWS.length)
  })
})

// ─── uniqueValues ─────────────────────────────────────────────────────────────

describe('uniqueValues', () => {
  it('returns distinct non-empty values sorted alphabetically by default', () => {
    const rows = [
      { type: 'switch' },
      { type: 'gateway' },
      { type: 'switch' },
      { type: '' },
      { type: null },
      { type: undefined },
    ]
    expect(uniqueValues(rows, (r) => r.type)).toEqual(['gateway', 'switch'])
  })

  it('orders by a custom comparator when supplied (severity rank)', () => {
    const rows = [
      { severity: 'Minor' },
      { severity: 'Critical' },
      { severity: 'Warning' },
      { severity: 'Major' },
      { severity: 'Critical' },
    ]
    // Rank order, not alphabetical (which would be Critical, Major, Minor, Warning by luck —
    // so include an unknown to prove rank wins): unknown sorts last.
    expect(uniqueValues(rows, (r) => r.severity, severityOrder)).toEqual([
      'Critical',
      'Major',
      'Minor',
      'Warning',
    ])
  })

  it('sorts unknown severities after known ones', () => {
    const rows = [{ severity: 'Emergency' }, { severity: 'Critical' }, { severity: 'Minor' }]
    expect(uniqueValues(rows, (r) => r.severity, severityOrder)).toEqual([
      'Critical',
      'Minor',
      'Emergency',
    ])
  })
})

// ─── Multiple active filters AND together ────────────────────────────────────

describe('applyTableFilter – multiple filters AND together', () => {
  it('both active filters must pass', () => {
    const spec: FilterSpec<Row> = {
      search: { fields: (r) => [r.name] },
      filters: [
        { paramKey: 'tag', predicate: (r, v) => r.tag === v },
        siteFilter<Row>(),
      ],
    }
    // tag=blue AND site=HQ → only ROW_A
    const result = applyTableFilter(
      ROWS,
      spec,
      new URLSearchParams('tag=blue&site=HQ'),
    )
    expect(result).toEqual([ROW_A])
  })

  it('search AND filter both active', () => {
    const spec: FilterSpec<Row> = {
      search: { fields: (r) => [r.name] },
      filters: [{ paramKey: 'tag', predicate: (r, v) => r.tag === v }],
    }
    // q=a AND tag=blue → ROW_A ("Alpha" contains "a", tag=blue) and ROW_C ("Gamma" contains "a", tag=blue)
    const result = applyTableFilter(
      ROWS,
      spec,
      new URLSearchParams('q=a&tag=blue'),
    )
    expect(result).toEqual([ROW_A, ROW_C])
  })
})
