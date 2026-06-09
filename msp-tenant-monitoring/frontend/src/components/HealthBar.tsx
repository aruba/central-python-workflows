import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

interface HealthBarProps {
  good: number
  fair: number
  poor: number
}

export function HealthBar({ good, fair, poor }: HealthBarProps) {
  const total = good + fair + poor

  if (total === 0) {
    return (
      <div className="h-1.5 w-full rounded-full bg-muted flex items-center justify-center">
        <span className="sr-only">No health data</span>
      </div>
    )
  }

  const goodPct = (good / total) * 100
  const fairPct = (fair / total) * 100
  const poorPct = (poor / total) * 100

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className="flex h-1.5 w-full overflow-hidden rounded-full"
            role="img"
            aria-label={`Health: Good ${good}, Fair ${fair}, Poor ${poor}`}
          >
            {good > 0 && (
              <div
                className="bg-success"
                style={{ width: `${goodPct}%` }}
              />
            )}
            {fair > 0 && (
              <div
                className="bg-warning"
                style={{ width: `${fairPct}%` }}
              />
            )}
            {poor > 0 && (
              <div
                className="bg-danger"
                style={{ width: `${poorPct}%` }}
              />
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent>
          <p>
            Good {good} · Fair {fair} · Poor {poor}
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
