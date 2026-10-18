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
