---
created: 2026-10-18
type: plan
status: proposed
summary: Phased plan for the real Faster Whisper worker, container image, Kubernetes Jobs/KEDA, and end-to-end verification.
---

# Worker Slice — Real Transcription to Kubernetes Jobs

Turns the fake one-shot worker into a real Faster Whisper worker, packages it as a
container, runs it as a KEDA `ScaledJob`, and verifies the pipeline end to end.

Related: [control-plane spec](../specs/control-plane.md),
[project overview](../project-overview.md), [decisions](../../decisions.md).

## Baseline

Already implemented:

- Control plane: projects, items, runs, tasks, artifacts, retries, DLQ, broker-gated
  starts (`api/src/transcributed/services/`, `api/src/transcributed/messaging/`).
- One-shot worker that consumes exactly one message and exits, with retry
  republishing and max-attempt handling (`api/src/transcributed/worker/main.py`).
- Fake transcriber only (`api/src/transcributed/worker/transcriber.py`).
- `GET /metrics`, `/healthz`, `/readyz` on the API.
- No Dockerfile, no Kubernetes manifests, no CI, no `faster-whisper` dependency.

Not in scope: UI, auth, GPU, KEDA tuning beyond a working baseline, NAS scanning,
per-model worker images (tiny/small/medium) selected at start.

## Phase 0 — Preconditions and decisions

Confirm or decide before writing code:

1. **Model delivery: decided (D-12, D-15).** Bake the `small` model into the worker
   image. The image layer lives on the node's container storage; there is no model PVC
   and no runtime download. Video remains the only PVC-backed volume (NAS, read-only).
   Separate tiny/small/medium images selected at start are deferred.
2. **Deployment tooling: decided (D-13).** Ship the app as a Helm chart; install
   KEDA and the CloudNativePG operator from their charts. No Kustomize.
3. **Cluster prerequisites.** KEDA, CloudNativePG, and an NFS CSI driver are
   installed; the NAS export is reachable from node IPs.
4. **Python wheels.** Check `faster-whisper`/`ctranslate2` wheels for Python 3.14 on
   `linux/amd64`. If unavailable, build the worker on Python 3.13 without changing
   the API image.
5. **Defaults.** CPU-only `int8`, model `small`, language `auto`, VAD on.

Record any durable choices with `node scripts/wiki.mjs decision`.

## Phase 1 — Real transcriber

Files:

- `api/pyproject.toml` — add optional dependency group `worker = ["faster-whisper>=…"]`
  so the API image stays slim; the worker image installs `--extra worker`.
- `api/src/transcributed/config.py` — add `whisper_device` (`cpu`),
  `whisper_compute_type` (`int8`), `whisper_model_dir`, `whisper_beam_size`,
  `whisper_vad_filter`, and a `worker_backend` (`fake` | `faster-whisper`) switch.
- `api/src/transcributed/worker/transcriber.py` — add `FasterWhisperTranscriber`
  behind the existing `Transcriber` protocol; keep `FakeTranscriber` for tests:
  - Lazily construct `WhisperModel(name, device=…, compute_type=…, download_root=…)`
    and cache it per model/compute type.
  - Map `spec["language"]` `auto` → `None`; pass `vad_filter` and `beam_size`.
  - Consume the segment generator **once** into a list, then render `txt`, `vtt`,
    and `json` from it (the JSON has segments, no word timestamps).
  - Render VTT with a timestamp helper (`HH:MM:SS.mmm`).
- `api/src/transcributed/worker/main.py` — choose the transcriber from settings in
  `process_task` when none is injected; put model/duration/elapsed fields in the
  metadata artifact; optionally persist `info.duration` to `videos.duration_seconds`.

Tests:

- Unit: all three formats render correctly from a segment list; `auto` maps to `None`.
- Integration: inject a fake transcriber (current pattern) — unchanged.
- Manual: run the fake and real backends against `api/samples/sample1.mp4`.

