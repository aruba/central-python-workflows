import { RefreshCw, MoreHorizontal, Sun, Moon, Monitor, Check, LogOut } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useTheme, type ThemeMode } from '@/lib/theme'
import { useExchange } from '@/lib/exchange'
import { DrilldownSettings } from '@/components/DrilldownSettings'

interface TopbarProps {
  autoEnabled: boolean
  onAutoToggle: (enabled: boolean) => void
  onRefresh: () => void
  onDisconnect: () => void
  demo?: boolean
}

export function Topbar({
  autoEnabled,
  onAutoToggle,
  onRefresh,
  onDisconnect,
  demo,
}: TopbarProps) {
  const { theme, setTheme } = useTheme()
  const { showSteps, setShowSteps } = useExchange()

  const themeItems: Array<{ mode: ThemeMode; label: string; icon: React.ReactNode }> = [
    { mode: 'light', label: 'Light', icon: <Sun className="h-3.5 w-3.5" /> },
    { mode: 'dark', label: 'Dark', icon: <Moon className="h-3.5 w-3.5" /> },
    { mode: 'system', label: 'System', icon: <Monitor className="h-3.5 w-3.5" /> },
  ]

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="flex h-16 items-center gap-4 px-6">
        {/* Left: title — geometric sans with negative tracking, mono eyebrow below */}
        <div className="flex flex-col">
          <span className="text-[15px] font-semibold leading-none tracking-display-md">
            MSP Control Tower
          </span>
          <span className="eyebrow mt-1 leading-none">Cross-tenant overview</span>
        </div>

        {demo && (
          <span className="rounded-full bg-warning/15 px-2 py-0.5 text-xs font-medium text-warning">
            Demo
          </span>
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Refresh button */}
        <Button
          variant="ghost"
          size="icon"
          onClick={onRefresh}
          aria-label="Refresh"
        >
          <RefreshCw className="h-4 w-4" />
        </Button>

        {/* Auto switch */}
        <div className="flex items-center gap-1.5">
          <span className="text-sm text-muted-foreground">Auto</span>
          <Switch
            checked={autoEnabled}
            onCheckedChange={onAutoToggle}
            aria-label="Toggle auto refresh"
          />
        </div>

        {/* Drilldown data settings */}
        <DrilldownSettings />

        {/* Overflow menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="More options">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {themeItems.map(({ mode, label, icon }) => (
              <DropdownMenuItem
                key={mode}
                onSelect={() => setTheme(mode)}
                className="flex items-center gap-2"
              >
                {icon}
                <span>Theme: {label}</span>
                {theme === mode && <Check className="h-3.5 w-3.5 ml-auto" />}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={(e) => { e.preventDefault(); setShowSteps(!showSteps) }}
              className="flex items-center gap-2"
            >
              <span>Show exchange steps</span>
              {showSteps && <Check className="h-3.5 w-3.5 ml-auto" />}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => onDisconnect()} className="flex items-center gap-2 text-destructive focus:text-destructive">
              <LogOut className="h-3.5 w-3.5" />
              <span>Disconnect</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
