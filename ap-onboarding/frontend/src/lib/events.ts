import { useEffect, useRef, useState } from "react";

// ─── Status types ────────────────────────────────────────────────────────────

export type StepStatus =
  | "pending"
  | "in_progress"
  | "success"
  | "failed"
  | "skipped";

function mapStatus(raw: unknown): StepStatus {
  switch (raw) {
    case "In Progress":
      return "in_progress";
    case "Success":
      return "success";
    case "Failed":
      return "failed";
    case "Skipped":
      return "skipped";
    default:
      return "pending";
  }
}

// ─── Device / onboarding state ───────────────────────────────────────────────

export interface DeviceStepState {
  status: StepStatus;
  error?: string;
}

export interface FirmwareState extends DeviceStepState {
  currentVersion?: string;
  minimumVersion?: string;
  detail?: string;
}

export interface DeviceState {
  serial: string;
  /** UI plan metadata retained alongside streamed state for results/export. */
  model?: string;
  subscriptionKey?: string;
  steps: Record<string, DeviceStepState>;
  firmware: FirmwareState;
  overall?: "Success" | "Failed" | "WARNING" | "Skipped (firmware)";
}

export interface OnboardingRunState {
  runId: string;
  active: boolean;
  devices: Record<string, DeviceState>;
  totalDevices: number;
  doneCount: number;
  successCount: number;
  warningCount: number;
  skippedCount: number;
  failedCount: number;
  startedAt: number;
  finishedAt?: number;
  resultsDir?: string;
  logEvents: RawEvent[];
}

// ─── Network setup state ─────────────────────────────────────────────────────

export interface EntityStepState {
  status: StepStatus;
  error?: string;
}

export interface NetworkSetupRunState {
  runId: string;
  active: boolean;
  sites: Record<string, Record<string, EntityStepState>>;
  groups: Record<string, Record<string, EntityStepState>>;
  startedAt: number;
  finishedAt?: number;
  resultsDir?: string;
  logEvents: RawEvent[];
}

export type RawEvent = Record<string, unknown>;

// ─── Reducers ────────────────────────────────────────────────────────────────

function ensureDevice(
  devices: Record<string, DeviceState>,
  serial: string
): DeviceState {
  if (!devices[serial]) {
    return {
      serial,
      steps: {},
      firmware: { status: "pending" },
    };
  }
  return devices[serial];
}

function reduceOnboardingEvent(
  state: OnboardingRunState,
  event: RawEvent
): OnboardingRunState {
  const type = event.type as string;

  if (type === "step") {
    const serial = event.serial as string;
    const step = event.step as string;
    const status = mapStatus(event.status);
    const error = event.error as string | undefined;

    const devices = { ...state.devices };
    const device = { ...ensureDevice(devices, serial) };

    if (step === "firmware_check") {
      device.firmware = {
        status,
        error,
        currentVersion: event.current_version as string | undefined,
        minimumVersion: event.minimum_version as string | undefined,
        detail: event.detail as string | undefined,
      };
    } else {
      device.steps = {
        ...device.steps,
        [step]: { status, error },
      };
    }

    devices[serial] = device;
    return { ...state, devices };
  }

  if (type === "device_done") {
    const serial = event.serial as string;
    const overall = event.overall as
      | "Success"
      | "Failed"
      | "WARNING"
      | "Skipped (firmware)";

    const devices = { ...state.devices };
    const device = { ...ensureDevice(devices, serial), overall };
    devices[serial] = device;

    const doneCount = state.doneCount + 1;
    const successCount =
      overall === "Success" ? state.successCount + 1 : state.successCount;
    const warningCount =
      overall === "WARNING" ? state.warningCount + 1 : state.warningCount;
    const skippedCount =
      overall === "Skipped (firmware)"
        ? state.skippedCount + 1
        : state.skippedCount;
    const failedCount =
      overall === "Failed" ? state.failedCount + 1 : state.failedCount;

    return {
      ...state,
      devices,
      doneCount,
      successCount,
      warningCount,
      skippedCount,
      failedCount,
    };
  }

  return state;
}

