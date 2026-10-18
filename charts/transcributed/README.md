# Transcributed Helm chart

Deploys the Transcributed API, the Faster Whisper worker as a KEDA `ScaledJob`,
and the database migration hook.

## Prerequisites

- Kubernetes 1.30+ (Talos)
- KEDA installed in the cluster (the chart renders `ScaledJob` and
  `TriggerAuthentication`, it does not install KEDA)
- PostgreSQL reachable from the cluster (CloudNativePG in the homelab)
- RabbitMQ reachable from the cluster
- A NAS share or an existing `ReadOnlyMany` PVC
- Images: `ghcr.io/rykhalskyi/transcributed-api` and
  `ghcr.io/rykhalskyi/transcributed-worker`

## Secrets

The chart expects an existing Secret (default `transcributed-secrets`) with:

| Key | Value |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/transcributed` |
| `RABBITMQ_URL` | `amqp://user:pass@host:5672/` |

Create it outside this repo, for example with SOPS in the homelab repository.
For a local trial only, set `secrets.create=true` and fill
`secrets.databaseUrl` / `secrets.rabbitmqUrl`; never commit real credentials.

If the GHCR packages are private, create a pull secret and pass it with
`imagePullSecrets`.

## Install

```bash
helm install transcributed charts/transcributed \
  --namespace transcributed --create-namespace \
  --set secrets.name=transcributed-secrets \
  --set nas.enabled=true \
  --set nas.existingClaim=transcributed-nas
```

The `post-install,pre-upgrade` Job runs `alembic upgrade head` with the API image.
On first install it therefore runs after the ConfigMap and Secret exist; on upgrades
it runs before the new workloads roll out. Use `--atomic` if you want a failed
migration to roll the release back.

## Values

| Value | Default | Purpose |
|---|---|---|
| `api.image.repository` | `ghcr.io/rykhalskyi/transcributed-api` | API image |
| `api.image.tag` | chart `appVersion` | Pin a `sha-<commit>` tag |
| `worker.image.repository` | `ghcr.io/rykhalskyi/transcributed-worker` | Worker image |
| `worker.image.tag` | chart `appVersion` | Pin a `sha-<commit>` tag |
| `config.whisperModel` | `small` | Model baked into the worker image |
| `worker.keda.maxReplicaCount` | `1` | Max concurrent Jobs |
| `config.rabbitmqJobsQueue` | `transcription.jobs` | KEDA RabbitMQ queue |
| `nas.enabled` | `false` | Mount the input share |
| `nas.existingClaim` | `""` | Use an existing PVC |
| `nas.create` | `false` | Render a static NFS PV/PVC |
| `nas.server` / `nas.share` | `""` | NFS server and export path |

The worker image is built with one model via the `WHISPER_MODEL` build arg. Keep
`config.whisperModel` in sync with the image; a task requesting another model
fails permanently instead of retrying.

## NAS

No NAS share exists yet. Leave `nas.enabled=false` to render no volumes and no
mounts. When the share is available either:

- create a `ReadOnlyMany` PVC yourself and set `nas.existingClaim`, or
- set `nas.create=true` together with `nas.server` and `nas.share` to render a
  static NFS PV/PVC.

Talos nodes need NFS mount support (NFS extension or `csi-driver-nfs`) before
the PV can bind.

## Images and chart releases

- `.github/workflows/images.yml` builds and pushes both images on `v*` tags and
  on manual dispatch. Tags are `vX.Y.Z` and `sha-<full-commit>`.
- `.github/workflows/chart.yml` lints and templates the chart on pull requests and
  pushes `transcributed-<version>.tgz` to
  `oci://ghcr.io/rykhalskyi/charts` on `v*` tags.

Consume the chart from Flux with an `OCIRepository`, for example:

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
