import type { ReactNode } from "react";
import { TopBar } from "@/components/TopBar";

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="command-center min-h-screen bg-[var(--cc-canvas)] text-[var(--cc-ink)]">
      <TopBar />
      <main className="mx-auto w-full max-w-[92rem] px-4 pb-24 pt-8 sm:px-6 sm:pt-10">
        {children}
      </main>
    </div>
  );
}
