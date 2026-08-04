"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Eye,
  EyeOff,
  ExternalLink,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
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
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getCredentials,
  getCredentialsStatus,
  saveCredentials,
  type CredentialsStatusResponse,
  type SaveCredentialsRequest,
} from "@/lib/api";
import {
  CLUSTER_ENDPOINTS,
  CLUSTER_KEYS,
  isClusterKey,
  type ClusterKey,
} from "@/lib/clusters";
import { cn } from "@/lib/utils";

type CredentialGroup = "unified" | "classic";
type SaveTarget = CredentialGroup | "all";

interface CredentialsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialSection?: "classic";
}

interface CredentialsContentProps {
  active?: boolean;
  embedded?: boolean;
  onSaved?: () => void;
  initialSection?: "classic";
}

interface PresenceState {
  clientId: boolean;
  clientSecret: boolean;
  workspaceId: boolean;
  accessToken: boolean;
}

interface ReplacementState {
  clientId: boolean;
  clientSecret: boolean;
  workspaceId: boolean;
  accessToken: boolean;
}

interface GroupErrors {
  unified?: string;
  classic?: string;
}

const EMPTY_PRESENCE: PresenceState = {
  clientId: false,
  clientSecret: false,
  workspaceId: false,
  accessToken: false,
};

const EMPTY_REPLACEMENTS: ReplacementState = {
  clientId: false,
  clientSecret: false,
  workspaceId: false,
  accessToken: false,
};

function getVerificationLabel(error: string) {
  if (/\b401\b/.test(error)) {
    return "Credential rejected (401)";
  }
  if (/\b403\b/.test(error)) {
    return "Permission missing (403)";
  }
  if (
    /\b404\b|transport|dns|tls|wrong base url|unreachable/i.test(error)
  ) {
    return "Endpoint unreachable (404 or transport)";
  }
  return "Verification failed";
}

function VerificationMessage({ error }: { error?: string }) {
  if (!error) return null;

  return (
    <div
      role="alert"
      className="rounded-lg border border-[color-mix(in_oklch,var(--cc-danger)_35%,var(--cc-line))] bg-[var(--cc-danger-soft)] px-3 py-2.5 text-xs text-[var(--cc-danger)]"
    >
      <p className="font-semibold">{getVerificationLabel(error)}</p>
      <p className="mt-1 leading-5">{error}</p>
    </div>
  );
}

function GroupStatus({
  saved,
  verified,
  loading,
}: {
  saved: boolean;
  verified: boolean;
  loading: boolean;
}) {
  if (loading) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-[var(--cc-ink-soft)]">
        <Loader2 aria-hidden="true" className="h-3.5 w-3.5 motion-safe:animate-spin" />
        Checking
      </span>
    );
  }

  if (saved && verified) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--cc-success)]">
        <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" />
        Verified
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--cc-ink-soft)]">
      <AlertCircle aria-hidden="true" className="h-3.5 w-3.5" />
      {saved ? "Needs verification" : "Not configured"}
    </span>
  );
}

