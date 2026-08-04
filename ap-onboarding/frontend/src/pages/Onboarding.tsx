import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ArrowRight,
  Check,
  ChevronDown,
  Circle,
  Loader2,
  Play,
  Server,
  X,
} from "lucide-react";
import {
  ConfigureStage,
  type ConfigureStageValue,
} from "@/components/ConfigureStage";
import { AddOnStepsSection } from "@/components/AddOnStepsSection";
import { CredentialsModal } from "@/components/CredentialsModal";
import {
  DevicesStage,
  type DevicesStageDevice,
} from "@/components/DevicesStage";
import {
  RunResultsStage,
  type RunDevicePlan,
  type RunResultsData,
  type RunSummary,
} from "@/components/RunResultsStage";
import { TopBar } from "@/components/TopBar";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  getLimits,
  getSteps,
  runOnboardingPreflight,
  startRun as startOnboardingRun,
  type ApplicationLookup,
  type PreflightResponse,
  type StepMeta,
} from "@/lib/api";
import { useRunEvents, type DeviceState } from "@/lib/events";
import { cn } from "@/lib/utils";

type StageNumber = 1 | 2 | 3;
type RunState = "idle" | "starting" | "running" | "complete";
type PreflightState = "idle" | "checking" | "passed" | "failed" | "error";

interface PreflightViewState {
  state: PreflightState;
  response: PreflightResponse | null;
  error: string | null;
}

const EMPTY_CONFIGURATION: ConfigureStageValue = {
  site: "",
  deviceGroup: "",
  batchSubscriptionKey: "",
  applicationAssignment: null,
  deviceFunction: "",
};

const STAGES: Array<{
  number: StageNumber;
  title: string;
}> = [
  {
    number: 1,
    title: "Configure",
  },
  {
    number: 2,
    title: "Devices",
  },
  {
    number: 3,
    title: "Run & results",
  },
];

function buildRunVariables(
  configuration: ConfigureStageValue,
  devices: DevicesStageDevice[]
): Record<string, unknown> {
  const defaults: Record<string, unknown> = {
    device_type: "ACCESS_POINT",
    // Served by /api/lookups; "Campus Access Point" is the lone persona today.
    device_function: configuration.deviceFunction || "Campus Access Point",
    site: configuration.site,
    device_group: configuration.deviceGroup,
  };
  if (configuration.batchSubscriptionKey) {
    defaults.subscription_key = configuration.batchSubscriptionKey;
  }
  if (configuration.applicationAssignment) {
    defaults.application_assignment = configuration.applicationAssignment;
  }

  return {
    defaults,
    devices: devices.map((device) => ({
      serial_number: device.serial_number,
      ...(device.subscription_key &&
      device.subscription_key !== configuration.batchSubscriptionKey
        ? { subscription_key: device.subscription_key }
        : {}),
      ...device.addOnValues,
    })),
  };
}

function formatAddOnValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") return value ? "True" : "False";
  return value === undefined ? "Not set" : String(value);
}

function makeRunPlan(devices: DevicesStageDevice[]): RunDevicePlan[] {
  return devices.map((device) => ({
    serial: device.serial_number,
    ...(device.model ? { model: device.model } : {}),
    ...(device.subscription_key
      ? { subscriptionKey: device.subscription_key }
      : {}),
  }));
}

function makeSummary(devices: Record<string, DeviceState>): RunSummary {
  const summary: RunSummary = {
    onboarded: 0,
    warnings: 0,
    failed: 0,
    skipped: 0,
  };

  for (const device of Object.values(devices)) {
    if (device.overall === "Success") summary.onboarded += 1;
    if (device.overall === "WARNING") summary.warnings += 1;
    if (device.overall === "Failed") summary.failed += 1;
    if (device.overall === "Skipped (firmware)") summary.skipped += 1;
  }
  return summary;
}


