"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { toast } from "sonner";
import yaml from "js-yaml";
import { ChevronDown, ChevronRight, Plus, Trash2, Upload, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/PageHeader";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getLookups, startRun, parseUpload } from "@/lib/api";
import { validateNetworkSetup } from "@/lib/validation";

// ─── Types ────────────────────────────────────────────────────────────────────

interface SiteForm {
  name: string;
  address: string;
  city: string;
  state: string;
  country: string;
  zipcode: string;
  timezone: string;
}

interface GroupForm {
  group: string;
  device_type: string;
}

interface EditorState {
  sites: SiteForm[];
  groups: GroupForm[];
}

interface StoredEditorState {
  sites?: SiteForm[];
  groups?: unknown[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const STORAGE_KEY = "network_setup_editor_state";

const DEVICE_TYPE_OPTIONS = [
  { value: "ACCESS_POINT", label: "Access Point" },
] as const;

const DEFAULT_DEVICE_TYPE = DEVICE_TYPE_OPTIONS[0].value;

// Source of truth: routers/creates.py:14 (AP_GROUP_ATTRIBUTES).
const GROUP_ATTRIBUTES_BY_DEVICE_TYPE: Record<
  string,
  Record<string, unknown>
> = /* group-attributes-sync-start */ {
  "ACCESS_POINT": {
    "template_info": { "Wired": false },
    "group_properties": {
      "AllowedDevTypes": ["AccessPoints"],
      "Architecture": "AOS10",
      "ApNetworkRole": "Standard",
      "NewCentral": true
    }
  }
} /* group-attributes-sync-end */;

// Migration-only match for the default emitted by the pre-#59 editor.
const LEGACY_DEFAULT_GROUP_ATTRIBUTES = {
  group_properties: { NewCentral: true },
};

function makeSite(): SiteForm {
  return { name: "", address: "", city: "", state: "", country: "", zipcode: "", timezone: "" };
}

function normalizeSite(site: SiteForm): SiteForm {
  return {
    name: site.name,
    address: site.address,
    city: site.city,
    state: site.state,
    country: site.country,
    zipcode: site.zipcode,
    timezone: site.timezone,
  };
}

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, entryValue]) => [key, canonicalize(entryValue)]),
    );
  }
  return value;
}

function valuesMatch(left: unknown, right: unknown): boolean {
  return JSON.stringify(canonicalize(left)) === JSON.stringify(canonicalize(right));
}

function isSupportedDeviceType(value: unknown): value is string {
  return (
    typeof value === "string" &&
    DEVICE_TYPE_OPTIONS.some((option) => option.value === value)
  );
}

function deviceTypeForAttributes(attributes: unknown): string | null {
  const match = DEVICE_TYPE_OPTIONS.find((option) =>
    valuesMatch(attributes, GROUP_ATTRIBUTES_BY_DEVICE_TYPE[option.value]),
  );
  return match?.value ?? null;
}

function hasLegacyDefaultAttributes(value: unknown): boolean {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  let attributes = (value as Record<string, unknown>).group_attributes;
  if (typeof attributes === "string") {
    try {
      attributes = JSON.parse(attributes) as unknown;
    } catch {
      return false;
    }
  }
  return valuesMatch(attributes, LEGACY_DEFAULT_GROUP_ATTRIBUTES);
}

function normalizeGroup(
  value: unknown,
  allowLegacyDefault = false,
): GroupForm | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;

  const group = value as Record<string, unknown>;
  const name = String(group.group ?? "");
  if (isSupportedDeviceType(group.device_type)) {
    return { group: name, device_type: group.device_type };
  }

  let attributes = group.group_attributes;
  if (typeof attributes === "string") {
    try {
      attributes = JSON.parse(attributes) as unknown;
    } catch {
      return null;
    }
  }

  const deviceType = deviceTypeForAttributes(attributes);
  if (deviceType) return { group: name, device_type: deviceType };

  if (allowLegacyDefault && valuesMatch(attributes, LEGACY_DEFAULT_GROUP_ATTRIBUTES)) {
    return { group: name, device_type: DEFAULT_DEVICE_TYPE };
  }

  return null;
}

