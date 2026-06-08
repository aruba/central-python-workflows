/**
 * Single source of truth for Alert severity → Tailwind class strings.
 * Covers the four Alert severities: CRITICAL / MAJOR / MINOR / WARNING.
 *
 * NOTE: Site health (good / fair / poor / critical) lives in SitesTab's
 * healthBadgeClass() — that is a distinct scale and must NOT be merged here.
 */

const SEVERITY_CLASSES: Record<string, string> = {
  CRITICAL: 'bg-danger/15 text-danger',
  MAJOR: 'bg-warning/15 text-warning',
  MINOR: 'bg-info/15 text-info',
  WARNING: 'bg-info/15 text-info',
}

/** Returns the badge className for a given Alert severity string (case-insensitive). */
export function severityBadgeClass(severity: string): string {
  return SEVERITY_CLASSES[severity?.toUpperCase() ?? ''] ?? ''
}

/**
 * Inline text color for an Alert severity chip/label (used in AlertBreakdown).
 * Distinct from the badge classes above (no background, smaller text widgets).
 */
const SEVERITY_TEXT_CLASSES: Record<string, string> = {
  CRITICAL: 'text-danger',
  MAJOR: 'text-warning',
  MINOR: 'text-info',
  WARNING: 'text-info',
}

/** Returns the inline text className for an Alert severity chip (case-insensitive). */
export function severityTextClass(severity: string): string {
  return SEVERITY_TEXT_CLASSES[severity?.toUpperCase() ?? ''] ?? 'text-muted-foreground'
}

/**
 * Operational rank for the four known severities (lower = more urgent). Used to
 * order derived severity filter options so they read Critical → Major → Minor →
 * Warning rather than alphabetically.
 */
const SEVERITY_RANK: Record<string, number> = {
  CRITICAL: 0,
  MAJOR: 1,
  MINOR: 2,
  WARNING: 3,
}

/**
 * Comparator for severity strings (case-insensitive). Known severities sort by
 * SEVERITY_RANK; any unknown value sorts after all known ones, then alphabetically.
 */
export function severityOrder(a: string, b: string): number {
  const ra = SEVERITY_RANK[a?.toUpperCase() ?? ''] ?? Number.MAX_SAFE_INTEGER
  const rb = SEVERITY_RANK[b?.toUpperCase() ?? ''] ?? Number.MAX_SAFE_INTEGER
  return ra === rb ? a.localeCompare(b) : ra - rb
}
