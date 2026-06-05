import * as React from "react";
import { Loader2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { login, loginDemo, AUTH_URL, type MspCredentials } from "@/lib/api";
import { STORAGE_KEYS } from "@/lib/constants";

interface LoginGateProps {
  onConnected: () => void;
}

const EMPTY_CREDS: MspCredentials = {
  base_url: "",
  workspace_id: "",
  client_id: "",
  client_secret: "",
};

const BASE_URL_OPTIONS = [
  { label: "EU-1 (eu)", host: "de1.api.central.arubanetworks.com" },
  {
    label: "EU-Central2 (eucentral2)",
    host: "de2.api.central.arubanetworks.com",
  },
  {
    label: "EU-Central3 (eucentral3)",
    host: "de3.api.central.arubanetworks.com",
  },
  { label: "UK (ukwest2)", host: "gb1.api.central.arubanetworks.com" },
  { label: "US-1 (prod)", host: "us1.api.central.arubanetworks.com" },
  { label: "US-2 (central-prod2)", host: "us2.api.central.arubanetworks.com" },
  { label: "US-WEST-4 (uswest4)", host: "us4.api.central.arubanetworks.com" },
  { label: "US-WEST-5 (uswest5)", host: "us5.api.central.arubanetworks.com" },
  { label: "US-East1 (us-east-1)", host: "us6.api.central.arubanetworks.com" },
  { label: "Canada-1 (starman)", host: "ca1.api.central.arubanetworks.com" },
  { label: "APAC-1 (apac)", host: "in1.api.central.arubanetworks.com" },
  { label: "APAC-EAST1 (apaceast)", host: "jp1.api.central.arubanetworks.com" },
  {
    label: "APAC-SOUTH1 (apacsouth)",
    host: "au1.api.central.arubanetworks.com",
  },
  { label: "UAE (uaenorth1)", host: "ae1.api.central.arubanetworks.com" },
  { label: "China (china-prod)", host: "cn1.api.central.arubanetworks.com.cn" },
  {
    label: "Internal (internal)",
    host: "internal.api.central.arubanetworks.com",
  },
].map((option) => ({
  ...option,
  value: `https://${option.host}`,
}));

function normalizeBaseUrl(baseUrl: string): string {
  const trimmed = baseUrl.trim();
  if (
    !trimmed ||
    trimmed.startsWith("http://") ||
    trimmed.startsWith("https://")
  ) {
    return trimmed;
  }
  return `https://${trimmed}`;
}

function serializeCredentials(creds: MspCredentials): MspCredentials {
  return {
    base_url: normalizeBaseUrl(creds.base_url),
    workspace_id: creds.workspace_id.trim(),
    client_id: creds.client_id.trim(),
    client_secret: creds.client_secret,
  };
}

export function LoginGate({ onConnected }: LoginGateProps) {
  const [creds, setCreds] = React.useState<MspCredentials>(EMPTY_CREDS);
  const [gatewayChoice, setGatewayChoice] = React.useState<string>("");
  const [remember, setRemember] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [demoing, setDemoing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    // The Base URL is a Select, so the browser's native autofill can't repopulate
    // it the way it does the text inputs. Persist/restore it on its own (it's a
    // non-secret gateway endpoint) so it survives a reopen regardless of "remember".
    const storedBaseUrl = localStorage.getItem(STORAGE_KEYS.baseUrl);
    if (storedBaseUrl) {
      const baseUrl = normalizeBaseUrl(storedBaseUrl);
      setCreds((prev) => ({ ...prev, base_url: baseUrl }));
      const isPreset = BASE_URL_OPTIONS.some((o) => o.value === baseUrl);
      setGatewayChoice(baseUrl ? (isPreset ? baseUrl : "custom") : "");
    }

    const stored = localStorage.getItem(STORAGE_KEYS.creds);
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as MspCredentials;
        const serialized = serializeCredentials({ ...EMPTY_CREDS, ...parsed });
        setCreds(serialized);
        const isPreset = BASE_URL_OPTIONS.some(
          (o) => o.value === serialized.base_url,
        );
        setGatewayChoice(
          serialized.base_url
            ? isPreset
              ? serialized.base_url
              : "custom"
            : "",
        );
      } catch {
        // ignore malformed stored value
      }
    }
  }, []);

  const isDisabled =
    submitting ||
    !creds.base_url.trim() ||
    !creds.workspace_id.trim() ||
    !creds.client_id.trim() ||
    !creds.client_secret.trim();

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const storedCreds = serializeCredentials(creds);
      await login(storedCreds);
      // Always remember the (non-secret) Base URL so the Select repopulates on
      // reopen, matching how the browser autofills the text inputs.
      if (storedCreds.base_url) {
        localStorage.setItem(STORAGE_KEYS.baseUrl, storedCreds.base_url);
      }
      if (remember) {
        localStorage.setItem(STORAGE_KEYS.creds, JSON.stringify(storedCreds));
      } else {
        localStorage.removeItem(STORAGE_KEYS.creds);
      }
      onConnected();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDemoMode() {
    setDemoing(true);
    setError(null);
    try {
      await loginDemo();
      onConnected();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDemoing(false);
    }
  }

  function setField(field: keyof MspCredentials) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setCreds((prev) => ({ ...prev, [field]: e.target.value }));
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Connect to Aruba Central MSP</CardTitle>
          <CardDescription>
            Enter your MSP workspace credentials to begin.
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form id="login-form" onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="base_url">Base URL</Label>
              <Select
                value={gatewayChoice}
                onValueChange={(value) => {
                  setGatewayChoice(value);
                  if (value !== "custom") {
                    setCreds((prev) => ({ ...prev, base_url: value }));
                  } else {
                    setCreds((prev) => ({ ...prev, base_url: "" }));
                  }
                }}
                required
                disabled={submitting}
              >
                <SelectTrigger id="base_url">
                  <SelectValue placeholder="Select a Central API gateway" />
                </SelectTrigger>
                <SelectContent>
                  {BASE_URL_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      <span className="flex flex-col">
                        <span>{option.label}</span>
                        <span className="text-xs text-muted-foreground">
                          {option.host}
                        </span>
                      </span>
                    </SelectItem>
                  ))}
                  <SelectItem value="custom">Custom…</SelectItem>
                </SelectContent>
              </Select>
              {gatewayChoice === "custom" && (
                <Input
                  id="custom_base_url"
                  type="text"
                  placeholder="https://your-gateway.example.com"
                  value={creds.base_url}
                  onChange={(e) =>
                    setCreds((prev) => ({ ...prev, base_url: e.target.value }))
                  }
                  disabled={submitting}
                  className="mt-2"
                />
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="workspace_id">Workspace ID</Label>
              <Input
                id="workspace_id"
                type="text"
                value={creds.workspace_id}
                onChange={setField("workspace_id")}
                required
                disabled={submitting}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="client_id">Client ID</Label>
              <Input
                id="client_id"
                type="text"
                value={creds.client_id}
                onChange={setField("client_id")}
                required
                disabled={submitting}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="client_secret">Client Secret</Label>
              <Input
                id="client_secret"
                type="password"
                value={creds.client_secret}
                onChange={setField("client_secret")}
                required
                disabled={submitting}
              />
            </div>

            <div className="flex items-center gap-2 pt-1">
              <Checkbox
                id="remember"
                checked={remember}
                onCheckedChange={(checked) => setRemember(checked === true)}
                disabled={submitting}
              />
              <div className="flex flex-col gap-0.5">
                <Label htmlFor="remember" className="cursor-pointer">
                  Remember on this device
                </Label>
                <span className="text-xs text-muted-foreground">
                  Stored in your browser
                </span>
              </div>
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}

            <Button
              type="submit"
              form="login-form"
              className="w-full"
              disabled={isDisabled}
            >
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {submitting ? "Connecting…" : "Connect"}
            </Button>
          </form>

          <div className="relative my-4">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">
                or
              </span>
            </div>
          </div>

          <Button
            type="button"
            variant="outline"
            className="w-full"
            disabled={submitting || demoing}
            onClick={handleDemoMode}
          >
            {demoing && <Loader2 className="h-4 w-4 animate-spin" />}
            {demoing ? "Loading demo…" : "Try demo mode"}
          </Button>
        </CardContent>

        <CardFooter>
          <a
            href={AUTH_URL}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Learn more about generating MSP API Credentials ↗
          </a>
        </CardFooter>
      </Card>
    </div>
  );
}
