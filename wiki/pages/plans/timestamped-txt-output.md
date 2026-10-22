---
created: 2026-10-22
type: plan
status: implemented
summary: Optional per-project timecodes in plain TXT transcripts, without adding a new output format.
---

# Timestamped TXT Output

Add a per-project option that prefixes every TXT transcript line with the
segment's time range, so phrases can be located in the source recording later.

Related: [project overview](../project-overview.md),
[running transcriptions](../running-transcriptions.md),
[control-plane spec](../specs/control-plane.md).

## Problem

`output_formats` already supports `vtt` and `json`, both of which carry segment
start/end times. Plain `txt` does not, so a user who wants a single readable text
file has no way to jump back to the audio.

## Proposed behaviour

Add a boolean project default, `txt_timestamps` (default `false`). It only has an
effect when `txt` is among the requested output formats.

When enabled, each segment becomes one line with its start and end time:

```text
[00:00:00.000 --> 00:00:02.480] Welcome to the lecture.
[00:00:02.480 --> 00:00:07.120] Today we cover ...
```

- Time format is the existing `HH:MM:SS.mmm` helper used by WebVTT.
- Start and end are both included so a phrase can be replayed at the source.
- The artifact format, filename (`transcript.txt`), and content type stay
  unchanged; only the body differs.
- Existing projects and runs are unaffected: missing `txt_timestamps` means
  `false`, and old run specs keep rendering as before.
- Per-item overrides stay limited to `language` and `model`; this is a project
  default only.

## Alternatives considered

- **New output format (`txt_timed` / `timed_txt`)** — would force changes to
  artifact naming, download paths, UI labels, and content types, while producing
  the same `.txt` file. Rejected.
- **New `srt` format** — useful, but a separate feature; VTT already covers
  subtitle-style output.
- **Start timestamp only** — shorter lines, but insufficient to recreate a clip.

## Plan

### 1. Backend spec and schema

- `api/src/transcributed/schemas.py`
  - Add `txt_timestamps: bool = False` to `ProjectDefaults` (Pydantic validates
    the type; `extra="forbid"` still rejects unknown keys).
- `api/src/transcributed/services/spec.py`
  - Include `txt_timestamps` in the dict returned by `build_effective_spec`,
    defaulting to `False` and coercing with `bool(...)`.
  - Bump `SPEC_VERSION` from `1` to `2`, since the snapshot shape changed. Old
    stored specs are not re-validated; the worker reads the new key with a
    default.
  - Keep the existing output-format validation untouched; this is not a new
    format value.

### 2. Worker rendering

- `api/src/transcributed/worker/transcriber.py`
  - Add `render_txt(segments, *, timestamps: bool = False)`, or a small
    `render_timed_txt` helper next to `render_txt`; reuse `_timestamp`.
  - `FasterWhisperTranscriber.transcribe`: when `"txt"` is requested, pass
    `bool(spec.get("txt_timestamps", False))`.
  - `FakeTranscriber.transcribe`: mirror the same behaviour so integration and
    local fake runs exercise the flag.
  - No change to `render_vtt`, `render_json`, artifact keys, or metadata shape
    (metadata already embeds the full task spec).

### 3. Frontend

- Regenerate the OpenAPI TypeScript types after the API change:
  `cd ui && npm run gen:api` (or point `API_OPENAPI_URL` at a local API).
  This adds `txt_timestamps?: boolean` to `ProjectDefaults`.
- `ui/src/pages/ProjectsPage.vue`
  - Add `txtTimestamps: false` to the create form state and reset it in
    `resetForm`.
  - Show a checkbox or toggle labelled **Include timestamps in TXT** below the
    output-format chips, visible or enabled only while `txt` is selected.
  - When `txt` is removed from the selection, clear `txtTimestamps`.
  - Send `txt_timestamps: form.txtTimestamps` in the `defaults` payload.
- `ui/src/lib/format.ts`
  - In `defaultsSummary`, render `txt (timestamps)` when the flag is true.
- No change needed in `RunPage.vue` / `ProjectPage.vue` download handling: the
  artifact remains `txt`.

### 4. Tests

- `api/tests/unit/test_transcriber.py`
  - `render_txt` stays byte-for-byte identical when `timestamps=False`.
  - Timestamped rendering of the existing `SEGMENTS` fixture produces
    `[00:00:00.000 --> 00:00:01.500] Hello` and the `01:01:01.250` case.
  - `FasterWhisperTranscriber` honours `txt_timestamps=True`, and ignores it for
    `vtt` / `json` / missing keys.
  - `FakeTranscriber` produces the timestamped line as well.
- `api/tests/unit/test_spec.py`
  - `build_effective_spec` defaults the flag to `false` and preserves `true`.
  - Invalid non-boolean values are rejected or coerced consistently with
    `ProjectDefaults` (test whichever behaviour the implementation chooses).
- `api/tests/integration/test_projects_api.py`
  - Create a project with `"txt_timestamps": true`, process with
    `FakeTranscriber`, and assert `GET /tasks/{id}/files/txt` returns a bracketed
    range.
  - Keep the existing default-project assertions unchanged (plain text).
- Run the documented checks:
  ```bash
  cd api && uv run pytest && uv run ruff check . && uv run mypy src tests
  cd ui && npm run build
  ```

### 5. Documentation

- `wiki/pages/running-transcriptions.md`
  - Extend the outputs table: `txt` may include segment time ranges when the
    project sets `txt_timestamps`.
  - Add the key to the create-project example and to the defaults reference.
- Update this page's `status` to `implemented`, add a short `## Outcome` with
  files changed, then run:
  ```bash
  node scripts/wiki.mjs index
  node scripts/wiki.mjs log update "timestamped TXT output — implemented"
  ```

## Risks and notes

- **Spec hash churn:** adding the field changes every new task's `spec_hash`.
  Nothing currently deduplicates on the hash, so this is harmless.
- **Mixed deployments:** an old worker ignores `txt_timestamps`; a new worker
  treats a missing key as `false`. Rolling API/worker upgrades are safe.
- **UI-only creation:** the UI sets project defaults only at creation time.
  Changing the option afterwards is API-only via
  `PATCH /api/v1/projects/{id}` until
  [project defaults editing](project-defaults-editing.md) lands.
- **Readability:** long ranges repeat on every line. If that proves noisy, a
  start-only variant can be added later without another schema change.

## Outcome

Shipped the `txt_timestamps` project default end to end:

- `api/src/transcributed/schemas.py` — `ProjectDefaults.txt_timestamps`.
- `api/src/transcributed/services/spec.py` — spec key plus `SPEC_VERSION = 2`.
- `api/src/transcributed/worker/transcriber.py` — timestamped `render_txt` and
  both real and fake transcriber support.
- `ui/src/pages/ProjectsPage.vue` — creation-time checkbox.
- `ui/src/lib/format.ts`, `ui/src/lib/types.gen.ts` — summary and generated type.
- Unit/integration tests cover default, enabled, fake, and spec-hash paths.
- `wiki/pages/running-transcriptions.md` documents the flag and TXT format.

Verified with `uv run pytest` (62 passed), `ruff`, `mypy`, and `npm run build`.
