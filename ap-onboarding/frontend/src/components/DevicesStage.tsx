import {
  type ChangeEvent,
  type FormEvent,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AlertCircle,
  ChevronDown,
  FileCheck,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getLimits,
  getLookups,
  parseUpload,
  type ApplicationLookup,
  type LookupDevice,
  type LookupsResponse,
  type StepMeta,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  validateAddOnField,
  type AddOnFieldValue,
} from "@/lib/validation";

interface Subscription {
  key: string;
  type: string;
  available: boolean | number;
}

interface DeviceRow {
  id: number;
  serial: string;
  model: string;
  mac: string;
  subscriptionOverrideKey: string;
  addOnInputs: Record<string, string>;
}

interface DeviceCandidate {
  serial: string;
  model?: string | null;
  mac?: string | null;
  subscriptionOverrideKey?: string;
  addOnInputs?: Record<string, string>;
}

export interface DevicesStageDevice {
  serial_number: string;
  model?: string;
  mac?: string;
  /**
   * Effective key for this device: its inline override first, then the batch
   * default supplied by the Configure stage.
   */
  subscription_key?: string;
  addOnValues: Record<string, AddOnFieldValue>;
  addOnsValid: boolean;
  blankAddOnKeys: string[];
}

export interface DevicesStageProps {
  batchSubscriptionKey?: string;
  steps?: StepMeta[];
  enabledStepKeys?: ReadonlySet<string>;
  onDevicesChange?: (devices: DevicesStageDevice[]) => void;
  currentApplication?: ApplicationLookup | null;
  onApplicationImported?: (application: ApplicationLookup) => void;
  revealNonce?: number;
}

type FeedbackTone = "neutral" | "imported" | "error";

const BATCH_DEFAULT_VALUE = "__batch_default__";
const ADD_ON_UNSET_VALUE = "__add_on_unset__";
const NO_ENABLED_STEPS = new Set<string>();
let nextDeviceId = 1;

interface AddOnIssue {
  inputId: string;
  deviceLabel: string;
  stepKey: string;
  stepLabel: string;
  kind: "blank" | "invalid";
  error: string;
}

interface AddOnIssueGroup {
  key: string;
  kind: AddOnIssue["kind"];
  stepLabel: string;
  error: string;
  offenders: AddOnIssue[];
}

function addOnInputId(deviceId: number, stepKey: string): string {
  return `device-${deviceId}-${stepKey}`;
}

function focusAndCenterControl(id: string) {
  const control = document.getElementById(id);
  if (!control) return;
  const reduceMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;
  control.focus({ preventScroll: true });
  control.scrollIntoView({
    behavior: reduceMotion ? "auto" : "smooth",
    block: "center",
  });
}

function labelWithArticle(label: string): string {
  const normalized = label.toLocaleLowerCase();
  const article = /^[aeiou]/u.test(normalized) ? "an" : "a";
  return `${article} ${normalized}`;
}

function normalizeSerial(serial: string): string {
  return serial.trim().toUpperCase();
}

function applicationKey(application: ApplicationLookup): string {
  return JSON.stringify([application.name, application.region]);
}

function applicationLabel(application: ApplicationLookup): string {
  return `${application.name} · ${application.region}`;
}

function makeRow(candidate: DeviceCandidate): DeviceRow {
  return {
    id: nextDeviceId++,
    serial: normalizeSerial(candidate.serial),
    model: candidate.model?.trim() ?? "",
    mac: candidate.mac?.trim() ?? "",
    subscriptionOverrideKey: candidate.subscriptionOverrideKey?.trim() ?? "",
    addOnInputs: candidate.addOnInputs ?? {},
  };
}

function inputValueForStep(device: DeviceRow, step: StepMeta): string {
  return device.addOnInputs[step.key] ?? "";
}

function inputValueFromParsedDevice(
  device: Record<string, unknown>,
  step: StepMeta
): string {
  const value = device[step.key];
  if (value === undefined || value === null) return "";
  if (step.field.type === "list[string]") {
    return Array.isArray(value) ? value.join(", ") : String(value);
  }
  if (step.field.type === "bool") {
    return typeof value === "boolean" ? String(value) : "";
  }
  return String(value);
}

function placeholderForStep(step: StepMeta): string | undefined {
  if (step.field.type === "list[string]" && Array.isArray(step.field.example)) {
    return step.field.example.join(", ");
  }
  if (
    typeof step.field.example === "string" ||
    typeof step.field.example === "number"
  ) {
    return String(step.field.example);
  }
  return undefined;
}

function subscriptionIsAvailable(subscription: Subscription): boolean {
  return typeof subscription.available === "number"
    ? subscription.available > 0
    : subscription.available;
}

