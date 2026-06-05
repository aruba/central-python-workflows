import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react'
import { STORAGE_KEYS } from './constants'

function readAutoEnabled(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEYS.auto) === 'true'
  } catch {
    return false
  }
}

interface AutoRefreshContextValue {
  autoEnabled: boolean
  setAutoEnabled: (enabled: boolean) => void
}

const AutoRefreshContext = createContext<AutoRefreshContextValue | null>(null)

export function AutoRefreshProvider({ children }: { children: ReactNode }) {
  const [autoEnabled, setAutoEnabledState] = useState<boolean>(readAutoEnabled)

  const setAutoEnabled = useCallback((enabled: boolean) => {
    setAutoEnabledState(enabled)
    try {
      localStorage.setItem(STORAGE_KEYS.auto, String(enabled))
    } catch { /* ignore storage errors */ }
  }, [])

  // Cross-tab sync: keep in-process state aligned when another tab writes the key.
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key === STORAGE_KEYS.auto) {
        setAutoEnabledState(readAutoEnabled())
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  return (
    <AutoRefreshContext.Provider value={{ autoEnabled, setAutoEnabled }}>
      {children}
    </AutoRefreshContext.Provider>
  )
}

export function useAutoRefreshContext(): AutoRefreshContextValue {
  const ctx = useContext(AutoRefreshContext)
  if (!ctx) throw new Error('useAutoRefreshContext must be used within an AutoRefreshProvider')
  return ctx
}

/**
 * Convenience hook: reads only the enabled boolean from context.
 * Drop-in replacement for the old `useAutoEnabled()` from polling.ts.
 */
export function useAutoEnabled(): boolean {
  return useAutoRefreshContext().autoEnabled
}

/**
 * Fires `onTick` on a repeating interval while `enabled` is true.
 * Cleans up the interval when `enabled` becomes false or the component unmounts.
 */
export function useAutoRefresh(
  enabled: boolean,
  intervalMs: number,
  onTick: () => void,
): void {
  useEffect(() => {
    if (!enabled) return
    const id = setInterval(onTick, intervalMs)
    return () => clearInterval(id)
  }, [enabled, intervalMs, onTick])
}