function PreflightDisclosure({
  preflight,
  locallyReady,
  onFixClassicCredential,
}: {
  preflight: PreflightViewState;
  locallyReady: boolean;
  onFixClassicCredential: () => void;
}) {
  const passes = preflight.state === "passed";
  const needsAttention =
    preflight.state === "failed" || preflight.state === "error";
  const [expanded, setExpanded] = useState(needsAttention);

  useEffect(() => {
    if (needsAttention) setExpanded(true);
    if (passes) setExpanded(false);
  }, [needsAttention, passes]);

  const label =
    preflight.state === "checking"
      ? "Checking Central prerequisites…"
      : passes
        ? "All preflight checks pass ✓"
        : needsAttention
          ? "Preflight checks need attention"
          : locallyReady
            ? "Preflight is waiting to run"
            : "Complete configuration and select devices";

  return (
    <div
      className={cn(
        "rounded-xl border",
        passes
          ? "border-[color-mix(in_oklch,var(--cc-success)_28%,var(--cc-line))] bg-[var(--cc-success-soft)]"
          : needsAttention
            ? "border-[color-mix(in_oklch,var(--cc-danger)_35%,var(--cc-line))] bg-[var(--cc-danger-soft)]"
            : "border-[var(--cc-line)] bg-[var(--cc-muted)]"
      )}
    >
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls="preflight-details"
        onClick={() => setExpanded((current) => !current)}
        className="flex min-h-11 w-full items-center justify-between gap-4 px-4 py-2.5 text-left text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--cc-accent)]"
      >
        <span
          className={cn(
            passes && "text-[var(--cc-success)]",
            needsAttention && "text-[var(--cc-danger)]",
            !passes && !needsAttention && "text-[var(--cc-ink-soft)]"
          )}
        >
          {label}
        </span>
        {preflight.state === "checking" ? (
          <Loader2
            aria-hidden="true"
            className="h-4 w-4 shrink-0 motion-safe:animate-spin"
          />
        ) : (
          <ChevronDown
            aria-hidden="true"
            className={cn(
              "h-4 w-4 shrink-0 transition-transform duration-200",
              expanded && "rotate-180"
            )}
          />
        )}
      </button>
      {expanded && (
        <div
          id="preflight-details"
          className="grid gap-2 border-t border-[var(--cc-line)] px-4 py-3 text-xs text-[var(--cc-ink-soft)]"
        >
          {preflight.error ? (
            <span className="text-[var(--cc-danger)]">{preflight.error}</span>
          ) : !preflight.response ? (
            <span>
              {preflight.state === "checking"
                ? "Verifying the selected site and device group in Central."
                : "Central checks run after configuration and device selection are complete."}
            </span>
          ) : (
            <>
              {Object.entries(
                preflight.response?.credential_errors ?? {}
              ).map(([credential, message]) => (
                // Without this the credential verdict is invisible: a dead
                // token fails pre-flight with both missing lists empty, so
                // every line below reads as a pass.
                <span
                  key={credential}
                  className="flex flex-wrap items-start justify-between gap-2 text-[var(--cc-warning)]"
                >
                  <span className="min-w-0 flex-1 leading-5">
                    {credential === "classic"
                      ? "Classic Central credential: "
                      : "GreenLake credential: "}
                    {message}
                  </span>
                  {credential === "classic" && (
                    <Button
                      type="button"
                      size="sm"
                      onClick={onFixClassicCredential}
                      className="h-7 shrink-0 bg-[var(--cc-accent)] px-2 text-xs text-[var(--cc-accent-ink)] hover:bg-[var(--cc-accent-hover)]"
                    >
                      Update token
                    </Button>
                  )}
                </span>
              ))}
              <span>
                Site:{" "}
                {preflight.response?.missing_sites.length
                  ? `missing (${preflight.response.missing_sites.join(", ")})`
                  : "exists ✓"}
              </span>
              <span>
                Device group:{" "}
                {preflight.response?.missing_device_groups.length
                  ? `missing (${preflight.response.missing_device_groups.join(", ")})`
                  : "exists ✓"}
              </span>
              <span>
                Device plan: {locallyReady ? "complete ✓" : "incomplete"}
              </span>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ReviewRunDialog({
  open,
  onOpenChange,
  onConfirm,
  configuration,
  devices,
  enabledSteps,
  deviceLimit,
  starting,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  configuration: ConfigureStageValue;
  devices: DevicesStageDevice[];
  enabledSteps: StepMeta[];
  deviceLimit: number | null;
  starting: boolean;
}) {
  // The GLP application decides which workspace receives the batch, so the
  // commitment gate has to state it alongside the rest of the plan.
  const summary = [
    ["Devices", `${devices.length} access points`],
    [
      "GLP application",
      configuration.applicationAssignment
        ? `${configuration.applicationAssignment.name} · ${configuration.applicationAssignment.region}`
        : "Not selected",
    ],
    ["Site", `${configuration.site} ✓`],
    ["Device group", `${configuration.deviceGroup} ✓`],
    ["Subscription", configuration.batchSubscriptionKey],
  ];

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-h-[calc(100vh-1rem)] w-[calc(100%-1rem)] max-w-5xl gap-0 overflow-hidden rounded-2xl border-[var(--cc-line-strong)] bg-[var(--cc-raised)] p-0 text-[var(--cc-ink)] shadow-[var(--cc-dialog-shadow)] sm:w-[calc(100%-2rem)]">
        <AlertDialogHeader className="relative space-y-1 border-b border-[var(--cc-line)] px-5 py-4 pr-16 text-left sm:px-6">
          <AlertDialogTitle className="text-xl tracking-tight">
            Review before run
          </AlertDialogTitle>
          <AlertDialogDescription className="max-w-3xl text-xs leading-5 text-[var(--cc-ink-soft)]">
            Confirm the complete execution plan.
          </AlertDialogDescription>
          <AlertDialogCancel
            aria-label="Close review"
            className="absolute right-4 top-3.5 mt-0 h-9 w-9 rounded-lg border-[var(--cc-line)] bg-transparent p-0 text-[var(--cc-ink-soft)] hover:bg-[var(--cc-muted)] hover:text-[var(--cc-ink)]"
          >
            <X aria-hidden="true" className="h-4 w-4" />
          </AlertDialogCancel>
        </AlertDialogHeader>

        <div className="overflow-y-auto px-5 py-5 sm:px-6">
          <section
            aria-label="Run summary"
            // Hairlines come from the gap showing the container's own colour,
            // so the band keeps its rules at any cell count or wrap point
            // rather than hand-tuned per-index border classes.
            // Five cells in a two-column grid leave a trailing empty track,
            // which the container colour would render as a solid block, so the
            // odd last cell spans the row instead.
            className="grid gap-px overflow-hidden rounded-xl border border-[var(--cc-line)] bg-[var(--cc-line)] sm:grid-cols-2 sm:[&>*:last-child]:col-span-2 lg:grid-cols-5 lg:[&>*:last-child]:col-span-1"
          >
            {summary.map(([label, value]) => (
              <div key={label} className="bg-[var(--cc-muted)] px-4 py-3">
                <p className="text-[0.625rem] font-bold uppercase tracking-[0.12em] text-[var(--cc-ink-faint)]">
                  {label}
                </p>
                <p className="mt-1 truncate text-sm font-semibold">{value}</p>
              </div>
            ))}
          </section>

          <section className="mt-4" aria-labelledby="execution-order-title">
            <h3
              id="execution-order-title"
              className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--cc-ink-faint)]"
            >
              Execution order
            </h3>
            <ol className="mt-2 grid overflow-hidden rounded-xl border border-[var(--cc-line)] bg-[var(--cc-muted)] md:grid-cols-2">
              {[
                "Verify site and device group",
                "Associate, provision, then add-ons",
              ].map((step, index) => (
                <li
                  key={step}
                  className={cn(
                    "flex items-center gap-3 px-4 py-3 text-xs font-medium",
                    index > 0 && "border-t border-[var(--cc-line)] md:border-l md:border-t-0"
                  )}
                >
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-[var(--cc-info-soft)] text-[0.6875rem] font-bold text-[var(--cc-info)]">
                    {index + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </section>

          <section className="mt-5" aria-labelledby="device-plan-title">
            <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
              <div>
                <h3 id="device-plan-title" className="text-sm font-semibold">
                  Full device plan
                </h3>
              </div>
              <span className="rounded-full border border-[var(--cc-line)] bg-[var(--cc-muted)] px-2.5 py-1 text-[0.6875rem] font-semibold text-[var(--cc-ink-soft)]">
                {devices.length} of {deviceLimit ?? "…"}
              </span>
            </div>
            <div className="overflow-x-auto rounded-xl border border-[var(--cc-line)]">
              <table className="w-full min-w-[42rem] border-collapse text-left text-xs">
                <thead className="bg-[var(--cc-muted)] text-[0.625rem] uppercase tracking-[0.1em] text-[var(--cc-ink-faint)]">
                  <tr>
                    <th className="px-4 py-3 font-bold">Serial number</th>
                    <th className="px-4 py-3 font-bold">Model</th>
                    <th className="px-4 py-3 font-bold">Site / group</th>
                    <th className="px-4 py-3 font-bold">Subscription</th>
                    {enabledSteps.map((step) => (
                      <th
                        key={step.key}
                        className="min-w-44 px-4 py-3 font-bold"
                      >
                        {step.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {devices.map((device) => (
                    <tr
                      key={device.serial_number}
                      className="border-t border-[var(--cc-line)] bg-[var(--cc-raised)]"
                    >
                      <td className="px-4 py-3 font-mono font-semibold">
                        {device.serial_number}
                      </td>
                      <td className="px-4 py-3">
                        {device.model || "Unknown"}
                      </td>
                      <td className="px-4 py-3">
                        {configuration.site} / {configuration.deviceGroup}
                      </td>
                      <td className="px-4 py-3 font-mono">
                        {device.subscription_key ||
                          configuration.batchSubscriptionKey}
                      </td>
                      {enabledSteps.map((step) => (
                        <td key={step.key} className="px-4 py-3">
                          {formatAddOnValue(device.addOnValues[step.key])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <div className="flex flex-col-reverse gap-3 border-t border-[var(--cc-line)] bg-[var(--cc-muted)] px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p className="text-xs text-[var(--cc-ink-soft)]">
            Cancel to make changes. Starting locks this plan for execution.
          </p>
          <div className="flex justify-end gap-2">
            <AlertDialogCancel className="mt-0 border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] hover:bg-[var(--cc-surface)]">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={onConfirm}
              disabled={starting}
              className="bg-[var(--cc-accent)] text-[var(--cc-accent-ink)] hover:bg-[var(--cc-accent-hover)]"
            >
              {starting ? (
                <Loader2 aria-hidden="true" className="h-4 w-4 motion-safe:animate-spin" />
              ) : (
                <Play aria-hidden="true" className="h-4 w-4" />
              )}
              {starting ? "Starting…" : "Confirm & start run"}
            </AlertDialogAction>
          </div>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function Onboarding() {
  const [activeStage, setActiveStage] = useState<StageNumber>(1);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [credentialsOpen, setCredentialsOpen] = useState(false);
  const [runState, setRunState] = useState<RunState>("idle");
  const [configuration, setConfiguration] =
    useState<ConfigureStageValue>(EMPTY_CONFIGURATION);
  const [importedApplication, setImportedApplication] =
    useState<ApplicationLookup | null>(null);
  const [devices, setDevices] = useState<DevicesStageDevice[]>([]);
  const [steps, setSteps] = useState<StepMeta[]>([]);
  const [enabledStepKeys, setEnabledStepKeys] = useState<Set<string>>(
    new Set()
  );
  const [stepsLoading, setStepsLoading] = useState(true);
  const [stepsError, setStepsError] = useState<string | null>(null);
  const [configureRevealNonce, setConfigureRevealNonce] = useState(0);
  const [devicesRevealNonce, setDevicesRevealNonce] = useState(0);
  const knownStepKeysRef = useRef<Set<string>>(new Set());
  const [deviceLimit, setDeviceLimit] = useState<number | null>(null);
  const [limitError, setLimitError] = useState<string | null>(null);
  const [preflight, setPreflight] = useState<PreflightViewState>({
    state: "idle",
    response: null,
    error: null,
  });
  const [preflightNonce, setPreflightNonce] = useState(0);
  const [runId, setRunId] = useState<string | null>(null);
  const [runPlan, setRunPlan] = useState<RunDevicePlan[]>([]);
  const [startError, setStartError] = useState<string | null>(null);
  const stageHeaderRefs = useRef<
    Partial<Record<StageNumber, HTMLButtonElement | null>>
  >({});
  const previousActiveStageRef = useRef(activeStage);

  useLayoutEffect(() => {
    const previousStage = previousActiveStageRef.current;
    if (previousStage !== activeStage) {
      const previousPanel = document.getElementById(
        `stage-panel-${previousStage}`
      );
      if (previousPanel?.contains(document.activeElement)) {
        stageHeaderRefs.current[previousStage]?.focus();
      }
      previousActiveStageRef.current = activeStage;
    }
  }, [activeStage]);

  const {
    onboarding,
    rawEvents,
    connectionState,
  } = useRunEvents(runId);

  const enabledSteps = useMemo(
    () => steps.filter((step) => enabledStepKeys.has(step.key)),
    [enabledStepKeys, steps]
  );
  const stepsReady = !stepsLoading && stepsError === null;
  const configurationValuesReady = Boolean(
    configuration.site &&
      configuration.deviceGroup &&
      configuration.batchSubscriptionKey &&
      configuration.applicationAssignment
  );
  const configureReady = configurationValuesReady && stepsReady;
  const devicesReady =
    deviceLimit !== null &&
    devices.length > 0 &&
    devices.length <= deviceLimit;
  const deviceAddOnsReady = devices.every(
    (device) =>
      device.addOnsValid && device.blankAddOnKeys.length === 0
  );
  const locallyReady = configureReady && devicesReady;
  const runVariables = useMemo(
    () => buildRunVariables(configuration, devices),
    [configuration, devices]
  );
  const runVariablesRef = useRef(runVariables);
  const hasDevices = devices.length > 0;
  const preflightPasses = preflight.state === "passed";
  const reviewReady =
    locallyReady && preflightPasses && runState === "idle";

  const loadSteps = useCallback(async () => {
    setStepsLoading(true);
    setStepsError(null);
    try {
      const response = await getSteps();
      const previousKeys = knownStepKeysRef.current;
      const responseKeys = new Set(response.map((step) => step.key));
      setEnabledStepKeys((current) => {
        const next = new Set(
          [...current].filter((key) => responseKeys.has(key))
        );
        for (const step of response) {
          if (!previousKeys.has(step.key) || step.field.required) {
            next.add(step.key);
          }
        }
        return next;
      });
      knownStepKeysRef.current = responseKeys;
      setSteps(response);
    } catch (error) {
      setStepsError(
        error instanceof Error ? error.message : "Unable to load add-on steps."
      );
    } finally {
      setStepsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSteps();
  }, [loadSteps]);

  useEffect(() => {
    let cancelled = false;
    getLimits()
      .then((response) => {
        if (cancelled) return;
        if (
          !Number.isInteger(response.max_devices) ||
          response.max_devices < 1
        ) {
          setLimitError("The service returned an invalid device limit.");
          return;
        }
        setDeviceLimit(response.max_devices);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setLimitError(
          error instanceof Error
            ? error.message
            : "Unable to load the service device limit."
        );
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    runVariablesRef.current = runVariables;
  }, [runVariables]);

  useEffect(() => {
    if (
      !configuration.site ||
      !configuration.deviceGroup ||
      !configuration.batchSubscriptionKey ||
      !configuration.applicationAssignment ||
      !hasDevices
    ) {
      setPreflight({
        state: "idle",
        response: null,
        error: null,
      });
      return;
    }
    if (runState !== "idle") return;

    let cancelled = false;
    setPreflight({
      state: "checking",
      response: null,
      error: null,
    });
    const timer = window.setTimeout(() => {
      void runOnboardingPreflight(runVariablesRef.current)
        .then((response) => {
          if (cancelled) return;
          setPreflight({
            state: response.ok ? "passed" : "failed",
            response,
            error: null,
          });
        })
        .catch((error: unknown) => {
          if (cancelled) return;
          setPreflight({
            state: "error",
            response: null,
            error:
              error instanceof Error
                ? error.message
                : "Unable to complete preflight.",
          });
        });
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    configuration.applicationAssignment,
    configuration.batchSubscriptionKey,
    configuration.deviceGroup,
    configuration.site,
    hasDevices,
    preflightNonce,
    runState,
  ]);

  useEffect(() => {
    if (
      runState === "running" &&
      rawEvents.some((event) => event.type === "run_finished")
    ) {
      setRunState("complete");
    }
  }, [rawEvents, runState]);

  const liveDevices = useMemo(() => {
    const next: Record<string, DeviceState> = {};
    for (const device of runPlan) {
      next[device.serial] = {
        serial: device.serial,
        model: device.model,
        subscriptionKey: device.subscriptionKey,
        steps: {},
        firmware: { status: "pending" },
      };
    }

    for (const [serial, streamed] of Object.entries(
      onboarding?.devices ?? {}
    )) {
      next[serial] = {
        ...next[serial],
        ...streamed,
        model: next[serial]?.model,
        subscriptionKey: next[serial]?.subscriptionKey,
      };
    }
    return next;
  }, [onboarding?.devices, runPlan]);

  const runSummary = useMemo(() => makeSummary(liveDevices), [liveDevices]);
  const resultsData: RunResultsData | null = runId
    ? {
        runId,
        plan: runPlan,
        devices: liveDevices,
        events: rawEvents,
        connectionState,
        active: runState === "running",
        startedAt: onboarding?.startedAt,
        finishedAt: onboarding?.finishedAt,
        resultsDir: onboarding?.resultsDir,
        summary: runSummary,
      }
    : null;

  const completedStages = new Set<StageNumber>();
  if (configureReady) completedStages.add(1);
  if (devicesReady && deviceAddOnsReady) completedStages.add(2);
  if (runState === "complete") completedStages.add(3);

  const startRun = async () => {
    if (!reviewReady) return;
    const plan = makeRunPlan(devices);
    setReviewOpen(false);
    setActiveStage(3);
    setRunState("starting");
    setStartError(null);
    setRunPlan(plan);

    try {
      const response = await startOnboardingRun("onboarding", runVariables);
      setRunId(response.run_id);
      setRunState("running");
    } catch (error) {
      setRunState("idle");
      setStartError(
        error instanceof Error ? error.message : "Unable to start onboarding."
      );
    }
  };

  const prepareAnotherRun = () => {
    setRunState("idle");
    setRunId(null);
    setStartError(null);
    setPreflight({ state: "idle", response: null, error: null });
    setActiveStage(2);
  };

  const handlePrimaryAction = () => {
    if (runState === "starting" || runState === "running") return;
    if (runState === "complete") {
      setActiveStage(3);
      document
        .getElementById("stage-panel-3")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    if (activeStage === 1) {
      if (!configurationValuesReady) {
        setConfigureRevealNonce((current) => current + 1);
        return;
      }
      setActiveStage(2);
      return;
    }
    if (!deviceAddOnsReady) {
      setActiveStage(2);
      setDevicesRevealNonce((current) => current + 1);
      return;
    }
    if (reviewReady) setReviewOpen(true);
  };

  const toggleStep = (key: string, enabled: boolean) => {
    const step = steps.find((candidate) => candidate.key === key);
    if (!step || (step.field.required && !enabled)) return;
    setEnabledStepKeys((current) => {
      const next = new Set(current);
      if (enabled) next.add(key);
      else next.delete(key);
      return next;
    });
  };

  const primaryLabel =
    runState === "starting"
      ? "Starting…"
      : runState === "running"
        ? "Running…"
        : runState === "complete"
          ? "View results"
          : activeStage === 1
            ? "Next: Devices"
            : "Review & run";

  const primaryDisabled =
    runState === "starting" ||
    runState === "running" ||
    (runState === "idle" && activeStage !== 1 && !reviewReady);

  const summaryForStage = (stage: StageNumber) => {
    if (stage === 1) {
      const addOnSummary = stepsLoading
        ? "add-ons loading"
        : stepsError
          ? "add-ons unavailable"
          : `${enabledSteps.length} of ${steps.length} add-ons enabled`;
      if (!configureReady) {
        // Naming the stage's purpose told operators to do work they had
        // already done and never mentioned the field actually blocking them,
        // so the collapsed stage reports what is still missing instead.
        const missing = [
          !configuration.site && "site",
          !configuration.deviceGroup && "device group",
          !configuration.batchSubscriptionKey && "subscription",
          !configuration.applicationAssignment && "GLP application",
        ].filter((field): field is string => Boolean(field));
        if (missing.length === 0) {
          return `Waiting for add-on steps · ${addOnSummary}`;
        }
        const listed =
          missing.length === 1
            ? missing[0]
            : `${missing.slice(0, -1).join(", ")} and ${missing[missing.length - 1]}`;
        return `Still needed: ${listed} · ${addOnSummary}`;
      }
      return `${configuration.site} · ${configuration.deviceGroup} · ${configuration.batchSubscriptionKey} · ${addOnSummary}`;
    }
    if (stage === 2) {
      return `${devices.length} selected · ${deviceLimit ?? "…"} device limit`;
    }
    if (runState === "starting") return "The service is accepting this plan";
    if (runState === "running") {
      return `Onboarding is running across ${runPlan.length} devices`;
    }
    if (runState === "complete") {
      return `${runSummary.onboarded} onboarded · ${runSummary.warnings} with warnings · ${runSummary.failed} failed · ${runSummary.skipped} skipped`;
    }
    return "Review the full plan before anything runs";
  };

  return (
    <div className="command-center min-h-screen bg-[var(--cc-canvas)] text-[var(--cc-ink)]">
      <TopBar
        meta={
          <div
            className="hidden min-w-[3.5rem] text-right leading-tight sm:block"
            aria-live="polite"
            title="Maximum enforced by the backend"
          >
            <strong className="block text-sm tabular-nums">
              {devices.length} / {deviceLimit ?? "…"}
            </strong>
            <span className="text-[0.625rem] text-[var(--cc-topbar-muted)]">
              devices
            </span>
          </div>
        }
        actions={
          <Button
            type="button"
            onClick={handlePrimaryAction}
            disabled={primaryDisabled}
            className="h-11 min-w-[9.75rem] justify-between rounded-lg bg-[var(--cc-primary-action)] px-4 font-bold text-[var(--cc-primary-action-ink)] hover:bg-[var(--cc-primary-action-hover)] focus-visible:ring-[var(--cc-topbar-focus)] focus-visible:ring-offset-[var(--cc-topbar)] disabled:bg-[var(--cc-topbar-disabled)] disabled:text-[var(--cc-topbar-muted)] disabled:opacity-100"
          >
            {runState === "starting" || runState === "running" ? (
              <Loader2 aria-hidden="true" className="h-4 w-4 motion-safe:animate-spin" />
            ) : (
              <span
                aria-hidden="true"
                className="h-2 w-2 rounded-full bg-current opacity-70"
              />
            )}
            <span>{primaryLabel}</span>
            {runState !== "starting" && runState !== "running" && (
              <ArrowRight aria-hidden="true" className="h-4 w-4" />
            )}
          </Button>
        }
      />

      <main className="mx-auto w-full max-w-[92rem] px-4 pb-24 pt-8 sm:px-6 sm:pt-10">
        <div className="mb-6 max-w-3xl">
          <h1 className="text-2xl font-bold tracking-[-0.035em] sm:text-3xl">
            Onboard access points
          </h1>
          <p className="mt-2 max-w-[68ch] text-sm leading-6 text-[var(--cc-ink-soft)]">
            Configure the batch, confirm the device plan, then review every
            execution detail before anything runs.
          </p>
        </div>

        <div className="stage-frame">
          {STAGES.map((stage) => {
            const active = activeStage === stage.number;
            const complete = completedStages.has(stage.number);
            const running =
              stage.number === 3 &&
              (runState === "starting" || runState === "running");

            return (
              <section
                key={stage.number}
                data-stage={stage.number}
                data-active={active ? "true" : "false"}
                className={cn(
                  "stage-section overflow-hidden bg-[var(--cc-surface)] transition-[border-color,box-shadow,background-color] duration-200",
                  active
                    ? "bg-[var(--cc-raised)]"
                    : "bg-[var(--cc-surface)]"
                )}
              >
                <button
                  ref={(element) => {
                    stageHeaderRefs.current[stage.number] = element;
                  }}
                  type="button"
                  aria-expanded={active}
                  aria-controls={`stage-panel-${stage.number}`}
                  onClick={() => setActiveStage(stage.number)}
                  className="stage-header grid w-full grid-cols-[2.5rem_minmax(6.5rem,0.55fr)_minmax(0,1.45fr)_1.5rem] items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-[var(--cc-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--cc-accent)] sm:px-5"
                >
                  <span
                    className={cn(
                      "grid h-8 w-8 place-items-center rounded-full border text-xs font-extrabold tabular-nums",
                      active
                        ? "border-[var(--cc-accent)] bg-[var(--cc-accent)] text-[var(--cc-accent-ink)]"
                        : "border-[var(--cc-line-strong)] text-[var(--cc-ink-soft)]"
                    )}
                  >
                    {stage.number}
                  </span>
                  <span
                    className={cn(
                      "text-sm font-bold tracking-tight",
                      active && "text-[var(--cc-accent)]"
                    )}
                  >
                    {stage.title}
                  </span>
                  <span className="truncate text-xs text-[var(--cc-ink-soft)]">
                    {summaryForStage(stage.number)}
                  </span>
                  <span className="grid h-6 w-6 place-items-center text-[var(--cc-ink-faint)]">
                    {running ? (
                      <Loader2 aria-label="Running" className="h-4 w-4 motion-safe:animate-spin" />
                    ) : complete ? (
                      <Check aria-label="Complete" className="h-4 w-4 text-[var(--cc-success)]" />
                    ) : (
                      <Circle aria-label="Ready" className="h-4 w-4" />
                    )}
                  </span>
                </button>

                <div
                  id={`stage-panel-${stage.number}`}
                  hidden={!active}
                  className="border-t border-[var(--cc-line)] p-4 sm:p-6"
                >
                  {stage.number === 1 && (
                    <div className="grid gap-5">
                      <ConfigureStage
                        onChange={setConfiguration}
                        importedApplication={importedApplication}
                        revealNonce={configureRevealNonce}
                      />
                      <AddOnStepsSection
                        steps={steps}
                        enabledStepKeys={enabledStepKeys}
                        loading={stepsLoading}
                        error={stepsError}
                        onToggle={toggleStep}
                        onRetry={() => void loadSteps()}
                      />
                      {configureReady && (
                        <PreflightDisclosure
                          preflight={preflight}
                          locallyReady={locallyReady}
                          onFixClassicCredential={() =>
                            setCredentialsOpen(true)
                          }
                        />
                      )}
                    </div>
                  )}
                  {stage.number === 2 && (
                    <DevicesStage
                      batchSubscriptionKey={
                        configuration.batchSubscriptionKey
                      }
                      steps={steps}
                      enabledStepKeys={enabledStepKeys}
                      onDevicesChange={setDevices}
                      currentApplication={
                        configuration.applicationAssignment
                      }
                      onApplicationImported={(application) =>
                        setImportedApplication({ ...application })
                      }
                      revealNonce={devicesRevealNonce}
                    />
                  )}
                  {stage.number === 3 && (
                    <RunResultsStage
                      data={resultsData}
                      starting={runState === "starting"}
                      startError={startError}
                      onPrepareAnotherRun={prepareAnotherRun}
                    />
                  )}
                </div>
              </section>
            );
          })}
        </div>

        <div className="mt-5 flex items-center gap-2 text-xs text-[var(--cc-ink-faint)]">
          <Server aria-hidden="true" className="h-3.5 w-3.5" />
          {limitError
            ? `Device limit unavailable: ${limitError}`
            : `Device batches are limited to ${deviceLimit ?? "…"} by the service.`}
        </div>
      </main>

      <CredentialsModal
        open={credentialsOpen}
        initialSection="classic"
        onOpenChange={(nextOpen) => {
          setCredentialsOpen(nextOpen);
          if (!nextOpen) {
            setPreflightNonce((current) => current + 1);
          }
        }}
      />

      <ReviewRunDialog
        open={reviewOpen}
        onOpenChange={setReviewOpen}
        onConfirm={() => void startRun()}
        configuration={configuration}
        devices={devices}
        enabledSteps={enabledSteps}
        deviceLimit={deviceLimit}
        starting={runState === "starting"}
      />
    </div>
  );
}
