const numberFmt = new Intl.NumberFormat('en-US')

export function formatNumber(n: number): string {
  return numberFmt.format(n)
}

export function formatRelativeTime(ts: number | null): string {
  if (ts === null) return 'never'
  const diffS = Math.floor(Date.now() / 1000 - ts)
  if (diffS < 60) return `${diffS}s ago`
  if (diffS < 3600) return `${Math.floor(diffS / 60)}m ago`
  return `${Math.floor(diffS / 3600)}h ago`
}