Exit criteria: `uv run pytest`, `uv run ruff check .`, `uv run mypy src tests` pass;
a local worker run writes `txt`/`vtt`/`json` artifacts for the sample.

## Phase 2 — Container image and local end-to-end

Files:

- `api/Dockerfile` — multi-stage `uv` build, non-root UID, `PYTHONUNBUFFERED=1`.
  Build the worker target with `uv sync --no-dev --extra worker`.
  Pre-bake the model with a `WHISPER_MODEL=small` build arg: download it into
  `/models` during the build, set `WHISPER_MODEL_DIR=/models`, and make the image
  read-only-friendly. Build-time smoke check: load the model with networking disabled
  to prove no runtime download. No model volume is defined.
- `api/.dockerignore` — exclude `.venv`, caches, `data/`, `samples/`, tests.
- `docker-compose.dev.yml` — optional `worker` service (profile `worker`) using the
  same database/broker and a read-only `./api/samples:/nas/lectures:ro` mount.
- `scripts/e2e-local.sh` — compose up, migrate, start the API, create a project from
  `samples/sample1.mp4`, start a run, run the worker, download the transcript.

Exit criteria: one command brings up the stack and produces a downloadable transcript
without touching the fake backend.

## Phase 3 — Helm chart and Kubernetes deployment

Chart layout:

```text
charts/transcributed/
├── Chart.yaml                 # version + appVersion; optional keda/cnpg deps
├── values.yaml
├── values.schema.json
├── README.md
├── templates/
│   ├── _helpers.tpl
│   ├── NOTES.txt
│   ├── serviceaccount.yaml
│   ├── configmap.yaml
│   ├── secret.yaml            # optional; existingSecret preferred
│   ├── nas-pv.yaml
│   ├── nas-pvc.yaml
│   ├── cnpg-cluster.yaml      # optional Cluster CR; operator prerequisite
│   ├── rabbitmq-statefulset.yaml
│   ├── rabbitmq-service.yaml
│   ├── migrate-job.yaml       # pre-install/pre-upgrade hook
│   ├── api-deployment.yaml
│   ├── api-service.yaml
│   ├── worker-scaledjob.yaml
│   └── keda-triggerauth.yaml
└── ci/                        # chart-testing values
```

Chart design:

- **One chart, optional infrastructure.** Default to external PostgreSQL/RabbitMQ via
  `existingSecret`; optionally render the CNPG `Cluster` and a single-broker RabbitMQ
  StatefulSet for homelab installs. KEDA and the CNPG operator come from their own
  charts (declared as optional dependencies).
- **Portability knobs:** image repository/tag, `nas.existingClaim` or
  `nas.nfs.{server,share}`, `database.existingSecret`, `rabbitmq.existingSecret`,
  `worker.nodeSelector`, `worker.maxReplicaCount`, `worker.resources`.
- **Migrations:** a Job annotated `helm.sh/hook: pre-install,pre-upgrade` with
  `hook-delete-policy: before-hook-creation`; use `--atomic` so a failed migration
  rolls back the release. Initial install may need `--wait`.
- **Secrets:** `existingSecret` preferred; `secret.create` only for local/dev. Never
  commit plaintext.
- **Validation:** `values.schema.json`, `helm lint`, `helm template | kubeconform`,
  and `ct lint`/`ct install` in CI.

Key workloads:

- **NAS**: static PV + PVC, `ReadOnlyMany`, NFSv4.1, `hard`, `noatime`, export
  restricted to node IPs. Mount into **both** API (preflight `stat`) and worker.
- **Model**: no volume. Baked into the worker image (D-12).
- **API**: Deployment + Service; readiness on `/readyz`.
- **Worker**: KEDA `ScaledJob` with `parallelism: 1`, `completions: 1`,
  `backoffLimit: 0` (queue owns retries), `restartPolicy: Never`,
  `ttlSecondsAfterFinished: 900`, `activeDeadlineSeconds` generous (for example 12h)
  or omitted, `terminationGracePeriodSeconds: 120`, CPU/memory requests and limits, and
  node affinity for the i5 node.
