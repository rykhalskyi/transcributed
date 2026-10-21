export function formatDate(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function baseName(path: string): string {
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

export function transcriptFilename(path: string, format: string): string {
  const name = baseName(path);
  const stem = name.includes(".") ? name.slice(0, name.lastIndexOf(".")) : name;
  return `${stem}.${format}`;
}

export function formatBytes(value?: number | null): string {
  if (value == null) return "—";
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = value / 1024;
  let unit = units[0];
  for (const next of units.slice(1)) {
    if (size < 1024) break;
    size /= 1024;
    unit = next;
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${unit}`;
}

export function defaultsSummary(defaults: Record<string, unknown>): string {
  const language = String(defaults.language ?? "auto");
  const model = String(defaults.model ?? "small");
  const formats = Array.isArray(defaults.output_formats)
    ? defaults.output_formats.join(", ")
    : "txt";
  return `${language.toUpperCase()} · ${model} · ${formats}`;
}
