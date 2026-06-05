import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react'
import type { IncludeType } from './api'
import { STORAGE_KEYS } from './constants'

const ALL: IncludeType[] = ['sites', 'devices', 'clients', 'alerts']

// Sites is the gating fetch for tenant drilldown — always included,
// regardless of stored selection. Preserves canonical ALL order.
function withSites(types: IncludeType[]): IncludeType[] {
  const set = new Set<IncludeType>(['sites', ...types])
  return ALL.filter((t) => set.has(t))
}

function readTypes(): IncludeType[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.drilldownTypes)
    if (!raw) return ALL
    const parsed = JSON.parse(raw) as string[]
    if (!Array.isArray(parsed)) return ALL
    return withSites(ALL.filter((t) => parsed.includes(t)))
  } catch {
    return ALL
  }
}

interface SelectionContextValue {
  selectedTypes: IncludeType[]
  setSelectedTypes: (types: IncludeType[]) => void
}

const SelectionContext = createContext<SelectionContextValue | null>(null)

export function SelectionProvider({ children }: { children: ReactNode }) {
  const [selectedTypes, setSelectedTypesState] = useState<IncludeType[]>(readTypes)

  const setSelectedTypes = useCallback((types: IncludeType[]) => {
    const next = withSites(types)
    setSelectedTypesState(next)
    try {
      localStorage.setItem(STORAGE_KEYS.drilldownTypes, JSON.stringify(next))
    } catch { /* ignore storage errors */ }
  }, [])

  // Cross-tab sync: keep in-process state aligned when another tab writes the key.
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key === STORAGE_KEYS.drilldownTypes) {
        setSelectedTypesState(readTypes())
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  return (
    <SelectionContext.Provider value={{ selectedTypes, setSelectedTypes }}>
      {children}
    </SelectionContext.Provider>
  )
}

export function useSelectionContext(): SelectionContextValue {
  const ctx = useContext(SelectionContext)
  if (!ctx) throw new Error('useSelectionContext must be used within a SelectionProvider')
  return ctx
}

/**
 * Convenience hook returning only the selected types array.
 * Drop-in replacement for the old `useSelectedTypes()` from selection.ts.
 */
export function useSelectedTypes(): IncludeType[] {
  return useSelectionContext().selectedTypes
}
