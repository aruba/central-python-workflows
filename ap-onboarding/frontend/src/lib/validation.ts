import type { FieldSpec } from "@/lib/api";

// ─── Add-on field validation ──────────────────────────────────────────────────

export type AddOnFieldValue = string | string[] | boolean | number;

export interface AddOnFieldValidation {
  valid: boolean;
  empty: boolean;
  value?: AddOnFieldValue;
  error?: string;
}

function emptyAddOnResult(
  field: FieldSpec,
  label: string
): AddOnFieldValidation {
  if (field.required) {
    return {
      valid: false,
      empty: true,
      error:
        field.type === "list[string]"
          ? `${label} must contain at least one item.`
          : `${label} is required.`,
    };
  }
  return { valid: true, empty: true };
}

function matchesFullPattern(value: string, pattern: string): boolean {
  const expression = new RegExp(`^(?:${pattern})$`, "u");
  const match = expression.exec(value);
  return match !== null && match[0].length === value.length;
}

/**
 * Convert a device-table editor value into the type declared by the registry
 * and apply the same required, max_len, and full-match pattern semantics as
 * steps.models.Field.validate.
 */
export function validateAddOnField(
  field: FieldSpec,
  rawValue: string,
  label: string
): AddOnFieldValidation {
  if (!rawValue.trim()) {
    return emptyAddOnResult(field, label);
  }

  if (field.type === "bool") {
    if (rawValue !== "true" && rawValue !== "false") {
      return {
        valid: false,
        empty: false,
        error: `${label} must be true or false.`,
      };
    }
    return {
      valid: true,
      empty: false,
      value: rawValue === "true",
    };
  }

  if (field.type === "int") {
    const value = Number(rawValue);
    if (!Number.isInteger(value)) {
      return {
        valid: false,
        empty: false,
        error: `${label} must be a whole number.`,
      };
    }
    return { valid: true, empty: false, value };
  }

  const values =
    field.type === "list[string]"
      ? rawValue.split(",").map((item) => item.trim())
      : [rawValue];

  if (
    field.type === "list[string]" &&
    field.max_len !== null &&
    values.length > field.max_len
  ) {
    return {
      valid: false,
      empty: false,
      error: `${label} must contain at most ${field.max_len} items.`,
    };
  }
  if (
    field.type === "string" &&
    field.max_len !== null &&
    [...rawValue].length > field.max_len
  ) {
    return {
      valid: false,
      empty: false,
      error: `${label} must be at most ${field.max_len} characters.`,
    };
  }

  if (field.pattern !== null) {
    try {
      const invalidItem = values.find(
        (value) => !matchesFullPattern(value, field.pattern!)
      );
      if (invalidItem !== undefined) {
        return {
          valid: false,
          empty: false,
          error: `${label} must match ${field.pattern}.`,
        };
      }
    } catch {
      return {
        valid: false,
        empty: false,
        error: `${label} has an invalid validation pattern.`,
      };
    }
  }

  return {
    valid: true,
    empty: false,
    value: field.type === "list[string]" ? values : rawValue,
  };
}

// ─── Onboarding validation ────────────────────────────────────────────────────

const SUPPORTED_DEVICE_TYPES = new Set(["ACCESS_POINT"]);
const MAX_DEVICES_PER_RUN = 50;
const CENTRAL_DEVICE_FIELDS = [
  "device_type",
  "device_function",
  "device_group",
  "site",
] as const;

type CentralField = (typeof CENTRAL_DEVICE_FIELDS)[number];

function isNonEmptyString(value: unknown): boolean {
  return typeof value === "string" && value.trim().length > 0;
}

function deviceHasOwnValue(
  device: Record<string, unknown>,
  field: CentralField
): boolean {
  return field in device && isNonEmptyString(device[field]);
}

/** Resolve a field, treating empty strings as missing on both sides. */
function resolveField(
  device: Record<string, unknown>,
  defaults: Record<string, unknown>,
  field: CentralField
): unknown {
  if (deviceHasOwnValue(device, field)) return device[field];
  return defaults[field];
}

/**
 * Validate a workflow variables object for the onboarding flow.
 * Returns a list of error strings. Empty list means valid.
 */
