---
created: 2026-10-17
type: spec
status: proposed
summary: Project/run/task control-plane model with explicit user-triggered ingestion.
---

# Control Plane — Projects, Runs, Tasks

The first implementation slice is the control plane: users explicitly choose lecture
files from the NAS, save them as a named project, and start processing. There is no
NAS scanner, watcher, or automatic discovery. No video bytes pass through the API or
the queue.

Related: [project overview](../project-overview.md),
[original idea](../../raw/01-app-idea.md), [decisions](../../decisions.md).

## Hierarchy

```text
Project ("Lectures set 1")     saved list, defaults, results
  └─ ProjectItem               one explicitly selected NAS file
Run                            one explicit Start action
  └─ Task                      one video → one queue message → one Job
       └─ Artifact             TXT / metadata in PostgreSQL
```

- **Project** is the durable user-facing container: name, default processing
  properties, list of lectures, and resulting transcriptions.
- **ProjectItem** references one video asset version and may override project
  defaults, for example the language.
- **Run** is one execution of the project. Starting again creates a new run, so old
  settings and outputs remain intact.
- **Task** is one lecture, one RabbitMQ message, and one Kubernetes Job.
- **Artifact** is a transcript stored as text in PostgreSQL and downloaded through
  the API.

## Decisions

- Projects, runs, tasks, and artifacts are separate entities (D-02).
- Ingestion is explicit and user-triggered; no NAS scanner or auto-discovery (D-03).
- One lecture file equals one video asset, one task, one queue message, and one Job;
  a project list is never sent as one queue message (D-04).
- Video submission is metadata-only: the API accepts a NAS-relative path and never
  uploads media bytes (D-05).
- Each Start creates a run snapshot; re-runs create new runs (D-06).
- Transcript artifacts are stored as text in PostgreSQL and downloaded through the API;
  the NAS is read-only input (D-08, supersedes D-07).
- Projects are living lists: they can be edited between runs, and the item list is
  locked only while a run is queued or running (D-09).
- Failed tasks retry through delayed queues up to `max_attempts`; terminal failures go
  to the dead-letter queue (D-10).
- Start fails with `503` and removes the new run when the broker is unavailable or a
  publish is not confirmed (D-11).

## Data model

| Table | Purpose | Key fields |
|---|---|---|
| `videos` | global source-file versions | `path`, `size_bytes`, `mtime` |
| `projects` | named lecture lists and defaults | `name`, `status`, `defaults` |
| `project_items` | selected lectures | `project_id`, `video_id`, `position`, `spec_overrides` |
| `runs` | explicit executions of a project | `project_id`, `status`, `spec` |
| `tasks` | one lecture per worker Job | `run_id`, `project_item_id`, `status`, `spec`, `attempts` |
| `artifacts` | transcript outputs | `task_id`, `format`, `filename`, `content_type`, `content` |

Key constraints:

- `videos (path, size_bytes, mtime)` is unique; a changed file is a new version.
- `project_items (project_id, video_id)` is unique.
- `tasks (run_id, project_item_id)` is unique.
- `artifacts (task_id, format)` is unique.
- At most one active run per project.
- Tasks record `enqueued_at`, so the control plane can republish tasks whose message
  publish was not confirmed.

## API sketch

```text
POST   /api/v1/projects                 create a named draft project
GET    /api/v1/projects
GET    /api/v1/projects/{id}
PATCH  /api/v1/projects/{id}            edit name/defaults while draft

POST   /api/v1/projects/{id}/items      add explicit NAS-relative paths
GET    /api/v1/projects/{id}/items
DELETE /api/v1/projects/{id}/items/{item_id}

POST   /api/v1/projects/{id}/start      create a run and enqueue its tasks
GET    /api/v1/projects/{id}/runs
GET    /api/v1/runs/{id}
GET    /api/v1/tasks/{id}
GET    /api/v1/tasks/{id}/files/{format}
```

There is deliberately no scan endpoint, no filesystem watcher, and no upload endpoint.
Adding an item accepts a path such as `2026/spring/lecture-01.mp4`, not a file body.

## Start semantics

1. Refuse to start if the project already has an active run.
2. Preflight each item: the source file still exists and matches the stored video
   version (`size_bytes`, `mtime`).
3. Snapshot project defaults and item overrides into the new run.
4. Create one task per included item and publish one queue message per task.
5. If the broker is enabled but unavailable, or any publish is not confirmed, return
   `503` and delete the new run and tasks (D-11).
6. Lock the item list while the run is queued or running; unlock it when the run
   reaches a terminal state.
7. As tasks finish, derive run and project status.

## Retry policy

- A processing failure increments `attempts`. While `attempts < max_attempts`, the
  task returns to `queued` and its message is republished to
  `transcription.retry.1m` (first retry) or `transcription.retry.10m` (later retries).
- When `attempts` reaches `max_attempts`, the task becomes `failed` and the message is
  rejected to `transcription.dead`.
- Retries keep the run `queued`/`running`; a terminal failure updates the run and
  project outcome.

A queue message contains only the task identity, for example:

```json
{"v": 1, "task_id": "…", "run_id": "…"}
```

The worker loads the effective spec from PostgreSQL. The project list is never
published as a single message.

## NAS access

The NAS is mounted read-only into the API and worker pods through a CSI driver
(`csi-driver-nfs` on Talos; SMB CSI only if the NAS has no NFS export). Use a static
PV/PVC with `ReadOnlyMany`, NFSv4.1, `hard`, `noatime`, and restrict the export to
cluster node IPs. No workload writes to the NAS; transcripts live in PostgreSQL.

## Results

- Transcript bytes are stored in `artifacts.content` (UTF-8 text) and indexed by
  `(task_id, format)`.
- The task inserts artifact rows in the same transaction that marks it succeeded, so
  there are no orphaned partial outputs.
- `GET /api/v1/tasks/{id}/files/{format}` returns the text as an attachment with the
  stored filename and content type.
- The default output is plain `txt`; VTT and segment-level JSON remain supported but
  are optional and must not include word-level timestamps.
- The project view aggregates the latest run: item status, language, duration, and
  download links.

## Non-goals for this slice

- NAS scanning, filesystem watchers, automatic discovery, or automatic starts.
- Video uploads through the API.
- Chunking a lecture into segments or assembling partial transcripts.
- Word-level timestamp JSON; the first slice produces plain text.
- NAS output volumes or transcript files on the NAS.
- Faster Whisper integration; this slice uses a fake worker.
- KEDA, UI, authentication, and multi-user authorization.

## Open questions

- Should a re-run process every included item, or only items without a successful
  transcript for the current spec?
- Per-item overrides: language per item (proposed yes) and model shared per project?
- May the same video belong to multiple projects, each with its own transcript output?
- Naming: keep `Project` in the API and database, or use `Collection`/`Set`?
