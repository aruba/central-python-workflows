import { Routes, Route, Navigate } from "react-router-dom";
import { Credentials } from "@/pages/Credentials";
import { NetworkSetup } from "@/pages/NetworkSetup";
import { Onboarding } from "@/pages/Onboarding";
import { Results } from "@/pages/Results";
import { Toaster } from "@/components/ui/sonner";

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/credentials" element={<Credentials />} />
        <Route path="/network-setup" element={<NetworkSetup />} />
        <Route path="/results" element={<Results />} />
        <Route path="*" element={<Navigate to="/onboarding" replace />} />
      </Routes>
      <Toaster />
    </>
  );
}
