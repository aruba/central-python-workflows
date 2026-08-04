import { useEffect, useState } from "react";
import {
  AlertCircle,
  ChevronDown,
  Download,
  Loader2,
  ScrollText,
  WifiOff,
} from "lucide-react";
import { StepBadge } from "@/components/DeviceRunTable";
import { LogStream } from "@/components/LogStream";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { downloadNdjson } from "@/lib/ndjson";
import { useRunEvents, type EntityStepState } from "@/lib/events";
import { cn } from "@/lib/utils";

interface NetworkSetupLiveViewProps {
  runId: string;
}

type EntityMap = Record<string, Record<string, EntityStepState>>;

interface EntityTableProps {
  entities: EntityMap;
  headingId: string;
  title: string;
}

function formatStepName(step: string): string {
  return step.replace(/_/g, " ");
}

function EntityTable({ entities, headingId, title }: EntityTableProps) {
  const entityNames = Object.keys(entities);
  const stepNames = Array.from(
    new Set(
      Object.values(entities).flatMap((steps) =>
        Object.keys(steps).filter((step) => step !== "__overall")
      )
    )
  );

  return (
    <section className="grid gap-2">
      <div className="flex items-baseline justify-between gap-3">
        <h3 id={headingId} className="text-sm font-bold">
          {title}
        </h3>
        <span className="text-xs tabular-nums text-[var(--cc-ink-soft)]">
          {entityNames.length} {entityNames.length === 1 ? "entity" : "entities"}
        </span>
      </div>
      <div className="overflow-hidden rounded-xl border border-[var(--cc-line)]">
        {entityNames.length === 0 ? (
          <div className="bg-[var(--cc-muted)] px-4 py-8 text-center text-xs text-[var(--cc-ink-soft)]">
            No entries yet
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table
              aria-labelledby={headingId}
              className="w-full min-w-[32rem] border-collapse text-xs"
            >
              <thead>
                <tr className="border-b border-[var(--cc-line)] bg-[var(--cc-muted)] text-[0.625rem] uppercase tracking-[0.08em] text-[var(--cc-ink-faint)]">
                  <th scope="col" className="px-3 py-3 text-left font-bold">
                    Name
                  </th>
                  {stepNames.map((step) => (
                    <th
                      key={step}
                      scope="col"
                      className="whitespace-nowrap px-3 py-3 text-center font-bold"
                    >
                      {formatStepName(step)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {entityNames.map((name) => (
                  <tr
                    key={name}
                    className="border-b border-[var(--cc-line)] bg-[var(--cc-raised)] transition-colors hover:bg-[var(--cc-muted)]"
                  >
                    <td className="px-3 py-3 font-mono font-semibold">{name}</td>
                    {stepNames.map((step) => (
                      <td key={step} className="px-3 py-3 text-center">
                        <StepBadge state={entities[name]?.[step]} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}

function realSteps(steps: Record<string, EntityStepState>): EntityStepState[] {
  return Object.entries(steps)
    .filter(([name]) => name !== "__overall")
    .map(([, state]) => state);
}

function isEntityDone(steps: Record<string, EntityStepState>): boolean {
  const states = realSteps(steps);
  return (
    states.length > 0 &&
    states.every((state) => state.status === "success" || state.status === "failed")
  );
}

function countDone(entities: EntityMap): number {
  return Object.values(entities).filter(isEntityDone).length;
}

function countSuccess(entities: EntityMap): number {
  return Object.values(entities).filter((steps) => {
    const states = realSteps(steps);
    return states.length > 0 && states.every((state) => state.status === "success");
  }).length;
}

function countFailed(entities: EntityMap): number {
  return Object.values(entities).filter((steps) =>
    realSteps(steps).some((state) => state.status === "failed")
  ).length;
}

export function NetworkSetupLiveView({ runId }: NetworkSetupLiveViewProps) {
  const { network, connectionState } = useRunEvents(runId);
  const [logOpen, setLogOpen] = useState(false);

  // The log was unconditionally visible before this surface became collapsible.
  // Collapsed-by-default during a live run would hide the only detail view a
  // running setup has, so open it the way RunResultsStage does.
  useEffect(() => {
    if (network?.active) setLogOpen(true);
  }, [network?.active, network?.runId]);

  const sites = network?.sites ?? {};
  const groups = network?.groups ?? {};
  const events = network?.logEvents ?? [];
  const totalCount = Object.keys(sites).length + Object.keys(groups).length;
  const doneCount = countDone(sites) + countDone(groups);
  const successCount = countSuccess(sites) + countSuccess(groups);
  const failedCount = countFailed(sites) + countFailed(groups);
  const runErrors = events.filter((event) => event.type === "error");
  const hasFailures = failedCount > 0 || runErrors.length > 0;
  const hasEvents = events.length > 0;
  const progress = totalCount > 0 ? (doneCount / totalCount) * 100 : 0;
  const active = network?.active ?? true;

  return (
    // [&>*]:min-w-0 keeps the entity tables inside the stage frame; grid items
    // are min-width:auto by default and would otherwise spill and clip.
    <section
      aria-labelledby="network-setup-results-title"
      className="grid gap-5 [&>*]:min-w-0"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id="network-setup-results-title"
            className="text-lg font-bold tracking-tight"
          >
            {active
              ? "Network setup in progress"
              : hasFailures
                ? "Network setup complete with failures"
                : "Network setup complete"}
          </h2>
          <p className="mt-1 text-xs text-[var(--cc-ink-soft)]">
            Run <span className="font-mono">{network?.runId ?? runId}</span>
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => downloadNdjson(events, "network-setup-events.ndjson")}
        >
          <Download aria-hidden="true" />
          Download log
        </Button>
      </div>

      {connectionState === "disconnected" && active && (
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
          aria-valuenow={doneCount}
          aria-label="Completed network setup entities"
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

      {!hasEvents ? (
        <div
          role="status"
          className="flex flex-col items-center justify-center py-10 text-sm text-[var(--cc-ink-soft)]"
        >
          <Loader2
            aria-hidden="true"
            className="mb-2 h-6 w-6 motion-safe:animate-spin"
          />
          <span>Waiting for events…</span>
          <span className="sr-only">Loading…</span>
        </div>
      ) : (
        <div className="grid gap-5">
          <EntityTable
            title="Sites"
            headingId="network-setup-sites-title"
            entities={sites}
          />
          <EntityTable
            title="Device Groups"
            headingId="network-setup-groups-title"
            entities={groups}
          />
        </div>
      )}

      {!active && (
        <p role="status" className="text-sm text-[var(--cc-ink-soft)]">
          The run finished: {doneCount} of {totalCount} entities complete, {successCount}{" "}
          succeeded and {failedCount} failed.
        </p>
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
            <LogStream events={events} maxHeight="288px" title={null} />
          </CollapsibleContent>
        </div>
      </Collapsible>
    </section>
  );
}
