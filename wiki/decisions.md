# Decisions

Append-only decision record. The "why" lives here; the full change history lives in git.

- [2026-10-17] D-01 — Use a project wiki under wiki/ — because knowledge should be versioned alongside the code
- [2026-10-17] D-02 — Model control-plane work as Project → ProjectItem → Run → Task → Artifact — because users need saved lecture lists, explicit runs, and durable per-run results
- [2026-10-17] D-03 — Require explicit user-triggered project starts and disable NAS scanning or auto-discovery — because unknown or incomplete files must never be transcribed automatically
- [2026-10-17] D-04 — Treat one lecture file as one video asset, one task, one queue message, and one Kubernetes Job; never send a project list as one message — because per-lecture isolation, retries, and KEDA scaling depend on it
- [2026-10-17] D-05 — Make video submission metadata-only by accepting a NAS-relative path; never upload video bytes through the API — because the NAS remains the media source of truth
- [2026-10-17] D-06 — Create a Run snapshot on every explicit project start — because re-runs with different settings must not overwrite prior results
- [2026-10-17] D-07 — Store transcript files on the NAS and index them in PostgreSQL as Artifact records — because transcripts are large while status and paths must remain queryable
- [2026-10-18] D-08 — Store transcript artifacts as text in PostgreSQL and serve downloads through the API; keep the NAS input read-only — because plain-text transcripts are small, DB writes are transactional, no output RWX mount is needed, and D-07's NAS output is no longer required
- [2026-10-18] D-09 — Treat projects as living lists editable between runs; lock items only while a run is queued/running — because users must be able to extend or correct a project and start a new run without losing prior results
- [2026-10-18] D-10 — Retry failed tasks through delayed 1m/10m queues up to max_attempts and route terminal failures to the dead-letter queue — because transient failures should recover without hot-looping and exhausted work must be visible
- [2026-10-18] D-11 — Fail project start with 503 and delete the new run when the broker is unavailable or a publish is not confirmed — because a run without queued tasks would be stranded and users should retry the start
- [2026-10-18] D-12 — Bake the Faster Whisper model into the worker image — because image layers already live on node disk, a shared model PVC adds cross-node RWX complexity and per-Job NFS reads, and the NAS should stay the only PVC-backed input
- [2026-10-18] D-13 — Ship the app as a Helm chart and install KEDA/CNPG from their charts — because third-party installs need versioned releases, values, hooks, and rollback, while Kustomize adds no distribution story
- [2026-10-18] D-14 — Add a cancelled terminal status with task/run cancel endpoints and cooperative worker checks — because users must stop queued or long-running work without triggering retries or dead-letter messages
- [2026-10-18] D-15 — Bake the small model into the worker image for the first slice and defer tiny/small/medium image variants — because one image keeps deployment simple, while per-start model choice needs an image mapping plus extra registry and storage
- [2026-10-18] D-16 — Keep the Helm chart in the app repo while homelab owns cluster deployment and secrets — because the app repo knows its workloads and values, while homelab owns Talos, Flux, KEDA, RabbitMQ, CNPG, NAS, and SOPS
- [2026-10-20] D-17 — Serve the UI as a Vue 3 SPA on the same host as the API (`/` UI, `/api` API), light-only white theme, LAN-only — because same-origin removes CORS from the main flow while keeping dev and separate-host CORS configurable
- [2026-10-20] D-18 — Add a read-only GET /api/v1/nas/files directory-listing endpoint for explicit file selection — because the UI needs browsing without uploading media or scanning the NAS automatically
- [2026-10-20] D-19 — Track worker_pod and worker_node on tasks via the Kubernetes downward API and expose GET /api/v1/workers — because the UI must show active workers and nodes without giving the API Kubernetes RBAC; cancellation stays task/run cancel for now
- [2026-10-20] D-20 — Return latest-task artifact metadata in GET /projects/{id}/items and update the UI by HTTP polling — because download buttons should appear without per-item task requests, and polling avoids new realtime infrastructure
- [2026-10-20] D-21 — Use the PNG-only logo with generated mark and favicon variants on white surfaces — because no vector source exists and the provided raster is high-resolution enough for 1x/2x
- [2026-10-20] D-22 — Persist per-task transcription progress (0–100) and report it from the worker — because the UI needs live lecture progress without WebSockets or SSE
