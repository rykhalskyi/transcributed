const LABELS: Record<string, string> = {
  draft: "Draft",
  active: "Active",
  queued: "Queued",
  running: "Running",
  processing: "Transcribing",
  succeeded: "Ready",
  completed: "Completed",
  partially_failed: "Partially failed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export type StatusTone = "neutral" | "purple" | "warning" | "success" | "danger";

export function statusLabel(status?: string | null): string {
  if (!status) return "Not started";
  return LABELS[status] ?? status;
}

export function statusTone(status?: string | null): StatusTone {
  switch (status) {
    case "active":
    case "running":
    case "processing":
      return "purple";
    case "queued":
      return "warning";
    case "succeeded":
    case "completed":
      return "success";
    case "failed":
    case "partially_failed":
      return "danger";
    case "cancelled":
      return "neutral";
    default:
      return "neutral";
  }
}

export function statusClasses(status?: string | null): string {
  switch (statusTone(status)) {
    case "purple":
      return "border-brand-purple/15 bg-brand-purple-soft text-brand-purple";
    case "warning":
      return "border-warning/20 bg-warning-soft text-warning";
    case "success":
      return "border-success/20 bg-success-soft text-success";
    case "danger":
      return "border-danger/20 bg-danger-soft text-danger";
    default:
      return "border-border bg-surface-muted text-text-muted";
  }
}

export function isLiveStatus(status?: string | null): boolean {
  return (
    status === "active" ||
    status === "queued" ||
    status === "running" ||
    status === "processing"
  );
}
