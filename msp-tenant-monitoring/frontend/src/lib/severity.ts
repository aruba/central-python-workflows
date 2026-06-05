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
