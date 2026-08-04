import { useState } from "react";
import { Loader2 } from "lucide-react";
import AppShell from "@/components/AppShell";
import { NetworkSetupEditor } from "@/components/NetworkSetupEditor";
import { NetworkSetupLiveView } from "@/components/NetworkSetupLiveView";
import { useCredentialGuard } from "@/lib/credentialGuard";

export function NetworkSetup() {
  const [runId, setRunId] = useState<string | null>(null);
  const { checking } = useCredentialGuard("/network-setup");

  return (
    <AppShell>
      {checking ? (
        <div role="status" className="flex items-center justify-center">
          <Loader2
            className="h-8 w-8 motion-safe:animate-spin text-[var(--cc-ink-soft)]"
            aria-hidden="true"
          />
          <span className="sr-only">Loading…</span>
        </div>
      ) : runId ? (
        <NetworkSetupLiveView runId={runId} />
      ) : (
        <NetworkSetupEditor onRunStarted={setRunId} />
      )}
    </AppShell>
  );
}