function CredentialField({
  id,
  label,
  value,
  onChange,
  saved,
  replacing,
  onReplace,
  disabled,
  placeholder,
  autoFocus = false,
  secret = false,
  visible = false,
  onVisibilityChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  saved: boolean;
  replacing: boolean;
  onReplace: () => void;
  disabled: boolean;
  placeholder: string;
  autoFocus?: boolean;
  secret?: boolean;
  visible?: boolean;
  onVisibilityChange?: () => void;
}) {
  const showSavedState = saved && !replacing;

  return (
    <div className="space-y-2">
      <Label htmlFor={id} className="text-xs font-semibold text-[var(--cc-ink)]">
        {label}
      </Label>
      {showSavedState ? (
        <div
          id={id}
          role="status"
          className="flex min-h-10 items-center justify-between gap-3 rounded-md border border-[var(--cc-line)] bg-[var(--cc-muted)] px-3"
        >
          <span className="font-mono text-sm tracking-wide text-[var(--cc-ink-soft)]">
            •••••••• · saved
          </span>
          <Button
            type="button"
            variant="link"
            size="sm"
            className="h-auto p-0 text-xs text-[var(--cc-accent)]"
            onClick={onReplace}
            disabled={disabled}
          >
            Replace
          </Button>
        </div>
      ) : (
        <div className="relative">
          <Input
            id={id}
            type={secret && !visible ? "password" : "text"}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder={placeholder}
            disabled={disabled}
            autoFocus={autoFocus}
            autoComplete={secret ? "new-password" : "off"}
            spellCheck={false}
            className={cn(
              "border-[var(--cc-line-strong)] bg-[var(--cc-surface)] text-[var(--cc-ink)] placeholder:text-[var(--cc-ink-faint)]",
              secret && "pr-10 font-mono"
            )}
          />
          {secret && (
            <button
              type="button"
              onClick={onVisibilityChange}
              disabled={disabled}
              aria-label={visible ? `Hide ${label}` : `Show ${label}`}
              aria-pressed={visible}
              className="absolute inset-y-0 right-0 grid w-10 place-items-center rounded-r-md text-[var(--cc-ink-soft)] hover:text-[var(--cc-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--cc-accent)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {visible ? (
                <EyeOff aria-hidden="true" className="h-4 w-4" />
              ) : (
                <Eye aria-hidden="true" className="h-4 w-4" />
              )}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function LoadingCredentials() {
  return (
    <div
      role="status"
      aria-label="Loading credentials"
      className="space-y-5"
    >
      <Skeleton className="h-28 w-full rounded-xl" />
      <Skeleton className="h-72 w-full rounded-xl" />
      <Skeleton className="h-14 w-full rounded-xl" />
    </div>
  );
}

export function CredentialsContent({
  active = true,
  embedded = false,
  onSaved,
  initialSection,
}: CredentialsContentProps) {
  const [cluster, setCluster] = useState<ClusterKey>("US-1");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [workspaceId, setWorkspaceId] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [showClientSecret, setShowClientSecret] = useState(false);
  const [showAccessToken, setShowAccessToken] = useState(false);
  const [classicOpen, setClassicOpen] = useState(
    initialSection === "classic"
  );
  const [isLoading, setIsLoading] = useState(true);
  const [savingTarget, setSavingTarget] = useState<SaveTarget | null>(null);
  const [presence, setPresence] = useState<PresenceState>(EMPTY_PRESENCE);
  const [replacing, setReplacing] =
    useState<ReplacementState>(EMPTY_REPLACEMENTS);
  const [status, setStatus] = useState<CredentialsStatusResponse | null>(null);
  const [groupErrors, setGroupErrors] = useState<GroupErrors>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [modeWarning, setModeWarning] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!active) return;

    let cancelled = false;
    setIsLoading(true);
    setLoadError(null);
    setGroupErrors({});
    setClassicOpen(initialSection === "classic");
    setReplacing(
      initialSection === "classic"
        ? { ...EMPTY_REPLACEMENTS, accessToken: true }
        : EMPTY_REPLACEMENTS
    );
    setClientId("");
    setClientSecret("");
    setWorkspaceId("");
    setAccessToken("");
    setShowClientSecret(false);
    setShowAccessToken(false);

    (async () => {
      const [credentialsResult, statusResult] = await Promise.allSettled([
        getCredentials(),
        getCredentialsStatus(),
      ]);
      if (cancelled) return;

      if (credentialsResult.status === "fulfilled") {
        const credentials = credentialsResult.value;
        if (credentials.cluster && isClusterKey(credentials.cluster)) {
          setCluster(credentials.cluster);
        }
        setPresence({
          clientId: credentials.unified?.client_id_present ?? false,
          clientSecret: credentials.unified?.client_secret_present ?? false,
          workspaceId: credentials.unified?.workspace_id_present ?? false,
          accessToken: credentials.classic?.access_token_present ?? false,
        });
        setModeWarning(
          credentials.unified?.mode_safe === false ||
            credentials.classic?.mode_safe === false
        );
      } else {
        setPresence(EMPTY_PRESENCE);
        setLoadError(
          "Credential presence could not be loaded. Retry before replacing credentials."
        );
      }

      if (statusResult.status === "fulfilled") {
        setStatus(statusResult.value);
        if (
          statusResult.value.classic_valid === false &&
          statusResult.value.creds_valid === true
        ) {
          setClassicOpen(true);
        }
      } else {
        setStatus(null);
      }

      setIsLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [active, initialSection, reloadKey]);

  const endpoints = useMemo(() => CLUSTER_ENDPOINTS[cluster], [cluster]);
  const unifiedSaved =
    presence.clientId && presence.clientSecret && presence.workspaceId;
  const classicSaved = presence.accessToken;
  const isSaving = savingTarget !== null;

  const replaceField = (field: keyof ReplacementState) => {
    setReplacing((current) => ({ ...current, [field]: true }));
    setGroupErrors((current) => ({
      ...current,
      [field === "accessToken" ? "classic" : "unified"]: undefined,
    }));
  };

  const validateCompletePair = () => {
    const nextErrors: GroupErrors = {};

    if (
      ((!presence.clientId || replacing.clientId) && !clientId.trim()) ||
      ((!presence.clientSecret || replacing.clientSecret) && !clientSecret) ||
      ((!presence.workspaceId || replacing.workspaceId) &&
        !workspaceId.trim())
    ) {
      nextErrors.unified =
        "Enter each missing or replaced GreenLake field.";
    }
    if (
      (!presence.accessToken || replacing.accessToken) &&
      !accessToken
    ) {
      nextErrors.classic =
        "Paste the missing or replacement Classic Central access token.";
      setClassicOpen(true);
    }

    setGroupErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSave = async (target: SaveTarget) => {
    if (!validateCompletePair()) return;

    setSavingTarget(target);
    setGroupErrors({});
    setLoadError(null);

    const request: SaveCredentialsRequest = {
      cluster,
      unified: {
        client_id: clientId.trim(),
        client_secret: clientSecret,
        workspace_id: workspaceId.trim(),
      },
      classic: {
        access_token: accessToken,
      },
    };

    try {
      const response = await saveCredentials(request);
      if (response.creds_valid && response.classic_valid) {
        setPresence({
          clientId: true,
          clientSecret: true,
          workspaceId: true,
          accessToken: true,
        });
        setReplacing(EMPTY_REPLACEMENTS);
        setStatus({ creds_valid: true, classic_valid: true });
        setClientId("");
        setClientSecret("");
        setWorkspaceId("");
        setAccessToken("");
        setShowClientSecret(false);
        setShowAccessToken(false);
        setClassicOpen(false);
        toast.success("Credentials verified and saved.");
        onSaved?.();
        return;
      }

      const unifiedError =
        response.errors.unified ??
        response.errors.new_central ??
        (!response.creds_valid
          ? "Verification failed. Check the GreenLake and New Central credentials, then retry."
          : undefined);
      const classicError =
        response.errors.classic ??
        response.errors.classic_central ??
        (!response.classic_valid
          ? "Verification failed. Check the Classic Central token, then retry."
          : undefined);

      setGroupErrors({
        unified: unifiedError,
        classic: classicError,
      });
      if (classicError) setClassicOpen(true);
      toast.warning("Verification failed. Existing credentials are unchanged.");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unknown credential error";
      setLoadError(
        `Credentials could not be verified or saved: ${message}. Existing credentials are unchanged.`
      );
      toast.error("Credentials were not changed.");
    } finally {
      setSavingTarget(null);
    }
  };

  if (isLoading) {
    return (
      <div className={embedded ? "px-5 py-5 sm:px-6" : ""}>
        <LoadingCredentials />
      </div>
    );
  }

  return (
    <div className={cn("space-y-5", embedded && "px-5 py-5 sm:px-6")}>
      {loadError && (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-lg border border-[color-mix(in_oklch,var(--cc-danger)_35%,var(--cc-line))] bg-[var(--cc-danger-soft)] px-3 py-2.5 text-xs leading-5 text-[var(--cc-danger)] sm:flex-row sm:items-center sm:justify-between"
        >
          <span>{loadError}</span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setReloadKey((current) => current + 1)}
            className="shrink-0 border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] hover:bg-[var(--cc-muted)]"
          >
            Retry
          </Button>
        </div>
      )}

      {modeWarning && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-[color-mix(in_oklch,var(--cc-warning)_35%,var(--cc-line))] bg-[var(--cc-warning-soft)] px-3 py-2.5 text-xs leading-5 text-[var(--cc-warning)]"
        >
          <AlertTriangle
            aria-hidden="true"
            className="mt-0.5 h-4 w-4 shrink-0"
          />
          <p>
            <span className="font-semibold">Warning:</span> Stored credential
            permissions are unsafe. Set them to owner-only before replacing
            credentials.
          </p>
        </div>
      )}

      <section
        aria-labelledby="central-cluster-title"
        className="rounded-xl border border-[var(--cc-line)] bg-[var(--cc-surface)]"
      >
        <div className="border-b border-[var(--cc-line)] px-4 py-3.5">
          <h3
            id="central-cluster-title"
            className="text-sm font-semibold text-[var(--cc-ink)]"
          >
            Central cluster
          </h3>
          <p className="mt-1 text-xs leading-5 text-[var(--cc-ink-soft)]">
            One physical cluster determines both service endpoints.
          </p>
        </div>
        <div className="space-y-4 px-4 py-4">
          <div className="grid gap-2 sm:grid-cols-[10rem_minmax(0,1fr)] sm:items-center">
            <Label
              htmlFor="credentials-cluster"
              className="text-xs font-semibold text-[var(--cc-ink)]"
            >
              Cluster / region
            </Label>
            <Select
              value={cluster}
              onValueChange={(value) => {
                if (isClusterKey(value)) setCluster(value);
              }}
              disabled={isSaving}
            >
              <SelectTrigger
                id="credentials-cluster"
                className="border-[var(--cc-line-strong)] bg-[var(--cc-surface)] text-[var(--cc-ink)]"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CLUSTER_KEYS.map((key) => (
                  <SelectItem key={key} value={key}>
                    {key}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </section>

      <section
        aria-labelledby="unified-credentials-title"
        className="rounded-xl border border-[var(--cc-line)] bg-[var(--cc-surface)]"
      >
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--cc-line)] px-4 py-3.5">
          <div>
            <h3
              id="unified-credentials-title"
              className="text-sm font-semibold text-[var(--cc-ink)]"
            >
              HPE GreenLake &amp; New Central
            </h3>
            <p className="mt-1 max-w-[58ch] text-xs leading-5 text-[var(--cc-ink-soft)]">
              One GreenLake credential set authenticates platform operations
              and New Central operations.
            </p>
          </div>
          <GroupStatus
            saved={unifiedSaved}
            verified={status?.creds_valid ?? false}
            loading={false}
          />
        </div>

        <div className="space-y-4 px-4 py-4">
          <VerificationMessage error={groupErrors.unified} />
          <div className="space-y-1.5">
            <Label
              htmlFor="new-central-endpoint"
              className="text-[0.6875rem] font-medium text-[var(--cc-ink-soft)]"
            >
              New Central hostname
            </Label>
            <Input
              id="new-central-endpoint"
              value={endpoints.newCentral}
              readOnly
              className="h-9 bg-[var(--cc-muted)] font-mono text-xs text-[var(--cc-ink-soft)]"
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <CredentialField
              id="glp-client-id"
              label="Client ID"
              value={clientId}
              onChange={setClientId}
              saved={presence.clientId}
              replacing={replacing.clientId}
              onReplace={() => replaceField("clientId")}
              disabled={isSaving}
              placeholder="Enter client ID"
            />
            <CredentialField
              id="glp-client-secret"
              label="Client secret"
              value={clientSecret}
              onChange={setClientSecret}
              saved={presence.clientSecret}
              replacing={replacing.clientSecret}
              onReplace={() => replaceField("clientSecret")}
              disabled={isSaving}
              placeholder="Enter client secret"
              secret
              visible={showClientSecret}
              onVisibilityChange={() =>
                setShowClientSecret((current) => !current)
              }
            />
            <CredentialField
              id="glp-workspace-id"
              label="Workspace ID"
              value={workspaceId}
              onChange={setWorkspaceId}
              saved={presence.workspaceId}
              replacing={replacing.workspaceId}
              onReplace={() => replaceField("workspaceId")}
              disabled={isSaving}
              placeholder="Enter workspace ID"
            />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            <a
              href="https://developer.arubanetworks.com/new-central/docs/generating-and-managing-access-tokens"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-sm text-xs font-medium text-[var(--cc-accent)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cc-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--cc-raised)]"
            >
              Find GreenLake credentials
              <ExternalLink aria-hidden="true" className="h-3.5 w-3.5" />
            </a>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => handleSave("unified")}
              disabled={isSaving}
              className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] hover:bg-[var(--cc-muted)]"
            >
              {savingTarget === "unified" ? (
                <>
                  <Loader2
                    aria-hidden="true"
                    className="motion-safe:animate-spin text-[var(--cc-accent)]"
                  />
                  Verifying
                </>
              ) : (
                "Save & verify"
              )}
            </Button>
          </div>
        </div>
      </section>

      <Collapsible open={classicOpen} onOpenChange={setClassicOpen}>
        <section
          aria-labelledby="classic-credentials-title"
          className="overflow-hidden rounded-xl border border-[var(--cc-line)] bg-[var(--cc-surface)]"
        >
          <CollapsibleTrigger asChild>
            <button
              type="button"
              className="flex w-full items-start justify-between gap-4 px-4 py-3.5 text-left hover:bg-[var(--cc-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--cc-accent)]"
            >
              <span>
                <span
                  id="classic-credentials-title"
                  className="block text-sm font-semibold text-[var(--cc-ink)]"
                >
                  Classic Central
                </span>
                <span className="mt-1 block max-w-[58ch] text-xs leading-5 text-[var(--cc-ink-soft)]">
                  Used for site and group operations. Tokens expire routinely;
                  when this one does, paste only a fresh token here.
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-2">
                <GroupStatus
                  saved={classicSaved}
                  verified={status?.classic_valid ?? false}
                  loading={false}
                />
                <ChevronDown
                  aria-hidden="true"
                  className={cn(
                    "h-4 w-4 text-[var(--cc-ink-soft)] transition-transform duration-200",
                    classicOpen && "rotate-180"
                  )}
                />
              </span>
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="space-y-4 border-t border-[var(--cc-line)] px-4 py-4">
              <VerificationMessage error={groupErrors.classic} />
              <div className="space-y-1.5">
                <Label
                  htmlFor="classic-central-endpoint"
                  className="text-[0.6875rem] font-medium text-[var(--cc-ink-soft)]"
                >
                  Classic Central base URL
                </Label>
                <Input
                  id="classic-central-endpoint"
                  value={endpoints.classicCentral}
                  readOnly
                  className="h-9 bg-[var(--cc-muted)] font-mono text-xs text-[var(--cc-ink-soft)]"
                />
              </div>
              <CredentialField
                id="classic-access-token"
                label="API access token"
                value={accessToken}
                onChange={setAccessToken}
                saved={presence.accessToken}
                replacing={replacing.accessToken}
                onReplace={() => replaceField("accessToken")}
                disabled={isSaving}
                placeholder="Paste a fresh access token"
                autoFocus={initialSection === "classic"}
                secret
                visible={showAccessToken}
                onVisibilityChange={() =>
                  setShowAccessToken((current) => !current)
                }
              />
              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <a
                  href="https://developer.arubanetworks.com/central/docs/access-token-management"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 rounded-sm text-xs font-medium text-[var(--cc-accent)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cc-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--cc-raised)]"
                >
                  Find a Classic Central token
                  <ExternalLink aria-hidden="true" className="h-3.5 w-3.5" />
                </a>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => handleSave("classic")}
                  disabled={isSaving}
                  className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] hover:bg-[var(--cc-muted)]"
                >
                  {savingTarget === "classic" ? (
                    <>
                      <Loader2
                        aria-hidden="true"
                        className="motion-safe:animate-spin text-[var(--cc-accent)]"
                      />
                      Verifying
                    </>
                  ) : (
                    "Save & verify"
                  )}
                </Button>
              </div>
            </div>
          </CollapsibleContent>
        </section>
      </Collapsible>

      <div className="flex flex-col gap-3 rounded-xl border border-[var(--cc-line)] bg-[var(--cc-muted)] px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex max-w-[55ch] items-start gap-2.5 text-xs leading-5 text-[var(--cc-ink-soft)]">
          <ShieldCheck
            aria-hidden="true"
            className="mt-0.5 h-4 w-4 shrink-0"
          />
          <p>
            Secrets live server-side and are never returned to the browser. A
            failed verification leaves the previously working credential pair
            unchanged.
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          onClick={() => handleSave("all")}
          disabled={isSaving}
          className="shrink-0 bg-[var(--cc-accent)] text-[var(--cc-accent-ink)] hover:bg-[var(--cc-accent-hover)]"
        >
          {savingTarget === "all" ? (
            <>
              <Loader2 aria-hidden="true" className="motion-safe:animate-spin" />
              Verifying all
            </>
          ) : (
            "Save & verify all"
          )}
        </Button>
      </div>
    </div>
  );
}

export function CredentialsModal({
  open,
  onOpenChange,
  initialSection,
}: CredentialsModalProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex w-full flex-col gap-0 overflow-hidden border-[var(--cc-line-strong)] bg-[var(--cc-raised)] p-0 text-[var(--cc-ink)] shadow-[var(--cc-dialog-shadow)] sm:max-w-2xl"
      >
        <SheetHeader className="shrink-0 border-b border-[var(--cc-line)] px-5 py-4 pr-14 text-left sm:px-6">
          <SheetTitle className="text-xl tracking-tight text-[var(--cc-ink)]">
            Manage credentials
          </SheetTitle>
          <SheetDescription className="max-w-[65ch] text-xs leading-5 text-[var(--cc-ink-soft)]">
            Connect both Central APIs to the same physical cluster.
          </SheetDescription>
        </SheetHeader>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <CredentialsContent
            active={open}
            embedded
            initialSection={initialSection}
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}
