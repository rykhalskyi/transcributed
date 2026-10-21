---
created: 2026-10-20
type: plan
status: in-progress
summary: Vue 3 white-themed LAN UI for projects, NAS file selection, runs, workers, and transcript downloads.
---

# UI Slice — Web Control Plane

Builds a LAN-only Vue 3 UI over the deployed API: create or choose a project, browse
and add NAS lectures, watch per-video transcription state, start or cancel runs, see
active workers and their nodes, and download finished transcripts.

Related: [control-plane spec](../specs/control-plane.md),
[project overview](../project-overview.md),
[running transcriptions](../running-transcriptions.md),
[build and deploy](../build-deploy.md), [decisions](../../decisions.md).

## Baseline

The deployed API already supports the full workflow:

| Need | Endpoint |
|---|---|
| List/create/update/delete projects | `GET/POST /api/v1/projects`, `GET/PATCH/DELETE /api/v1/projects/{id}` |
| Add NAS paths | `POST /api/v1/projects/{id}/items` |
| List project videos | `GET /api/v1/projects/{id}/items` |
| Include/exclude or per-item overrides | `PATCH /api/v1/projects/{id}/items/{item_id}` |
| Remove an item | `DELETE /api/v1/projects/{id}/items/{item_id}` |
| Start a run | `POST /api/v1/projects/{id}/start` |
| Run history and live run detail | `GET /api/v1/projects/{id}/runs`, `GET /api/v1/runs/{id}` |
| Task detail | `GET /api/v1/tasks/{id}` |
| Cancel task/run | `POST /api/v1/tasks/{id}/cancel`, `POST /api/v1/runs/{id}/cancel` |
| Download artifacts | `GET /api/v1/tasks/{id}/files/{txt\|vtt\|json\|metadata}` |
| Health | `/healthz`, `/readyz`, `/metrics` |

Constraints that shape the UI:

- One active run per project; items and defaults are locked while it is `queued` or
  `running`.
- Submission is metadata-only: a NAS-relative path, never an upload.
- The deployed worker image contains only the `small` model.
- Cancellation is cooperative; a worker notices within roughly 30 seconds of audio.
- There is no authentication.
- There is no NAS listing endpoint, no worker/node data, and no artifact list in
  project items yet.

## Decisions

- **D-17** — Serve the UI as a Vue 3 SPA on the same host as the API (`/` UI,
  `/api` API), light-only white theme, LAN-only. CORS stays configurable for local
  development and separate-host deployments.
- **D-18** — Add a read-only `GET /api/v1/nas/files` directory-listing endpoint for
  explicit file selection; no upload, scan, or auto-discovery.
- **D-19** — Track `worker_pod` and `worker_node` on tasks via the Kubernetes
  downward API and expose `GET /api/v1/workers`; cancel remains task/run cancel for
  now, with no forced Pod kill and no Kubernetes RBAC for the API.
- **D-20** — Return latest-task artifact metadata in
  `GET /api/v1/projects/{id}/items` and update the UI by HTTP polling instead of
  adding WebSocket/SSE infrastructure.
- **D-21** — Use the PNG-only logo with generated mark and favicon variants on white
  surfaces; no vector source exists, and the provided raster is high-resolution enough
  for 1x/2x.
- **D-22** — Persist a 0–100 `progress` percentage on each task, updated by the worker
  during transcription and exposed in task, worker, and project-item responses — because
  the UI must show live lecture progress without a new realtime channel.

## Scope

In scope:

- Project list and creation with defaults.
- Project workspace with NAS browser, item list, start/cancel controls, and worker
  panel.
- Per-item status, spinner, error, and transcript downloads.
- Run history and run detail.
- White UI using the Transcributed logo.
- Per-task transcription progress with progress bars on lecture and run views.
- Chart, CI image, and deployment changes for the UI.
- Backend additions listed below.

Not in scope:

- Authentication or multi-user accounts.
- Video upload or media streaming through the API.
- Forced worker/Pod termination.
- Realtime WebSocket/SSE updates.
- Dark mode.
- NAS scanning, filesystem watchers, or automatic starts.
- Per-model worker images; the model selector stays on `small`.

## API additions

### Read-only NAS listing

New route `api/src/transcributed/api/routes/nas.py`, registered in
`api/src/transcributed/api/app.py`.

```text
GET /api/v1/nas/files?path=2026/spring&limit=500
```