function feedbackForMerge(
  added: number,
  merged: number,
  blocked: number,
  ignoredAddOnValues: number
): string {
  const messages: string[] = [];
  if (added > 0) {
    messages.push(`Added ${added} device${added === 1 ? "" : "s"}.`);
  }
  if (merged > 0) {
    messages.push(
      `${merged} duplicate${merged === 1 ? "" : "s"} merged into the existing table.`
    );
  }
  if (blocked > 0) {
    messages.push(
      `${blocked} device${blocked === 1 ? " was" : "s were"} skipped at the device limit.`
    );
  }
  if (ignoredAddOnValues > 0) {
    messages.push(
      `${ignoredAddOnValues} imported add-on value${ignoredAddOnValues === 1 ? " was" : "s were"} not applied because the existing table value${ignoredAddOnValues === 1 ? " was" : "s were"} kept.`
    );
  }
  return messages.join(" ");
}

export function DevicesStage({
  batchSubscriptionKey = "",
  steps = [],
  enabledStepKeys = NO_ENABLED_STEPS,
  onDevicesChange,
  currentApplication = null,
  onApplicationImported,
  revealNonce = 0,
}: DevicesStageProps) {
  const [inventory, setInventory] = useState<LookupDevice[]>([]);
  const [lookups, setLookups] = useState<LookupsResponse | null>(null);
  const [maxDevices, setMaxDevices] = useState<number | null>(null);
  const [devices, setDevices] = useState<DeviceRow[]>([]);
  const deviceRowsRef = useRef<DeviceRow[]>([]);
  const [inventoryLoading, setInventoryLoading] = useState(true);
  const [limitLoading, setLimitLoading] = useState(true);
  const [inventoryError, setInventoryError] = useState<string | null>(null);
  const [limitError, setLimitError] = useState<string | null>(null);
  const [csvOpen, setCsvOpen] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [manualSerial, setManualSerial] = useState("");
  const [uploading, setUploading] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [feedbackTone, setFeedbackTone] =
    useState<FeedbackTone>("neutral");
  const [reloadKey, setReloadKey] = useState(0);
  const [touchedAddOnInputs, setTouchedAddOnInputs] = useState<Set<string>>(
    new Set()
  );
  const csvInputId = useId();
  const manualInputId = useId();

  const subscriptions =
    (
      lookups as
        | (LookupsResponse & { subscriptions?: Subscription[] })
        | null
    )?.subscriptions ?? [];
  const enabledSteps = useMemo(
    () => steps.filter((step) => enabledStepKeys.has(step.key)),
    [enabledStepKeys, steps]
  );
  const addOnIssues = useMemo<AddOnIssue[]>(
    () =>
      devices.flatMap<AddOnIssue>((device, deviceIndex) =>
        enabledSteps.flatMap<AddOnIssue>((step) => {
          const validation = validateAddOnField(
            step.field,
            inputValueForStep(device, step),
            step.label
          );
          if (validation.empty) {
            return [
              {
                inputId: addOnInputId(device.id, step.key),
                deviceLabel: device.serial || `device ${deviceIndex + 1}`,
                stepKey: step.key,
                stepLabel: step.label,
                kind: "blank",
                error: `${step.label} is required while this add-on is enabled.`,
              },
            ];
          }
          if (!validation.valid) {
            return [
              {
                inputId: addOnInputId(device.id, step.key),
                deviceLabel: device.serial || `device ${deviceIndex + 1}`,
                stepKey: step.key,
                stepLabel: step.label,
                kind: "invalid",
                error:
                  validation.error ?? `${step.label} needs to be corrected.`,
              },
            ];
          }
          return [];
        })
      ),
    [devices, enabledSteps]
  );
  const addOnIssueGroups = useMemo(() => {
    const groups = new Map<string, AddOnIssueGroup>();
    for (const issue of addOnIssues) {
      const key =
        issue.kind === "blank"
          ? `${issue.kind}:${issue.stepKey}`
          : `${issue.kind}:${issue.stepKey}:${issue.error}`;
      const existing = groups.get(key);
      if (existing) {
        existing.offenders.push(issue);
      } else {
        groups.set(key, {
          key,
          kind: issue.kind,
          stepLabel: issue.stepLabel,
          error: issue.error,
          offenders: [issue],
        });
      }
    }
    return [...groups.values()];
  }, [addOnIssues]);
  const addOnIssuesRef = useRef(addOnIssues);
  addOnIssuesRef.current = addOnIssues;

  useEffect(() => {
    if (revealNonce === 0) return;
    const firstOffender = addOnIssuesRef.current[0];
    if (firstOffender) focusAndCenterControl(firstOffender.inputId);
  }, [revealNonce]);

  const markAddOnInputTouched = (id: string) => {
    setTouchedAddOnInputs((current) => {
      if (current.has(id)) return current;
      const next = new Set(current);
      next.add(id);
      return next;
    });
  };

  const showFeedback = (
    message: string,
    tone: FeedbackTone = "neutral"
  ) => {
    setFeedback(message);
    setFeedbackTone(tone);
  };

  const replaceDevices = (next: DeviceRow[]) => {
    deviceRowsRef.current = next;
    setDevices(next);
  };

  useEffect(() => {
    let cancelled = false;
    setInventoryLoading(true);
    setLimitLoading(true);
    setInventoryError(null);
    setLimitError(null);
    setMaxDevices(null);

    getLookups()
      .then((data) => {
        if (cancelled) return;
        setLookups(data);
        setInventory(data.devices ?? []);
        const inventoryLookupError =
          data.errors?.devices ?? data.errors?.new_central;
        if (inventoryLookupError) {
          setInventoryError(
            `Could not load GLP inventory: ${inventoryLookupError}`
          );
        }
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : String(error);
        setInventoryError(`Could not load GLP inventory: ${message}`);
      })
      .finally(() => {
        if (!cancelled) setInventoryLoading(false);
      });

    getLimits()
      .then((data) => {
        if (cancelled) return;
        if (!Number.isInteger(data.max_devices) || data.max_devices < 1) {
          setLimitError("The service returned an invalid device limit.");
          return;
        }
        setMaxDevices(data.max_devices);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : String(error);
        setLimitError(`Could not load the device limit: ${message}`);
      })
      .finally(() => {
        if (!cancelled) setLimitLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  useEffect(() => {
    if (!onDevicesChange) return;
    onDevicesChange(
      devices.map((device) => {
        const addOnValues: Record<string, AddOnFieldValue> = {};
        let addOnsValid = true;
        const blankAddOnKeys: string[] = [];

        for (const step of enabledSteps) {
          const validation = validateAddOnField(
            step.field,
            inputValueForStep(device, step),
            step.label
          );
          if (!validation.valid) addOnsValid = false;
          if (validation.empty) blankAddOnKeys.push(step.key);
          if (
            validation.valid &&
            !validation.empty &&
            validation.value !== undefined
          ) {
            addOnValues[step.key] = validation.value;
          }
        }

        return {
          serial_number: device.serial,
          ...(device.model ? { model: device.model } : {}),
          ...(device.mac ? { mac: device.mac } : {}),
          ...((device.subscriptionOverrideKey || batchSubscriptionKey)
            ? {
                subscription_key:
                  device.subscriptionOverrideKey || batchSubscriptionKey,
              }
            : {}),
          addOnValues,
          addOnsValid,
          blankAddOnKeys,
        };
      })
    );
  }, [
    batchSubscriptionKey,
    devices,
    enabledSteps,
    onDevicesChange,
  ]);

  // Returns the message it showed, so an importer can append to it rather
  // than overwrite the device count the operator needs to see.
  const mergeDevices = (candidates: DeviceCandidate[]): string => {
    if (maxDevices === null) {
      const message = "Wait for the service device limit before adding devices.";
      showFeedback(message);
      return message;
    }

    const next = deviceRowsRef.current.map((device) => ({ ...device }));
    const serialIndexes = new Map(
      next
        .map((device, index) => [normalizeSerial(device.serial), index] as const)
        .filter(([serial]) => serial)
    );
    let added = 0;
    let merged = 0;
    let blocked = 0;
    let ignoredAddOnValues = 0;

    for (const candidate of candidates) {
      const serial = normalizeSerial(candidate.serial);
      if (!serial) continue;

      const existingIndex = serialIndexes.get(serial);
      if (existingIndex !== undefined) {
        const existing = next[existingIndex];
        const addOnInputs = { ...existing.addOnInputs };
        for (const [key, candidateValue] of Object.entries(
          candidate.addOnInputs ?? {}
        )) {
          const incoming = candidateValue.trim();
          if (!incoming) continue;
          const current = addOnInputs[key]?.trim() ?? "";
          if (!current) {
            addOnInputs[key] = candidateValue;
          } else if (current !== incoming) {
            ignoredAddOnValues += 1;
          }
        }
        next[existingIndex] = {
          ...existing,
          model: existing.model || candidate.model?.trim() || "",
          mac: existing.mac || candidate.mac?.trim() || "",
          subscriptionOverrideKey:
            existing.subscriptionOverrideKey ||
            candidate.subscriptionOverrideKey?.trim() ||
            "",
          addOnInputs,
        };
        merged += 1;
        continue;
      }

      if (next.length >= maxDevices) {
        blocked += 1;
        continue;
      }

      const row = makeRow({ ...candidate, serial });
      serialIndexes.set(serial, next.length);
      next.push(row);
      added += 1;
    }

    replaceDevices(next);
    const message =
      feedbackForMerge(added, merged, blocked, ignoredAddOnValues) ||
      "No serial numbers found.";
    showFeedback(message);
    return message;
  };

  const toggleInventoryDevice = (device: LookupDevice) => {
    const serial = normalizeSerial(device.serial);
    const selected = deviceRowsRef.current.some(
      (row) => normalizeSerial(row.serial) === serial
    );
    if (selected) {
      replaceDevices(
        deviceRowsRef.current.filter(
          (row) => normalizeSerial(row.serial) !== serial
        )
      );
      showFeedback(`Removed ${serial}.`);
      return;
    }
    mergeDevices([device]);
  };

  const addAllInventory = () => {
    mergeDevices(inventory);
  };

  const handleManualSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const serial = normalizeSerial(manualSerial);
    if (!serial) {
      showFeedback("Enter a serial number first.");
      return;
    }
    const inventoryMatch = inventory.find(
      (device) => normalizeSerial(device.serial) === serial
    );
    mergeDevices([inventoryMatch ?? { serial }]);
    setManualSerial("");
  };

  const handleCsvUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const parsed = await parseUpload(file);
      const candidates = parsed.devices.flatMap((value) => {
        if (!value || typeof value !== "object") return [];
        const device = value as Record<string, unknown>;
        if (typeof device.serial_number !== "string") return [];
        return [
          {
            serial: device.serial_number,
            model: typeof device.model === "string" ? device.model : "",
            mac: typeof device.mac === "string" ? device.mac : "",
            subscriptionOverrideKey:
              typeof device.subscription_key === "string"
                ? device.subscription_key
                : "",
            addOnInputs: Object.fromEntries(
              steps.map((step) => [
                step.key,
                inputValueFromParsedDevice(device, step),
              ])
            ),
          },
        ];
      });
      const importSummary = mergeDevices(candidates);

      const importedValue = parsed.defaults?.application_assignment;
      if (
        importedValue &&
        typeof importedValue === "object" &&
        !Array.isArray(importedValue)
      ) {
        const importedApplication = importedValue as Record<string, unknown>;
        const importedName = importedApplication.name;
        const importedRegion = importedApplication.region;
        const validRegion =
          importedRegion === undefined || typeof importedRegion === "string";

        if (
          typeof importedName === "string" &&
          importedName.length > 0 &&
          validRegion
        ) {
          const match = lookups?.applications.find(
            (application) =>
              application.name === importedName &&
              (importedRegion === undefined ||
                application.region === importedRegion)
          );
          const importedLabel =
            typeof importedRegion === "string"
              ? `${importedName} · ${importedRegion}`
              : importedName;

          if (!match) {
            const reportedApplications =
              lookups?.applications.length
                ? lookups.applications.map(applicationLabel).join(", ")
                : "none";
            showFeedback(
              `${importSummary} The file names the GLP application “${importedLabel}”, which this workspace does not report. It reports: ${reportedApplications}. The GLP application selection was left unchanged.`,
              "error"
            );
          } else {
            onApplicationImported?.(match);
            if (
              currentApplication &&
              applicationKey(currentApplication) !== applicationKey(match)
            ) {
              showFeedback(
                `${importSummary} The file changed the GLP application from “${applicationLabel(currentApplication)}” to “${applicationLabel(match)}”.`,
                "imported"
              );
            } else {
              showFeedback(
                `${importSummary} The file set the GLP application to “${applicationLabel(match)}”.`,
                "imported"
              );
            }
          }
        }
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      showFeedback(`CSV import failed: ${message}`, "error");
    } finally {
      input.value = "";
      setUploading(false);
    }
  };

  const updateSerial = (id: number, value: string) => {
    const serial = value.toUpperCase();
    const normalized = normalizeSerial(serial);
    const duplicate = deviceRowsRef.current.some(
      (device) =>
        device.id !== id && normalizeSerial(device.serial) === normalized
    );
    if (normalized && duplicate) {
      showFeedback(`${normalized} is already in the device table.`);
      return;
    }

    const inventoryMatch = inventory.find(
      (device) => normalizeSerial(device.serial) === normalized
    );
    replaceDevices(
      deviceRowsRef.current.map((device) =>
        device.id === id
          ? {
              ...device,
              serial,
              model: inventoryMatch?.model ?? "",
              mac: inventoryMatch?.mac ?? "",
            }
          : device
      )
    );
  };

  const updateSubscription = (id: number, value: string) => {
    replaceDevices(
      deviceRowsRef.current.map((device) =>
        device.id === id
          ? {
              ...device,
              subscriptionOverrideKey:
                value === BATCH_DEFAULT_VALUE ? "" : value,
            }
          : device
      )
    );
  };

  const updateAddOnInput = (id: number, key: string, value: string) => {
    replaceDevices(
      deviceRowsRef.current.map((device) =>
        device.id === id
          ? {
              ...device,
              addOnInputs: {
                ...device.addOnInputs,
                [key]: value,
              },
            }
          : device
      )
    );
  };

  const removeDevice = (id: number) => {
    const device = deviceRowsRef.current.find((row) => row.id === id);
    replaceDevices(deviceRowsRef.current.filter((row) => row.id !== id));
    if (device) showFeedback(`Removed ${device.serial}.`);
  };

  const atLimit = maxDevices !== null && devices.length >= maxDevices;
  const addingDisabled = maxDevices === null || atLimit;
  const counterLabel =
    maxDevices === null
      ? `${devices.length} selected`
      : `${devices.length} of ${maxDevices} selected`;

  return (
    // Grid items default to min-width:auto, so the wrappers around the wide
    // tables below refuse to shrink to their overflow-x box and spill past the
    // stage frame, which clips them with no scrollbar to reach them.
    <div className="grid gap-5 [&>*]:min-w-0">
      {revealNonce > 0 && addOnIssues.length > 0 && (
        <div
          key={revealNonce}
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-[color-mix(in_oklch,var(--cc-danger)_35%,var(--cc-line))] bg-[var(--cc-danger-soft)] px-3.5 py-3 text-xs text-[var(--cc-danger)] motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-0.5 motion-safe:duration-200 motion-safe:ease-out"
        >
          <AlertCircle
            aria-hidden="true"
            className="mt-0.5 h-4 w-4 shrink-0"
          />
          <div>
            <p className="font-semibold">
              Correct enabled add-on values before review.
            </p>
            <ul className="mt-1 list-disc space-y-1 pl-4 leading-5">
              {addOnIssueGroups.map((group) => {
                const count = group.offenders.length;
                const deviceNoun = count === 1 ? "device" : "devices";
                const verb = count === 1 ? "is" : "are";
                const hasVerb = count === 1 ? "has" : "have";
                const lowerLabel = group.stepLabel.toLocaleLowerCase();
                return (
                  <li key={group.key}>
                    {group.kind === "blank" ? (
                      <>
                        {count} {deviceNoun} {verb} missing{" "}
                        {labelWithArticle(group.stepLabel)}. Enter {lowerLabel} for{" "}
                      </>
                    ) : (
                      <>
                        {count} {deviceNoun} {hasVerb} {lowerLabel} values that
                        need correction. {group.error} Fix{" "}
                      </>
                    )}
                    {group.offenders.map((offender, index) => (
                      <span key={offender.inputId}>
                        {index > 0 && (index === count - 1 ? " and " : ", ")}
                        <a
                          href={`#${offender.inputId}`}
                          onClick={(event) => {
                            event.preventDefault();
                            focusAndCenterControl(offender.inputId);
                          }}
                          className="font-semibold underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cc-danger)]"
                        >
                          {offender.deviceLabel}
                        </a>
                      </span>
                    ))}
                    .
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      )}
      <section aria-labelledby="inventory-picker-title">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h3 id="inventory-picker-title" className="text-sm font-semibold">
              GLP inventory
            </h3>
            <p className="mt-1 text-xs leading-5 text-[var(--cc-ink-soft)]">
              Select devices from the connected workspace.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "rounded-full border px-2.5 py-1 text-[0.6875rem] font-semibold tabular-nums",
                atLimit
                  ? "border-[color-mix(in_oklch,var(--cc-danger)_35%,var(--cc-line))] bg-[var(--cc-danger-soft)] text-[var(--cc-danger)]"
                  : "border-[var(--cc-line)] bg-[var(--cc-muted)] text-[var(--cc-ink-soft)]"
              )}
            >
              {limitLoading ? "Loading limit…" : counterLabel}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={addAllInventory}
              disabled={
                addingDisabled || inventoryLoading || inventory.length === 0
              }
              className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] hover:bg-[var(--cc-muted)]"
            >
              Add all
            </Button>
          </div>
        </div>

        {limitError && (
          <div
            role="alert"
            className="mt-3 flex flex-col gap-3 rounded-lg border border-[color-mix(in_oklch,var(--cc-danger)_35%,var(--cc-line))] bg-[var(--cc-danger-soft)] px-3 py-2 text-xs text-[var(--cc-danger)] sm:flex-row sm:items-center sm:justify-between"
          >
            <span>{limitError} Selection is disabled.</span>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setReloadKey((current) => current + 1)}
              className="shrink-0 border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] hover:bg-[var(--cc-muted)]"
            >
              <RefreshCw aria-hidden="true" />
              Retry
            </Button>
          </div>
        )}

        <div className="mt-3 max-h-72 overflow-auto rounded-xl border border-[var(--cc-line)]">
          {inventoryLoading ? (
            <div className="grid gap-2 p-3" aria-label="Loading GLP inventory">
              {[0, 1, 2].map((row) => (
                <Skeleton
                  key={row}
                  className="h-11 bg-[var(--cc-muted)]"
                />
              ))}
            </div>
          ) : inventoryError ? (
            <div
              role="alert"
              className="flex flex-col items-center gap-3 px-4 py-8 text-center text-sm text-[var(--cc-danger)]"
            >
              <span>{inventoryError}</span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setReloadKey((current) => current + 1)}
                className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] hover:bg-[var(--cc-muted)]"
              >
                <RefreshCw aria-hidden="true" />
                Retry
              </Button>
            </div>
          ) : inventory.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <p className="text-sm font-semibold">
                No unassigned devices in this GLP workspace
              </p>
              <p className="mx-auto mt-1 max-w-[52ch] text-xs leading-5 text-[var(--cc-ink-soft)]">
                Inventory lists access points that are not yet assigned to an
                application. Add serials with Upload CSV or Enter serial
                manually below, or check the workspace on the Central instance
                chip above.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-[var(--cc-line)]">
              {inventory.map((device) => {
                const selected = devices.some(
                  (row) =>
                    normalizeSerial(row.serial) ===
                    normalizeSerial(device.serial)
                );
                return (
                  <li key={device.serial}>
                    <label
                      className={cn(
                        "grid min-h-12 cursor-pointer grid-cols-[auto_minmax(8rem,1fr)_minmax(7rem,0.8fr)_minmax(10rem,1fr)] items-center gap-3 px-4 py-2 text-xs transition-colors hover:bg-[var(--cc-muted)]",
                        selected &&
                          "bg-[var(--cc-accent-soft)] ring-1 ring-inset ring-[var(--cc-accent)]",
                        // No opacity here: the serial, model and MAC stay
                        // readable reference data even when the row cannot be
                        // added. The disabled control and the counter turning
                        // red already carry the unavailability.
                        !selected && addingDisabled && "cursor-not-allowed"
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        disabled={!selected && addingDisabled}
                        onChange={() => toggleInventoryDevice(device)}
                        className={cn(
                          "h-4 w-4 rounded-sm accent-[var(--cc-accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cc-accent)] focus-visible:ring-offset-2",
                          selected
                            ? "focus-visible:ring-offset-[var(--cc-accent-soft)]"
                            : "focus-visible:ring-offset-[var(--cc-raised)]"
                        )}
                      />
                      <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                        <span className="font-mono font-semibold">
                          {device.serial}
                        </span>
                        {selected && (
                          <span className="rounded-full border border-[var(--cc-accent)] px-1.5 py-0.5 text-[0.625rem] font-semibold text-[var(--cc-accent)]">
                            Selected
                          </span>
                        )}
                      </span>
                      <span className="text-[var(--cc-ink-soft)]">
                        {device.model || "Model unavailable"}
                      </span>
                      <span
                        className={cn(
                          "font-mono",
                          selected
                            ? "text-[var(--cc-ink-soft)]"
                            : "text-[var(--cc-ink-faint)]"
                        )}
                      >
                        {device.mac || "MAC unavailable"}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-y border-[var(--cc-line)] py-2">
        <span className="text-xs text-[var(--cc-ink-faint)]">
          Other ways to add devices
        </span>
        <Button
          type="button"
          variant="link"
          aria-expanded={csvOpen}
          aria-controls="devices-csv-upload"
          onClick={() => setCsvOpen((open) => !open)}
          className="h-auto gap-1 p-0 text-xs font-semibold text-[var(--cc-accent)]"
        >
          Upload CSV
          <ChevronDown
            aria-hidden="true"
            className={cn(
              "h-3.5 w-3.5 transition-transform duration-200",
              csvOpen && "rotate-180"
            )}
          />
        </Button>
        <Button
          type="button"
          variant="link"
          aria-expanded={manualOpen}
          aria-controls="devices-manual-serial"
          onClick={() => setManualOpen((open) => !open)}
          className="h-auto gap-1 p-0 text-xs font-semibold text-[var(--cc-accent)]"
        >
          Enter serial manually
          <ChevronDown
            aria-hidden="true"
            className={cn(
              "h-3.5 w-3.5 transition-transform duration-200",
              manualOpen && "rotate-180"
            )}
          />
        </Button>
      </div>

      {csvOpen && (
        <div
          id="devices-csv-upload"
          className="rounded-xl border border-[var(--cc-line)] bg-[var(--cc-muted)] p-4"
        >
          <label
            htmlFor={csvInputId}
            className="text-xs font-semibold text-[var(--cc-ink)]"
          >
            CSV file
          </label>
          <p className="mt-1 text-xs leading-5 text-[var(--cc-ink-soft)]">
            Use a <span className="font-mono">serial_number</span> column.
            Existing serials are merged.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Input
              id={csvInputId}
              type="file"
              accept=".csv,text/csv"
              onChange={handleCsvUpload}
              disabled={uploading || maxDevices === null || inventoryLoading}
              className="max-w-md border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-xs text-[var(--cc-ink)] file:text-[var(--cc-ink)]"
            />
            {uploading && (
              <span className="inline-flex items-center gap-2 text-xs text-[var(--cc-ink-soft)]">
                <Loader2
                  aria-hidden="true"
                  className="h-3.5 w-3.5 motion-safe:animate-spin"
                />
                Importing…
              </span>
            )}
          </div>
        </div>
      )}

      {manualOpen && (
        <form
          id="devices-manual-serial"
          onSubmit={handleManualSubmit}
          className="rounded-xl border border-[var(--cc-line)] bg-[var(--cc-muted)] p-4"
        >
          <label
            htmlFor={manualInputId}
            className="text-xs font-semibold text-[var(--cc-ink)]"
          >
            Serial number
          </label>
          <div className="mt-2 flex max-w-xl flex-col gap-2 sm:flex-row">
            <Input
              id={manualInputId}
              value={manualSerial}
              onChange={(event) => setManualSerial(event.target.value)}
              placeholder="CNXXXXXXXX"
              autoComplete="off"
              disabled={addingDisabled}
              className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] font-mono uppercase text-[var(--cc-ink)]"
            />
            <Button
              type="submit"
              variant="outline"
              disabled={addingDisabled}
              className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] hover:bg-[var(--cc-muted)]"
            >
              <Plus aria-hidden="true" />
              Add serial
            </Button>
          </div>
        </form>
      )}

      {feedback && (
        <p
          aria-live="polite"
          className={cn(
            "flex items-start gap-2 text-xs leading-5",
            feedbackTone === "error"
              ? "text-[var(--cc-danger)]"
              : feedbackTone === "imported"
                ? "text-[var(--cc-accent)]"
                : "text-[var(--cc-ink-soft)]"
          )}
        >
          {feedbackTone === "error" ? (
            <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
          ) : feedbackTone === "imported" ? (
            <FileCheck aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
          ) : null}
          <span>{feedback}</span>
        </p>
      )}

      <section aria-labelledby="device-table-title">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h3 id="device-table-title" className="text-sm font-semibold">
              Device table
            </h3>
            <p className="mt-1 text-xs leading-5 text-[var(--cc-ink-soft)]">
              Edit serials, subscription overrides, and enabled add-on values
              here. Every enabled add-on requires a value for every device.
            </p>
          </div>
          <span className="text-xs font-semibold tabular-nums text-[var(--cc-ink-soft)]">
            {counterLabel}
          </span>
        </div>

        <div className="mt-3 overflow-x-auto rounded-xl border border-[var(--cc-line)]">
          <table className="w-full min-w-[48rem] border-collapse text-left text-xs">
            <thead className="bg-[var(--cc-muted)] text-[0.625rem] uppercase tracking-[0.1em] text-[var(--cc-ink-faint)]">
              <tr>
                <th className="px-4 py-3 font-bold">Serial number</th>
                <th className="px-4 py-3 font-bold">Model</th>
                <th className="px-4 py-3 font-bold">MAC address</th>
                <th className="w-64 px-4 py-3 font-bold">Subscription</th>
                {enabledSteps.map((step) => (
                  <th
                    key={step.key}
                    data-field-type={step.field.type}
                    className="min-w-56 px-4 py-3 font-bold"
                  >
                    {step.label}
                    {/* aria-label on a generic span is ignored, so the
                        asterisk would announce as "star". Hide the glyph and
                        give the column a real accessible suffix instead. */}
                    <span aria-hidden="true" className="ml-1 text-[var(--cc-danger)]">
                      *
                    </span>
                    <span className="sr-only">(required)</span>
                  </th>
                ))}
                <th className="w-14 px-4 py-3">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {devices.length === 0 ? (
                <tr>
                  <td
                    colSpan={5 + enabledSteps.length}
                    className="bg-[var(--cc-raised)] px-4 py-10 text-center text-sm text-[var(--cc-ink-soft)]"
                  >
                    Select from inventory, upload a CSV, or enter a serial.
                  </td>
                </tr>
              ) : (
                devices.map((device) => {
                  const currentSubscriptionIsListed = subscriptions.some(
                    (subscription) =>
                      subscription.key === device.subscriptionOverrideKey
                  );
                  return (
                    <tr
                      key={device.id}
                      className="border-t border-[var(--cc-line)] bg-[var(--cc-raised)] [&>td]:align-top"
                    >
                      <td className="min-w-44 px-3 py-2">
                        <Input
                          value={device.serial}
                          onChange={(event) =>
                            updateSerial(device.id, event.target.value)
                          }
                          aria-label={`Serial number for ${device.serial}`}
                          className="h-8 border-[var(--cc-line)] bg-[var(--cc-surface)] font-mono text-xs font-semibold uppercase text-[var(--cc-ink)]"
                        />
                      </td>
                      <td className="px-4 py-2 text-[var(--cc-ink-soft)]">
                        {device.model || "Not reported"}
                      </td>
                      <td className="px-4 py-2 font-mono text-[var(--cc-ink-soft)]">
                        {device.mac || "Not reported"}
                      </td>
                      <td className="px-3 py-2">
                        <Select
                          value={
                            device.subscriptionOverrideKey ||
                            BATCH_DEFAULT_VALUE
                          }
                          onValueChange={(value) =>
                            updateSubscription(device.id, value)
                          }
                        >
                          <SelectTrigger
                            aria-label={`Subscription for ${device.serial}`}
                            className="h-8 border-[var(--cc-line)] bg-[var(--cc-surface)] text-xs text-[var(--cc-ink)]"
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value={BATCH_DEFAULT_VALUE}>
                              Batch default
                            </SelectItem>
                            {device.subscriptionOverrideKey &&
                              !currentSubscriptionIsListed && (
                                <SelectItem
                                  value={device.subscriptionOverrideKey}
                                >
                                  {device.subscriptionOverrideKey}
                                </SelectItem>
                              )}
                            {subscriptions.map((subscription) => (
                              <SelectItem
                                key={subscription.key}
                                value={subscription.key}
                                disabled={!subscriptionIsAvailable(subscription)}
                              >
                                {subscription.key} · {subscription.type} ·{" "}
                                {subscription.available} available
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </td>
                      {enabledSteps.map((step) => {
                        const value = inputValueForStep(device, step);
                        const validation = validateAddOnField(
                          step.field,
                          value,
                          step.label
                        );
                        const inputId = addOnInputId(device.id, step.key);
                        const errorId = `${inputId}-error`;
                        const helpId = `${inputId}-help`;
                        const fieldHasError =
                          validation.empty || !validation.valid;
                        const showFieldError =
                          fieldHasError &&
                          (revealNonce > 0 || touchedAddOnInputs.has(inputId));
                        const fieldError = validation.empty
                          ? `${step.label} is required while this add-on is enabled.`
                          : validation.error;

                        return (
                          <td
                            key={step.key}
                            className="min-w-56 px-3 py-2 align-top"
                          >
                            {step.field.type === "bool" ? (
                              <Select
                                value={value || ADD_ON_UNSET_VALUE}
                                onValueChange={(nextValue) =>
                                  updateAddOnInput(
                                    device.id,
                                    step.key,
                                    nextValue === ADD_ON_UNSET_VALUE
                                      ? ""
                                      : nextValue
                                  )
                                }
                              >
                                <SelectTrigger
                                  id={inputId}
                                  aria-label={`${step.label} for ${device.serial}`}
                                  aria-required="true"
                                  aria-invalid={showFieldError}
                                  aria-describedby={
                                    showFieldError ? errorId : helpId
                                  }
                                  onBlur={() => markAddOnInputTouched(inputId)}
                                  className={cn(
                                    "h-8 border-[var(--cc-line)] bg-[var(--cc-surface)] text-xs text-[var(--cc-ink)]",
                                    showFieldError &&
                                      "border-[var(--cc-danger)] focus:ring-[var(--cc-danger)]"
                                  )}
                                >
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value={ADD_ON_UNSET_VALUE}>
                                    {step.field.required
                                      ? "Choose true or false"
                                      : "Not set"}
                                  </SelectItem>
                                  <SelectItem value="true">True</SelectItem>
                                  <SelectItem value="false">False</SelectItem>
                                </SelectContent>
                              </Select>
                            ) : (
                              <Input
                                id={inputId}
                                type={
                                  step.field.type === "int" ? "number" : "text"
                                }
                                step={
                                  step.field.type === "int" ? 1 : undefined
                                }
                                value={value}
                                onChange={(event) =>
                                  updateAddOnInput(
                                    device.id,
                                    step.key,
                                    event.target.value
                                  )
                                }
                                placeholder={placeholderForStep(step)}
                                aria-label={`${step.label} for ${device.serial}`}
                                aria-required="true"
                                aria-invalid={showFieldError}
                                aria-describedby={
                                  showFieldError ? errorId : helpId
                                }
                                onBlur={() => markAddOnInputTouched(inputId)}
                                className={cn(
                                  "h-8 border-[var(--cc-line)] bg-[var(--cc-surface)] text-xs text-[var(--cc-ink)]",
                                  showFieldError &&
                                    "border-[var(--cc-danger)] focus-visible:ring-[var(--cc-danger)]"
                                )}
                              />
                            )}
                            <div className="min-h-12 pt-1.5">
                              {showFieldError ? (
                                <p
                                  id={errorId}
                                  role={
                                    revealNonce === 0 ? "alert" : undefined
                                  }
                                  className="break-words text-[0.6875rem] leading-4 text-[var(--cc-danger)]"
                                >
                                  {fieldError}
                                </p>
                              ) : (
                                <p
                                  id={helpId}
                                  className="text-[0.6875rem] leading-4 text-[var(--cc-ink-faint)]"
                                >
                                  {step.field.type === "list[string]"
                                    ? "Separate items with commas."
                                    : step.field.help}
                                </p>
                              )}
                            </div>
                          </td>
                        );
                      })}
                      <td className="px-3 py-2 text-right">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label={`Remove ${device.serial}`}
                          onClick={() => removeDevice(device.id)}
                          className="h-8 w-8 text-[var(--cc-danger)] hover:bg-[var(--cc-danger-soft)] hover:text-[var(--cc-danger)]"
                        >
                          <Trash2 aria-hidden="true" className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
