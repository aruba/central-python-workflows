import { useEffect, useRef, useState } from "react";
import { Loader2, TriangleAlert } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ConnectionState, RawEvent } from "@/lib/events";

interface LogStreamProps {
  events: RawEvent[];
  maxHeight?: string;
  connectionState?: ConnectionState;
  title?: string | null;
}

const ROW_HEIGHT = 32;

export function LogStream({
  events,
  maxHeight = "300px",
  connectionState,
  title = "Event stream",
}: LogStreamProps) {
  const [serialFilter, setSerialFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("All");
  const eventTypes = [
    "All",
    ...Array.from(
      new Set(
        events
          .map((event) => event.type)
          .filter((type): type is string => typeof type === "string")
      )
    ).sort(),
  ];
  const hasFilters = serialFilter.trim().length > 0 || typeFilter !== "All";
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);
  const [scrollTop, setScrollTop] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Filter events
  const filteredEvents = events.filter((event) => {
    // Filter by type
    if (typeFilter !== "All") {
      if ((event.type as string) !== typeFilter) {
        return false;
      }
    }

    // Filter by serial/name (case-insensitive)
    if (serialFilter.trim()) {
      const serial = event.serial as string | undefined;
      const name = event.name as string | undefined;
      const searchText = serialFilter.toLowerCase();

      if (
        !serial?.toLowerCase().includes(searchText) &&
        !name?.toLowerCase().includes(searchText)
      ) {
        return false;
      }
    }

    return true;
  });

  // Auto-scroll handler
  useEffect(() => {
    if (!shouldAutoScroll || !scrollRef.current) {
      return;
    }

    // Scroll to bottom
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [filteredEvents, shouldAutoScroll]);

  // Detect manual scroll
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget;
    setScrollTop(target.scrollTop);
    const isAtBottom =
      Math.abs(
        target.scrollHeight - target.scrollTop - target.clientHeight
      ) < 50;
    setShouldAutoScroll(isAtBottom);
  };

  // Virtual scrolling calculation
  const containerHeight = parseFloat(maxHeight);
  const totalHeight = filteredEvents.length * ROW_HEIGHT;
  const startIdx = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - 5);
  const endIdx = Math.min(
    filteredEvents.length,
    startIdx + Math.ceil(containerHeight / ROW_HEIGHT) + 10
  );

  const visibleEvents = filteredEvents.slice(startIdx, endIdx);
  const offsetTop = startIdx * ROW_HEIGHT;

  // Format event row
  const formatEventRow = (event: RawEvent): string => {
    const type = event.type as string;

    if (type === "step") {
      const serial = event.serial as string | undefined;
      const step = event.step as string | undefined;
      const status = event.status as string | undefined;
      const message = event.message as string | undefined;
      if (step === "firmware_check" && message) {
        return `${serial} → ${message}`;
      }
      return `${serial} → ${step}: ${status}`;
    }

    if (type === "device_done") {
      const serial = event.serial as string | undefined;
      const overall = event.overall as string | undefined;
      return `${serial} → overall: ${overall}`;
    }

    if (type === "site") {
      const name = event.name as string | undefined;
      const step = event.step as string | undefined;
      const status = event.status as string | undefined;
      return `${name} → ${step}: ${status}`;
    }

    if (type === "site_collection") {
      const name = event.name as string | undefined;
      const step = event.step as string | undefined;
      const status = event.status as string | undefined;
      return `${name} → ${step}: ${status}`;
    }

    if (type === "group" || type === "group_done") {
      const name = event.name as string | undefined;
      const step = event.step as string | undefined;
      const status = event.status as string | undefined;
      return `${name} → ${step ?? "overall"}: ${status}`;
    }

    if (type === "profile") {
      const target = event.target as string | undefined;
      const profile = event.profile as string | undefined;
      const status = event.status as string | undefined;
      return `${target} → ${profile}: ${status}`;
    }

    if (type === "error") {
      const message = event.message as string | undefined;
      return `Error: ${message}`;
    }

    return JSON.stringify(event);
  };

  const getBadgeVariant = (
    type: string
  ): "default" | "secondary" | "destructive" | "outline" => {
    if (type === "error") return "destructive";
    if (type === "run_started") return "secondary";
    return "outline";
  };

  return (
    <Card className="border-0 bg-transparent text-[var(--cc-ink)] shadow-none">
      {title && (
        <CardHeader className="px-0 pb-3 pt-0">
          <CardTitle className="text-sm">{title}</CardTitle>
        </CardHeader>
      )}

      <CardContent className="space-y-3 px-0 pb-0">
        {connectionState === "disconnected" && (
          <div
            role="status"
            aria-live="polite"
            className="flex items-center gap-2 rounded-md border border-[color-mix(in_oklch,var(--cc-warning)_35%,var(--cc-line))] bg-[var(--cc-warning-soft)] px-3 py-2 text-xs text-[var(--cc-warning)]"
          >
            <TriangleAlert aria-hidden="true" className="h-4 w-4 shrink-0" />
            Connection lost, retrying…
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            aria-label="Filter log by device"
            placeholder="Filter by device serial or name"
            value={serialFilter}
            onChange={(e) => setSerialFilter(e.target.value)}
            className="h-9 flex-1 border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] placeholder:text-[var(--cc-ink-faint)] focus-visible:ring-[var(--cc-accent)]"
          />
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger
              aria-label="Filter log by event type"
              className="h-9 w-full border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)] focus:ring-[var(--cc-accent)] sm:w-44"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="border-[var(--cc-line-strong)] bg-[var(--cc-raised)] text-[var(--cc-ink)]">
              {eventTypes.map((type) => (
                <SelectItem key={type} value={type}>
                  {type}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Event log */}
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          style={{ maxHeight, minHeight: maxHeight }}
          className="overflow-y-auto rounded-lg border border-[var(--cc-line)] bg-[var(--cc-muted)]"
          aria-label="Live event updates"
        >
            {/* Virtual scroll container */}
            <div style={{ height: totalHeight, position: "relative" }}>
              <div style={{ transform: `translateY(${offsetTop}px)` }}>
                {filteredEvents.length === 0 ? (
                  events.length === 0 && !hasFilters ? (
                    <div
                      role="status"
                      className="flex flex-col items-center justify-center p-6 text-xs text-[var(--cc-ink-soft)]"
                    >
                      <Loader2
                        aria-hidden="true"
                        className="mb-2 h-5 w-5 text-[var(--cc-accent)] motion-safe:animate-spin"
                      />
                      <span>Waiting for events…</span>
                    </div>
                  ) : (
                    <div className="p-4 text-center text-xs text-[var(--cc-ink-soft)]">
                      No events match the current filters.
                    </div>
                  )
                ) : (
                  visibleEvents.map((event, idx) => {
                    const actualIdx = startIdx + idx;
                    const type = event.type as string;

                    return (
                      <div
                        key={actualIdx}
                        style={{
                          height: ROW_HEIGHT,
                          display: "flex",
                          alignItems: "center",
                          paddingLeft: "12px",
                          paddingRight: "12px",
                          gap: "8px",
                        }}
                        className={
                          type === "error"
                            ? "border-b border-[var(--cc-line)] bg-[var(--cc-danger-soft)]"
                            : "border-b border-[var(--cc-line)]"
                        }
                      >
                        <Badge
                          variant={getBadgeVariant(type)}
                          className="text-xs shrink-0"
                        >
                          {type}
                        </Badge>
                        <code className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap text-xs text-[var(--cc-ink-soft)]">
                          {formatEventRow(event)}
                        </code>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
        </div>

        {/* Info text */}
        <div
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className="text-xs tabular-nums text-[var(--cc-ink-soft)]"
        >
          {filteredEvents.length} / {events.length} events
        </div>
      </CardContent>
    </Card>
  );
}
