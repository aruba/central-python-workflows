import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getStatus } from "@/lib/api";

export function useCredentialGuard(returnTo: string): { checking: boolean } {
  const [checking, setChecking] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    getStatus()
      .then((status) => {
        if (!status.creds_valid || !status.classic_creds_valid) {
          navigate(`/credentials?returnTo=${encodeURIComponent(returnTo)}`);
        } else {
          setChecking(false);
        }
      })
      .catch(() => {
        // On error, let the page load — backend will reject the run if needed
        setChecking(false);
      });
  }, [returnTo, navigate]);

  return { checking };
}
