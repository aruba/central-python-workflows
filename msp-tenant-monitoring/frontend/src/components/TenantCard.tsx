import {
  ArrowRight,
  AlertTriangle,
  Building2,
  Server,
} from 'lucide-react'
import type React from 'react'
import { useExchange } from '@/lib/exchange'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { HealthBar } from '@/components/HealthBar'
import { formatNumber } from '@/lib/format'
import type { Tenant } from '@/lib/api'

interface TenantCardProps {
  tenant: Tenant
}

export function TenantCard({ tenant }: TenantCardProps) {
  const { beginDrilldown } = useExchange()
  const { summary } = tenant

  const siteCount = summary.total_sites
  const degradedSites = summary.degraded_sites
  const deviceCount = summary.device_health.total

  const criticalAlerts = summary.alerts.critical
  const totalAlerts = summary.alerts.total
  const healthSummary = [
    `${formatNumber(summary.device_health.good)} good`,
    `${formatNumber(summary.device_health.fair)} fair`,
    `${formatNumber(summary.device_health.poor)} poor`,
  ].join(' · ')
  const unhealthyDevices = summary.device_health.fair + summary.device_health.poor
  const deviceSublabel =
    deviceCount === 0
      ? 'No devices'
      : unhealthyDevices > 0
        ? `${formatNumber(unhealthyDevices)} need attention`
        : 'All healthy'

  const hasWorkspace = summary.glp_workspace_id != null
  const alertLabel =
    criticalAlerts > 0
      ? `${formatNumber(criticalAlerts)} critical`
      : totalAlerts > 0
        ? `${formatNumber(totalAlerts)} active`
        : 'No active alerts'

  return (
    <Card className="hover:shadow-stack-2 hover:border-foreground/20 transition-shadow">
      <CardContent className="p-5 flex flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <div className="flex items-center gap-2">
              <span className="font-semibold leading-tight tracking-display-md text-[15px] truncate">
                {summary.tenant_name}
              </span>
              {summary.device_ownership && (
                <Badge
                  variant="outline"
                  className="shrink-0 tabular-nums px-1.5 py-0 font-normal text-muted-foreground"
                >
                  {summary.device_ownership === 'MSP' ? 'MSP owned' : 'Tenant owned'}
                </Badge>
              )}
            </div>
          </div>
          <div className="shrink-0">
            {criticalAlerts > 0 ? (
              <Badge variant="destructive" className="flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" />
                {alertLabel}
              </Badge>
            ) : totalAlerts > 0 ? (
              <Badge variant="secondary">{alertLabel}</Badge>
            ) : (
              <Badge variant="outline" className="font-normal text-muted-foreground">
                No alerts
              </Badge>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <MetricTile
            icon={<Building2 className="h-3.5 w-3.5" />}
            label="Sites"
            value={siteCount}
            sublabel={
              degradedSites > 0
                ? `${formatNumber(degradedSites)} degraded`
                : 'All healthy'
            }
            tone={degradedSites > 0 ? 'warning' : 'neutral'}
          />
          <MetricTile
            icon={<Server className="h-3.5 w-3.5" />}
            label="Devices"
            value={deviceCount}
            sublabel={deviceSublabel}
            tone={unhealthyDevices > 0 ? 'warning' : 'neutral'}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between gap-2">
            <span className="eyebrow">Device health</span>
            <span className="text-[11px] text-muted-foreground tabular-nums">
              {healthSummary}
            </span>
          </div>
          <HealthBar
            good={summary.device_health.good}
            fair={summary.device_health.fair}
            poor={summary.device_health.poor}
          />
        </div>

        {totalAlerts > 0 && (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <span className="eyebrow">Alerts</span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {formatNumber(totalAlerts)} total
              </span>
            </div>
            <AlertBar
              critical={summary.alerts.critical}
              major={summary.alerts.major}
              minor={summary.alerts.minor}
            />
            <div className="flex items-center gap-3 text-[11px] text-muted-foreground tabular-nums">
              {summary.alerts.critical > 0 && (
                <span className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-danger" />
                  Critical {summary.alerts.critical}
                </span>
              )}
              {summary.alerts.major > 0 && (
                <span className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-warning" />
                  Major {summary.alerts.major}
                </span>
              )}
              {summary.alerts.minor > 0 && (
                <span className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-info" />
                  Minor {summary.alerts.minor}
                </span>
              )}
            </div>
          </div>
        )}

        <div className="flex items-center justify-end border-t pt-3">
          {hasWorkspace ? (
            <Button
              type="button"
              size="sm"
              onClick={() => beginDrilldown({ id: summary.tenant_id, name: summary.tenant_name })}
              className="h-8 px-3 text-xs"
            >
              Open tenant
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          ) : (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="inline-flex">
                    <Button
                      type="button"
                      size="sm"
                      disabled
                      className="h-8 px-3 text-xs"
                    >
                      Open tenant
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent>
                  No GLP workspace found, tenant detail is unavailable
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

interface MetricTileProps {
  icon: React.ReactNode
  label: string
  value: number
  sublabel: string
  tone?: 'neutral' | 'warning'
}

function MetricTile({
  icon,
  label,
  value,
  sublabel,
  tone = 'neutral',
}: MetricTileProps) {
  return (
    <div className="rounded-md border bg-muted/20 px-3 py-2.5">
      <div className="flex items-center justify-between gap-2 text-muted-foreground">
        <span className="flex items-center gap-1.5 text-xs">
          {icon}
          {label}
        </span>
        <span className="text-lg font-semibold leading-none text-foreground tabular-nums">
          {formatNumber(value)}
        </span>
      </div>
      <p
        className={`mt-1 text-[11px] tabular-nums ${
          tone === 'warning'
            ? 'text-warning'
            : 'text-muted-foreground'
        }`}
      >
        {sublabel}
      </p>
    </div>
  )
}

interface AlertBarProps {
  critical: number
  major: number
  minor: number
}

function AlertBar({ critical, major, minor }: AlertBarProps) {
  const total = critical + major + minor
  if (total === 0) return null
  const criticalPct = (critical / total) * 100
  const majorPct = (major / total) * 100
  const minorPct = (minor / total) * 100
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className="flex h-1.5 w-full overflow-hidden rounded-full"
            role="img"
            aria-label={`Alerts: Critical ${critical}, Major ${major}, Minor ${minor}`}
          >
            {critical > 0 && (
              <div className="bg-danger" style={{ width: `${criticalPct}%` }} />
            )}
            {major > 0 && (
              <div className="bg-warning" style={{ width: `${majorPct}%` }} />
            )}
            {minor > 0 && (
              <div className="bg-info" style={{ width: `${minorPct}%` }} />
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent>
          <p>
            Critical {critical} · Major {major} · Minor {minor}
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