Response:

```json
{
  "path": "2026/spring",
  "parent": "2026",
  "directories": [{"name": "week-01", "path": "2026/spring/week-01"}],
  "files": [
    {
      "name": "lecture-01.mp4",
      "path": "2026/spring/lecture-01.mp4",
      "size_bytes": 123456,
      "mtime": "2026-10-20T12:00:00Z"
    }
  ],
  "truncated": false
}
```

Rules:

- `path` is relative to `NAS_INPUT_ROOT`; empty means the root.
- Reuse the safety rules from `services/spec.py`: reject absolute paths, `.`, `..`,
  empty segments, backslashes, and null bytes.
- Resolve symlinks and verify the result remains inside the NAS root.
- Return directories plus only files with allowed extensions.
- Sort directories first, then files; cap results at `limit` and set `truncated`.
- Return metadata only; never read or stream media bytes.

Add `NasEntry`, `NasDirectory`, and `NasListing` schemas.

### Worker and node telemetry

- Migration adds `worker_pod` and `worker_node` (nullable strings) to `tasks`.
- Add both fields to `Task` and `TaskRead`.
- The worker reads `POD_NAME` and `NODE_NAME` from the environment when it marks a
  task `PROCESSING`, and writes them to the task row.
- Include pod and node in the `metadata.json` artifact.
- Inject the values in `charts/transcributed/templates/worker-scaledjob.yaml` through
  the downward API: `metadata.name` to `POD_NAME`, `spec.nodeName` to `NODE_NAME`.

New endpoint:

```text
GET /api/v1/workers?project_id=<uuid>&run_id=<uuid>
```

```json
{
  "active": 2,
  "queued": 5,
  "workers": [
    {
      "task_id": "...",
      "run_id": "...",
      "project_id": "...",
      "project_name": "...",
      "path": "2026/spring/lecture-01.mp4",
      "status": "processing",
      "node": "talos-worker-2",
      "pod": "transcributed-worker-abcde",
      "started_at": "..."
    }
  ]
}
```

Implementation: `services/workers.py` and `routes/workers.py`, joining non-terminal
tasks to run, project, item, and video. `active` counts `processing`; `queued` counts
`queued`. Cancelling a worker is `POST /api/v1/tasks/{task_id}/cancel`.

### Task progress

- Migration adds `progress` (integer, default `0`) to `tasks`.
- The worker resets it to `0` when a task starts `PROCESSING`, passes an `on_progress`
  callback to the transcriber, and sets `100` on success. Faster Whisper reports the
  decoded-audio percentage; the fake worker reports `100` immediately.
- Expose `progress` in `TaskRead` and `WorkerRead`, and `latest_task_progress` in
  `ProjectItemRead`.
- Progress writes use a short-lived synchronous psycopg connection (the same pattern
  as cancellation checks) and `GREATEST(progress, …)`, so reports never move backwards
  and never block on the worker's async session.

### Artifacts in project items

- Add `latest_task_artifacts: list[ArtifactRead]` to `ProjectItemRead`.
- Update `services/projects.py` so the latest task per item contributes its artifact
  metadata.
- Load artifacts only for the latest task per item and defer `Artifact.content`, so
  polling the item list never reads transcript bodies.
- This lets the UI show download buttons without one task request per item.

### CORS

- Add `expose_headers=["Content-Disposition"]` to `CORSMiddleware` so browsers can
  read download filenames cross-origin.
- Add `api.corsOrigins` to chart values and `CORS_ORIGINS` to the ConfigMap as a JSON
  array. Keep `http://localhost:5173` for development and add the deployed UI origin.
- Update `values.schema.json`.
- Same-host production routing avoids CORS, but development and separate-host
  deployments stay correct.

## UI

### Stack

- Vue 3 + TypeScript + Vite.
- Vue Router and Pinia.
- Tailwind CSS and shadcn-vue.
- Typed API client generated from `/openapi.json` with `openapi-typescript` and
  `openapi-fetch`.
- Vitest + Vue Test Utils; one Playwright smoke flow.

### Visual system

Light-only white theme. Colours are CSS variables in
`ui/src/assets/styles/tokens.css` so dark mode can be added later.

