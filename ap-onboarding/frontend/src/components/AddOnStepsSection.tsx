import { AlertCircle, ChevronDown, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type { StepMeta } from "@/lib/api";
import { cn } from "@/lib/utils";

interface AddOnStepsSectionProps {
  steps: StepMeta[];
  enabledStepKeys: ReadonlySet<string>;
  loading: boolean;
  error: string | null;
  onToggle: (key: string, enabled: boolean) => void;
  onRetry: () => void;
}

function fieldTypeLabel(step: StepMeta): string {
  switch (step.field.type) {
    case "list[string]":
      return "List";
    case "bool":
      return "True / false";
    case "int":
      return "Whole number";
    default:
      return "Text";
  }
}

export function AddOnStepsSection({
  steps,
  enabledStepKeys,
  loading,
  error,
  onToggle,
  onRetry,
}: AddOnStepsSectionProps) {
  const enabledCount = steps.filter((step) =>
    enabledStepKeys.has(step.key)
  ).length;

  return (
    <Collapsible
      className="overflow-hidden rounded-xl border border-[var(--cc-line)] bg-[var(--cc-surface)]"
      defaultOpen={false}
    >
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className="group flex min-h-14 w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-[var(--cc-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--cc-accent)]"
        >
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-semibold">Add-on steps</span>
            <span
              className={cn(
                "mt-0.5 block text-xs",
                error
                  ? "text-[var(--cc-danger)]"
                  : "text-[var(--cc-ink-soft)]"
              )}
            >
              {loading
                ? "Loading available steps…"
                : error
                  ? "Available steps could not be loaded"
                  : `${enabledCount} of ${steps.length} enabled`}
            </span>
          </span>
          {loading && (
            <Loader2
              aria-label="Loading add-on steps"
              className="h-4 w-4 motion-safe:animate-spin text-[var(--cc-ink-faint)]"
            />
          )}
          <ChevronDown
            aria-hidden="true"
            className="h-4 w-4 text-[var(--cc-ink-faint)] transition-transform duration-200 group-data-[state=open]:rotate-180"
          />
        </button>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="border-t border-[var(--cc-line)] p-4">
          {error ? (
            <div
              role="alert"
              className="flex flex-col gap-3 rounded-lg border border-[color-mix(in_oklch,var(--cc-danger)_35%,var(--cc-line))] bg-[var(--cc-danger-soft)] px-3.5 py-3 text-xs text-[var(--cc-danger)] sm:flex-row sm:items-center sm:justify-between"
            >
              <span className="flex min-w-0 items-start gap-2">
                <AlertCircle
                  aria-hidden="true"
                  className="mt-0.5 h-4 w-4 shrink-0"
                />
                <span>Could not load add-on steps: {error}</span>
              </span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={onRetry}
                className="shrink-0 border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)]"
              >
                <RefreshCw aria-hidden="true" />
                Retry
              </Button>
            </div>
          ) : loading ? (
            <p className="text-xs text-[var(--cc-ink-soft)]">
              Loading step metadata from the service.
            </p>
          ) : steps.length === 0 ? (
            <p className="text-xs text-[var(--cc-ink-soft)]">
              No add-on steps are registered.
            </p>
          ) : (
            <div className="divide-y divide-[var(--cc-line)] border-y border-[var(--cc-line)]">
              {steps.map((step) => {
                const enabled = enabledStepKeys.has(step.key);
                const inputId = `add-on-step-${step.key}`;
                return (
                  <label
                    key={step.key}
                    htmlFor={inputId}
                    className={cn(
                      "flex min-h-11 cursor-pointer gap-3 px-2 py-3 transition-colors duration-200 ease-out",
                      enabled
                        ? "bg-[var(--cc-accent-soft)] ring-1 ring-inset ring-[var(--cc-accent)]"
                        : "bg-[var(--cc-muted)]",
                      step.field.required && "cursor-not-allowed"
                    )}
                  >
                    <input
                      id={inputId}
                      type="checkbox"
                      role="switch"
                      checked={enabled}
                      disabled={step.field.required}
                      onChange={(event) =>
                        onToggle(step.key, event.target.checked)
                      }
                      className={cn(
                        "mt-0.5 h-4 w-4 shrink-0 rounded-sm accent-[var(--cc-accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cc-accent)] focus-visible:ring-offset-2",
                        enabled
                          ? "focus-visible:ring-offset-[var(--cc-accent-soft)]"
                          : "focus-visible:ring-offset-[var(--cc-muted)]"
                      )}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold">
                          {step.label}
                        </span>
                        <span className="rounded-full border border-[var(--cc-line)] bg-[var(--cc-surface)] px-2 py-0.5 text-[0.625rem] font-bold uppercase tracking-[0.08em] text-[var(--cc-ink-faint)]">
                          {fieldTypeLabel(step)}
                        </span>
                        {step.field.required && (
                          <span className="text-[0.6875rem] font-semibold text-[var(--cc-accent)]">
                            Required
                          </span>
                        )}
                      </span>
                      <span className="mt-1 block text-xs leading-5 text-[var(--cc-ink-soft)]">
                        {step.description}
                      </span>
                      <span
                        className={cn(
                          "mt-2 block text-[0.6875rem] leading-4",
                          enabled
                            ? "text-[var(--cc-ink-soft)]"
                            : "text-[var(--cc-ink-faint)]"
                        )}
                      >
                        {step.field.help}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
