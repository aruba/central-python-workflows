import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AlertCircle,
  FileCheck,
  Loader2,
  RefreshCw,
} from "lucide-react";

import { CredentialsModal } from "@/components/CredentialsModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  createGroup,
  createSite,
  getGeo,
  getLookups,
  type ApplicationLookup,
  type CreateSiteRequest,
  type GeoCountry,
  type SubscriptionLookup,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const EMPTY_SITE_FORM: CreateSiteRequest = {
  name: "",
  address: "",
  city: "",
  state: "",
  country: "",
  zipcode: "",
  timezone: "",
};

export interface ConfigureStageValue {
  site: string;
  deviceGroup: string;
  batchSubscriptionKey: string;
  applicationAssignment: ApplicationLookup | null;
  deviceFunction: string;
}

export interface ConfigureStageProps {
  onChange?: (value: ConfigureStageValue) => void;
  importedApplication?: ApplicationLookup | null;
  revealNonce?: number;
}

type ApplicationSelectionSource = "auto" | "manual" | "import" | null;

function subscriptionLabel(subscription: SubscriptionLookup) {
  return `${subscription.key} · ${subscription.type} · ${subscription.available} available`;
}

function applicationKey(application: ApplicationLookup) {
  return JSON.stringify([application.name, application.region]);
}

function applicationLabel(application: ApplicationLookup) {
  return `${application.name} · ${application.region}`;
}

