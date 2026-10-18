---
created: 2026-10-17
type: build-deploy
summary: Build, test, lint, release images and the Helm chart, and deploy through the homelab repo.
---

# Build & Deploy

## Build, test, lint

Run from `api/`:

```bash
cd api
uv sync --extra worker
uv run pytest
uv run ruff check .
uv run mypy src tests
```

The real worker needs the `worker` extra. For API-only work, set
`WORKER_BACKEND=fake` in `.env` and a plain `uv sync` is enough.

Local stack (PostgreSQL + RabbitMQ, optional API/worker profiles):

```bash
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml --profile app up -d --build
docker compose -f docker-compose.dev.yml --profile worker run --rm worker
```

`scripts/e2e-local.sh` runs the full local API → queue → worker path.

## Release

Pushing a `v*` tag runs `.github/workflows/images.yml` and
`.github/workflows/chart.yml`:

- build and push `ghcr.io/rykhalskyi/transcributed-api` and
  `ghcr.io/rykhalskyi/transcributed-worker`, tagged `vX.Y.Z` and
  `sha-<full-commit>`;
- package the chart and push `transcributed-<version>.tgz` to
  `oci://ghcr.io/rykhalskyi/charts`.

The worker build uses `WHISPER_MODEL=small`. Keep `config.whisperModel` in the
chart values in sync with that build arg; a task requesting another model fails
permanently instead of retrying.

Chart validation runs on pull requests that touch `charts/` or the chart workflow:
`helm lint`, `helm template`, and kubeconform (KEDA CRDs are skipped).

## Deployment ownership

This repository ships the chart; it does not deploy to the cluster or create
cluster secrets.

- Deployment, Flux reconciliation, namespaces, and secrets live in the
  `homelab` repository (`infra/clusters/talos/`).
- The chart assumes KEDA, RabbitMQ, and PostgreSQL (CloudNativePG) already exist
  in the cluster. It renders the API, the migration hook, the KEDA `ScaledJob`,
  and the `TriggerAuthentication`; it does not install those operators.
- Secrets are created in `homelab` (SOPS/age) and referenced here by name.

See [the chart README](../../charts/transcributed/README.md) for every value.

## Secrets contract

The chart expects an existing Secret, default name `transcributed-secrets`, with:

| Key | Value |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/transcributed` |
| `RABBITMQ_URL` | `amqp://user:pass@host:5672/` |

Override with `secrets.name`, `database.urlKey`, and `rabbitmq.urlKey`.
`secrets.create=true` renders a Secret from values for a local trial only; never
commit real credentials.

If the GHCR packages stay private, create a pull secret in `homelab` and pass it
as `imagePullSecrets`.

## NAS

There is no NAS share yet, so `nas.enabled=false` is the default: the chart
renders no volumes and no mounts.

When the share exists, choose one:

- create a `ReadOnlyMany` PVC in `homelab` and set `nas.existingClaim`; or
- set `nas.create=true` with `nas.server` and `nas.share` to render a static NFS
  PV/PVC.

Talos nodes need NFS mount support (NFS extension or `csi-driver-nfs`) before the
PV can bind. The NAS stays read-only at `NAS_INPUT_ROOT` (default
`/nas/lectures`).

## Install / upgrade

Install is driven from `homelab`, either with `helm` or a Flux `HelmRelease` over
the OCI chart:

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: transcributed
  namespace: flux-system
spec:
  interval: 1h
  url: oci://ghcr.io/rykhalskyi/charts/transcributed
  ref:
    tag: 0.1.0
```

The migration Job runs `alembic upgrade head` as a `post-install,pre-upgrade`
hook, so on first install the chart's ConfigMap and Secret exist before it runs.
Use `--atomic` to roll back a failed migration.

## Verify

```bash
kubectl -n transcributed get deploy,svc,scaledjob,job
kubectl -n transcributed port-forward svc/transcributed-api 8000:8000
curl -fsS http://localhost:8000/readyz
```

KEDA scales one worker Job per message above `queueLength` (default `1`), with
`maxReplicaCount: 1`.
