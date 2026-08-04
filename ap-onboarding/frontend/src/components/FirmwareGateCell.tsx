import {
  CheckCircle2,
  Circle,
  Loader2,
  MinusCircle,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import type { FirmwareState } from "@/lib/events";

interface FirmwareGateCellProps {
  firmware: FirmwareState;
}

export function FirmwareGateCell({ firmware }: FirmwareGateCellProps) {
  const version = firmware.currentVersion;

  // The version stays on screen rather than in a title: a tooltip is
  // unreachable by touch, and aria-label on the badge would not be announced
  // either, since Badge renders a plain div with no role. Dropping
  // whitespace-nowrap is what lets the column shrink now that min-w-64 is gone.
  if (firmware.status === "success") {
    return (
      <div className="flex flex-col items-center gap-1">
        <Badge
          variant="secondary"
          className="border-[color-mix(in_oklch,var(--cc-success)_30%,var(--cc-line))] bg-[var(--cc-success-soft)] text-xs text-[var(--cc-success)]"
        >
          <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" />
          Meets minimum
        </Badge>
        {version && (
          <span className="font-mono text-[0.6875rem]">
            {version}
          </span>
        )}
      </div>
    );
  }

  if (firmware.status === "skipped") {
    return (
      <div className="flex flex-col items-center gap-1">
        <Badge
          variant="secondary"
          className="border-[color-mix(in_oklch,var(--cc-info)_30%,var(--cc-line))] bg-[var(--cc-info-soft)] text-xs text-[var(--cc-info)]"
        >
          <MinusCircle aria-hidden="true" className="h-3.5 w-3.5" />
          Skipped (firmware)
        </Badge>
        {version && (
          <span className="font-mono text-[0.6875rem] text-[var(--cc-info)]">
            {version} &lt; {firmware.minimumVersion}
          </span>
        )}
      </div>
    );
  }

  if (firmware.status === "failed") {
    return (
      <Sheet>
        <SheetTrigger asChild>
          <button
            type="button"
            aria-label="Firmware check failed, view error"
            className="rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cc-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--cc-raised)]"
          >
            <Badge variant="destructive" className="cursor-pointer text-xs">
              <XCircle aria-hidden="true" className="h-3.5 w-3.5" />
              Check failed
            </Badge>
          </button>
        </SheetTrigger>
        <SheetContent
          side="right"
          className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)]"
        >
          <SheetHeader>
            <SheetTitle className="text-[var(--cc-ink)]">
              Firmware check error
            </SheetTitle>
          </SheetHeader>
          <p className="mt-4 whitespace-pre-wrap break-words text-sm text-[var(--cc-ink-soft)]">
            {firmware.error || "No error detail was reported."}
          </p>
        </SheetContent>
      </Sheet>
    );
  }

  if (firmware.status === "in_progress") {
    const detail = firmware.detail || "waiting for device to come online";
    return (
      <div
        role="status"
        aria-label={`Firmware check in progress: ${detail}`}
        className="flex flex-col items-center gap-1"
      >
        <Badge
          variant="secondary"
          className="border-[color-mix(in_oklch,var(--cc-accent)_30%,var(--cc-line))] bg-[var(--cc-accent-soft)] text-xs text-[var(--cc-accent)]"
        >
          <Loader2
            aria-hidden="true"
            className="h-3 w-3 shrink-0 motion-safe:animate-spin"
          />
          Running
        </Badge>
        <span className="font-mono text-[0.6875rem] text-[var(--cc-accent)]">
          {detail}
        </span>
      </div>
    );
  }

  return (
    <Badge variant="secondary" className="text-xs" aria-label="Pending">
      <Circle aria-hidden="true" className="h-3.5 w-3.5" />
      Pending
    </Badge>
  );
}
