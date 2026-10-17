# Decisions

Append-only decision record. The "why" lives here; the full change history lives in git.

- [2026-10-17] D-01 — Use a project wiki under wiki/ — because knowledge should be versioned alongside the code
- [2026-10-17] D-02 — Model control-plane work as Project → ProjectItem → Run → Task → Artifact — because users need saved lecture lists, explicit runs, and durable per-run results
- [2026-10-17] D-03 — Require explicit user-triggered project starts and disable NAS scanning or auto-discovery — because unknown or incomplete files must never be transcribed automatically
- [2026-10-17] D-04 — Treat one lecture file as one video asset, one task, one queue message, and one Kubernetes Job; never send a project list as one message — because per-lecture isolation, retries, and KEDA scaling depend on it
- [2026-10-17] D-05 — Make video submission metadata-only by accepting a NAS-relative path; never upload video bytes through the API — because the NAS remains the media source of truth
- [2026-10-17] D-06 — Create a Run snapshot on every explicit project start — because re-runs with different settings must not overwrite prior results
- [2026-10-17] D-07 — Store transcript files on the NAS and index them in PostgreSQL as Artifact records — because transcripts are large while status and paths must remain queryable
