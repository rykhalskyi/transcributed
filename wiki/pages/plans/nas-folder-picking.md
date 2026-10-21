---
created: 2026-10-21
type: plan
status: proposed
summary: Recursive NAS folder browsing and batch lecture picking across directory trees.
---

# NAS Folder & Subfolder File Picking

Plan to allow selecting media files from a designated NAS folder and its subdirectories, replacing manual one-by-one path entry.

Related: [project overview](../project-overview.md), [control-plane spec](../specs/control-plane.md), [ui slice plan](ui-slice.md).

## Problem

Currently, adding lectures to a project requires either:
1. Typing or pasting individual relative file paths line-by-line into a textarea (e.g. `2026/spring/lecture-01.mp4`).
2. Using the "Browse NAS" modal, which only lists the direct children of a single directory at a time. The user cannot see files across subdirectories, cannot select a folder to include all nested files, and cannot expand a directory path in the input form. If a folder path is entered, `resolve_input_path` rejects it as `"Input path is not a regular file"`.

## Goals

1. **Recursive directory browsing**: Browse a folder and view all supported media files across its subfolders.
2. **Bulk folder selection**: Select an entire folder (including nested subfolders) and add all discovered media files in one action.
3. **Folder path expansion in input**: Allow pasting folder paths into the "Add lectures" input form so the API expands them into their contained media files.
4. **Safety & constraints**: Preserve security boundary (reject paths escaping NAS input root), respect file limits (`limit` / `truncated`), and maintain file extension filtering.

---

## Phase 1 — Backend Recursive Scanning (`api`)

### Changes

- `api/src/transcributed/services/nas.py`:
  - Extend `list_directory` with `recursive: bool = False`.
  - When `recursive=True`, recursively walk `target` (using `os.walk` or recursive generator).
  - Check symlink safety: verify every resolved directory and file stays within `root_resolved`.
  - Filter files by `allowed_extensions`.
  - Maintain relative paths starting from the requested path / NAS root (e.g. `course/week-01/lecture.mp4`).
  - Enforce `limit` and mark `truncated = True` if file count exceeds the limit.
- `api/src/transcributed/api/routes/nas.py`:
  - Add query parameter `recursive: bool = Query(default=False)`.
- `api/tests/integration/test_nas_api.py`:
  - Add test cases for recursive directory listings across multi-level directory trees.
  - Verify boundary security (symlinks pointing outside NAS root are ignored).
  - Verify limit truncation during recursive scans.

---

## Phase 2 — Backend Folder Expansion on Import (`api`)

### Changes

- `api/src/transcributed/services/projects.py` & `api/src/transcributed/services/spec.py`:
  - Support expanding directory paths in the item-add flow (`add_project_items`
    route -> `add_items` service):
    - When a provided path resolves to a directory within the NAS root:
      - Recursively discover all valid media files inside that directory.
      - Add each discovered file as an accepted project item.
    - If a path resolves to a file, continue existing single-file behavior.
  - Add integration tests in `api/tests/integration/test_projects_api.py`:
    - Submitting a directory path adds all nested audio/video files.
    - Non-media files inside the folder are skipped.
    - Escaping or non-existent folder paths return appropriate validation errors.

---

## Phase 3 — Frontend NAS Browser UI (`ui`)

### Changes

- `ui/src/lib/endpoints.ts`:
  - Update `listNasFiles(path?: string, recursive?: boolean, limit?: number)` to pass `recursive`.
- `ui/src/pages/ProjectPage.vue`:
  - **Include Subfolders Toggle**: Add a checkbox / switch `Include subfolders` in the NAS browser modal.
    - When enabled, loads files with `recursive: true`.
    - Displays all files found across nested subdirectories, showing relative subfolder paths (e.g. `week-01/lecture-01.mp4`).
  - **Select All Across Subfolders**: "Select all" in recursive mode selects all files across all subdirectories.
  - **Add Entire Folder Action**:
    - Add an "Add current folder (X files)" button in the modal footer or header.
    - Add a quick "Add all" action next to each directory in the folder list.
  - **Search / Filter Input**:
    - Add an in-modal text filter to quickly filter files by name or subfolder path.

---

## Phase 4 — Verification & Documentation

1. Run backend unit and integration tests: `pytest`.
2. Run frontend build / lint: `npm run build`.
3. Manual verification against sample NAS hierarchy:
   - Root folder with multiple subdirectories containing `.mp4` and `.mkv` files.
   - Verify selecting root or subfolder imports all files with correct paths.
   - Verify start run triggers transcription on the imported files.
4. Update wiki index and activity log via `scripts/wiki.mjs`.