export function validateOnboarding(data: {
  defaults?: Record<string, unknown>;
  devices?: unknown[];
}): string[] {
  const errors: string[] = [];
  const defaults = data.defaults ?? {};

  // Must have a non-empty devices array
  if (!Array.isArray(data.devices) || data.devices.length === 0) {
    errors.push(
      "Missing or invalid 'devices' list (at least one device required)"
    );
    return errors; // Can't continue without devices
  }

  if (data.devices.length > MAX_DEVICES_PER_RUN) {
    errors.push(
      `Too many devices (${data.devices.length}). A maximum of ${MAX_DEVICES_PER_RUN} devices is allowed per onboarding run.`
    );
  }

  // Validate defaults device_type if present
  if (
    "device_type" in defaults &&
    !SUPPORTED_DEVICE_TYPES.has(defaults.device_type as string)
  ) {
    errors.push(
      `defaults.device_type '${defaults.device_type}' is unsupported. Only ACCESS_POINT is supported by this workflow.`
    );
  }

  const serialsSeen = new Set<string>();

  for (let idx = 0; idx < data.devices.length; idx++) {
    const device = data.devices[idx];

    if (typeof device !== "object" || device === null || Array.isArray(device)) {
      errors.push(`Device ${idx} must be an object`);
      continue;
    }

    const dev = device as Record<string, unknown>;

    // Must have serial_number
    if (!("serial_number" in dev)) {
      errors.push(`Device ${idx} missing required field: serial_number`);
      continue; // Can't identify without serial
    }

    const serial = dev.serial_number as string;

    // No duplicate serials
    if (serialsSeen.has(serial)) {
      errors.push(`Duplicate serial_number '${serial}' found in devices list.`);
    }
    serialsSeen.add(serial);

    // application_assignment not allowed at device level
    if ("application_assignment" in dev) {
      errors.push(
        `Device ${idx} has application_assignment. Use defaults.application_assignment for a single workflow-wide assignment.`
      );
    }

    // Each required Central field must resolve to a non-empty value on the
    // device or in defaults. For device_group / site, an empty defaults value
    // is treated as "not provided" — they are only required from defaults if
    // at least one device lacks its own value.
    for (const field of CENTRAL_DEVICE_FIELDS) {
      const deviceHas = deviceHasOwnValue(dev, field);
      const defaultsHas = isNonEmptyString(defaults[field]);
      if (!deviceHas && !defaultsHas) {
        errors.push(
          `Device '${serial}' missing required field '${field}' and no defaults.${field} was provided.`
        );
      }
    }

    // device_type must be supported
    const deviceType = resolveField(dev, defaults, "device_type") as
      | string
      | undefined;
    if (deviceType !== undefined && !SUPPORTED_DEVICE_TYPES.has(deviceType)) {
      errors.push(
        `Device '${serial}' has unsupported device_type '${deviceType}'. Only ACCESS_POINT is supported by this workflow.`
      );
    }

    // device_function must resolve to a non-empty string
    if (!isNonEmptyString(resolveField(dev, defaults, "device_function"))) {
      errors.push(
        `Device '${serial}' device_function must be a non-empty string`
      );
    }

    // device_group must resolve to a non-empty string
    if (!isNonEmptyString(resolveField(dev, defaults, "device_group"))) {
      errors.push(
        `Device '${serial}' device_group must be a non-empty string`
      );
    }

    // site must resolve to a non-empty string
    if (!isNonEmptyString(resolveField(dev, defaults, "site"))) {
      errors.push(`Device '${serial}' site must be a non-empty string`);
    }

    // subscription_key must be a non-empty string if present
    if ("subscription_key" in dev) {
      if (!isNonEmptyString(dev.subscription_key)) {
        errors.push(
          `Device ${idx} subscription_key must be a non-empty string`
        );
      }
    }
  }

  return errors;
}

// ─── Network setup validation ─────────────────────────────────────────────────

type ProfileBinding = Record<string, unknown>;

/**
 * Validate a workflow variables object for the network setup flow.
 * Returns a list of error strings. Empty list means valid.
 */
export function validateNetworkSetup(data: {
  sites?: unknown[];
  site_collections?: unknown[];
  device_groups?: unknown[];
  configuration_profiles?: unknown[];
  defaults?: Record<string, unknown>;
}): string[] {
  const errors: string[] = [];

  // Must have at least one non-empty section
  const hasSites = Array.isArray(data.sites) && data.sites.length > 0;
  const hasSiteCollections =
    Array.isArray(data.site_collections) && data.site_collections.length > 0;
  const hasDeviceGroups =
    Array.isArray(data.device_groups) && data.device_groups.length > 0;
  const hasConfigProfiles =
    Array.isArray(data.configuration_profiles) &&
    data.configuration_profiles.length > 0;

  if (!hasSites && !hasSiteCollections && !hasDeviceGroups && !hasConfigProfiles) {
    errors.push(
      "network_setup requires at least one of: 'sites', 'site_collections', 'device_groups', or 'configuration_profiles'"
    );
  }

  // Validate configuration_profiles if present
  if (Array.isArray(data.configuration_profiles)) {
    for (let idx = 0; idx < data.configuration_profiles.length; idx++) {
      const binding = data.configuration_profiles[idx] as ProfileBinding;

      const hasSite = "site" in binding;
      const hasCollection = "site_collection" in binding;

      if (hasSite && hasCollection) {
        errors.push(
          `configuration_profiles[${idx}]: specify either 'site' or 'site_collection', not both`
        );
      } else if (!hasSite && !hasCollection) {
        errors.push(
          `configuration_profiles[${idx}]: must specify either 'site' or 'site_collection'`
        );
      }

      const profiles = binding.profiles;
      if (!Array.isArray(profiles) || profiles.length === 0) {
        const target = hasSite ? binding.site : binding.site_collection;
        errors.push(
          `configuration_profiles entry for '${target}' must have a non-empty 'profiles' list`
        );
      } else {
        for (let pidx = 0; pidx < profiles.length; pidx++) {
          const p = profiles[pidx] as Record<string, unknown>;
          if (!("profile_name" in p) && !("name" in p)) {
            errors.push(
              `configuration_profiles[${idx}].profiles[${pidx}] missing required field 'profile_name'`
            );
          }
        }
      }
    }
  }

  return errors;
}
