import type { RunResultsData } from "@/components/RunResultsStage";
import type {
  DeviceState,
  DeviceStepState,
  RawEvent,
  StepStatus,
} from "@/lib/events";

const CORE_STEP_KEYS = new Set([
  "glp_application",
  "glp_subscription",
  "firmware_check",
  "site_assoc",
  "device_function",
  "group_assign",
  "provision",
]);
const REGISTERED_ADD_ON_KEYS = ["hostname"];

export interface ResultExportRow {
  exportDateTime: string;
  serial: string;
  model: string;
  effectiveSubscription: string;
  glpApplicationStatus: string;
  glpSubscriptionStatus: string;
  firmwareCheckStatus: string;
  discoveredFirmware: string;
  minimumFirmware: string;
  siteAssocStatus: string;
  deviceFunctionStatus: string;
  groupAssignStatus: string;
  provisionStatus: string;
  addOnSteps: Record<string, DeviceStepState | undefined>;
  overallStatus: string;
  reason: string;
  failedStep: string;
  errorDetails: string;
  warningSteps: string;
  warningDetails: string;
}

function formatDateTime(timestamp: number): string {
  const date = new Date(timestamp);
  const pad = (value: number) => String(value).padStart(2, "0");
  return [
    date.getFullYear(),
    "-",
    pad(date.getMonth() + 1),
    "-",
    pad(date.getDate()),
    " ",
    pad(date.getHours()),
    ":",
    pad(date.getMinutes()),
    ":",
    pad(date.getSeconds()),
  ].join("");
}

function displayStatus(status: StepStatus | undefined): string {
  if (!status || status === "pending") return "";
  if (status === "in_progress") return "In Progress";
  return status[0].toUpperCase() + status.slice(1);
}

function eventText(
  events: RawEvent[],
  serial: string,
  step: string,
  field: "error" | "message"
): string {
  const event = events.find(
    (candidate) =>
      candidate.type === "step" &&
      candidate.serial === serial &&
      candidate.step === step &&
      typeof candidate[field] === "string"
  );
  return typeof event?.[field] === "string" ? event[field] : "";
}

function stepFailures(
  device: DeviceState,
  keys: string[]
): Array<{ step: string; error: string }> {
  return keys.flatMap((step) => {
    const state = device.steps[step];
    return state?.status === "failed" && state.error
      ? [{ step, error: state.error }]
      : [];
  });
}

function skippedReason(
  data: RunResultsData,
  device: DeviceState
): string {
  const eventMessage = eventText(
    data.events,
    device.serial,
    "firmware_check",
    "message"
  );
  if (eventMessage) return eventMessage;

  const current = device.firmware.currentVersion;
  const minimum = device.firmware.minimumVersion;
  if (current && minimum) {
    return `Firmware check: ${current} is below the minimum ${minimum}`;
  }
  return device.firmware.error ?? "Firmware did not meet the required minimum";
}

function titleCaseStep(step: string): string {
  return step
    .split("_")
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join("_");
}

export function getAddOnStepKeys(data: RunResultsData): string[] {
  const discovered = data.plan.flatMap((planDevice) =>
    Object.keys(data.devices[planDevice.serial]?.steps ?? {})
  );
  return Array.from(
    new Set([
      ...REGISTERED_ADD_ON_KEYS,
      ...discovered.filter((step) => !CORE_STEP_KEYS.has(step)),
    ])
  );
}

export function buildResultExportRows(
  data: RunResultsData
): ResultExportRow[] {
  const exportDateTime = formatDateTime(
    data.finishedAt ?? data.startedAt ?? Date.now()
  );
  const addOnKeys = getAddOnStepKeys(data);

  return data.plan.map((planDevice) => {
    const device = data.devices[planDevice.serial] ?? {
      serial: planDevice.serial,
      steps: {},
      firmware: { status: "pending" as const },
    };
    const coreFailures = stepFailures(device, [
      "glp_application",
      "glp_subscription",
      "site_assoc",
      "device_function",
      "group_assign",
      "provision",
    ]);
    if (device.firmware.status === "failed" && device.firmware.error) {
      coreFailures.splice(1, 0, {
        step: "firmware_check",
        error: device.firmware.error,
      });
    }
    const warnings = stepFailures(device, addOnKeys);
    const failedStep = coreFailures.map(({ step }) => step).join(", ");
    const errorDetails = coreFailures.map(({ error }) => error).join("; ");
    const warningSteps = warnings.map(({ step }) => step).join(", ");
    const warningDetails = warnings.map(({ error }) => error).join("; ");
    const reason =
      device.overall === "WARNING"
        ? warningDetails
        : device.overall === "Failed"
          ? errorDetails
          : device.overall === "Skipped (firmware)"
            ? skippedReason(data, device)
            : "";

    return {
      exportDateTime,
      serial: planDevice.serial,
      model: planDevice.model ?? device.model ?? "",
      effectiveSubscription:
        planDevice.subscriptionKey ?? device.subscriptionKey ?? "",
      glpApplicationStatus: displayStatus(
        device.steps.glp_application?.status
      ),
      glpSubscriptionStatus: displayStatus(
        device.steps.glp_subscription?.status
      ),
      firmwareCheckStatus: displayStatus(device.firmware.status),
      discoveredFirmware: device.firmware.currentVersion ?? "",
      minimumFirmware: device.firmware.minimumVersion ?? "",
      siteAssocStatus: displayStatus(device.steps.site_assoc?.status),
      deviceFunctionStatus: displayStatus(
        device.steps.device_function?.status
      ),
      groupAssignStatus: displayStatus(device.steps.group_assign?.status),
      provisionStatus: displayStatus(device.steps.provision?.status),
      addOnSteps: Object.fromEntries(
        addOnKeys.map((step) => [step, device.steps[step]])
      ),
      overallStatus: device.overall ?? "In Progress",
      reason,
      failedStep,
      errorDetails,
      warningSteps,
      warningDetails,
    };
  });
}

function csvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

export function buildResultsCsv(data: RunResultsData): string {
  const addOnKeys = getAddOnStepKeys(data);
  const headers = [
    "Export_Date_Time",
    "Serial_Number",
    "GLP_Application_Status",
    "GLP_Subscription_Status",
    "Firmware_Check_Status",
    "Discovered_Firmware",
    "Minimum_Firmware",
    "Site_Assoc_Status",
    "Device_Function_Status",
    "Group_Assign_Status",
    "Provision_Status",
    ...addOnKeys.flatMap((step) => {
      const column = titleCaseStep(step);
      return [`${column}_Status`, `${column}_Error`];
    }),
    "Overall_Status",
    "Effective_Subscription",
    "Reason",
    "Failed_Step",
    "Error_Details",
    "Warning_Steps",
    "Warning_Details",
  ];
  const rows = buildResultExportRows(data).map((row) => [
    row.exportDateTime,
    row.serial,
    row.glpApplicationStatus,
    row.glpSubscriptionStatus,
    row.firmwareCheckStatus,
    row.discoveredFirmware,
    row.minimumFirmware,
    row.siteAssocStatus,
    row.deviceFunctionStatus,
    row.groupAssignStatus,
    row.provisionStatus,
    ...addOnKeys.flatMap((step) => [
      displayStatus(row.addOnSteps[step]?.status),
      row.addOnSteps[step]?.error ?? "",
    ]),
    row.overallStatus,
    row.effectiveSubscription,
    row.reason,
    row.failedStep,
    row.errorDetails,
    row.warningSteps,
    row.warningDetails,
  ]);

  return [
    headers.map(csvCell).join(","),
    ...rows.map((row) => row.map(csvCell).join(",")),
  ].join("\r\n");
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function reportTimestamp(timestamp: number | undefined): string {
  return timestamp === undefined
    ? "Not recorded"
    : new Date(timestamp).toLocaleString();
}

export function buildHtmlReport(data: RunResultsData): string {
  const rows = buildResultExportRows(data);
  const { summary } = data;
  const tableRows = rows
    .map(
      (row) => `<tr>
<td><code>${escapeHtml(row.serial)}</code></td>
<td>${escapeHtml(row.model || "Unknown")}</td>
<td>${escapeHtml(row.overallStatus)}</td>
<td>${escapeHtml(row.reason)}</td>
<td><code>${escapeHtml(row.effectiveSubscription || "None")}</code></td>
<td>${escapeHtml(row.discoveredFirmware || "Not discovered")}</td>
</tr>`
    )
    .join("");

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AP onboarding results</title>
<style>
:root{color-scheme:light}body{margin:40px;color:#181e2c;background:#f0f3fa;font:14px/1.5 system-ui,sans-serif}main{max-width:1200px;margin:auto}h1{margin:0 0 4px;font-size:28px}p{color:#4e566b}.summary{display:grid;grid-template-columns:repeat(4,1fr);margin:24px 0;overflow:hidden;border:1px solid #cbd3e3;border-radius:10px;background:#fcfdff}.summary div{padding:16px;border-right:1px solid #cbd3e3}.summary div:last-child{border:0}.summary strong{display:block;font-size:24px}table{width:100%;border-collapse:collapse;background:#fcfdff}th,td{padding:9px;border:1px solid #cbd3e3;text-align:left;vertical-align:top}th{background:#e7ecf6;font-size:11px;text-transform:uppercase}code{font-size:12px;overflow-wrap:anywhere}@media(max-width:700px){body{margin:16px}.summary{grid-template-columns:1fr 1fr}.summary div:nth-child(2){border-right:0}.summary div:nth-child(-n+2){border-bottom:1px solid #cbd3e3}.table-wrap{overflow-x:auto}}
</style>
</head>
<body>
<main>
<h1>AP onboarding results</h1>
<p>Run <code>${escapeHtml(data.runId)}</code><br>Started: ${escapeHtml(reportTimestamp(data.startedAt))}<br>Finished: ${escapeHtml(reportTimestamp(data.finishedAt))}</p>
<section class="summary" aria-label="Run summary">
<div><strong>${summary.onboarded}</strong>Onboarded</div>
<div><strong>${summary.warnings}</strong>With warnings</div>
<div><strong>${summary.failed}</strong>Failed</div>
<div><strong>${summary.skipped}</strong>Skipped</div>
</section>
<div class="table-wrap">
<table>
<thead><tr><th>Serial</th><th>Model</th><th>Outcome</th><th>Reason</th><th>Effective subscription</th><th>Discovered firmware</th></tr></thead>
<tbody>${tableRows}</tbody>
</table>
</div>
</main>
</body>
</html>`;
}

export function resultsExportBaseName(data: RunResultsData): string {
  if (data.resultsDir && /^results_[A-Za-z0-9T-]+$/.test(data.resultsDir)) {
    return data.resultsDir;
  }
  const timestamp = new Date(
    data.finishedAt ?? data.startedAt ?? Date.now()
  )
    .toISOString()
    .replace(/\.\d{3}Z$/, "Z")
    .replace(/-/g, "")
    .replace(/:/g, "");
  return `results_${timestamp}`;
}

export function downloadText(
  content: string,
  filename: string,
  mimeType: string
): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