function includesName(values: string[], candidate: string) {
  const normalized = candidate.trim().toLocaleLowerCase();
  return values.some(
    (value) => value.trim().toLocaleLowerCase() === normalized
  );
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

export function ConfigureStage({
  onChange,
  importedApplication = null,
  revealNonce = 0,
}: ConfigureStageProps) {
  const [sites, setSites] = useState<string[]>([]);
  const [groups, setGroups] = useState<string[]>([]);
  const [subscriptions, setSubscriptions] = useState<SubscriptionLookup[]>([]);
  const [applications, setApplications] = useState<ApplicationLookup[]>([]);
  const [applicationAssignment, setApplicationAssignment] =
    useState<ApplicationLookup | null>(null);
  const [applicationImported, setApplicationImported] = useState(false);
  const applicationAssignmentRef = useRef<ApplicationLookup | null>(null);
  const applicationSelectionSourceRef =
    useRef<ApplicationSelectionSource>(null);
  const handledImportedApplicationRef = useRef<ApplicationLookup | null>(null);
  const [selectedSite, setSelectedSite] = useState("");
  const [selectedGroup, setSelectedGroup] = useState("");
  const [batchSubscriptionKey, setBatchSubscriptionKey] = useState("");
  const [deviceFunctions, setDeviceFunctions] = useState<string[]>([]);
  const [deviceFunction, setDeviceFunction] = useState("");
  const [createdSites, setCreatedSites] = useState<Set<string>>(new Set());
  const [createdGroups, setCreatedGroups] = useState<Set<string>>(new Set());
  const [siteFormOpen, setSiteFormOpen] = useState(false);
  const [groupFormOpen, setGroupFormOpen] = useState(false);
  const [siteForm, setSiteForm] =
    useState<CreateSiteRequest>(EMPTY_SITE_FORM);
  const [countries, setCountries] = useState<GeoCountry[]>([]);
  const [groupName, setGroupName] = useState("");
  const [siteFormError, setSiteFormError] = useState<string | null>(null);
  const [groupFormError, setGroupFormError] = useState<string | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [classicError, setClassicError] = useState<string | null>(null);
  const [credentialsOpen, setCredentialsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [savingSite, setSavingSite] = useState(false);
  const [savingGroup, setSavingGroup] = useState(false);
  const [touchedRequiredControls, setTouchedRequiredControls] = useState<
    Set<string>
  >(new Set());

  const applyApplicationAssignment = useCallback(
    (
      application: ApplicationLookup | null,
      source: ApplicationSelectionSource
    ) => {
      applicationAssignmentRef.current = application;
      applicationSelectionSourceRef.current = source;
      setApplicationAssignment(application);
      setApplicationImported(source === "import");
    },
    []
  );

  const loadLookups = useCallback(async () => {
    setLoading(true);
    setLookupError(null);
    setClassicError(null);
    try {
      const result = await getLookups();
      setSites(result.sites);
      setGroups(result.device_groups);
      setSubscriptions(result.subscriptions);
      setApplications(result.applications);
      const current = applicationAssignmentRef.current;
      const currentSource = applicationSelectionSourceRef.current;
      const currentMatch =
        current &&
        result.applications.find(
          (application) =>
            applicationKey(application) === applicationKey(current)
        );
      if (
        currentMatch &&
        (currentSource === "manual" || currentSource === "import")
      ) {
        applyApplicationAssignment(currentMatch, currentSource);
      } else {
        const automaticApplication =
          result.applications.length === 1 ? result.applications[0] : null;
        applyApplicationAssignment(
          automaticApplication,
          automaticApplication ? "auto" : null
        );
      }
      setDeviceFunctions(result.device_functions);
      setDeviceFunction(
        (current) => current || result.device_functions[0] || ""
      );
      setSelectedSite((current) => current || result.sites[0] || "");
      setSelectedGroup(
        (current) => current || result.device_groups[0] || ""
      );
      setBatchSubscriptionKey(
        (current) =>
          current ||
          result.subscriptions.find(
            (subscription) => subscription.available > 0
          )?.key ||
          ""
      );

      const failedLookups = Object.entries(result.errors);
      const classicAuthFailures = failedLookups.filter(
        ([lookup, message]) =>
          (lookup === "device_groups" || lookup === "classic_central") &&
          /401|invalid_token|expired/i.test(message)
      );
      const otherFailures = failedLookups.filter(
        (failure) => !classicAuthFailures.includes(failure)
      );
      if (classicAuthFailures.length > 0) {
        setClassicError(
          classicAuthFailures
            .map(([lookup, message]) => `${lookup}: ${message}`)
            .join(" · ")
        );
      }
      if (otherFailures.length > 0) {
        setLookupError(
          otherFailures
            .map(([lookup, message]) => `${lookup}: ${message}`)
            .join(" · ")
        );
      }
    } catch (error) {
      setLookupError(
        error instanceof Error ? error.message : "Unable to load lookups."
      );
    } finally {
      setLoading(false);
    }
  }, [applyApplicationAssignment]);

  useEffect(() => {
    void loadLookups();
  }, [loadLookups]);

  useEffect(() => {
    if (
      !importedApplication ||
      handledImportedApplicationRef.current === importedApplication
    ) {
      return;
    }
    const match = applications.find((application) =>
      importedApplication.region
        ? applicationKey(application) === applicationKey(importedApplication)
        : application.name === importedApplication.name
    );
    if (!match) return;
    handledImportedApplicationRef.current = importedApplication;
    applyApplicationAssignment(match, "import");
  }, [applications, applyApplicationAssignment, importedApplication]);

  useEffect(() => {
    // Static reference data; a failure here only costs the timezone
    // suggestion, so it stays out of the lookup error banner.
    getGeo()
      .then((geo) => setCountries(geo.countries))
      .catch(() => setCountries([]));
  }, []);

  // Central validates the country string, so render the standard English name
  // for each ISO code rather than shipping a hand-kept list.
  const countryOptions = useMemo(() => {
    const names = new Intl.DisplayNames(["en"], { type: "region" });
    return countries
      .map((country) => ({
        ...country,
        name: names.of(country.code) ?? country.code,
      }))
      .sort((left, right) => left.name.localeCompare(right.name));
  }, [countries]);

  const timezoneOptions =
    countryOptions.find((country) => country.name === siteForm.country)
      ?.timezones ?? [];

  const selectCountry = (country: string) => {
    const zones =
      countryOptions.find((entry) => entry.name === country)?.timezones ?? [];
    setSiteForm((current) => ({
      ...current,
      country,
      // One zone means there is nothing to choose; the field stays editable.
      timezone: zones.length === 1 ? zones[0] : "",
    }));
  };

  useEffect(() => {
    onChange?.({
      site: selectedSite,
      deviceGroup: selectedGroup,
      batchSubscriptionKey,
      applicationAssignment,
      deviceFunction,
    });
  }, [applicationAssignment, batchSubscriptionKey, deviceFunction, onChange, selectedGroup, selectedSite]);

  const openSiteForm = () => {
    setSiteFormError(null);
    setGroupFormOpen(false);
    setSiteFormOpen((current) => !current);
  };

  const openGroupForm = () => {
    setGroupFormError(null);
    setSiteFormOpen(false);
    setGroupFormOpen((current) => !current);
  };

  const saveSite = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const request = {
      name: siteForm.name.trim(),
      address: siteForm.address.trim(),
      city: siteForm.city.trim(),
      state: siteForm.state.trim(),
      country: siteForm.country.trim(),
      zipcode: siteForm.zipcode.trim(),
      timezone: siteForm.timezone.trim(),
    };

    if (!request.name) {
      setSiteFormError("Enter a site name.");
      return;
    }
    if (includesName(sites, request.name)) {
      setSiteFormError("That site name already exists.");
      return;
    }
    if (
      !request.address ||
      !request.city ||
      !request.state ||
      !request.country ||
      !request.zipcode ||
      !request.timezone
    ) {
      setSiteFormError(
        "Complete address, city, state, country, ZIP, and timezone."
      );
      return;
    }

    setSavingSite(true);
    setSiteFormError(null);
    try {
      const created = await createSite(request);
      setSites((current) =>
        [...current, created.name].sort((left, right) =>
          left.localeCompare(right)
        )
      );
      setCreatedSites((current) => new Set(current).add(created.name));
      setSelectedSite(created.name);
      setSiteForm(EMPTY_SITE_FORM);
      setSiteFormOpen(false);
    } catch (error) {
      setSiteFormError(
        error instanceof Error ? error.message : "Unable to create site."
      );
    } finally {
      setSavingSite(false);
    }
  };

  const saveGroup = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = groupName.trim();

    if (!name) {
      setGroupFormError("Enter a device group name.");
      return;
    }
    if (includesName(groups, name)) {
      setGroupFormError("That device group name already exists.");
      return;
    }

    setSavingGroup(true);
    setGroupFormError(null);
    try {
      const created = await createGroup({ name });
      setGroups((current) =>
        [...current, created.name].sort((left, right) =>
          left.localeCompare(right)
        )
      );
      setCreatedGroups((current) => new Set(current).add(created.name));
      setSelectedGroup(created.name);
      setGroupName("");
      setGroupFormOpen(false);
    } catch (error) {
      setGroupFormError(
        error instanceof Error
          ? error.message
          : "Unable to create device group."
      );
    } finally {
      setSavingGroup(false);
    }
  };

  const siteExists = Boolean(selectedSite);
  const groupExists = Boolean(selectedGroup);
  const subscriptionSelected = Boolean(batchSubscriptionKey);
  const applicationSelected = applicationAssignment !== null;
  const configurationReady =
    siteExists && groupExists && subscriptionSelected && applicationSelected;
  const requiredControls = useMemo(
    () => [
      {
        id: "configure-application",
        label: "GLP application",
        missing: !applicationSelected,
      },
      {
        id: "configure-subscription",
        label: "batch subscription default",
        missing: !subscriptionSelected,
      },
      { id: "configure-site", label: "site", missing: !siteExists },
      { id: "configure-group", label: "device group", missing: !groupExists },
    ],
    [
      applicationSelected,
      groupExists,
      siteExists,
      subscriptionSelected,
    ]
  );
  const missingRequiredControls = requiredControls.filter(
    (control) => control.missing
  );
  const missingRequiredControlsRef = useRef(missingRequiredControls);
  missingRequiredControlsRef.current = missingRequiredControls;

  useEffect(() => {
    if (revealNonce === 0) return;
    const firstMissing = missingRequiredControlsRef.current[0];
    if (firstMissing) focusAndCenterControl(firstMissing.id);
  }, [revealNonce]);

  const markRequiredControlTouched = (id: string) => {
    setTouchedRequiredControls((current) => {
      if (current.has(id)) return current;
      const next = new Set(current);
      next.add(id);
      return next;
    });
  };

  const showRequiredError = (id: string, missing: boolean) =>
    missing && (revealNonce > 0 || touchedRequiredControls.has(id));

  return (
    <>
      <section aria-labelledby="configure-stage-title">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2
            id="configure-stage-title"
            className="text-lg font-bold tracking-tight"
          >
            Batch assignments
          </h2>
          <p className="mt-1 max-w-[68ch] text-sm leading-6 text-[var(--cc-ink-soft)]">
            Choose assignments and a subscription default before adding devices.
            New sites and groups are created immediately.
          </p>
        </div>
        <p
          aria-label="Asterisk marks required fields"
          className="text-xs font-semibold text-[var(--cc-ink-soft)]"
        >
          <span aria-hidden="true" className="text-[var(--cc-danger)]">
            *
          </span>{" "}
          marks required fields
        </p>
      </div>

      {revealNonce > 0 && !configurationReady && (
        <div
          key={revealNonce}
          role="alert"
          className="mb-5 flex items-start gap-2 rounded-lg border border-[color-mix(in_oklch,var(--cc-danger)_35%,var(--cc-line))] bg-[var(--cc-danger-soft)] px-3.5 py-3 text-xs text-[var(--cc-danger)] motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-0.5 motion-safe:duration-200 motion-safe:ease-out"
        >
          <AlertCircle
            aria-hidden="true"
            className="mt-0.5 h-4 w-4 shrink-0"
          />
          <div>
            <p className="font-semibold">
              Complete the required batch assignments before continuing.
            </p>
            <p className="mt-1 leading-5">
              Select a value for:
            </p>
            <ul className="mt-1 list-disc space-y-1 pl-4">
              {missingRequiredControls.map((control) => (
                <li key={control.id}>
                  <a
                    href={`#${control.id}`}
                    onClick={(event) => {
                      event.preventDefault();
                      focusAndCenterControl(control.id);
                    }}
                    className="font-semibold underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cc-danger)]"
                  >
                    {control.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {classicError && (
        <div
          role="alert"
          className="mb-4 flex flex-col gap-3 rounded-lg border border-[color-mix(in_oklch,var(--cc-warning)_35%,var(--cc-line))] bg-[var(--cc-warning-soft)] px-3.5 py-3 text-xs text-[var(--cc-warning)] sm:flex-row sm:items-center sm:justify-between"
        >
          <span className="flex min-w-0 items-start gap-2">
            <AlertCircle
              aria-hidden="true"
              className="mt-0.5 h-4 w-4 shrink-0"
            />
            <span className="min-w-0">
              <span className="block font-semibold">
                Classic Central token expired or invalid
              </span>
              <span className="mt-1 block leading-5">
                Device groups can&apos;t load until a fresh token is saved.
              </span>
              <details className="mt-1.5">
                <summary className="w-fit cursor-pointer rounded-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cc-warning)]">
                  Show details
                </summary>
                <p className="mt-1 break-words leading-5">{classicError}</p>
              </details>
            </span>
          </span>
          <span className="flex shrink-0 flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              onClick={() => setCredentialsOpen(true)}
              className="bg-[var(--cc-accent)] text-[var(--cc-accent-ink)] hover:bg-[var(--cc-accent-hover)]"
            >
              Update token
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => void loadLookups()}
              className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)]"
            >
              <RefreshCw aria-hidden="true" />
              Retry
            </Button>
          </span>
        </div>
      )}

      {lookupError && (
        <div
          role="alert"
          className="mb-4 flex flex-col gap-3 rounded-lg border border-[color-mix(in_oklch,var(--cc-danger)_35%,var(--cc-line))] bg-[var(--cc-danger-soft)] px-3.5 py-3 text-xs text-[var(--cc-danger)] sm:flex-row sm:items-center sm:justify-between"
        >
          <span className="flex min-w-0 items-start gap-2">
            <AlertCircle
              aria-hidden="true"
              className="mt-0.5 h-4 w-4 shrink-0"
            />
            <span className="break-words">{lookupError}</span>
          </span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void loadLookups()}
            className="shrink-0 border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)]"
          >
            <RefreshCw aria-hidden="true" />
            Retry
          </Button>
        </div>
      )}

      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--cc-ink-soft)]">
        GreenLake
      </h3>
      <div className="grid gap-x-6 gap-y-5 lg:grid-cols-2">
        <div className="min-w-0">
          <div className="mb-2 flex min-h-6 items-center">
            <Label htmlFor="configure-application">
              GLP application
              <span aria-hidden="true" className="ml-1 text-[var(--cc-danger)]">
                *
              </span>
            </Label>
          </div>
          {applications.length > 1 ? (
            <Select
              value={
                applicationAssignment
                  ? applicationKey(applicationAssignment)
                  : ""
              }
              onValueChange={(key) => {
                applyApplicationAssignment(
                  applications.find(
                    (application) => applicationKey(application) === key
                  ) ?? null,
                  "manual"
                );
              }}
              disabled={loading}
            >
              <SelectTrigger
                id="configure-application"
                aria-required="true"
                aria-invalid={showRequiredError(
                  "configure-application",
                  !applicationSelected
                )}
                aria-describedby={
                  showRequiredError(
                    "configure-application",
                    !applicationSelected
                  )
                    ? "configure-application-error"
                    : undefined
                }
                onBlur={() =>
                  markRequiredControlTouched("configure-application")
                }
                className={cn(
                  "border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] focus:ring-[var(--cc-accent)]",
                  showRequiredError(
                    "configure-application",
                    !applicationSelected
                  ) &&
                    "border-[var(--cc-danger)] focus:ring-[var(--cc-danger)]"
                )}
              >
                <SelectValue placeholder="Select a GLP application" />
              </SelectTrigger>
              <SelectContent className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)]">
                {applications.map((application) => (
                  <SelectItem
                    key={applicationKey(application)}
                    value={applicationKey(application)}
                  >
                    {applicationLabel(application)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            // Single application: state it rather than offering a one-item menu.
            <p
              id="configure-application"
              aria-live="polite"
              aria-required="true"
              aria-invalid={showRequiredError(
                "configure-application",
                !applicationSelected
              )}
              aria-describedby={
                showRequiredError(
                  "configure-application",
                  !applicationSelected
                )
                  ? "configure-application-error"
                  : undefined
              }
              tabIndex={applicationSelected ? undefined : -1}
              onBlur={() =>
                markRequiredControlTouched("configure-application")
              }
              className={cn(
                "flex h-9 items-center rounded-md border border-[var(--cc-line)] bg-[var(--cc-muted)] px-3 text-sm text-[var(--cc-ink-soft)]",
                showRequiredError(
                  "configure-application",
                  !applicationSelected
                ) && "border-[var(--cc-danger)]"
              )}
            >
              {loading
                ? "Loading…"
                : applications.length === 0
                  ? "No GLP applications available in this workspace"
                  : applicationLabel(applications[0])}
            </p>
          )}
          {!loading &&
            applications.length > 1 &&
            applicationAssignment === null &&
            !showRequiredError(
              "configure-application",
              !applicationSelected
            ) && (
              <p role="status" className="mt-2 text-xs text-[var(--cc-ink-soft)]">
                Select a GLP application to continue.
              </p>
            )}
          {showRequiredError(
            "configure-application",
            !applicationSelected
          ) && (
            <p
              id="configure-application-error"
              role={revealNonce === 0 ? "alert" : undefined}
              className="mt-2 text-xs text-[var(--cc-danger)]"
            >
              Select a GLP application.
            </p>
          )}
          {applicationImported && applicationAssignment && (
            <p
              role="status"
              className="mt-2 flex items-start gap-2 text-xs leading-5 text-[var(--cc-accent)]"
            >
              <FileCheck
                aria-hidden="true"
                className="mt-0.5 h-4 w-4 shrink-0"
              />
              <span>
                GLP application set from imported file:{" "}
                {applicationLabel(applicationAssignment)}.
              </span>
            </p>
          )}
        </div>

        <div className="min-w-0">
          <div className="mb-2 flex min-h-6 items-center">
            <Label htmlFor="configure-subscription">
              Batch subscription default
              <span aria-hidden="true" className="ml-1 text-[var(--cc-danger)]">
                *
              </span>
            </Label>
          </div>
          <Select
            value={batchSubscriptionKey}
            onValueChange={setBatchSubscriptionKey}
            disabled={loading || subscriptions.length === 0}
          >
            <SelectTrigger
              id="configure-subscription"
              aria-required="true"
              aria-invalid={showRequiredError(
                "configure-subscription",
                !subscriptionSelected
              )}
              aria-describedby={
                showRequiredError(
                  "configure-subscription",
                  !subscriptionSelected
                )
                  ? "configure-subscription-error"
                  : undefined
              }
              onBlur={() =>
                markRequiredControlTouched("configure-subscription")
              }
              className={cn(
                "border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] focus:ring-[var(--cc-accent)]",
                showRequiredError(
                  "configure-subscription",
                  !subscriptionSelected
                ) &&
                  "border-[var(--cc-danger)] focus:ring-[var(--cc-danger)]"
              )}
            >
              <SelectValue
                placeholder={
                  loading
                    ? "Loading subscriptions…"
                    : subscriptions.length === 0
                      ? "No AP subscriptions available in this workspace"
                      : "Select a subscription"
                }
              />
            </SelectTrigger>
            <SelectContent className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)]">
              {subscriptions.map((subscription) => (
                <SelectItem
                  key={subscription.key}
                  value={subscription.key}
                  disabled={subscription.available <= 0}
                >
                  {subscriptionLabel(subscription)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {showRequiredError(
            "configure-subscription",
            !subscriptionSelected
          ) && (
            <p
              id="configure-subscription-error"
              role={revealNonce === 0 ? "alert" : undefined}
              className="mt-2 text-xs text-[var(--cc-danger)]"
            >
              Select a batch subscription default.
            </p>
          )}
          {!loading &&
            subscriptions.length > 0 &&
            subscriptions.every((subscription) => subscription.available <= 0) && (
              <p
                role="status"
                className="mt-2 text-xs text-[var(--cc-danger)]"
              >
                No subscription has available capacity.
              </p>
            )}
        </div>

      </div>

      <h3 className="mb-3 mt-6 text-xs font-semibold uppercase tracking-wider text-[var(--cc-ink-soft)]">
        Central
      </h3>
      <div className="grid gap-x-6 gap-y-5 lg:grid-cols-3">
        <div className="min-w-0">
          <div className="mb-2 flex min-h-6 items-center justify-between gap-3">
            <Label htmlFor="configure-site">
              Site
              <span aria-hidden="true" className="ml-1 text-[var(--cc-danger)]">
                *
              </span>
            </Label>
            <Button
              type="button"
              variant="link"
              onClick={openSiteForm}
              aria-expanded={siteFormOpen}
              aria-controls="new-site-form"
              className="h-auto p-0 text-xs font-semibold text-[var(--cc-accent)]"
            >
              + New site
            </Button>
          </div>
          <Select
            value={selectedSite}
            onValueChange={setSelectedSite}
            disabled={loading || sites.length === 0}
          >
            <SelectTrigger
              id="configure-site"
              aria-required="true"
              aria-invalid={showRequiredError("configure-site", !siteExists)}
              aria-describedby={
                showRequiredError("configure-site", !siteExists)
                  ? "configure-site-error"
                  : undefined
              }
              onBlur={() => markRequiredControlTouched("configure-site")}
              className={cn(
                "border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] focus:ring-[var(--cc-accent)]",
                showRequiredError("configure-site", !siteExists) &&
                  "border-[var(--cc-danger)] focus:ring-[var(--cc-danger)]"
              )}
            >
              <SelectValue
                placeholder={
                  loading
                    ? "Loading sites…"
                    : sites.length === 0
                      ? "No sites available"
                      : "Select a site"
                }
              />
            </SelectTrigger>
            <SelectContent className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)]">
              {sites.map((site) => (
                <SelectItem key={site} value={site}>
                  {site}
                  {createdSites.has(site) ? " · Created ✓" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {showRequiredError("configure-site", !siteExists) && (
            <p
              id="configure-site-error"
              role={revealNonce === 0 ? "alert" : undefined}
              className="mt-2 text-xs text-[var(--cc-danger)]"
            >
              Select a site.
            </p>
          )}
          {createdSites.has(selectedSite) && (
            <p
              aria-live="polite"
              className="mt-2 text-xs font-semibold text-[var(--cc-success)]"
            >
              {selectedSite} · Created ✓
            </p>
          )}
        </div>

        <div className="min-w-0">
          <div className="mb-2 flex min-h-6 items-center justify-between gap-3">
            <Label htmlFor="configure-group">
              Device group
              <span aria-hidden="true" className="ml-1 text-[var(--cc-danger)]">
                *
              </span>
            </Label>
            <Button
              type="button"
              variant="link"
              onClick={openGroupForm}
              aria-expanded={groupFormOpen}
              aria-controls="new-group-form"
              className="h-auto p-0 text-xs font-semibold text-[var(--cc-accent)]"
            >
              + New device group
            </Button>
          </div>
          <Select
            value={selectedGroup}
            onValueChange={setSelectedGroup}
            disabled={loading || groups.length === 0}
          >
            <SelectTrigger
              id="configure-group"
              aria-required="true"
              aria-invalid={showRequiredError("configure-group", !groupExists)}
              aria-describedby={
                showRequiredError("configure-group", !groupExists)
                  ? "configure-group-error"
                  : undefined
              }
              onBlur={() => markRequiredControlTouched("configure-group")}
              className={cn(
                "border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] focus:ring-[var(--cc-accent)]",
                showRequiredError("configure-group", !groupExists) &&
                  "border-[var(--cc-danger)] focus:ring-[var(--cc-danger)]"
              )}
            >
              <SelectValue
                placeholder={
                  loading
                    ? "Loading device groups…"
                    : groups.length === 0
                      ? "No device groups available"
                      : "Select a device group"
                }
              />
            </SelectTrigger>
            <SelectContent className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)]">
              {groups.map((group) => (
                <SelectItem key={group} value={group}>
                  {group}
                  {createdGroups.has(group) ? " · Created ✓" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {showRequiredError("configure-group", !groupExists) && (
            <p
              id="configure-group-error"
              role={revealNonce === 0 ? "alert" : undefined}
              className="mt-2 text-xs text-[var(--cc-danger)]"
            >
              Select a device group.
            </p>
          )}
          {createdGroups.has(selectedGroup) && (
            <p
              aria-live="polite"
              className="mt-2 text-xs font-semibold text-[var(--cc-success)]"
            >
              {selectedGroup} · Created ✓
            </p>
          )}
        </div>

        <div className="min-w-0">
          <div className="mb-2 flex min-h-6 items-center">
            <Label htmlFor="configure-device-function">Device function</Label>
          </div>
          {deviceFunctions.length > 1 ? (
            <Select value={deviceFunction} onValueChange={setDeviceFunction}>
              <SelectTrigger
                id="configure-device-function"
                className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] focus:ring-[var(--cc-accent)]"
              >
                <SelectValue placeholder="Select a device function" />
              </SelectTrigger>
              <SelectContent className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)]">
                {deviceFunctions.map((fn) => (
                  <SelectItem key={fn} value={fn}>
                    {fn}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            // Single persona: state it rather than offering a one-item menu.
            <p
              id="configure-device-function"
              className="flex h-9 items-center rounded-md border border-[var(--cc-line)] bg-[var(--cc-muted)] px-3 text-sm text-[var(--cc-ink-soft)]"
            >
              {deviceFunction || "Loading…"}
            </p>
          )}
        </div>
      </div>

      {siteFormOpen && (
        <form
          id="new-site-form"
          noValidate
          onSubmit={saveSite}
          className="mt-5 rounded-xl border border-[var(--cc-line)] bg-[var(--cc-muted)] p-4"
        >
          <h3 className="text-sm font-semibold">Create a site now</h3>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <div className="sm:col-span-2">
              <Label htmlFor="new-site-name" className="text-xs">
                Site name
              </Label>
              <Input
                id="new-site-name"
                value={siteForm.name}
                onChange={(event) =>
                  setSiteForm((current) => ({
                    ...current,
                    name: event.target.value,
                  }))
                }
                maxLength={80}
                autoComplete="off"
                className="mt-1 border-[var(--cc-line-strong)] bg-[var(--cc-raised)]"
              />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="new-site-address" className="text-xs">
                Address
              </Label>
              <Input
                id="new-site-address"
                value={siteForm.address}
                onChange={(event) =>
                  setSiteForm((current) => ({
                    ...current,
                    address: event.target.value,
                  }))
                }
                maxLength={120}
                autoComplete="street-address"
                className="mt-1 border-[var(--cc-line-strong)] bg-[var(--cc-raised)]"
              />
            </div>
            <div>
              <Label htmlFor="new-site-city" className="text-xs">
                City
              </Label>
              <Input
                id="new-site-city"
                value={siteForm.city}
                onChange={(event) =>
                  setSiteForm((current) => ({
                    ...current,
                    city: event.target.value,
                  }))
                }
                maxLength={80}
                autoComplete="address-level2"
                className="mt-1 border-[var(--cc-line-strong)] bg-[var(--cc-raised)]"
              />
            </div>
            <div>
              <Label htmlFor="new-site-state" className="text-xs">
                State
              </Label>
              <Input
                id="new-site-state"
                value={siteForm.state}
                onChange={(event) =>
                  setSiteForm((current) => ({
                    ...current,
                    state: event.target.value,
                  }))
                }
                maxLength={80}
                autoComplete="address-level1"
                className="mt-1 border-[var(--cc-line-strong)] bg-[var(--cc-raised)]"
              />
            </div>
            <div>
              <Label htmlFor="new-site-zipcode" className="text-xs">
                ZIP or postal code
              </Label>
              <Input
                id="new-site-zipcode"
                value={siteForm.zipcode}
                onChange={(event) =>
                  setSiteForm((current) => ({
                    ...current,
                    zipcode: event.target.value,
                  }))
                }
                maxLength={20}
                autoComplete="postal-code"
                className="mt-1 border-[var(--cc-line-strong)] bg-[var(--cc-raised)]"
              />
            </div>
            <div>
              <Label htmlFor="new-site-country" className="text-xs">
                Country
              </Label>
              <Select value={siteForm.country} onValueChange={selectCountry}>
                <SelectTrigger
                  id="new-site-country"
                  className="mt-1 border-[var(--cc-line-strong)] bg-[var(--cc-raised)]"
                >
                  <SelectValue placeholder="Select" />
                </SelectTrigger>
                <SelectContent className="max-h-64 border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)]">
                  {countryOptions.map((country) => (
                    <SelectItem key={country.code} value={country.name}>
                      {country.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="new-site-timezone" className="text-xs">
                Timezone
              </Label>
              <Select
                value={siteForm.timezone}
                onValueChange={(timezone) =>
                  setSiteForm((current) => ({ ...current, timezone }))
                }
                disabled={timezoneOptions.length === 0}
              >
                <SelectTrigger
                  id="new-site-timezone"
                  className="mt-1 border-[var(--cc-line-strong)] bg-[var(--cc-raised)]"
                >
                  <SelectValue
                    placeholder={
                      siteForm.country ? "Select" : "Pick a country first"
                    }
                  />
                </SelectTrigger>
                <SelectContent className="max-h-64 border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)]">
                  {timezoneOptions.map((timezone) => (
                    <SelectItem key={timezone} value={timezone}>
                      {timezone}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          {siteFormError && (
            <p role="alert" className="mt-3 text-xs text-[var(--cc-danger)]">
              {siteFormError}
            </p>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setSiteFormOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              variant="outline"
              disabled={savingSite}
              className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] hover:bg-[var(--cc-muted)]"
            >
              {savingSite && <Loader2 aria-hidden="true" className="motion-safe:animate-spin" />}
              {savingSite ? "Creating…" : "Save site"}
            </Button>
          </div>
        </form>
      )}

      {groupFormOpen && (
        <form
          id="new-group-form"
          noValidate
          onSubmit={saveGroup}
          className="mt-5 rounded-xl border border-[var(--cc-line)] bg-[var(--cc-muted)] p-4"
        >
          <h3 className="text-sm font-semibold">
            Create an AP device group now
          </h3>
          <div className="mt-3 max-w-md">
            <Label htmlFor="new-group-name" className="text-xs">
              Device group name
            </Label>
            <Input
              id="new-group-name"
              value={groupName}
              onChange={(event) => setGroupName(event.target.value)}
              maxLength={80}
              autoComplete="off"
              className="mt-1 border-[var(--cc-line-strong)] bg-[var(--cc-raised)]"
            />
            <p className="mt-1.5 text-xs text-[var(--cc-ink-soft)]">
              AOS 10 AP settings are applied automatically.
            </p>
          </div>
          {groupFormError && (
            <p role="alert" className="mt-3 text-xs text-[var(--cc-danger)]">
              {groupFormError}
            </p>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setGroupFormOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              variant="outline"
              disabled={savingGroup}
              className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] hover:bg-[var(--cc-muted)]"
            >
              {savingGroup && (
                <Loader2 aria-hidden="true" className="motion-safe:animate-spin" />
              )}
              {savingGroup ? "Creating…" : "Save device group"}
            </Button>
          </div>
        </form>
      )}

      </section>
      <CredentialsModal
        open={credentialsOpen}
        initialSection="classic"
        onOpenChange={(nextOpen) => {
          setCredentialsOpen(nextOpen);
          if (!nextOpen) void loadLookups();
        }}
      />
    </>
  );
}
