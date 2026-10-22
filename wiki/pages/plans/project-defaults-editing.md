---
created: 2026-10-22
type: plan
status: implemented
summary: Edit transcription defaults, including txt_timestamps, from the project page instead of the API only.
---

# Edit Project Defaults in the UI

Expose `PATCH /api/v1/projects/{id}` from the project page so defaults such as
`txt_timestamps` can be changed without curl.

Related: [timestamped TXT output](timestamped-txt-output.md),
[running transcriptions](../running-transcriptions.md),
[project overview](../project-overview.md).

## Problem

The API already supports updating `name`, `description`, and the full `defaults`
object, including `txt_timestamps`. The UI only sends defaults from the **New
project** dialog on `ProjectsPage.vue`; `ProjectPage.vue` has no way to change
them afterwards. Users must call the API with a complete `defaults` object, and
omitting fields silently resets them to schema defaults.

## Goals

1. Change project defaults (language, output formats, TXT timestamps) from the
   project page.
2. Send the **complete** defaults object on save so unrelated values are not
   reset.
3. Keep the run lock: disable editing while the project has an active/queued run
   and surface the API `409` if the state changes underneath.
4. Reuse the existing create-dialog controls instead of duplicating them.
5. Preserve the project's existing `model` value; it is edited via the API only,
   matching the creation dialog and the deployed worker image.

## Non-goals

- Per-item overrides (`language`/`model`) — separate feature.
- Editing a past run's snapshot — runs keep their own spec by design.
- Reworking project lifecycle/status handling.

## Design

### Shared defaults editor

Extract the language select, output-format chips, and "Include timestamps in
TXT" checkbox into `ui/src/components/ProjectDefaultsForm.vue`.

- Props: the current draft (`language`, `outputFormats`, `txtTimestamps`) plus a
  disabled flag.
- Emits: updated draft, or use `v-model` on a small draft object.
- Owns the same rules currently in `ProjectsPage.vue`: at least one format,
  deduplicate toggles, clear `txtTimestamps` when `txt` is removed, show the
  checkbox only while `txt` is selected.
- `ProjectsPage.vue` switches its create dialog to this component; behaviour and
  payload stay unchanged.

### Project page edit dialog

- `ui/src/lib/endpoints.ts`: add
  `updateProject(projectId, body: ProjectUpdate): Promise<Project>` calling
  `PATCH /api/v1/projects/{project_id}`.
- `ui/src/lib/types.ts`: export `ProjectUpdate` from the generated schemas.
- `ui/src/pages/ProjectPage.vue`:
  - Add an **Edit defaults** secondary button in the header, disabled when
    `locked` or `busy`, with an explanatory `title` while a run is active.
  - Add a modal/dialog patterned after the NAS browser dialog.
  - Seed the draft from `project.defaults` each time it opens. Include
    `language`, `model`, `output_formats`, and `txt_timestamps` so saving
    preserves the model and unrelated defaults.
  - Save sends the complete object:
    ```json
    {
      "defaults": {
        "language": "ru",
        "model": "small",
        "output_formats": ["txt", "vtt"],
        "txt_timestamps": true
      }
    }
    ```
  - On success: close, `await load()`, and flash "Defaults updated." so the
    summary line (`EN · small · txt (timestamps)`) refreshes.
  - On failure: show `messageOf(err)` in the dialog; reload on `409` so the
    lock state is accurate.
  - Reset the draft on close/cancel.

### Optional name/description

`ProjectUpdate` also accepts `name` and `description`. If included in the same
dialog, prefill and send them only when changed; this is optional and should not
block the defaults feature. Keep the first iteration scoped to defaults.

## Tests and verification

No backend change or migration is required; the API route and service already
validate and replace defaults atomically.

1. `cd ui && npm run build` (Vue type-check plus Vite build).
2. Manual checks:
   - Edit a project's defaults and confirm the header summary updates.
   - Enable `txt_timestamps`, run a new transcription, and verify the TXT
     artifact has bracketed ranges.
   - Disable it again and verify plain TXT on the next run.
   - Start a run, confirm the edit button is disabled, and confirm a direct API
     `PATCH` returns `409`.
   - Change only the language and confirm formats/timestamps are preserved
     (proves the full object is sent).
3. `cd api && uv run pytest` remains green; existing PATCH integration coverage
   is sufficient for the backend.

## Documentation

- Update `wiki/pages/running-transcriptions.md`: the UI now edits defaults, so
  remove or soften the "API-only" note.
- Flip this page to `implemented` and add an `## Outcome` after shipping.
- Run `node scripts/wiki.mjs index` and
  `node scripts/wiki.mjs log update "Project defaults editing — implemented"`.

## Risks

- **Partial defaults reset:** always build the payload from existing
  `project.defaults`, then override edited fields; never send only
  `txt_timestamps`.
- **Stale project data:** polling updates `project.value` while the dialog is
  open. Seed the draft only on open, not on every poll, so user edits are not
  overwritten.
- **Lock race:** another client can start a run between opening the dialog and
  saving. Treat `409` as expected, close or refresh, and let `load()` reflect the
  active run.
- **Model drift:** the model is read from the project and sent back unchanged,
  but there is no model control in the dialog; if the worker gains configurable
  models later, the shared component needs a model field.


## Outcome

Shipped the project-page defaults editor:

- `ui/src/components/ProjectDefaultsForm.vue` — shared language/format/TXT
  timestamp controls with `v-model` bindings.
- `ui/src/lib/projectDefaults.ts` — draft conversion and full-payload helper
  that preserves the project's model and clears `txt_timestamps` when TXT is
  not selected.
- `ui/src/pages/ProjectsPage.vue` — create dialog now uses the shared form.
- `ui/src/pages/ProjectPage.vue` — **Edit defaults** button and modal, run-lock
  handling, refresh and success notice.
- `ui/src/lib/endpoints.ts`, `ui/src/lib/types.ts` — `updateProject` and
  `ProjectUpdate`.
- `wiki/pages/running-transcriptions.md` — documents the UI path.

No backend changes. Verified with `cd ui && npm run build`.
