import { useState, useEffect } from "react";
import { ChevronDown, ChevronRight, Download, Loader2 } from "lucide-react";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import AppShell from "@/components/AppShell";
import { PageHeader } from "@/components/PageHeader";
import {
  listResults,
  listResultsFolder,
  getResultFileUrl,
} from "@/lib/api";

interface ExpandedFolder {
  [folderName: string]: boolean;
}

interface FolderContents {
  [folderName: string]: string[] | "loading";
}

export function Results() {
  const [folders, setFolders] = useState<string[]>([]);
  const [expandedFolders, setExpandedFolders] = useState<ExpandedFolder>({});
  const [folderContents, setFolderContents] = useState<FolderContents>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load all folders on mount
  useEffect(() => {
    const loadFolders = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await listResults();
        setFolders(response.folders);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load results");
      } finally {
        setLoading(false);
      }
    };

    loadFolders();
  }, []);

  // Load folder contents when expanded
  const handleFolderToggle = async (folderName: string, isOpen: boolean) => {
    setExpandedFolders((prev) => ({
      ...prev,
      [folderName]: isOpen,
    }));

    // Only load if not already loaded
    if (isOpen && !folderContents[folderName]) {
      setFolderContents((prev) => ({
        ...prev,
        [folderName]: "loading",
      }));

      try {
        const response = await listResultsFolder(folderName);
        setFolderContents((prev) => ({
          ...prev,
          [folderName]: response.files,
        }));
      } catch {
        setFolderContents((prev) => ({
          ...prev,
          [folderName]: [],
        }));
      }
    }
  };

  if (loading) {
    return (
      <AppShell>
        <div
          className="mx-auto max-w-4xl"
          role="status"
          aria-busy="true"
          aria-label="Loading results"
        >
          <div className="mb-6">
            <Skeleton className="h-9 w-40 motion-safe:animate-pulse" />
            <Skeleton className="mt-2 h-4 w-56 motion-safe:animate-pulse" />
          </div>
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-lg border border-[var(--cc-line)] bg-[var(--cc-surface)] px-4 py-3"
              >
                <Skeleton className="h-4 w-64 motion-safe:animate-pulse" />
                <Skeleton className="ml-2 h-4 w-4 motion-safe:animate-pulse" />
              </div>
            ))}
          </div>
          <span className="sr-only">Loading…</span>
        </div>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell>
        <div className="mx-auto max-w-4xl">
          <div className="rounded-lg bg-[var(--cc-danger-soft)] p-4 text-[var(--cc-danger)]">
            <p className="text-sm font-medium">Error loading results</p>
            <p className="mt-1 text-xs">{error}</p>
          </div>
        </div>
      </AppShell>
    );
  }

  if (folders.length === 0) {
    return (
      <AppShell>
        <div className="mx-auto flex max-w-4xl items-center justify-center">
          <div className="text-center text-[var(--cc-ink-soft)]">
            <p className="text-sm">No past results found.</p>
            <p className="mt-1 text-xs">Run a workflow to generate results.</p>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <div className="mb-6">
          <PageHeader
            title="Results"
            description="Browse historical workflow runs"
          />
        </div>

        <div className="space-y-2">
          {folders.map((folderName) => {
            const isOpen = expandedFolders[folderName] || false;
            const contents = folderContents[folderName];
            const isLoading = contents === "loading";
            const files = Array.isArray(contents) ? contents : [];

            return (
              <Collapsible
                key={folderName}
                open={isOpen}
                onOpenChange={(open) => handleFolderToggle(folderName, open)}
              >
                <div className="rounded-lg border border-[var(--cc-line)] bg-[var(--cc-surface)] transition-colors hover:bg-[var(--cc-muted)]">
                  <CollapsibleTrigger asChild>
                    <Button
                      variant="ghost"
                      className="w-full justify-between px-4 py-3 h-auto rounded-lg font-mono text-sm"
                    >
                      <span className="text-left flex-1">{folderName}</span>
                      {isOpen ? (
                        <ChevronDown className="w-4 h-4 ml-2 flex-shrink-0" />
                      ) : (
                        <ChevronRight className="w-4 h-4 ml-2 flex-shrink-0" />
                      )}
                    </Button>
                  </CollapsibleTrigger>

                  <CollapsibleContent>
                    <div className="border-t border-[var(--cc-line)] bg-[var(--cc-muted)] px-4 py-2">
                      {isLoading ? (
                        <div className="flex items-center justify-center py-4">
                          <Loader2 className="mr-2 h-4 w-4 text-[var(--cc-ink-soft)] motion-safe:animate-spin" />
                          <p className="text-xs text-[var(--cc-ink-soft)]">
                            Loading files...
                          </p>
                        </div>
                      ) : files.length === 0 ? (
                        <p className="py-2 text-xs text-[var(--cc-ink-soft)]">
                          No files found in this folder
                        </p>
                      ) : (
                        <ul className="space-y-2">
                          {files.map((filename) => {
                            const fileUrl = getResultFileUrl(folderName, filename);
                            return (
                              <li
                                key={filename}
                                className="flex items-center justify-between py-1 group"
                              >
                                <span className="flex-1 truncate font-mono text-xs text-[var(--cc-ink)]">
                                  {filename}
                                </span>
                                <a
                                  href={fileUrl}
                                  download
                                  className="ml-2 flex-shrink-0"
                                >
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-7 px-2 opacity-0 group-hover:opacity-100 transition-opacity"
                                    title={`Download ${filename}`}
                                    aria-label={`Download ${filename}`}
                                  >
                                    <Download className="w-4 h-4" />
                                  </Button>
                                </a>
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </div>
                  </CollapsibleContent>
                </div>
              </Collapsible>
            );
          })}
        </div>
      </div>
    </AppShell>
  );
}
