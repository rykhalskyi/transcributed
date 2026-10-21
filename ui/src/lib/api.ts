import createClient from "openapi-fetch";

import type { paths } from "./types.gen";

const configured = import.meta.env.VITE_API_BASE_URL?.trim();

export const apiOrigin = (() => {
  if (!configured) return "";
  const trimmed = configured.replace(/\/+$/, "");
  return trimmed.endsWith("/api/v1")
    ? trimmed.slice(0, -"/api/v1".length)
    : trimmed;
})();

export const api = createClient<paths>({ baseUrl: apiOrigin });

export class ApiError extends Error {
  readonly status: number;
  readonly details?: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

function messageFromError(error: unknown, status: number): string {
  if (typeof error === "string") return error;
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return `Request failed (${status})`;
}

export async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${apiOrigin}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
    signal: init?.signal ?? AbortSignal.timeout(10000),
  });

  if (!response.ok) {
    let error: unknown = null;
    try {
      error = await response.json();
    } catch {
      error = null;
    }
    throw new ApiError(
      messageFromError(error, response.status),
      response.status,
      error,
    );
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function downloadArtifact(
  taskId: string,
  format: string,
  filename: string,
): Promise<void> {
  const response = await fetch(
    `${apiOrigin}/api/v1/tasks/${taskId}/files/${encodeURIComponent(format)}`,
    { signal: AbortSignal.timeout(60000) },
  );
  if (!response.ok) {
    let error: unknown = null;
    try {
      error = await response.json();
    } catch {
      error = null;
    }
    throw new ApiError(
      messageFromError(error, response.status),
      response.status,
      error,
    );
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
