import { useEffect, useState } from "react";
import { Check, Circle, XCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { getStatus, type StatusResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

type CredentialState = "valid" | "invalid" | "unknown";

interface CredentialBadgeProps {
  loading: boolean;
  name: string;
  valid: boolean | null;
}

function CredentialBadge({ loading, name, valid }: CredentialBadgeProps) {
  const credentialState: CredentialState =
    valid === null ? "unknown" : valid ? "valid" : "invalid";

  return (
    <Badge
      variant="secondary"
      className={cn(
        "cursor-pointer",
        credentialState === "valid"
          ? "border-[color-mix(in_oklch,var(--cc-success)_30%,var(--cc-line))] bg-[var(--cc-success-soft)] text-[var(--cc-success)]"
          : credentialState === "invalid"
            ? "border-[color-mix(in_oklch,var(--cc-danger)_35%,var(--cc-line))] bg-[var(--cc-danger-soft)] text-[var(--cc-danger)]"
            : "border-[var(--cc-line)] bg-[var(--cc-muted)] text-[var(--cc-ink-soft)]",
        loading && "motion-safe:animate-pulse"
      )}
    >
      {credentialState === "valid" ? (
        <Check aria-hidden="true" className="h-3.5 w-3.5" />
      ) : credentialState === "invalid" ? (
        <XCircle aria-hidden="true" className="h-3.5 w-3.5" />
      ) : (
        <Circle aria-hidden="true" className="h-3.5 w-3.5" />
      )}
      {name} ·{" "}
      {credentialState === "valid"
        ? "Verified"
        : credentialState === "invalid"
          ? "Invalid"
          : "Status unavailable"}
    </Badge>
  );
}

export function CredentialPills() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch status on mount
    const fetchStatus = async () => {
      try {
        const data = await getStatus();
        setStatus(data);
      } catch {
        // Leave status as null on error (both pills will be grey)
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();

    // Poll every 60 seconds
    const interval = setInterval(fetchStatus, 60000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div
      className="flex gap-2"
      role="status"
      aria-live="polite"
      aria-label="Credential status"
    >
      {/* No aria-label on these links: it would override the badge text, and
          the state word is the whole point of the pill. The badge content is
          the accessible name, so it matches what is on screen. */}
      <Link to="/credentials">
        <CredentialBadge
          loading={loading}
          name="Central"
          valid={status?.creds_valid ?? null}
        />
      </Link>
      <Link to="/credentials">
        <CredentialBadge
          loading={loading}
          name="Classic Central"
          valid={status?.classic_creds_valid ?? null}
        />
      </Link>
    </div>
  );
}
