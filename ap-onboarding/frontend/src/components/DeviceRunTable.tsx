import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  Circle,
  Loader2,
  MinusCircle,
  XCircle,
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { FirmwareGateCell } from "@/components/FirmwareGateCell";
import type { DeviceState, DeviceStepState, StepStatus } from "@/lib/events";
import { cn } from "@/lib/utils";

interface DeviceRunTableProps {
  devices: Record<string, DeviceState>;
}

interface StepBadgeProps {
  state: DeviceStepState | undefined;
  /** The device reached a terminal outcome, so a silent step never will. */
  terminal?: boolean;
}

export function StepBadge({ state, terminal = false }: StepBadgeProps) {
  const status: StepStatus = state?.status ?? "pending";
  const error = state?.error;

  // An optional add-on the operator left blank is skipped by steps/runner.py
  // without emitting any event, so the cell has no state to read. Falling
  // through to "Pending" claimed work was outstanding on a device that had
  // already finished successfully.
  if (!state && terminal) {
    return (
      <Badge
        variant="secondary"
        className="text-xs text-[var(--cc-ink-faint)]"
        aria-label="Not requested"
      >
        <MinusCircle aria-hidden="true" className="h-3.5 w-3.5" />
        Not requested
      </Badge>
    );
  }

  if (status === "failed" && error) {
    return (
      <Sheet>
        <SheetTrigger asChild>
          <button
            type="button"
            className="cursor-pointer rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cc-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--cc-raised)]"
            aria-label="Failed, view error"
          >
            <Badge
              variant="destructive"
              className="gap-1 px-1.5 text-xs hover:bg-[var(--cc-danger)]"
              aria-label="Failed"
            >
              <XCircle aria-hidden="true" className="h-3.5 w-3.5" />
              <span>View</span>
            </Badge>
          </button>
        </SheetTrigger>
        <SheetContent
          side="right"
          className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)]"
        >
          <SheetHeader>
            <SheetTitle className="text-[var(--cc-ink)]">Step error</SheetTitle>
          </SheetHeader>
          <div className="mt-4 whitespace-pre-wrap break-words text-sm text-[var(--cc-ink-soft)]">
            {error}
          </div>
        </SheetContent>
      </Sheet>
    );
  }

  if (status === "failed") {
    return (
      <Badge variant="destructive" className="text-xs" aria-label="Failed">
        <XCircle aria-hidden="true" className="h-3.5 w-3.5" />
      </Badge>
    );
  }

  if (status === "success") {
    return (
      <Badge
        variant="secondary"
        className="border-[color-mix(in_oklch,var(--cc-success)_30%,var(--cc-line))] bg-[var(--cc-success-soft)] text-xs text-[var(--cc-success)]"
        aria-label="Success"
      >
        <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" />
      </Badge>
    );
  }

  if (status === "in_progress") {
    return (
      <Badge variant="default" className="text-xs" aria-label="In progress">
        <Loader2
          aria-hidden="true"
          className="h-3.5 w-3.5 motion-safe:animate-spin"
        />
      </Badge>
    );
  }

  if (status === "skipped") {
    // Skipped and Pending were both bare secondary badges, separable only by a
    // 14px glyph across seven columns. Skipped now carries the same info tint
    // the overall column uses, plus the word.
    return (
      <Badge
        variant="secondary"
        className="border-[color-mix(in_oklch,var(--cc-info)_30%,var(--cc-line))] bg-[var(--cc-info-soft)] text-xs text-[var(--cc-info)]"
        aria-label="Skipped"
      >
        <MinusCircle aria-hidden="true" className="h-3.5 w-3.5" />
        Skipped
      </Badge>
    );
  }

  return (
    <Badge variant="secondary" className="text-xs" aria-label="Pending">
      <Circle aria-hidden="true" className="h-3.5 w-3.5" />
    </Badge>
  );
}

