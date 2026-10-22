import type { components } from "./types.gen";

export type Project = components["schemas"]["ProjectRead"];
export type ProjectCreate = components["schemas"]["ProjectCreate"];
export type ProjectUpdate = components["schemas"]["ProjectUpdate"];
export type ProjectDefaults = components["schemas"]["ProjectDefaults"];
export type ProjectItem = components["schemas"]["ProjectItemRead"];
export type ProjectItemsAddResponse =
  components["schemas"]["ProjectItemsAddResponse"];
export type Run = components["schemas"]["RunRead"];
export type RunDetail = components["schemas"]["RunDetail"];
export type Task = components["schemas"]["TaskRead"];
export type StartProjectResponse =
  components["schemas"]["StartProjectResponse"];
export type NasListing = components["schemas"]["NasListing"];
export type NasFile = components["schemas"]["NasFile"];
export type NasDirectory = components["schemas"]["NasDirectory"];
export type Worker = components["schemas"]["WorkerRead"];
export type WorkersResponse = components["schemas"]["WorkersResponse"];

export type TaskStatus = Task["status"];
export type RunStatus = Run["status"];
export type ProjectStatus = Project["status"];
