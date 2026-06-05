export type DetailType = 'sites' | 'devices' | 'clients' | 'alerts'

export const detailKey = (id: string, type: DetailType) =>
  ['tenant-detail', id, type] as const

// PURE tri-state projection (lifted from tri() in TenantDetail.tsx).
// null  => show "Fetch now" placeholder (deselected & not fired)  OR an error occurred
// undefined => show skeleton (selected, in-flight or timer not yet popped)
// T[]   => render the data
export function projectDetail<T>(input: {
  fired: boolean
  selected: boolean
  data: T[] | undefined
  error: unknown
}): T[] | null | undefined {
  if (!input.fired) return input.selected ? undefined : null
  if (input.error) return null
  return input.data
}