| Token | Value | Use |
|---|---|---|
| `--brand-navy` | `#1E0A4E` | Logo document, headings, primary text |
| `--brand-purple` | `#6A1FD0` | Primary buttons, active nav, processing, focus rings |
| `--brand-purple-soft` | `#F3EEFF` | Active nav, selected rows |
| `--brand-orange` | `#F5A300` | Queued/running accents and highlights |
| `--brand-gold` | `#A87500` | “buted” wordmark, secondary accent text |
| `--surface` | `#FFFFFF` | Page and card background |
| `--surface-muted` | `#FAFAFC` | Table zebra and subtle panels |
| `--border` | `#E8E4F1` | Card, table, and sidebar borders |
| `--text-muted` | `#6B6480` | Secondary labels and timestamps |

Status colours: queued `#B37700` on `#FFF6E0`; processing purple on `#F3EEFF`;
succeeded `#1B7F4B` on `#EAF7F0`; failed `#B42318` on `#FEECEB`; cancelled neutral
grey. Spinners use brand purple.

Layout:

- White page, white sidebar with a 1px border.
- Sidebar header: logo mark + wordmark, linked to `/projects`; mark only on narrow
  screens.
- Top bar: project breadcrumb and API health indicator.
- White cards and tables with subtle borders, 12px radius, and light shadow.
- Purple primary buttons, white secondary buttons, red destructive actions, purple
  focus ring.
- Full logo lockup on the empty projects state.
- White modals over a 40% navy overlay.
- Responsive sidebar and tables; tables scroll horizontally on narrow screens.

### Brand assets (PNG only)

Source, committed once:

```text
ui/brand/transcributed-logo.png
```

Generated and committed:

```text
ui/src/assets/brand/transcributed-logo.png
ui/src/assets/brand/transcributed-logo@2x.png
ui/src/assets/brand/transcributed-mark.png
ui/src/assets/brand/transcributed-mark@2x.png
ui/public/favicon.ico
ui/public/favicon-32.png
ui/public/apple-touch-icon.png
```

A `ui/scripts/build-brand.mjs` using `sharp` crops the icon area, trims whitespace,
creates 1x/2x variants, and generates the favicon set. It runs only when the source
logo changes (`npm run brand:build`). Use lossless optimization such as `oxipng`; do
not use lossy compression on the wordmark.

Usage rules:

- Keep the logo on white surfaces; the PNG has no transparency and does not need it.
- Sidebar: mark at 28-32px plus the wordmark at roughly 120-140px.
- Collapsed sidebar and narrow screens: mark only.
- Empty projects page: full lockup at 240-320px.
- Always set explicit `width`/`height` and `object-fit: contain`.
- Keep the wordmark as an image; do not recreate the “Transcri”/“buted” split as
  text.
- Use `alt="Transcributed"` for the logo.

### Screens

`/projects`

- Project list with status chips and search.
- Create dialog: name, description, language, and output formats.
- Model fixed to `small` with a note about the deployed worker image.

`/projects/:id`

- Header with project status/defaults and edit/delete.
- Add lectures: a compact block with only a **Browse NAS** button.
  - NAS browser modal using `GET /api/v1/nas/files`: breadcrumbs, directory
    navigation, multi-select, allowed files only.
  - Show per-file `accepted`/`rejected` results from `ProjectItemsAddResponse`.
- Item table:
  - Path/basename, included toggle, language/model override.
  - Status badge; spinner for `processing`, clock for `queued`, and a percentage
    progress bar from `latest_task_progress` while processing.
  - Error display.
  - Download menu from `latest_task_artifacts` (`txt`, `vtt`, `json`, `metadata`).
  - Remove item.
- Start run: disabled while an active run exists or no items are included; surface
  `409` and `503` errors.
- Cancel run with confirmation.
- Brief worker pill in the header linking to `/workers?project_id=...`, showing
  active and queued counts.
- Run history from `GET /api/v1/projects/{id}/runs`.
- Header progress bar combining finished tasks with the live percentage of active ones.

`/workers`

- Global worker overview from `GET /api/v1/workers`.
- `?project_id=...` filters the list to one project.
- Table: worker/pod, node, project, lecture, progress, started time, cancel action.
- Active/queued summary counts.

`/runs/:id`

- Task table with status, timings, error, artifacts, and cancel actions.
- Poll only while the run is `queued` or `running`.

### Polling

- `usePolling` composable: configurable interval, immediate first call,
  `AbortController`, no overlapping requests, stale-response guard, and pause when
  the tab is hidden.
