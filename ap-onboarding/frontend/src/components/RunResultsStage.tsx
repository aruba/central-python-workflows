import { useEffect, useState } from "react";
import {
  AlertCircle,
  Check,
  ChevronDown,
  Circle,
  FileText,
  Loader2,
  ScrollText,
  Table2,
  TriangleAlert,
  WifiOff,
} from "lucide-react";

import { DeviceRunTable } from "@/components/DeviceRunTable";
import { CredentialsModal } from "@/components/CredentialsModal";
import { LogStream } from "@/components/LogStream";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type {
  ConnectionState,
  DeviceState,
  RawEvent,
} from "@/lib/events";
import { getStatus } from "@/lib/api";
import { downloadNdjson } from "@/lib/ndjson";
import {
  buildHtmlReport,
  buildResultsCsv,
  downloadText,
  resultsExportBaseName,
} from "@/lib/results-export";
import { cn } from "@/lib/utils";

export interface RunDevicePlan {
  serial: string;
  model?: string;
  subscriptionKey?: string;
}

export interface RunSummary {
  onboarded: number;
  warnings: number;
  failed: number;
  skipped: number;
}

/**
 * Stable results seam for the export work in ticket #25. Everything needed
 * for client-side report, CSV, and log generation is kept together here.
 */
export interface RunResultsData {
  runId: string;
  plan: RunDevicePlan[];
  devices: Record<string, DeviceState>;
  events: RawEvent[];
  connectionState: ConnectionState;
  active: boolean;
  startedAt?: number;
  finishedAt?: number;
  resultsDir?: string;
  summary: RunSummary;
}

interface RunResultsStageProps {
  data: RunResultsData | null;
  starting: boolean;
  startError: string | null;
  onPrepareAnotherRun: () => void;
}

type PhaseStatus = "pending" | "active" | "complete" | "failed";

function phaseIcon(status: PhaseStatus) {
  if (status === "active") {
    return <Loader2 aria-label="In progress" className="h-4 w-4 motion-safe:animate-spin" />;
  }
  if (status === "complete") {
    return <Check aria-label="Complete" className="h-4 w-4" />;
  }
  if (status === "failed") {
    return <AlertCircle aria-label="Failed" className="h-4 w-4" />;
  }
  return <Circle aria-label="Pending" className="h-4 w-4" />;
}

function phaseStatusClass(status: PhaseStatus) {
  if (status === "complete") {
    return "border-[color-mix(in_oklch,var(--cc-success)_28%,var(--cc-line))] bg-[var(--cc-success-soft)] text-[var(--cc-success)]";
  }
  if (status === "failed") {
    return "border-[color-mix(in_oklch,var(--cc-danger)_35%,var(--cc-line))] bg-[var(--cc-danger-soft)] text-[var(--cc-danger)]";
  }
  if (status === "active") {
    return "border-[color-mix(in_oklch,var(--cc-accent)_30%,var(--cc-line))] bg-[var(--cc-accent-soft)] text-[var(--cc-accent)]";
  }
  return "border-[var(--cc-line)] bg-[var(--cc-muted)] text-[var(--cc-ink-faint)]";
}

function isFailedEvent(event: RawEvent) {
  return (
    event.type === "error" ||
    event.status === "Failed" ||
    event.status === "failed"
  );
}

function isNetworkVerificationEvent(event: RawEvent) {
  const type = event.type;
  const phase = event.phase;
  const step = event.step;
  return (
    type === "network_setup" ||
    type === "network_verification" ||
    type === "site" ||
    type === "group" ||
    type === "group_done" ||
    phase === "network_setup_verification" ||
    phase === "network_verification" ||
    step === "preflight"
  );
}

