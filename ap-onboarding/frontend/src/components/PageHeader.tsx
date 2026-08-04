import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  description?: string;
  /** Optional actions rendered on the trailing edge of the header row. */
  actions?: ReactNode;
}

/**
 * Standard page header used across every top-level surface so title
 * typography, spacing, and the optional actions row stay consistent.
 */
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold tracking-[-0.035em] sm:text-3xl">
          {title}
        </h1>
        {description && (
          <p className="mt-2 max-w-[68ch] text-sm leading-6 text-[var(--cc-ink-soft)]">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex gap-2 mt-1 shrink-0">{actions}</div>}
    </div>
  );
}
