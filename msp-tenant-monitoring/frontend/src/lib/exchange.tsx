import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { TenantExchangeModal } from '@/components/TenantExchangeModal'
import { STORAGE_KEYS } from './constants'

function getInitialShowSteps(): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.exchangeShowSteps)
    if (stored === 'false') return false
  } catch { /* ignore */ }
  return true
}

export interface ExchangeContextValue {
  showSteps: boolean
  setShowSteps: (v: boolean) => void
  beginDrilldown: (tenant: { id: string; name: string }) => void
}

const ExchangeContext = createContext<ExchangeContextValue | null>(null)

export function ExchangeProvider({ children }: { children: ReactNode }) {
  const [showSteps, setShowStepsState] = useState<boolean>(getInitialShowSteps)
  const [activeTenant, setActiveTenant] = useState<{ id: string; name: string } | null>(null)
  const navigate = useNavigate()

  const setShowSteps = useCallback((v: boolean) => {
    setShowStepsState(v)
    try {
      localStorage.setItem(STORAGE_KEYS.exchangeShowSteps, String(v))
    } catch { /* ignore */ }
  }, [])

  const beginDrilldown = useCallback(
    (tenant: { id: string; name: string }) => {
      if (showSteps) {
        setActiveTenant(tenant)
      } else {
        navigate(`/tenants/${tenant.id}`)
      }
    },
    [showSteps, navigate],
  )

  return (
    <ExchangeContext.Provider value={{ showSteps, setShowSteps, beginDrilldown }}>
      {children}
      <TenantExchangeModal tenant={activeTenant} onClose={() => setActiveTenant(null)} />
    </ExchangeContext.Provider>
  )
}

export function useExchange(): ExchangeContextValue {
  const ctx = useContext(ExchangeContext)
  if (!ctx) throw new Error('useExchange must be used within an ExchangeProvider')
  return ctx
}
