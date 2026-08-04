import { useNavigate, useSearchParams } from "react-router-dom";
import { CredentialsContent } from "@/components/CredentialsModal";
import AppShell from "@/components/AppShell";
import { PageHeader } from "@/components/PageHeader";

export function Credentials() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get("returnTo");

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <div className="mb-6">
          <PageHeader
            title="Credentials"
            description="Connect HPE GreenLake, New Central, and Classic Central"
          />
        </div>
        <CredentialsContent
          onSaved={() => {
            if (returnTo) navigate(returnTo);
          }}
        />
      </div>
    </AppShell>
  );
}
