import { useEffect, useRef, useState } from 'react'
import type React from 'react'
import { useNavigate } from 'react-router-dom'
import { useSWRConfig } from 'swr'
import { AlertCircle, Check } from 'lucide-react'

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  exchangeTenant,
  getTenantDetail,
  DOCS_URL,
  type ExchangeInfo,
  type TenantDetail,
} from '@/lib/api'
import { detailKey } from '@/lib/detailKeys'
import { useExchange } from '@/lib/exchange'

type StepStatus = 'pending' | 'running' | 'done' | 'error'

interface StepState {
  status: StepStatus
  detail?: string
  subDetail?: string
}

const initialSteps: StepState[] = [
  { status: 'pending' },
  { status: 'pending' },
  { status: 'pending' },
  { status: 'pending' },
]

// The rail node morphs through the four states. The progress rail stays
// monochrome (foreground) so completion reads as "advanced", not "succeeded";
// color is reserved for the one state that needs attention: error.
function StepNode({ status }: { status: StepStatus }) {
  const base =
    'relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full transition-colors duration-300'
  if (status === 'done') {
    return (
      <span className={`${base} bg-foreground text-background`}>
        <Check className="h-3.5 w-3.5" strokeWidth={2.5} />
      </span>
    )
  }
  if (status === 'error') {
    return (
      <span className={`${base} bg-danger text-white`}>
        <AlertCircle className="h-3.5 w-3.5" />
      </span>
    )
  }
  if (status === 'running') {
    return (
      <span className={`${base} border-2 border-muted`}>
        <span className="absolute inset-[-2px] animate-spin rounded-full border-2 border-transparent border-t-foreground" />
      </span>
    )
  }
  // pending
  return (
    <span className={`${base} border border-border bg-muted`}>
      <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40" />
    </span>
  )
}

// A masked credential / endpoint shown on the wire as it resolves.
function WireChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="animate-wire inline-flex max-w-full items-center gap-1.5 break-all rounded-md border bg-muted/40 px-2 py-1 font-mono text-[11px] leading-tight text-muted-foreground">
      {children}
    </span>
  )
}

function TimingBadge({ ms }: { ms: number }) {
  return (
    <span className="animate-wire inline-flex items-center rounded-full bg-muted px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-muted-foreground">
      {ms}ms
    </span>
  )
}

const STEP_TITLES = [
  'MSP Access Token',
  'Request Tenant-Scoped Token',
  'Receive Tenant Token',
  'Fetching Sites',
]

// Presentation pacing. Each step holds "running" for at least STEP_DWELL_MS
// so the rail walks node-by-node and the exchange shape is readable; real
// network time wins when slower (dwells gate presentation, never add latency
// on top of a slow call). COMPLETE_HOLD_MS keeps the finished rail on screen
// before auto-navigating. Errors bypass all pacing.
const STEP_DWELL_MS = 550
const COMPLETE_HOLD_MS = 800

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms))
}

// Never resolves; rejects iff `p` rejects. Racing this against a dwell lets
// a real failure cut through the presentation instead of waiting it out.
function failFast(p: Promise<unknown>): Promise<never> {
  return p.then(() => new Promise<never>(() => {}))
}