function reduceNetworkEvent(
  state: NetworkSetupRunState,
  event: RawEvent
): NetworkSetupRunState {
  const type = event.type as string;

  if (type === "site") {
    const name = event.name as string;
    const step = event.step as string;
    const status = mapStatus(event.status);
    const error = event.error as string | undefined;
    const sites = {
      ...state.sites,
      [name]: { ...state.sites[name], [step]: { status, error } },
    };
    return { ...state, sites };
  }

  if (type === "group" || type === "group_done") {
    const name = event.name as string;
    if (type === "group") {
      const step = event.step as string;
      const status = mapStatus(event.status);
      const error = event.error as string | undefined;
      const groups = {
        ...state.groups,
        [name]: { ...state.groups[name], [step]: { status, error } },
      };
      return { ...state, groups };
    }
    // group_done: update overall status in the group map under a synthetic "__overall" key
    const overall = event.overall as string;
    const groups = {
      ...state.groups,
      [name]: {
        ...state.groups[name],
        __overall: { status: mapStatus(overall) },
      },
    };
    return { ...state, groups };
  }

  return state;
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export type ConnectionState = "connecting" | "connected" | "disconnected";

const DISCONNECT_GRACE_MS = 4_000;

export function useRunEvents(runId: string | null): {
  onboarding: OnboardingRunState | null;
  network: NetworkSetupRunState | null;
  rawEvents: RawEvent[];
  connectionState: ConnectionState;
} {
  const [onboarding, setOnboarding] = useState<OnboardingRunState | null>(null);
  const [network, setNetwork] = useState<NetworkSetupRunState | null>(null);
  const [rawEvents, setRawEvents] = useState<RawEvent[]>([]);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("connecting");

  // Use a ref to track the current mode so the message handler can see it
  const modeRef = useRef<"onboarding" | "network_setup" | null>(null);

  useEffect(() => {
    if (!runId) {
      return;
    }

    // Reset state for new run
    setOnboarding(null);
    setNetwork(null);
    setRawEvents([]);
    setConnectionState("connecting");
    modeRef.current = null;

    const es = new EventSource(`/api/events/${runId}`);
    let disconnectTimer: number | null = null;

    const clearDisconnectTimer = () => {
      if (disconnectTimer === null) return;
      window.clearTimeout(disconnectTimer);
      disconnectTimer = null;
    };

    const markConnected = () => {
      clearDisconnectTimer();
      setConnectionState("connected");
    };

    es.onopen = () => {
      markConnected();
    };

    es.onmessage = (e: MessageEvent) => {
      // Any message implies the connection is healthy
      markConnected();
      let event: RawEvent;
      try {
        event = JSON.parse(e.data as string) as RawEvent;
      } catch {
        return;
      }

      setRawEvents((prev) => [...prev, event]);

      const type = event.type as string;

      if (type === "run_started") {
        const mode = event.mode as "onboarding" | "network_setup";
        modeRef.current = mode;

        if (mode === "onboarding") {
          setOnboarding({
            runId: event.run_id as string,
            active: true,
            devices: {},
            totalDevices: 0,
            doneCount: 0,
            successCount: 0,
            warningCount: 0,
            skippedCount: 0,
            failedCount: 0,
            startedAt: Date.now(),
            logEvents: [event],
          });
        } else {
          setNetwork({
            runId: event.run_id as string,
            active: true,
            sites: {},
            groups: {},
            startedAt: Date.now(),
            logEvents: [event],
          });
        }
        return;
      }

      if (type === "run_finished") {
        clearDisconnectTimer();
        const resultsDir = event.results_dir as string | null | undefined;
        if (modeRef.current === "onboarding") {
          setOnboarding((prev) =>
            prev
              ? {
                  ...prev,
                  active: false,
                  finishedAt: Date.now(),
                  resultsDir: resultsDir ?? undefined,
                  logEvents: [...prev.logEvents, event],
                }
              : prev
          );
        } else {
          setNetwork((prev) =>
            prev
              ? {
                  ...prev,
                  active: false,
                  finishedAt: Date.now(),
                  resultsDir: resultsDir ?? undefined,
                  logEvents: [...prev.logEvents, event],
                }
              : prev
          );
        }
        es.close();
        return;
      }

      if (type === "error") {
        // Append to logEvents for both modes
        if (modeRef.current === "onboarding") {
          setOnboarding((prev) =>
            prev ? { ...prev, logEvents: [...prev.logEvents, event] } : prev
          );
        } else {
          setNetwork((prev) =>
            prev ? { ...prev, logEvents: [...prev.logEvents, event] } : prev
          );
        }
        return;
      }

      // Route domain events
      if (modeRef.current === "onboarding") {
        setOnboarding((prev) => {
          if (!prev) return prev;
          const next = reduceOnboardingEvent(prev, event);
          return { ...next, logEvents: [...prev.logEvents, event] };
        });
      } else if (modeRef.current === "network_setup") {
        setNetwork((prev) => {
          if (!prev) return prev;
          const next = reduceNetworkEvent(prev, event);
          return { ...next, logEvents: [...prev.logEvents, event] };
        });
      }
    };

    es.onerror = () => {
      // The server closes the stream between polls, so reconnects during an
      // active run are expected. Only surface a sustained event gap.
      if (
        es.readyState !== EventSource.CLOSED &&
        disconnectTimer === null
      ) {
        disconnectTimer = window.setTimeout(() => {
          disconnectTimer = null;
          if (es.readyState !== EventSource.OPEN) {
            setConnectionState("disconnected");
          }
        }, DISCONNECT_GRACE_MS);
      }
    };

    return () => {
      clearDisconnectTimer();
      es.close();
    };
  }, [runId]);

  return { onboarding, network, rawEvents, connectionState };
}