function OverallBadge({
  overall,
}: {
  overall?: "Success" | "Failed" | "WARNING" | "Skipped (firmware)";
}) {
  if (overall === "Success") {
    return (
      <Badge
        variant="secondary"
        className="border-[color-mix(in_oklch,var(--cc-success)_30%,var(--cc-line))] bg-[var(--cc-success-soft)] text-xs text-[var(--cc-success)]"
        aria-label="Overall: Success"
      >
        Onboarded
      </Badge>
    );
  }
  if (overall === "Failed") {
    return (
      <Badge variant="destructive" className="text-xs" aria-label="Overall: Failed">
        Failed
      </Badge>
    );
  }
  if (overall === "WARNING") {
    return (
      <Badge
        variant="secondary"
        className="border-[color-mix(in_oklch,var(--cc-warning)_35%,var(--cc-line))] bg-[var(--cc-warning-soft)] text-xs text-[var(--cc-warning)]"
        aria-label="Overall: Warning"
      >
        Warning
      </Badge>
    );
  }
  if (overall === "Skipped (firmware)") {
    return (
      <Badge
        variant="secondary"
        className="border-[color-mix(in_oklch,var(--cc-info)_30%,var(--cc-line))] bg-[var(--cc-info-soft)] text-xs text-[var(--cc-info)]"
        aria-label="Overall: Skipped"
      >
        Skipped (firmware)
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className="text-xs" aria-label="Overall: Pending">
      Pending
    </Badge>
  );
}

export function DeviceRunTable({ devices }: DeviceRunTableProps) {
  const serials = Object.keys(devices);

  if (serials.length === 0) {
    return (
      <div className="bg-[var(--cc-muted)] px-4 py-8 text-center text-xs text-[var(--cc-ink-soft)]">
        Waiting for device events…
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[76rem] border-collapse text-xs">
        <thead>
          <tr className="border-b border-[var(--cc-line-strong)] bg-[var(--cc-surface)] text-[0.6875rem] uppercase tracking-[0.14em] text-[var(--cc-ink-soft)]">
            <td colSpan={3} aria-hidden="true" />
            <th
              scope="colgroup"
              colSpan={2}
              className="border-x border-[var(--cc-line)] px-3 py-2 text-center font-bold"
            >
              GLP
            </th>
            <th
              scope="colgroup"
              colSpan={6}
              className="border-r border-[var(--cc-line)] px-3 py-2 text-center font-bold"
            >
              Central
            </th>
            <td aria-hidden="true" />
          </tr>
          <tr className="border-b border-[var(--cc-line)] bg-[var(--cc-muted)] text-[0.625rem] uppercase tracking-[0.08em] text-[var(--cc-ink-faint)]">
            <th scope="col" className="px-3 py-3 text-left font-bold">
              Serial
            </th>
            <th scope="col" className="px-3 py-3 text-left font-bold">
              Model
            </th>
            <th scope="col" className="px-3 py-3 text-left font-bold">
              Subscription
            </th>
            <th scope="col" className="px-3 py-3 text-center font-bold">
              Application Assignment
            </th>
            <th scope="col" className="px-3 py-3 text-center font-bold">
              Subscription Assignment
            </th>
            <th scope="col" className="px-3 py-3 text-center font-bold">
              Min Firmware Check
            </th>
            <th scope="col" className="px-3 py-3 text-center font-bold">
              Site Association
            </th>
            <th scope="col" className="px-3 py-3 text-center font-bold">
              Persona
            </th>
            <th scope="col" className="px-3 py-3 text-center font-bold">
              Group Assignment
            </th>
            <th scope="col" className="px-3 py-3 text-center font-bold">
              Provisioning
            </th>
            <th scope="col" className="px-3 py-3 text-center font-bold">
              Hostname
            </th>
            <th scope="col" className="px-3 py-3 text-center font-bold">
              Overall
            </th>
          </tr>
        </thead>
        <tbody>
          {serials.map((serial) => {
            const d = devices[serial];
            const terminal = Boolean(d.overall);
            return (
              <tr
                key={serial}
                className={cn(
                  "border-b border-[var(--cc-line)] bg-[var(--cc-raised)] transition-colors hover:bg-[var(--cc-muted)]",
                  d.overall === "WARNING" &&
                    "bg-[color-mix(in_oklch,var(--cc-warning-soft)_30%,var(--cc-raised))]",
                  d.overall === "Failed" &&
                    "bg-[color-mix(in_oklch,var(--cc-danger-soft)_30%,var(--cc-raised))]",
                  d.overall === "Skipped (firmware)" &&
                    "bg-[color-mix(in_oklch,var(--cc-info-soft)_30%,var(--cc-raised))]"
                )}
              >
                <td className="px-3 py-3 font-mono font-semibold">{serial}</td>
                <td className="px-3 py-3 text-[var(--cc-ink-soft)]">
                  {d.model || "Unknown"}
                </td>
                <td className="max-w-44 truncate px-3 py-3 font-mono text-[0.6875rem] text-[var(--cc-ink-soft)]">
                  {d.subscriptionKey || "None"}
                </td>
                <td className="px-3 py-3 text-center">
                  <StepBadge
                    state={d.steps["glp_application"]}
                    terminal={terminal}
                  />
                </td>
                <td className="px-3 py-3 text-center">
                  <StepBadge
                    state={d.steps["glp_subscription"]}
                    terminal={terminal}
                  />
                </td>
                <td className="px-3 py-3 text-center">
                  <FirmwareGateCell firmware={d.firmware} />
                </td>
                <td className="px-3 py-3 text-center">
                  <StepBadge state={d.steps["site_assoc"]} terminal={terminal} />
                </td>
                <td className="px-3 py-3 text-center">
                  <StepBadge state={d.steps["device_function"]} terminal={terminal} />
                </td>
                <td className="px-3 py-3 text-center">
                  <StepBadge state={d.steps["group_assign"]} terminal={terminal} />
                </td>
                <td className="px-3 py-3 text-center">
                  <StepBadge state={d.steps["provision"]} terminal={terminal} />
                </td>
                <td className="px-3 py-3 text-center">
                  <StepBadge state={d.steps["hostname"]} terminal={terminal} />
                </td>
                <td className="px-3 py-3 text-center">
                  <OverallBadge overall={d.overall} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