export function TenantExchangeModal({
  tenant,
  onClose,
}: {
  tenant: { id: string; name: string } | null
  onClose: () => void
}) {
  const navigate = useNavigate()
  const { mutate } = useSWRConfig()
  const { setShowSteps } = useExchange()

  const [steps, setSteps] = useState<StepState[]>(initialSteps)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [exchangeInfo, setExchangeInfo] = useState<ExchangeInfo | null>(null)
  const startedForRef = useRef<string | null>(null)

  // Reset when dialog closes
  useEffect(() => {
    if (tenant === null) {
      setSteps(initialSteps)
      setErrorMsg(null)
      setExchangeInfo(null)
    }
  }, [tenant])

  useEffect(() => {
    if (!tenant) return
    if (startedForRef.current === tenant.id) return
    startedForRef.current = tenant.id

    let aborted = false

    function setStep(i: number, state: StepState) {
      setSteps((prev) => prev.map((s, idx) => (idx === i ? state : s)))
    }

    function fail(i: number, e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : String(e))
      setStep(i, { status: 'error' })
    }

    async function run() {
      if (!tenant) return

      // Kick the real work off immediately; the dwells below only gate
      // what's shown, not when the network runs.
      const exchangePromise = exchangeTenant(tenant.id)
      exchangePromise.catch(() => {}) // observed below; avoid unhandled rejection

      // Step 1: MSP token already held. Give it a beat so the rail visibly
      // starts from the top instead of loading half-finished.
      setStep(0, { status: 'running' })
      try {
        await Promise.race([sleep(STEP_DWELL_MS), failFast(exchangePromise)])
      } catch (e) {
        if (aborted) return
        setStep(0, { status: 'done', detail: 'Authenticated as MSP workspace' })
        fail(1, e)
        return
      }
      if (aborted) return
      setStep(0, { status: 'done', detail: 'Authenticated as MSP workspace' })

      // Step 2: request tenant-scoped token
      setStep(1, { status: 'running' })
      let info: ExchangeInfo
      try {
        ;[info] = await Promise.all([exchangePromise, sleep(STEP_DWELL_MS)])
      } catch (e) {
        if (aborted) return
        fail(1, e)
        return
      }
      if (aborted) return

      // The sites fetch can start now — it overlaps the remaining beats.
      const detailPromise = getTenantDetail(tenant.id, ['sites'])
      detailPromise.catch(() => {}) // observed below; avoid unhandled rejection

      setExchangeInfo(info)
      setSteps((prev) => {
        const next = [...prev]
        next[0] = {
          status: 'done',
          detail: 'Authenticated as MSP workspace',
          subDetail: info.msp_token_masked,
        }
        next[1] = {
          status: 'done',
          detail: `POST ${info.token_url}`,
          subDetail: info.grant_type,
        }
        return next
      })

      // Step 3: receive tenant token — its own beat so request/receive read
      // as the two halves of the exchange rather than one flash. The cached
      // case keeps the beat too: "reused from cache" is part of the lesson.
      const receivedStep: StepState = {
        status: 'done',
        detail: info.cached
          ? 'Tenant token reused from cache, exchange skipped'
          : (info.tenant_token_masked ?? undefined),
        subDetail: `Token exchange: ${info.duration_ms}ms`,
      }
      setStep(2, { status: 'running' })
      try {
        await Promise.race([sleep(STEP_DWELL_MS), failFast(detailPromise)])
      } catch (e) {
        if (aborted) return
        setStep(2, receivedStep)
        fail(3, e)
        return
      }
      if (aborted) return
      setStep(2, receivedStep)

      // Step 4: fetch sites only — the gating data for the detail page.
      // Devices/clients/alerts load progressively after navigation.
      setStep(3, { status: 'running' })
      let detail: TenantDetail
      try {
        ;[detail] = await Promise.all([detailPromise, sleep(STEP_DWELL_MS)])
      } catch (e) {
        if (aborted) return
        fail(3, e)
        return
      }
      if (aborted) return

      const sites = detail.sites ?? []
      // Pre-warm the per-type key the detail page reads so sites render
      // immediately on landing without a refetch.
      mutate(detailKey(tenant.id, 'sites'), sites, false)
      setStep(3, {
        status: 'done',
        detail: `${sites.length} site${sites.length === 1 ? '' : 's'} loaded`,
      })

      // Hold the completed rail so the full sequence registers before leaving.
      await sleep(COMPLETE_HOLD_MS)
      if (aborted) return
      onClose()
      navigate(`/tenants/${tenant.id}`)
    }

    run()

    return () => {
      aborted = true
    }
  }, [tenant?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const activeErrorStep = steps.findIndex((s) => s.status === 'error')

  return (
    <Dialog open={tenant !== null} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="w-[calc(100vw-2rem)] overflow-hidden sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="break-words pr-6">
            {tenant ? `Connecting to ${tenant.name}` : 'Tenant token exchange'}
            {exchangeInfo?.simulated && (
              <span className="ml-2 inline-flex items-center rounded-full bg-info/15 px-2 py-0.5 text-xs font-medium text-info">
                Simulated
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col py-2">
          {steps.map((step, i) => {
            const isLast = i === steps.length - 1
            // The connector below node i fills once that step has resolved.
            const segmentFilled = step.status === 'done'
            return (
              <div key={i} className="relative flex gap-3 pb-5 last:pb-0">
                {/* Rail connector to the next node (track + growing fill) */}
                {!isLast && (
                  <span
                    aria-hidden
                    className="absolute left-3 top-6 bottom-0 w-px -translate-x-1/2 bg-border"
                  >
                    <span
                      className="rail-fill block w-full bg-foreground"
                      style={{ height: segmentFilled ? '100%' : '0%' }}
                    />
                  </span>
                )}

                <StepNode status={step.status} />

                <div className="min-w-0 flex-1 pt-0.5">
                  <p
                    className={`text-sm font-medium transition-colors duration-300 ${
                      step.status === 'pending' ? 'text-muted-foreground' : 'text-foreground'
                    }`}
                  >
                    {STEP_TITLES[i]}
                  </p>

                  {/* Step-specific payload on the wire */}
                  {i === 0 && step.status === 'done' && (
                    <div className="mt-1.5 flex flex-col gap-1.5">
                      <p className="text-xs text-muted-foreground">{step.detail}</p>
                      {step.subDetail && <WireChip>{step.subDetail}</WireChip>}
                    </div>
                  )}

                  {i === 1 && step.status !== 'pending' && (
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      {step.detail && <WireChip>{step.detail}</WireChip>}
                      {step.subDetail && <WireChip>{step.subDetail}</WireChip>}
                    </div>
                  )}

                  {i === 2 && step.status === 'done' && (
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      {exchangeInfo?.cached ? (
                        <span className="animate-wire text-xs text-warning">{step.detail}</span>
                      ) : (
                        step.detail && <WireChip>{step.detail}</WireChip>
                      )}
                      {exchangeInfo && <TimingBadge ms={exchangeInfo.duration_ms} />}
                    </div>
                  )}

                  {i === 3 && step.status === 'running' && (
                    <p className="mt-1 text-xs text-muted-foreground">Loading sites…</p>
                  )}

                  {i === 3 && step.status === 'done' && step.detail && (
                    <p className="animate-wire mt-1 text-xs text-muted-foreground">{step.detail}</p>
                  )}
                </div>
              </div>
            )
          })}

          {errorMsg && activeErrorStep !== -1 && (
            <div className="mt-1 rounded-md border border-destructive/30 bg-destructive/10 p-3">
              <p className="text-sm text-destructive">{errorMsg}</p>
              <Button
                variant="destructive"
                size="sm"
                className="mt-2"
                onClick={() => {
                  onClose()
                  if (tenant) navigate(`/tenants/${tenant.id}`)
                }}
              >
                Continue anyway
              </Button>
            </div>
          )}
        </div>

        <DialogFooter className="flex-row items-center justify-between sm:justify-between">
          <div className="flex items-center gap-2">
            <Checkbox
              id="dont-show-exchange"
              onCheckedChange={(checked) => {
                if (checked) setShowSteps(false)
              }}
            />
            <Label htmlFor="dont-show-exchange" className="cursor-pointer text-muted-foreground">
              Don&apos;t show this again
            </Label>
          </div>
          <a
            href={DOCS_URL}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-muted-foreground underline-offset-4 hover:underline"
          >
            Learn more ↗
          </a>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
