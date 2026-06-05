import { Suspense, lazy, useCallback } from 'react'
import { Routes, Route } from 'react-router-dom'
import useSWR, { useSWRConfig } from 'swr'
import { toast } from 'sonner'
import { Toaster } from '@/components/ui/sonner'
import { Topbar } from '@/components/Topbar'
import { getStatus, postRefresh, logout } from '@/lib/api'
import { AutoRefreshProvider, useAutoRefreshContext, useAutoRefresh } from '@/lib/autoRefresh'
import { AUTO_INTERVAL_MS, STORAGE_KEYS } from '@/lib/constants'
import { ExchangeProvider } from '@/lib/exchange'
import { SelectionProvider } from '@/lib/selection'
import { LoginGate } from '@/components/LoginGate'

const Overview = lazy(() => import('@/pages/Overview').then((module) => ({ default: module.Overview })))
const TenantDetail = lazy(() =>
  import('@/pages/TenantDetail').then((module) => ({ default: module.TenantDetail })),
)

function LoadingScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-muted-foreground text-sm">Loading…</div>
    </div>
  )
}

function AppShell() {
  const { autoEnabled, setAutoEnabled } = useAutoRefreshContext()
  const { mutate } = useSWRConfig()

  const { data: status, mutate: mutateStatus } = useSWR('/api/status', getStatus, { refreshInterval: 30_000 })

  const handleRefresh = useCallback(async () => {
    try {
      await postRefresh()
      await Promise.all([
        mutateStatus(),
        mutate((key) => Array.isArray(key) ? key[0] === 'overview' || key[0] === 'tenant-detail' : false),
      ])
      toast.success('Refreshed successfully')
    } catch (err) {
      toast.error(`Refresh failed: ${err instanceof Error ? err.message : String(err)}`)
    }
  }, [mutateStatus, mutate])

  const handleDisconnect = useCallback(async () => {
    try {
      await logout()
      localStorage.removeItem(STORAGE_KEYS.creds)
      await mutateStatus()
    } catch (err) {
      toast.error(`Disconnect failed: ${err instanceof Error ? err.message : String(err)}`)
    }
  }, [mutateStatus])

  useAutoRefresh(autoEnabled, AUTO_INTERVAL_MS, handleRefresh)

  if (!status) {
    return <LoadingScreen />
  }
  if (!status.authenticated) {
    return <LoginGate onConnected={() => { void mutateStatus() }} />
  }

  return (
    <ExchangeProvider>
      <div className="min-h-screen bg-background">
        <Topbar autoEnabled={autoEnabled} onAutoToggle={setAutoEnabled} onRefresh={handleRefresh} onDisconnect={handleDisconnect} demo={status.demo ?? false} />
        <main className="container py-6">
          <Suspense fallback={<LoadingScreen />}>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/tenants/:id" element={<TenantDetail />} />
            </Routes>
          </Suspense>
        </main>
        <Toaster />
      </div>
    </ExchangeProvider>
  )
}

export default function App() {
  return (
    <AutoRefreshProvider>
      <SelectionProvider>
        <AppShell />
      </SelectionProvider>
    </AutoRefreshProvider>
  )
}
