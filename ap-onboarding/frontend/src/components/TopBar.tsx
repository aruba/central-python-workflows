import {
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { useTheme } from "next-themes";
import { NavLink } from "react-router-dom";
import {
  Check,
  ChevronDown,
  Circle,
  Cloud,
  Loader2,
  Moon,
  Sun,
} from "lucide-react";
import { CredentialsModal } from "@/components/CredentialsModal";
import { Button } from "@/components/ui/button";
import { getCredentials, getCredentialsStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/credentials", label: "Credentials" },
  { to: "/network-setup", label: "Network Setup" },
  { to: "/onboarding", label: "Onboarding" },
  { to: "/results", label: "Results" },
] as const;

function CentralInstanceChip() {
  const [open, setOpen] = useState(false);
  const [credentialsOpen, setCredentialsOpen] = useState(false);
  const [cluster, setCluster] = useState<string | null>(null);
  const [credentialState, setCredentialState] = useState<
    "checking" | "verified" | "needs-attention" | "unavailable"
  >("checking");
  const containerRef = useRef<HTMLDivElement>(null);

  const loadCentralInstance = useCallback(async () => {
    setCredentialState("checking");
    const [credentialsResult, statusResult] = await Promise.allSettled([
      getCredentials(),
      getCredentialsStatus(),
    ]);

    if (credentialsResult.status === "fulfilled") {
      setCluster(credentialsResult.value.cluster);
    } else {
      setCluster(null);
    }

    if (statusResult.status === "rejected") {
      setCredentialState("unavailable");
      return;
    }

    setCredentialState(
      statusResult.value.creds_valid && statusResult.value.classic_valid
        ? "verified"
        : "needs-attention"
    );
  }, []);

  useEffect(() => {
    void loadCentralInstance();
  }, [loadCentralInstance]);

  useEffect(() => {
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  return (
    <>
      <div className="relative min-w-0" ref={containerRef}>
        <button
          type="button"
          aria-expanded={open}
          aria-controls="central-instance-details"
          onClick={() => {
            setOpen((current) => {
              const next = !current;
              if (next) void loadCentralInstance();
              return next;
            });
          }}
          className="inline-flex h-9 max-w-[18rem] items-center gap-2 rounded-lg border border-[var(--cc-topbar-line)] bg-[var(--cc-topbar-control)] px-3 text-left text-xs text-[var(--cc-topbar-muted)] transition-colors hover:border-[var(--cc-topbar-line-hover)] hover:bg-[var(--cc-topbar-control-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cc-topbar-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--cc-topbar)]"
        >
          <span
            aria-hidden="true"
            className={cn(
              "h-2 w-2 shrink-0 rounded-full",
              credentialState === "verified"
                ? "bg-[var(--cc-success)] shadow-[var(--cc-topbar-status-halo)]"
                : credentialState === "needs-attention"
                  ? "bg-[var(--cc-warning)]"
                  : "bg-[var(--cc-topbar-muted)]"
            )}
          />
          <strong className="truncate font-semibold text-[var(--cc-topbar-ink)]">
            {cluster ? `Central ${cluster}` : "Central instance"}
          </strong>
          <ChevronDown
            aria-hidden="true"
            className={cn(
              "h-3.5 w-3.5 shrink-0 transition-transform duration-200",
              open && "rotate-180"
            )}
          />
        </button>

        {open && (
          <div
            id="central-instance-details"
            role="dialog"
            aria-label="Central instance details"
            className="absolute left-0 top-[calc(100%+0.625rem)] z-50 w-[min(21rem,calc(100vw-2rem))] rounded-xl border border-[var(--cc-line-strong)] bg-[var(--cc-raised)] p-4 text-[var(--cc-ink)] shadow-[var(--cc-shadow)]"
          >
            <div className="mb-3 flex items-center gap-2 border-b border-[var(--cc-line)] pb-3">
              <Cloud
                aria-hidden="true"
                className="h-4 w-4 text-[var(--cc-accent)]"
              />
              <p className="text-sm font-semibold">Central connection</p>
            </div>
            <dl className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-x-3 gap-y-2.5 text-xs">
              <dt className="text-[var(--cc-ink-soft)]">Cluster</dt>
              <dd className="font-medium">{cluster ?? "Not configured"}</dd>
              <dt className="text-[var(--cc-ink-soft)]">Credentials</dt>
              <dd
                className={cn(
                  "inline-flex items-center gap-1.5 font-medium",
                  credentialState === "verified"
                    ? "text-[var(--cc-success)]"
                    : credentialState === "needs-attention"
                      ? "text-[var(--cc-warning)]"
                      : "text-[var(--cc-ink-soft)]"
                )}
              >
                {credentialState === "checking" ? (
                  <Loader2
                    aria-hidden="true"
                    className="h-3.5 w-3.5 motion-safe:animate-spin"
                  />
                ) : credentialState === "verified" ? (
                  <Check aria-hidden="true" className="h-3.5 w-3.5" />
                ) : (
                  <Circle aria-hidden="true" className="h-3.5 w-3.5" />
                )}
                {credentialState === "checking"
                  ? "Checking"
                  : credentialState === "verified"
                    ? "Verified"
                    : credentialState === "needs-attention"
                      ? "Needs verification"
                      : "Status unavailable"}
              </dd>
            </dl>
            <p className="mt-3 text-xs leading-5 text-[var(--cc-ink-soft)]">
              Credentials are stored server-side. Secrets do not appear in the
              plan or run log.
            </p>
            <Button
              type="button"
              variant="link"
              className="mt-2 h-auto justify-start p-0 text-xs text-[var(--cc-accent)]"
              onClick={() => {
                setOpen(false);
                setCredentialsOpen(true);
              }}
            >
              Manage credentials
            </Button>
          </div>
        )}
      </div>
      <CredentialsModal
        open={credentialsOpen}
        onOpenChange={(nextOpen) => {
          setCredentialsOpen(nextOpen);
          if (!nextOpen) void loadCentralInstance();
        }}
      />
    </>
  );
}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const dark = mounted && resolvedTheme === "dark";

  return (
    <button
      type="button"
      onClick={() => setTheme(dark ? "light" : "dark")}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      title={dark ? "Switch to light theme" : "Switch to dark theme"}
      className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-[var(--cc-topbar-line)] bg-[var(--cc-topbar-control)] text-[var(--cc-topbar-ink)] transition-colors hover:border-[var(--cc-topbar-line-hover)] hover:bg-[var(--cc-topbar-control-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cc-topbar-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--cc-topbar)]"
    >
      {dark ? (
        <Sun aria-hidden="true" className="h-4 w-4" />
      ) : (
        <Moon aria-hidden="true" className="h-4 w-4" />
      )}
    </button>
  );
}

/**
 * `meta` renders before the theme toggle, `actions` after it, so the primary
 * action of a surface always sits at the trailing edge with the utility
 * controls tucked inside it.
 */
export function TopBar({
  meta,
  actions,
}: {
  meta?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--cc-topbar-line)] bg-[var(--cc-topbar)] text-[var(--cc-topbar-ink)] shadow-[var(--cc-topbar-shadow)]">
      <div className="mx-auto flex min-h-16 max-w-[92rem] flex-wrap items-center gap-3 px-4 py-2.5 sm:px-6 lg:flex-nowrap">
        <div
          className="flex min-w-fit items-center gap-2.5"
          aria-label="AP Onboarding"
        >
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-[var(--cc-brand-mark)] text-[0.6875rem] font-extrabold tracking-tight text-[var(--cc-brand-mark-ink)]">
            AP
          </span>
          <div>
            <p className="text-sm font-bold tracking-tight">AP Onboarding</p>
            <p className="text-[0.625rem] font-semibold uppercase tracking-[0.14em] text-[var(--cc-topbar-muted)]">
              Guided command center
            </p>
          </div>
        </div>

        <nav
          aria-label="Main navigation"
          className="order-3 flex min-w-0 basis-full gap-1 overflow-x-auto lg:order-none lg:basis-auto"
        >
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "shrink-0 rounded-lg px-3 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cc-topbar-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--cc-topbar)]",
                  isActive
                    ? "bg-[var(--cc-topbar-control)] font-semibold text-[var(--cc-topbar-ink)]"
                    : "font-medium text-[var(--cc-topbar-muted)] hover:bg-[var(--cc-topbar-control-hover)] hover:text-[var(--cc-topbar-ink)]"
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="order-3 min-w-0 flex-1 basis-full lg:order-none lg:basis-auto">
          <CentralInstanceChip />
        </div>

        <div className="ml-auto flex items-center gap-2">
          {meta}
          <ThemeToggle />
          {actions}
        </div>
      </div>
    </header>
  );
}