function makeGroup(): GroupForm {
  return { group: "", device_type: DEFAULT_DEVICE_TYPE };
}

interface BackendVariables {
  sites: SiteForm[];
  device_groups: { group: string; group_attributes: Record<string, unknown> }[];
}

function flattenToBackend(
  sites: SiteForm[],
  groups: GroupForm[]
): BackendVariables {
  return {
    sites,
    device_groups: groups.map((g) => ({
      group: g.group,
      group_attributes: GROUP_ATTRIBUTES_BY_DEVICE_TYPE[g.device_type],
    })),
  };
}

function validateGroupNames(
  groups: GroupForm[],
  existingGroupNames: string[],
): string[] {
  const errors: string[] = [];
  const existingNames = new Set(
    existingGroupNames.map((name) => name.trim().toLocaleLowerCase()),
  );
  const draftNames = new Set<string>();

  groups.forEach((group, idx) => {
    const name = group.group.trim();
    if (!name) {
      errors.push(`Device group ${idx + 1}: Group Name is required.`);
      return;
    }

    const normalizedName = name.toLocaleLowerCase();
    if (existingNames.has(normalizedName)) {
      errors.push(`Device group '${name}' already exists.`);
    }
    if (draftNames.has(normalizedName)) {
      errors.push(`Duplicate device group name '${name}' in this draft.`);
    }
    draftNames.add(normalizedName);
  });

  return errors;
}

function loadFromStorage(): StoredEditorState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StoredEditorState;
  } catch {
    return null;
  }
}

function saveToStorage(state: EditorState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore storage errors
  }
}

// ─── Section wrapper ──────────────────────────────────────────────────────────