- Project workspace: every 2.5-3 seconds while any task is `queued`/`processing` or a
  run is active; every 15-30 seconds when idle.
- Run detail: every 2 seconds while non-terminal; stop at `completed`,
  `partially_failed`, `failed`, or `cancelled`.
- Workers page: every 3 seconds while visible.
- Refresh project and items after start, cancel, add, and remove.
- Poll artifact metadata only; never fetch transcript content for the list.

### Downloads and errors

- Fetch the artifact as a blob from `/tasks/{id}/files/{format}`.
- Rename to `<source-basename>.<format>` because the server always sends
  `transcript.*`.
- Show the menu only when the latest task is `succeeded` and the artifact exists.
- Handle `404` with a toast.
- Map `409` to active-run/changed-file messages, `503` to queue unavailable, and
  `422` to invalid path or extension.
- Show “cancelling…” until a poll returns `cancelled`.
- No credentials or secrets in the UI; keep the deployment LAN-only.

## Deployment

- `ui/Dockerfile`: multi-stage Node build, then nginx serving the SPA with history
  fallback.
- Chart values: `ui.enabled`, image, replicas, service, resources, ingress.
- New templates: `ui-deployment.yaml`, `ui-service.yaml`, `ui-ingress.yaml`.
- Same-host routing:
  - `/api`, `/docs`, `/openapi.json`, `/healthz`, `/readyz` to the API service.
  - `/` to the UI service.
- Build-time `VITE_API_BASE_URL=/api/v1` for same-origin; Vite dev proxy to
  `http://localhost:8000`.
- Add the UI image to `.github/workflows/images.yml`.
- Update homelab Helm values to enable the UI ingress and set `CORS_ORIGINS` if a
  separate host is ever used.
- Keep the deployment LAN-only; do not add a Cloudflare tunnel.

## Testing

Backend:

- NAS listing: root, nested directory, extension filtering, `limit`/`truncated`,
  traversal attempts, backslashes, null bytes, and symlink escape.
- Workers endpoint: active/queued counts, project/run filters, node and pod fields.
- Item list: only the latest task artifacts, without loading transcript content.
- Progress: reporter updates persist, ignore lower values, and surface in task,
  worker, and item responses.
- CORS: configured origins and `Content-Disposition` exposure.

UI:

- Vitest: polling lifecycle, status rendering, download filename, and error mapping.
- Playwright: create project, browse/add a file, start, see a spinner, cancel one
  task, and download a transcript against the local compose stack with the fake
  worker.

Run `uv run ruff check`, `uv run mypy`, `pytest`, `npm run lint`,
`npm run typecheck`, and `npm run test`.

## Implementation order

1. Backend NAS endpoint, schemas, and tests.
2. Worker telemetry migration, worker env, `/workers`, item artifacts, and tests.
3. CORS, ConfigMap, chart values, and schema updates.
4. UI scaffold, generated client, polling composable, and brand tokens/assets.
5. Projects page, create dialog, and NAS browser.
6. Project workspace, item table, worker panel, start/cancel.
7. Run detail, downloads, status and error polish.
8. UI Dockerfile, chart ingress, and CI image.
9. Wiki updates, index regeneration, lint, and log.

## Risks

- **Polling load:** keep intervals conservative and stop when the tab is hidden or the
  run is terminal. Avoid loading artifact content in list responses.
- **PNG scaling:** the raster is only sufficient while used at 1x/2x; do not stretch
  the wordmark beyond the source resolution.
- **Worker/node accuracy:** a task can be `processing` while its Pod has already been
  killed; the UI reflects database state, not live Kubernetes state. A crash before
  the next cancellation check can delay “cancelled”.
- **Ingress path ordering:** the `/` UI route must not shadow `/api`; rely on
  longest-prefix matching and verify `/docs`, `/healthz`, and downloads in the
  deployed environment.
- **CORS and downloads:** if a separate UI host is used, `Content-Disposition` must be
  exposed or the UI must fall back to generated filenames.
- **No auth:** the UI must never be exposed beyond the LAN.

## Prerequisites

- Source PNG is available at `ui/brand/transcributed-logo.png` (transparent) and
  `ui/brand/transcributed-logo-opaque.png`; `ui/scripts/build_brand.py` generates the
  mark, wordmark, retina, and favicon assets.
- Confirm the homelab ingress path layout (`/` UI, `/api` API) during deployment.
