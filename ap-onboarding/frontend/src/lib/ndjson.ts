/**
 * Serialize an array of objects to NDJSON format (newline-delimited JSON).
 * Each object is stringified and separated by a newline.
 */
export function toNdjson(events: unknown[]): string {
  return events.map((event) => JSON.stringify(event)).join("\n");
}

/**
 * Serialize an array of objects to NDJSON and trigger a browser download.
 * Creates a blob with MIME type application/x-ndjson and uses a temporary
 * anchor element to initiate the download.
 */
export function downloadNdjson(events: unknown[], filename: string): void {
  const ndjsonContent = toNdjson(events);
  const blob = new Blob([ndjsonContent], { type: "application/x-ndjson" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Copy NDJSON string to clipboard.
 * Serializes the events array to NDJSON and copies it to the clipboard.
 */
export async function copyNdjsonToClipboard(events: unknown[]): Promise<void> {
  const ndjsonContent = toNdjson(events);
  await navigator.clipboard.writeText(ndjsonContent);
}
