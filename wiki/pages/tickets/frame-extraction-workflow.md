---
created: 2026-11-02
type: ticket
status: implemented
summary: Project-level frame extraction workflow with per-video timecode files, PNG frames, and ZIP downloads.
---

# Frame Extraction Workflow

## Spec

Frame extraction is a second project-level workflow beside transcription. A user
creates a frame project, adds videos from the NAS, attaches one plain-text timecode
file per video, and starts a run. A dedicated ffmpeg worker extracts one PNG per
`HH:MM:SS` line.

- Timecode files are `.txt`, one `HH:MM:SS` per line; blank lines and `#` comments
  are ignored.
- Invalid lines reject the attach and start. Up to 50 timecodes per video.
- Timecodes beyond the video duration and ffmpeg failures are skipped silently.
- Successful frames are stored in PostgreSQL; a per-video ZIP is generated on
  demand and includes `manifest.json`.
- If no frames are extracted, the task fails; a partial extraction succeeds and
  records the skipped count.
- Frame tasks use a separate `frames.jobs` queue and an ffmpeg-only worker image.
- Workflow is fixed at project creation.

## Plan

1. Add `projects.workflow`, `timecode_files`, `project_items.timecode_file_id`,
   `task_frames`, and frame counters on `tasks`.
2. Add the timecode parser, workflow-aware spec builder, and start-time preflight.
3. Add attach/remove timecode endpoints and a NAS `kind=timecode` listing.
4. Add `FfmpegFrameExtractor`, frame persistence, manifest, and ZIP download.
5. Route frame tasks to `frames.jobs` and add `transcributed-frame-worker`.
6. Add the `frame-worker` Docker target, compose service, KEDA `ScaledJob`, chart
   values, and CI image build.
7. Add workflow-aware project/run UI and per-item timecode attachment.

## Outcome

Implemented across the API, worker, queue, chart, and UI. Unit and integration
tests cover parsing, spec building, PNG dimensions, ZIP generation, attach/start
validation, partial skips, all-skipped failure, and the existing transcription
path. Checks: `pytest`, `ruff`, `mypy`, `npm run typecheck`, `npm run build`,
`helm lint`, and `helm template`.