// A WARNING device did onboard: the core pipeline succeeded and an add-on step
// did not. Counting it outside "onboarded" made "0 onboarded, 1 warnings" read
// as though nothing landed, so every clause names what happened to the device.
function summarySentence(summary: RunSummary): string {
  const devices = (count: number) =>
    `${count} device${count === 1 ? "" : "s"}`;
  return [
    `${devices(summary.onboarded)} onboarded`,
    `${devices(summary.warnings)} onboarded with warnings`,
    `${devices(summary.failed)} failed`,
    `${devices(summary.skipped)} skipped for firmware`,
  ].join(", ");
}

export function RunResultsStage({
  data,
  starting,
  startError,
  onPrepareAnotherRun,
}: RunResultsStageProps) {
  const [logOpen, setLogOpen] = useState(false);
  const [credentialsOpen, setCredentialsOpen] = useState(false);

  useEffect(() => {
    if (data?.active) setLogOpen(true);
  }, [data?.active, data?.runId]);

  if (!data) {
    return (
      <section aria-labelledby="run-results-title" className="grid gap-4">
        <div>
          <h2 id="run-results-title" className="text-lg font-bold tracking-tight">
            Run onboarding
          </h2>
          <p className="mt-1 max-w-[68ch] text-sm leading-6 text-[var(--cc-ink-soft)]">
            Review the complete plan from the top action. Live firmware,
            device progress, and logs appear here after the service accepts the
            run.
          </p>
        </div>

        {startError && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-xl border border-[color-mix(in_oklch,var(--cc-danger)_35%,var(--cc-line))] bg-[var(--cc-danger-soft)] px-4 py-3 text-sm text-[var(--cc-danger)]"
          >
            <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{startError}</span>
          </div>
        )}

        <div className="flex min-h-32 items-center justify-center rounded-xl border border-dashed border-[var(--cc-line-strong)] bg-[var(--cc-muted)] px-5 text-center">
          <div>
            {starting ? (
              <Loader2
                aria-hidden="true"
                className="mx-auto h-5 w-5 motion-safe:animate-spin text-[var(--cc-accent)]"
              />
            ) : (
              <Circle
                aria-hidden="true"
                className="mx-auto h-5 w-5 text-[var(--cc-ink-faint)]"
              />
            )}
            <p className="mt-2 text-sm font-semibold">
              {starting ? "Starting onboarding…" : "Ready for review"}
            </p>
            <p className="mt-1 text-xs text-[var(--cc-ink-soft)]">
              No firmware value is assumed before execution.
            </p>
          </div>
        </div>
      </section>
    );
  }

  const { devices, events, summary } = data;
  const classicAuthFailed =
    !data.active &&
    Object.values(devices).some((device) =>
      [device.firmware, ...Object.values(device.steps)].some(
        (step) =>
          step.status === "failed" &&
          Boolean(step.error && /401|invalid_token|expired/i.test(step.error))
      )
    );
  const terminalCount =
    summary.onboarded + summary.warnings + summary.failed + summary.skipped;
  const totalCount = data.plan.length;
  const progress = totalCount > 0 ? (terminalCount / totalCount) * 100 : 0;
  const networkEvents = events.filter(isNetworkVerificationEvent);
  const networkFailed = networkEvents.some(isFailedEvent);
  const runErrors = events.filter((event) => event.type === "error");
  const runHasGlobalError = runErrors.length > 0;

  const phases: Array<{
    label: string;
    detail: string;
    status: PhaseStatus;
  }> = [
    {
      label: "Network verification",
      detail:
        networkEvents.length > 0
          ? `${networkEvents.length} verification event${networkEvents.length === 1 ? "" : "s"}`
          : "Site and device group preflight passed",
      status: networkFailed ? "failed" : "complete",
    },
    {
      label: "Device onboarding",
      detail: `${terminalCount} of ${totalCount} terminal`,
      status:
        !data.active && runErrors.length > 0
          ? "failed"
          : data.active
            ? "active"
            : "complete",
    },
  ];

  return (
    // [&>*]:min-w-0 keeps the 76rem device table inside the stage frame; grid
    // items are min-width:auto by default and would otherwise spill and clip.
    <section
      aria-labelledby="run-results-title"
      className="grid gap-5 [&>*]:min-w-0"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id="run-results-title"
            className="text-lg font-bold tracking-tight"
          >
            {data.active
              ? "Onboarding in progress"
              : runHasGlobalError
                ? "Run finished with error"
                : summary.failed > 0
                  ? "Run finished with failures"
                  : summary.warnings > 0 || summary.skipped > 0
                    ? "Run complete with warnings"
                    : "Run complete"}
          </h2>
          <p className="mt-1 text-xs text-[var(--cc-ink-soft)]">
            Run <span className="font-mono">{data.runId}</span>
          </p>
        </div>
        <div className="text-right text-xs text-[var(--cc-ink-soft)]">
          <strong className="block text-sm tabular-nums text-[var(--cc-ink)]">
            {terminalCount} / {totalCount}
          </strong>
          terminal devices
        </div>
      </div>

      {classicAuthFailed && (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-lg border border-[color-mix(in_oklch,var(--cc-warning)_35%,var(--cc-line))] bg-[var(--cc-warning-soft)] px-3.5 py-3 text-xs text-[var(--cc-warning)] sm:flex-row sm:items-center sm:justify-between"
        >
          <span className="flex min-w-0 items-start gap-2">
            <TriangleAlert
              aria-hidden="true"
              className="mt-0.5 h-4 w-4 shrink-0"
            />
            <span className="min-w-0">
              <span className="block font-semibold">
                Warning: Classic Central token expired or invalid
              </span>
              <span className="mt-1 block leading-5">
                Update the token, then inspect the preserved device plan before
                another run.
              </span>
            </span>
          </span>
          <Button
            type="button"
            size="sm"
            onClick={() => setCredentialsOpen(true)}
            className="shrink-0 bg-[var(--cc-accent)] text-[var(--cc-accent-ink)] hover:bg-[var(--cc-accent-hover)]"
          >
            Update token
          </Button>
        </div>
      )}

      {data.connectionState === "disconnected" && data.active && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-2 rounded-xl border border-[color-mix(in_oklch,var(--cc-warning)_35%,var(--cc-line))] bg-[var(--cc-warning-soft)] px-4 py-3 text-xs text-[var(--cc-warning)]"
        >
          <WifiOff aria-hidden="true" className="h-4 w-4 shrink-0" />
          No live updates for several seconds. Reconnecting to the event stream.
        </div>
      )}

      {runErrors.map((event, index) => (
        <div
          key={`${String(event.message)}-${index}`}
          role="alert"
          className="flex items-start gap-2 rounded-xl border border-[color-mix(in_oklch,var(--cc-danger)_35%,var(--cc-line))] bg-[var(--cc-danger-soft)] px-4 py-3 text-sm text-[var(--cc-danger)]"
        >
          <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{String(event.message ?? "The run reported an error.")}</span>
        </div>
      ))}

      <div>
        <div className="mb-2 flex items-center justify-between gap-3 text-xs">
          <span className="font-semibold">Batch progress</span>
          <span className="tabular-nums text-[var(--cc-ink-soft)]">
            {Math.round(progress)}%
          </span>
        </div>
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={totalCount}
          aria-valuenow={terminalCount}
          aria-label="Terminal devices"
          className="h-2 overflow-hidden rounded-full bg-[var(--cc-muted)]"
        >
          <div
            className="h-full rounded-full bg-[var(--cc-accent)] transition-transform duration-200"
            style={{
              transform: `translateX(-${100 - progress}%)`,
              transformOrigin: "left",
            }}
          />
        </div>
      </div>

      <ol className="grid overflow-hidden rounded-xl border border-[var(--cc-line)] md:grid-cols-2">
        {phases.map((phase, index) => (
          <li
            key={phase.label}
            className={cn(
              "flex items-center gap-3 bg-[var(--cc-muted)] px-4 py-3",
              index > 0 &&
                "border-t border-[var(--cc-line)] md:border-l md:border-t-0"
            )}
          >
            <span
              className={cn(
                "grid h-8 w-8 shrink-0 place-items-center rounded-full border",
                phaseStatusClass(phase.status)
              )}
            >
              {phaseIcon(phase.status)}
            </span>
            <span className="min-w-0">
              <strong className="block text-xs">{phase.label}</strong>
              <span className="block truncate text-[0.6875rem] text-[var(--cc-ink-soft)]">
                {phase.detail}
              </span>
            </span>
          </li>
        ))}
      </ol>

      {!data.active && (
        <p role="status" className="text-sm text-[var(--cc-ink-soft)]">
          The run finished: {summarySentence(summary)}.
        </p>
      )}

      <div className="overflow-hidden rounded-xl border border-[var(--cc-line)]">
        <DeviceRunTable devices={devices} />
      </div>

      {!data.active && (
        <div
          aria-label="Export results"
          className="flex flex-wrap items-center justify-between gap-3 border-y border-[var(--cc-line)] py-4"
        >
          <div>
            <p className="text-sm font-semibold">Export results</p>
            <p className="mt-0.5 text-xs text-[var(--cc-ink-soft)]">
              Download a portable report, device data, or the raw event log.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                const baseName = resultsExportBaseName(data);
                downloadText(
                  buildHtmlReport(data),
                  `${baseName}_report.html`,
                  "text/html;charset=utf-8"
                );
              }}
            >
              <FileText aria-hidden="true" />
              HTML report
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                const baseName = resultsExportBaseName(data);
                downloadText(
                  buildResultsCsv(data),
                  `${baseName}_devices.csv`,
                  "text/csv;charset=utf-8"
                );
              }}
            >
              <Table2 aria-hidden="true" />
              Results CSV
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() =>
                downloadNdjson(
                  data.events,
                  `${resultsExportBaseName(data)}_run-log.ndjson`
                )
              }
            >
              <ScrollText aria-hidden="true" />
              Run log
            </Button>
          </div>
        </div>
      )}

      <Collapsible open={logOpen} onOpenChange={setLogOpen}>
        <div className="overflow-hidden rounded-xl border border-[var(--cc-line)] bg-[var(--cc-raised)]">
          <CollapsibleTrigger className="flex min-h-12 w-full items-center justify-between gap-4 px-4 py-3 text-left transition-colors hover:bg-[var(--cc-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--cc-accent)]">
            <span className="flex items-center gap-2">
              <ScrollText
                aria-hidden="true"
                className="h-4 w-4 text-[var(--cc-accent)]"
              />
              <span className="text-sm font-semibold">Live run log</span>
              <span className="text-xs tabular-nums text-[var(--cc-ink-soft)]">
                {events.length} events
              </span>
            </span>
            <ChevronDown
              aria-hidden="true"
              className={cn(
                "h-4 w-4 text-[var(--cc-ink-faint)] transition-transform duration-200",
                logOpen && "rotate-180"
              )}
            />
          </CollapsibleTrigger>
          <CollapsibleContent className="border-t border-[var(--cc-line)] p-3 sm:p-4">
            <LogStream
              events={events}
              maxHeight="288px"
              title={null}
            />
          </CollapsibleContent>
        </div>
      </Collapsible>
      <CredentialsModal
        open={credentialsOpen}
        initialSection="classic"
        onOpenChange={(nextOpen) => {
          setCredentialsOpen(nextOpen);
          // Dismissing without replacing the token must not discard the run:
          // this surface is the only place a finished run stays readable, and
          // nothing reloads a past run into it. Hand control back only once
          // Classic actually verifies.
          if (!nextOpen) {
            void getStatus()
              .then((status) => {
                if (status.classic_creds_valid) onPrepareAnotherRun();
              })
              .catch(() => undefined);
          }
        }}
      />
    </section>
  );
}
