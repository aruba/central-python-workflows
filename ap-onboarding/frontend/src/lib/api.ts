// Status endpoint response
export interface StatusResponse {
  creds_ok: boolean;
  classic_creds_ok: boolean;
  creds_valid: boolean;
  classic_creds_valid: boolean;
  creds_error?: string;
  classic_creds_error?: string;
  busy: boolean;
}

// Lookups endpoint response. `errors` keys: `sites`, `site_collections`,
// `device_groups`, `subscriptions`, `applications`, `devices`, `new_central`,
// `classic_central`. When any key is present, that lookup failed and the
// corresponding list will be empty.
export interface SubscriptionLookup {
  key: string;
  type: string;
  available: number;
}

export interface ApplicationLookup {
  name: string;
  region: string;
}

export interface LookupDevice {
  serial: string;
  model: string | null;
  mac: string | null;
}

export interface LookupsResponse {
  sites: string[];
  site_collections: string[];
  device_groups: string[];
  subscriptions: SubscriptionLookup[];
  applications: ApplicationLookup[];
  devices: LookupDevice[];
  device_functions: string[];
  profile_types: string[];
  device_types: string[];
  errors: Record<string, string>;
}

export interface CreateSiteRequest {
  name: string;
  address: string;
  city: string;
  state: string;
  country: string;
  zipcode: string;
  timezone: string;
}

export interface GeoCountry {
  code: string;
  timezones: string[];
}

export interface GeoResponse {
  countries: GeoCountry[];
}

export interface CreateGroupRequest {
  name: string;
}

export interface CreatedEntityResponse {
  name: string;
  created: boolean;
}

export interface LimitsResponse {
  max_devices: number;
}

export interface FieldSpec {
  type: "string" | "list[string]" | "bool" | "int";
  required: boolean;
  max_len: number | null;
  pattern: string | null;
  help: string;
  example: unknown;
}

export interface StepMeta {
  key: string;
  label: string;
  description: string;
  field: FieldSpec;
}

// Run endpoint response
export interface RunResponse {
  run_id: string;
}

// Onboarding pre-flight response
export interface PreflightResponse {
  ok: boolean;
  missing_sites: string[];
  missing_device_groups: string[];
  // Keyed "unified" / "classic". Populated when a credential fails
  // verification, in which case the missing_* lists are empty because the
  // Central prerequisite checks never ran.
  credential_errors?: Record<string, string>;
}

// Parse upload endpoint response
export interface ParseUploadResponse {
  defaults: Record<string, unknown>;
  sites: string[];
  device_groups: string[];
  configuration_profiles: unknown[];
  devices: unknown[];
}

// Results folder listing response
export interface ResultsFolderResponse {
  folder: string;
  files: string[];
}

// Results list response (all folders)
export interface ResultsListResponse {
  folders: string[];
}

// Credentials status response
export interface CredentialsStatusResponse {
  creds_valid: boolean;
  classic_valid: boolean;
}

// Save credentials response
export interface SaveCredentialsResponse {
  creds_valid: boolean;
  classic_valid: boolean;
  errors: Record<string, string>;
}

// Save credentials request
export interface SaveCredentialsRequest {
  cluster: string;
  unified: {
    client_id: string;
    client_secret: string;
    workspace_id: string;
  };
  classic: {
    access_token: string;
  };
}

// Common error handler
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const json = await response.json();
      if (json.detail) {
        detail = json.detail;
      }
    } catch {
      // If response is not JSON, use the default message
    }
    throw new Error(detail);
  }
  return response.json();
}

// API functions
export async function getStatus(): Promise<StatusResponse> {
  const response = await fetch("/api/status");
  return handleResponse<StatusResponse>(response);
}

export async function getLookups(): Promise<LookupsResponse> {
  const response = await fetch("/api/lookups");
  return handleResponse<LookupsResponse>(response);
}

export async function getGeo(): Promise<GeoResponse> {
  const response = await fetch("/api/geo");
  return handleResponse<GeoResponse>(response);
}

export async function createSite(
  request: CreateSiteRequest
): Promise<CreatedEntityResponse> {
  const response = await fetch("/api/sites", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return handleResponse<CreatedEntityResponse>(response);
}

export async function createGroup(
  request: CreateGroupRequest
): Promise<CreatedEntityResponse> {
  const response = await fetch("/api/groups", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return handleResponse<CreatedEntityResponse>(response);
}

export async function getLimits(): Promise<LimitsResponse> {
  const response = await fetch("/api/limits");
  return handleResponse<LimitsResponse>(response);
}

export async function getSteps(): Promise<StepMeta[]> {
  const response = await fetch("/api/steps");
  return handleResponse<StepMeta[]>(response);
}

export async function startRun(
  mode: string,
  variables: Record<string, unknown>
): Promise<RunResponse> {
  const response = await fetch("/api/run", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ mode, variables }),
  });
  return handleResponse<RunResponse>(response);
}

export function getEventsUrl(runId: string): string {
  return `/api/events/${runId}`;
}

export async function runOnboardingPreflight(
  variables: Record<string, unknown>
): Promise<PreflightResponse> {
  const response = await fetch("/api/onboarding/preflight", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ variables }),
  });
  return handleResponse<PreflightResponse>(response);
}

export async function parseUpload(file: File): Promise<ParseUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch("/api/parse-upload", {
    method: "POST",
    body: formData,
  });
  return handleResponse<ParseUploadResponse>(response);
}

export async function listResults(): Promise<ResultsListResponse> {
  const response = await fetch("/api/results");
  return handleResponse<ResultsListResponse>(response);
}

export async function listResultsFolder(
  folderName: string
): Promise<ResultsFolderResponse> {
  const response = await fetch(`/api/results/${encodeURIComponent(folderName)}`);
  return handleResponse<ResultsFolderResponse>(response);
}

export function getResultFileUrl(folderName: string, filename: string): string {
  return `/api/results/${encodeURIComponent(folderName)}/${encodeURIComponent(filename)}`;
}

export async function saveCredentials(
  req: SaveCredentialsRequest
): Promise<SaveCredentialsResponse> {
  const response = await fetch("/api/credentials", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(req),
  });
  return handleResponse<SaveCredentialsResponse>(response);
}

export async function getCredentialsStatus(): Promise<CredentialsStatusResponse> {
  const response = await fetch("/api/credentials/status");
  return handleResponse<CredentialsStatusResponse>(response);
}

export interface GetCredentialsResponse {
  cluster: string | null;
  unified: {
    saved: boolean;
    mode_safe: boolean;
    client_id: string;
    client_id_present: boolean;
    client_secret: string;
    client_secret_present: boolean;
    workspace_id: string;
    workspace_id_present: boolean;
  } | null;
  classic: {
    saved: boolean;
    mode_safe: boolean;
    access_token: string;
    access_token_present: boolean;
  } | null;
}

export async function getCredentials(): Promise<GetCredentialsResponse> {
  const response = await fetch("/api/credentials");
  return handleResponse<GetCredentialsResponse>(response);
}
