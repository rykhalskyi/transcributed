import { api, ApiError, request } from "./api";
import type {
  NasListing,
  Project,
  ProjectCreate,
  ProjectItem,
  ProjectItemsAddResponse,
  Run,
  RunDetail,
  StartProjectResponse,
  Task,
  WorkersResponse,
} from "./types";

type ApiResult<T> = {
  data?: T;
  error?: unknown;
  response: Response;
};

function messageFromError(error: unknown, status: number): string {
  if (typeof error === "string") return error;
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return `Request failed (${status})`;
}

function unwrap<T>(result: ApiResult<T>): T {
  if (result.error != null) {
    throw new ApiError(
      messageFromError(result.error, result.response.status),
      result.response.status,
      result.error,
    );
  }
  if (result.data === undefined) {
    throw new ApiError(
      `Request failed (${result.response.status})`,
      result.response.status,
    );
  }
  return result.data;
}

function assertOk(result: ApiResult<unknown>): void {
  if (result.error != null) {
    throw new ApiError(
      messageFromError(result.error, result.response.status),
      result.response.status,
      result.error,
    );
  }
}

export function getHealth(): Promise<{ status: string }> {
  return request<{ status: string }>("/healthz");
}

export function getReadiness(): Promise<{ status: string }> {
  return request<{ status: string }>("/readyz");
}

export async function getApiVersion(): Promise<string> {
  const response = await request<{ version: string }>("/api/v1/version");
  return response.version;
}

export async function listNasFiles(
  path = "",
  limit = 500,
): Promise<NasListing> {
  return unwrap(
    await api.GET("/api/v1/nas/files", {
      params: { query: { path, limit } },
    }),
  );
}

export async function listWorkers(
  projectId?: string,
  runId?: string,
): Promise<WorkersResponse> {
  return unwrap(
    await api.GET("/api/v1/workers", {
      params: {
        query: {
          project_id: projectId ?? null,
          run_id: runId ?? null,
        },
      },
    }),
  );
}

export async function listProjects(limit = 100): Promise<Project[]> {
  return unwrap(
    await api.GET("/api/v1/projects", { params: { query: { limit } } }),
  );
}

export async function createProject(body: ProjectCreate): Promise<Project> {
  return unwrap(await api.POST("/api/v1/projects", { body }));
}

export async function getProject(projectId: string): Promise<Project> {
  return unwrap(
    await api.GET("/api/v1/projects/{project_id}", {
      params: { path: { project_id: projectId } },
    }),
  );
}

export async function listProjectItems(
  projectId: string,
  limit = 500,
): Promise<ProjectItem[]> {
  return unwrap(
    await api.GET("/api/v1/projects/{project_id}/items", {
      params: { path: { project_id: projectId }, query: { limit } },
    }),
  );
}

export async function addProjectItems(
  projectId: string,
  paths: string[],
): Promise<ProjectItemsAddResponse> {
  return unwrap(
    await api.POST("/api/v1/projects/{project_id}/items", {
      params: { path: { project_id: projectId } },
      body: { items: paths.map((path) => ({ path })) },
    }),
  );
}

export async function setProjectItemIncluded(
  projectId: string,
  itemId: string,
  included: boolean,
): Promise<ProjectItem> {
  return unwrap(
    await api.PATCH("/api/v1/projects/{project_id}/items/{item_id}", {
      params: { path: { project_id: projectId, item_id: itemId } },
      body: { included },
    }),
  );
}

export async function removeProjectItem(
  projectId: string,
  itemId: string,
): Promise<void> {
  assertOk(
    await api.DELETE("/api/v1/projects/{project_id}/items/{item_id}", {
      params: { path: { project_id: projectId, item_id: itemId } },
    }),
  );
}

export async function startProject(
  projectId: string,
): Promise<StartProjectResponse> {
  return unwrap(
    await api.POST("/api/v1/projects/{project_id}/start", {
      params: { path: { project_id: projectId } },
    }),
  );
}

export async function listProjectRuns(
  projectId: string,
  limit = 20,
): Promise<Run[]> {
  return unwrap(
    await api.GET("/api/v1/projects/{project_id}/runs", {
      params: { path: { project_id: projectId }, query: { limit } },
    }),
  );
}

export async function getRun(runId: string): Promise<RunDetail> {
  return unwrap(
    await api.GET("/api/v1/runs/{run_id}", {
      params: { path: { run_id: runId } },
    }),
  );
}

export async function cancelRun(runId: string): Promise<RunDetail> {
  return unwrap(
    await api.POST("/api/v1/runs/{run_id}/cancel", {
      params: { path: { run_id: runId } },
    }),
  );
}

export async function getTask(taskId: string): Promise<Task> {
  return unwrap(
    await api.GET("/api/v1/tasks/{task_id}", {
      params: { path: { task_id: taskId } },
    }),
  );
}

export async function cancelTask(taskId: string): Promise<Task> {
  return unwrap(
    await api.POST("/api/v1/tasks/{task_id}/cancel", {
      params: { path: { task_id: taskId } },
    }),
  );
}