function SectionCard({
  title,
  defaultOpen = true,
  children,
  action,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <Card>
      <Collapsible open={open} onOpenChange={setOpen}>
        <CardHeader className="pb-0">
          <div className="flex items-center justify-between">
            <CollapsibleTrigger asChild>
              <button
                type="button"
                className="flex items-center gap-2 text-left hover:opacity-80 transition-opacity"
              >
                {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                <CardTitle className="text-base">{title}</CardTitle>
              </button>
            </CollapsibleTrigger>
            {action}
          </div>
        </CardHeader>
        <CollapsibleContent>
          <CardContent className="pt-4">{children}</CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export interface NetworkSetupEditorProps {
  onRunStarted: (runId: string) => void;
}

export function NetworkSetupEditor({ onRunStarted }: NetworkSetupEditorProps) {
  const [sites, setSites] = useState<SiteForm[]>([makeSite()]);
  const [groups, setGroups] = useState<GroupForm[]>([]);
  const [existingGroupNames, setExistingGroupNames] = useState<string[]>([]);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [showConfirm, setShowConfirm] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load from localStorage on mount
  useEffect(() => {
    const saved = loadFromStorage();
    if (saved) {
      if (saved.sites && saved.sites.length > 0) setSites(saved.sites.map(normalizeSite));
      if (saved.groups) {
        const migratedGroups = saved.groups.filter(hasLegacyDefaultAttributes).length;
        const restoredGroups = saved.groups
          .map((group) => normalizeGroup(group, true))
          .filter((group): group is GroupForm => group !== null);
        setGroups(restoredGroups);

        const ignoredGroups = saved.groups.length - restoredGroups.length;
        if (ignoredGroups > 0) {
          toast.warning(
            `Ignored ${ignoredGroups} device group${ignoredGroups === 1 ? "" : "s"} from the saved draft because its attributes are not supported.`,
          );
        }
        if (migratedGroups > 0) {
          toast.warning(
            `Updated ${migratedGroups} legacy device group${migratedGroups === 1 ? "" : "s"} to the supported Access Point settings.`,
          );
        }
      }
    }
  }, []);

  // Existing names improve feedback, but a failed lookup must not block a run.
  useEffect(() => {
    let cancelled = false;
    getLookups()
      .then((lookups) => {
        if (!cancelled) setExistingGroupNames(lookups.device_groups ?? []);
      })
      .catch(() => {
        // The backend remains authoritative and will reject an existing name.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Debounced save to localStorage
  const debouncedSave = useCallback((state: EditorState) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => saveToStorage(state), 500);
  }, []);

  useEffect(() => {
    debouncedSave({ sites, groups });
  }, [sites, groups, debouncedSave]);

  // ── Sites helpers ─────────────────────────────────────────────────────────

  const updateSite = (idx: number, field: keyof SiteForm, value: string) => {
    setSites((prev) => prev.map((s, i) => (i === idx ? { ...s, [field]: value } : s)));
  };

  const addSite = () => setSites((prev) => [...prev, makeSite()]);

  const removeSite = (idx: number) => setSites((prev) => prev.filter((_, i) => i !== idx));

  // ── Groups helpers ────────────────────────────────────────────────────────

  const updateGroup = (idx: number, field: keyof GroupForm, value: string) => {
    setGroups((prev) => prev.map((g, i) => (i === idx ? { ...g, [field]: value } : g)));
  };

  const addGroup = () => setGroups((prev) => [...prev, makeGroup()]);

  const removeGroup = (idx: number) => setGroups((prev) => prev.filter((_, i) => i !== idx));

  // ── Import ────────────────────────────────────────────────────────────────

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const parsed = await parseUpload(file);
      const raw = parsed as unknown as Record<string, unknown>;

      const onboardingOnlyKeys = ["defaults", "devices"];
      const presentOnboardingKeys = onboardingOnlyKeys.filter((k) => {
        const v = raw[k];
        if (k === "devices") return Array.isArray(v) && (v as unknown[]).length > 0;
        return v && typeof v === "object" && Object.keys(v as Record<string, unknown>).length > 0;
      });
      const networkKeys = ["sites", "device_groups"];
      const hasNetworkContent = networkKeys.some(
        (k) => Array.isArray(raw[k]) && (raw[k] as unknown[]).length > 0,
      );
      if (presentOnboardingKeys.length > 0 && !hasNetworkContent) {
        toast.error(
          `This looks like an onboarding_variables.yaml (contains: ${presentOnboardingKeys.join(", ")}). ` +
            "Import it on the Onboarding page instead.",
        );
        return;
      }

      // Site collections and configuration profiles were removed from Network
      // Setup (#57, #58). A file that still carries them must not be dropped silently.
      const droppedCollections = Array.isArray(raw.site_collections)
        ? (raw.site_collections as unknown[]).length
        : 0;
      const droppedConfigurationProfiles = Array.isArray(raw.configuration_profiles)
        ? (raw.configuration_profiles as unknown[]).length
        : 0;
      let droppedDeviceGroups = 0;

      // Populate sites
      if (Array.isArray(raw.sites) && raw.sites.length > 0) {
        const importedSites: SiteForm[] = (raw.sites as Record<string, unknown>[]).map((s) => ({
          name: String(s.name ?? ""),
          address: String(s.address ?? ""),
          city: String(s.city ?? ""),
          state: String(s.state ?? ""),
          country: String(s.country ?? ""),
          zipcode: String(s.zipcode ?? ""),
          timezone: String(s.timezone ?? ""),
        }));
        setSites(importedSites);
      }

      // Populate device groups
      if (Array.isArray(raw.device_groups) && raw.device_groups.length > 0) {
        const importedGroups = (raw.device_groups as unknown[])
          .map((group) => normalizeGroup(group))
          .filter((group): group is GroupForm => group !== null);
        droppedDeviceGroups = raw.device_groups.length - importedGroups.length;
        setGroups(importedGroups);
      }

      if (
        droppedCollections > 0 ||
        droppedConfigurationProfiles > 0 ||
        droppedDeviceGroups > 0
      ) {
        const parts: string[] = [];
        if (droppedCollections > 0) {
          parts.push(
            `${droppedCollections} site collection${droppedCollections === 1 ? "" : "s"}`,
          );
        }
        if (droppedConfigurationProfiles > 0) {
          parts.push(
            `${droppedConfigurationProfiles} configuration profile binding${droppedConfigurationProfiles === 1 ? "" : "s"}`,
          );
        }
        if (droppedDeviceGroups > 0) {
          parts.push(
            `${droppedDeviceGroups} device group${droppedDeviceGroups === 1 ? "" : "s"} with unsupported attributes`,
          );
        }
        toast.warning(
          `Ignored ${parts.join(" and ")}. These entries cannot be represented in Network Setup.`,
        );
      }

      if (
        hasNetworkContent ||
        (droppedCollections === 0 && droppedConfigurationProfiles === 0)
      ) {
        toast.success("YAML imported successfully");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      toast.error(`Import failed: ${msg}`);
    } finally {
      // Reset input so same file can be re-imported
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // ── Export ────────────────────────────────────────────────────────────────

  const handleExport = () => {
    try {
      const variables = flattenToBackend(sites, groups);
      const yamlStr = yaml.dump(variables, { lineWidth: 120 });
      const blob = new Blob([yamlStr], { type: "text/yaml" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "network_setup_variables.yaml";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      toast.error(`Export failed: ${msg}`);
    }
  };

  // ── Submit ────────────────────────────────────────────────────────────────

  const handleSubmitClick = () => {
    const variables = flattenToBackend(sites, groups);
    const errors = [
      ...validateNetworkSetup(variables),
      ...validateGroupNames(groups, existingGroupNames),
    ];
    if (errors.length > 0) {
      setValidationErrors(errors);
      return;
    }
    setValidationErrors([]);
    setShowConfirm(true);
  };

  const handleConfirm = async () => {
    setShowConfirm(false);
    setIsSubmitting(true);
    try {
      const variables = flattenToBackend(sites, groups);
      const { run_id } = await startRun("network_setup", variables as unknown as Record<string, unknown>);
      onRunStarted(run_id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      toast.error(`Failed to start run: ${msg}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  const siteCount = sites.filter((s) => s.name.trim()).length;
  const groupCount = groups.filter((g) => g.group.trim()).length;

  return (
    <>
      <div className="mx-auto max-w-5xl space-y-6">
        {/* Page header */}
        <PageHeader
          title="Network Setup"
          description="Configure sites and device groups"
          actions={
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept=".yaml,.yml"
                className="hidden"
                onChange={handleImport}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="h-4 w-4 mr-2" />
                Import YAML
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={handleExport}>
                <Download className="h-4 w-4 mr-2" />
                Export YAML
              </Button>
            </>
          }
        />

        {/* Sites section */}
        <SectionCard
          title={`Sites${siteCount > 0 ? ` (${siteCount})` : ""}`}
          action={
            <Button type="button" variant="outline" size="sm" onClick={addSite}>
              <Plus className="h-4 w-4 mr-1" />
              Add Site
            </Button>
          }
        >
          {sites.length === 0 ? (
            <p className="text-sm text-muted-foreground">No sites added yet.</p>
          ) : (
            <div className="space-y-4">
              {sites.map((site, idx) => (
                <div key={idx} className="border border-border rounded-lg p-4 relative">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-medium text-muted-foreground">
                      Site {idx + 1}{site.name ? `: ${site.name}` : ""}
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive hover:text-destructive"
                      onClick={() => removeSite(idx)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label className="text-xs">Name *</Label>
                      <Input
                        value={site.name}
                        onChange={(e) => updateSite(idx, "name", e.target.value)}
                        placeholder="Site name"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Address</Label>
                      <Input
                        value={site.address}
                        onChange={(e) => updateSite(idx, "address", e.target.value)}
                        placeholder="Street address"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">City</Label>
                      <Input
                        value={site.city}
                        onChange={(e) => updateSite(idx, "city", e.target.value)}
                        placeholder="City"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">State</Label>
                      <Input
                        value={site.state}
                        onChange={(e) => updateSite(idx, "state", e.target.value)}
                        placeholder="State / Province"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Country</Label>
                      <Input
                        value={site.country}
                        onChange={(e) => updateSite(idx, "country", e.target.value)}
                        placeholder="Country"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">ZIP / Postal Code</Label>
                      <Input
                        value={site.zipcode}
                        onChange={(e) => updateSite(idx, "zipcode", e.target.value)}
                        placeholder="ZIP code"
                      />
                    </div>
                    <div className="col-span-2 space-y-1">
                      <Label className="text-xs">Timezone</Label>
                      <Input
                        value={site.timezone}
                        onChange={(e) => updateSite(idx, "timezone", e.target.value)}
                        placeholder="e.g. America/New_York"
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </SectionCard>

        {/* Groups section */}
        <SectionCard
          title={`Device Groups${groupCount > 0 ? ` (${groupCount})` : ""}`}
          defaultOpen={false}
          action={
            <Button type="button" variant="outline" size="sm" onClick={addGroup}>
              <Plus className="h-4 w-4 mr-1" />
              Add Group
            </Button>
          }
        >
          {groups.length === 0 ? (
            <p className="text-sm text-muted-foreground">No device groups added yet.</p>
          ) : (
            <div className="space-y-4">
              {groups.map((g, idx) => (
                <div key={idx} className="border border-border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-medium text-muted-foreground">
                      Group {idx + 1}{g.group ? `: ${g.group}` : ""}
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive hover:text-destructive"
                      onClick={() => removeGroup(idx)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="space-y-1">
                      <Label htmlFor={`group-name-${idx}`} className="text-xs">
                        Group Name *
                      </Label>
                      <Input
                        id={`group-name-${idx}`}
                        value={g.group}
                        onChange={(e) => updateGroup(idx, "group", e.target.value)}
                        placeholder="Group name"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor={`group-device-type-${idx}`} className="text-xs">
                        Device Type *
                      </Label>
                      <Select
                        value={g.device_type}
                        onValueChange={(value) => updateGroup(idx, "device_type", value)}
                      >
                        <SelectTrigger id={`group-device-type-${idx}`}>
                          <SelectValue placeholder="Select a device type" />
                        </SelectTrigger>
                        <SelectContent>
                          {DEVICE_TYPE_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </SectionCard>

        {/* Validation errors */}
        {validationErrors.length > 0 && (
          <div
            role="alert"
            aria-live="polite"
            className="rounded-lg border border-destructive/50 bg-destructive/10 p-4"
          >
            <p className="text-sm font-medium text-destructive mb-2">
              Please fix the following errors before submitting:
            </p>
            <ul className="space-y-1">
              {validationErrors.map((err, i) => (
                <li key={i} className="text-sm text-destructive">
                  {err}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Submit button */}
        <div className="flex justify-end pb-6">
          <Button
            type="button"
            size="lg"
            disabled={isSubmitting}
            onClick={handleSubmitClick}
          >
            {isSubmitting ? "Starting..." : "Run Network Setup"}
          </Button>
        </div>
      </div>

      {/* Confirmation dialog */}
      <AlertDialog open={showConfirm} onOpenChange={setShowConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Start Network Setup Run?</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div>
                <p className="mb-2">This will create/configure:</p>
                <ul className="space-y-1 text-sm list-disc list-inside mb-3">
                  <li>{siteCount} site{siteCount !== 1 ? "s" : ""}</li>
                  <li>{groupCount} device group{groupCount !== 1 ? "s" : ""}</li>
                </ul>
                <p className="text-sm font-medium">
                  Once started, the run cannot be cancelled.
                </p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirm}>
              Start Run
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