- **KEDA trigger**: RabbitMQ `QueueLength` on `transcription.jobs`, `value: "1"`,
  `maxReplicaCount: 1` initially, `TriggerAuthentication` from a Secret. One job per
  message; parallelism above one only after measuring throughput.
- **Distribution**: package and push the chart to GHCR as an OCI artifact
  (`helm push transcributed-*.tgz oci://ghcr.io/…/charts`), with a README covering
  prerequisites and `helm install`.

Exit criteria: `helm lint charts/transcributed` and `helm template` succeed; a lecture
submitted through the API is processed by a Job and the artifact is downloadable.

## Phase 4 — Observability and hardening

- Add API counters for starts, publish failures, and queue-unavailable responses
  (a `/metrics` endpoint already exists).
- Deploy the RabbitMQ Prometheus exporter and rely on KEDA + kube-state-metrics for
  queue depth and Job/Pod state.
- Worker logs: add `model`, `audio_seconds`, `transcription_seconds`, `task_id`,
  `run_id`; keep structlog JSON output.
- Optional Grafana dashboard for queue depth, running Jobs, duration, failures.
- Hardening follow-up (recommended before calling it production-ready): a
  reconciler/CronJob that republishes tasks stuck `queued` with `enqueued_at IS NULL`
  and resets tasks stuck `processing` past a timeout (the spec's recovery hook is not
  implemented yet).

Exit criteria: queue depth, Job completions/failures, and transcription duration are
visible; stuck-task recovery is either implemented or filed.

## Phase 5 — Verification drills

| Scenario | Expected |
|---|---|
| Happy path, one lecture | Job succeeds; `txt` downloadable; run/project `completed` |
| Burst of 3 tasks, `maxReplicaCount: 1` | Jobs run serially; all artifacts present |
| Broker down during start | `503`; run/tasks removed; project stays `draft` |
| Worker pod killed mid-transcription | Message redelivered; attempts increments; retry policy applies |
| Source file deleted or changed | Start refuses with `409` and per-item details |
| Retry exhaustion | Task `failed`, run/project `failed`, message in `transcription.dead` |
| Duplicate delivery after success | Worker no-ops and acks; artifacts unchanged |

Add automated integration coverage where feasible; keep the rest as documented manual
drills.

## Phase 6 — Documentation

- Rewrite `wiki/pages/build-deploy.md` (currently says no build system exists).
- Record the model-delivery, Helm, and KEDA decisions.
- Ship `charts/transcributed/README.md` with prerequisites and install/upgrade steps.
- Fill this plan's Outcome once the slice ships, and update the control-plane spec's
  non-goals (remove "fake worker").

## Risks

- **Long lectures**: a 2h+ lecture can take hours on CPU and a failed or evicted Job
  restarts from zero, consuming an attempt. Keep `maxReplicaCount` low, use a generous
  deadline, and treat chunking/checkpointing as a later spec change.
- **Measured memory**: `medium` on a 5-minute clip peaked at ~1.7 GiB RSS. A 2-hour
  lecture adds ~0.5 GiB for decoded audio, so budget roughly 3 GiB limit / 2 GiB
  request for `medium`; `small` is lower.
- **Python 3.14 wheels** for `ctranslate2`/`faster-whisper` may lag; pin the worker to
  3.13 if needed.
- **Memory**: `small` int8 plus decoding can approach 2 GiB; measure before raising
  `maxReplicaCount`.
- **Long lectures** may hit `activeDeadlineSeconds`; size it from real files.
- **NFS throughput/latency** dominates CPU time for large files; test on the NAS, not
  local disk.
- **At-least-once delivery** is already handled by the terminal-status guard and
  delete-then-insert artifacts, but verify with the duplicate-delivery drill.
- **Crash between commit and publish** can strand a run; the Phase 4 reconciler is the
  mitigation.
