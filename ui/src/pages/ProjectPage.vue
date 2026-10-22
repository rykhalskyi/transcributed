<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import ProjectDefaultsForm from "@/components/ProjectDefaultsForm.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { usePolling } from "@/composables/usePolling";
import { downloadArtifact } from "@/lib/api";
import {
  addProjectItems,
  getProject,
  listNasFiles,
  listProjectItems,
  listProjectRuns,
  listWorkers,
  removeProjectItem,
  setProjectItemIncluded,
  startProject,
  updateProject,
} from "@/lib/endpoints";
import { messageOf } from "@/lib/errors";
import {
  baseName,
  defaultsSummary,
  formatBytes,
  formatDate,
  transcriptFilename,
} from "@/lib/format";
import {
  defaultsFromProject,
  projectDefaultsFromDraft,
  type DefaultsDraft,
} from "@/lib/projectDefaults";
import { isLiveStatus } from "@/lib/status";
import type {
  NasListing,
  Project,
  ProjectItem,
  ProjectItemsAddResponse,
  Run,
  WorkersResponse,
} from "@/lib/types";

const props = defineProps<{ id: string }>();
const router = useRouter();

const project = ref<Project | null>(null);
const items = ref<ProjectItem[]>([]);
const runs = ref<Run[]>([]);
const workers = ref<WorkersResponse | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const actionError = ref<string | null>(null);
const notice = ref<string | null>(null);
const busy = ref(false);
const adding = ref(false);
const downloading = ref<string | null>(null);
const addResult = ref<ProjectItemsAddResponse | null>(null);

const defaultsOpen = ref(false);
const defaultsSaving = ref(false);
const defaultsError = ref<string | null>(null);
const defaultsDraft = reactive<DefaultsDraft>({
  language: "auto",
  outputFormats: ["txt"],
  txtTimestamps: false,
});

const nasOpen = ref(false);
const nasLoading = ref(false);
const nasError = ref<string | null>(null);
const nasListing = ref<NasListing | null>(null);
const nasSelected = ref<string[]>([]);

const locked = computed(() => project.value?.status === "active");
const includedCount = computed(
  () => items.value.filter((item) => item.included).length,
);
const transcribedCount = computed(
  () =>
    items.value.filter(
      (item) => item.included && item.latest_task_status === "succeeded",
    ).length,
);
const lectureProgress = computed(() =>
  includedCount.value
    ? Math.round((transcribedCount.value / includedCount.value) * 100)
    : 0,
);
const latestRun = computed(() => runs.value[0] ?? null);
const canStart = computed(() => !locked.value && includedCount.value > 0);
const hasLiveWork = computed(
  () =>
    project.value?.status === "active" ||
    Boolean(workers.value?.active) ||
    items.value.some((item) => isLiveStatus(item.latest_task_status)) ||
    runs.value.some((run) => isLiveStatus(run.status)),
);
const nasSegments = computed(() => {
  const path = nasListing.value?.path ?? "";
  if (!path) return [];
  const parts = path.split("/");
  return parts.map((name, index) => ({
    name,
    path: parts.slice(0, index + 1).join("/"),
  }));
});
const allNasFilesSelected = computed(() => {
  const files = nasListing.value?.files ?? [];
  return (
    files.length > 0 &&
    files.every((file) => nasSelected.value.includes(file.path))
  );
});

async function load() {
  try {
    const [projectResponse, itemResponse, runResponse, workerResponse] =
      await Promise.all([
        getProject(props.id),
        listProjectItems(props.id),
        listProjectRuns(props.id),
        listWorkers(props.id).catch(() => null),
      ]);
    project.value = projectResponse;
    items.value = itemResponse;
    runs.value = runResponse;
    workers.value = workerResponse;
    error.value = null;
  } catch (err) {
    error.value = messageOf(err);
  } finally {
    loading.value = false;
  }
}

usePolling(load, {
  interval: 3000,
  enabled: () => hasLiveWork.value,
  immediate: false,
});

function flash(message: string) {
  notice.value = message;
  window.setTimeout(() => {
    if (notice.value === message) notice.value = null;
  }, 4000);
}

function openDefaults() {
  if (!project.value || locked.value) return;
  const draft = defaultsFromProject(project.value.defaults);
  defaultsDraft.language = draft.language;
  defaultsDraft.outputFormats = draft.outputFormats;
  defaultsDraft.txtTimestamps = draft.txtTimestamps;
  defaultsError.value = null;
  defaultsOpen.value = true;
}

function closeDefaults() {
  if (defaultsSaving.value) return;
  defaultsOpen.value = false;
  defaultsError.value = null;
}

async function saveDefaults() {
  if (defaultsSaving.value) return;
  defaultsSaving.value = true;
  defaultsError.value = null;
  try {
    await updateProject(props.id, {
      defaults: projectDefaultsFromDraft(defaultsDraft),
    });
    defaultsOpen.value = false;
    await load();
    flash("Defaults updated.");
  } catch (err) {
    defaultsError.value = messageOf(err);
    await load();
  } finally {
    defaultsSaving.value = false;
  }
}

async function runAction(action: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true;
  actionError.value = null;
  try {
    await action();
  } catch (err) {
    actionError.value = messageOf(err);
    await load();
  } finally {
    busy.value = false;
  }
}

async function startRun() {
  if (!canStart.value) return;
  await runAction(async () => {
    const response = await startProject(props.id);
    await router.push({ name: "run", params: { id: response.run.id } });
  });
}

async function addPaths(paths: string[]): Promise<boolean> {
  if (!paths.length || locked.value || adding.value) return false;

  adding.value = true;
  actionError.value = null;
  addResult.value = null;
  try {
    const result = await addProjectItems(props.id, paths);
    addResult.value = result;
    if (result.rejected === 0) {
      flash(`Added ${result.accepted} lecture${result.accepted === 1 ? "" : "s"}.`);
    }
    await load();
    return true;
  } catch (err) {
    actionError.value = messageOf(err);
    return false;
  } finally {
    adding.value = false;
  }
}

async function toggleIncluded(item: ProjectItem) {
  await runAction(async () => {
    await setProjectItemIncluded(props.id, item.id, !item.included);
    await load();
  });
}

async function removeItem(item: ProjectItem) {
  if (!window.confirm(`Remove "${baseName(item.path)}" from this project?`)) {
    return;
  }
  await runAction(async () => {
    await removeProjectItem(props.id, item.id);
    await load();
  });
}

async function downloadItemArtifact(item: ProjectItem, format: string) {
  if (!item.latest_task_id) return;
  const key = `${item.id}:${format}`;
  downloading.value = key;
  actionError.value = null;
  try {
    await downloadArtifact(
      item.latest_task_id,
      format,
      transcriptFilename(item.path, format),
    );
  } catch (err) {
    actionError.value = messageOf(err);
  } finally {
    downloading.value = null;
  }
}

async function openNasBrowser() {
  if (locked.value) return;
  nasOpen.value = true;
  nasSelected.value = [];
  nasError.value = null;
  await browseNas("");
}

async function browseNas(path: string) {
  nasLoading.value = true;
  nasError.value = null;
  try {
    nasListing.value = await listNasFiles(path);
  } catch (err) {
    nasError.value = messageOf(err);
  } finally {
    nasLoading.value = false;
  }
}

function closeNasBrowser() {
  if (!adding.value) nasOpen.value = false;
}

function toggleNasFile(path: string) {
  const index = nasSelected.value.indexOf(path);
  if (index >= 0) {
    nasSelected.value.splice(index, 1);
    return;
  }
  nasSelected.value.push(path);
}

function selectAllNasFiles() {
  const files = nasListing.value?.files ?? [];
  nasSelected.value = allNasFilesSelected.value
    ? []
    : files.map((file) => file.path);
}

async function addSelectedNas() {
  if (await addPaths(nasSelected.value.slice())) {
    nasOpen.value = false;
    nasSelected.value = [];
  }
}

onMounted(load);
</script>

<template>
  <div class="space-y-6">
    <nav class="flex items-center gap-2 text-sm text-text-muted" aria-label="Breadcrumb">
      <RouterLink to="/projects" class="hover:text-brand-purple">Projects</RouterLink>
      <span>/</span>
      <span class="truncate text-brand-navy">{{ project?.name || "Project" }}</span>
    </nav>

    <div
      v-if="error"
      class="rounded-lg border border-danger/20 bg-danger-soft px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {{ error }}
    </div>

    <div v-if="loading" class="flex items-center gap-3 py-12 text-sm text-text-muted">
      <span class="spinner" />
      Loading project…
    </div>

    <template v-else-if="project">
      <header class="flex flex-wrap items-start justify-between gap-4">
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2">
            <h1 class="truncate text-2xl font-bold tracking-tight">
              {{ project.name }}
            </h1>
            <StatusBadge :status="project.status" />
          </div>
          <p v-if="project.description" class="mt-1 text-sm text-text-muted">
            {{ project.description }}
          </p>
          <p class="mt-2 text-xs text-text-muted">
            {{ defaultsSummary(project.defaults) }} · Updated
            {{ formatDate(project.updated_at) }}
          </p>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <RouterLink
            v-if="workers"
            :to="{ name: 'workers', query: { project_id: props.id } }"
            class="inline-flex items-center gap-2 rounded-full border border-border bg-surface-muted px-3 py-1.5 text-xs font-semibold text-text-muted transition hover:border-brand-purple/30 hover:text-brand-purple"
            title="View workers"
          >
            <span
              class="h-1.5 w-1.5 rounded-full"
              :class="workers.active ? 'bg-brand-purple' : 'bg-text-muted'"
            />
            {{ workers.active }} active · {{ workers.queued }} queued
          </RouterLink>
          <span v-else class="text-xs text-text-muted">Workers unavailable</span>
          <button
            type="button"
            class="btn-secondary"
            :disabled="locked || busy"
            :title="
              locked
                ? 'A run is active'
                : 'Edit transcription defaults for future runs'
            "
            @click="openDefaults"
          >
            Edit defaults
          </button>
          <RouterLink
            v-if="latestRun"
            :to="{ name: 'run', params: { id: latestRun.id } }"
            class="btn-secondary"
          >
            Latest run
          </RouterLink>
          <button
            type="button"
            class="btn-primary"
            :disabled="!canStart || busy"
            :title="
              locked
                ? 'A run is active'
                : includedCount === 0
                  ? 'Add and include at least one lecture'
                  : 'Start a transcription run'
            "
            @click="startRun"
          >
            <span v-if="busy" class="spinner-light" />
            {{ locked ? "Run active" : "Start transcription" }}
          </button>
        </div>
      </header>

      <div
        v-if="locked"
        class="rounded-lg border border-warning/20 bg-warning-soft px-4 py-3 text-sm text-warning"
      >
        A run is active. Lectures and defaults are locked until it finishes or is
        cancelled.
      </div>

      <div
        v-if="notice"
        class="rounded-lg border border-success/20 bg-success-soft px-4 py-3 text-sm text-success"
        role="status"
      >
        {{ notice }}
      </div>

      <div
        v-if="actionError"
        class="rounded-lg border border-danger/20 bg-danger-soft px-4 py-3 text-sm text-danger"
        role="alert"
      >
        {{ actionError }}
      </div>

      <section class="card p-5">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 class="text-base font-bold">Lectures</h2>
            <p class="text-sm text-text-muted">
              Choose lectures from the NAS; media never passes through the API.
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-3">
            <span class="text-xs font-semibold text-text-muted">
              {{ items.length }} item{{ items.length === 1 ? "" : "s" }} ·
              {{ includedCount }} included
            </span>
            <span class="text-xs font-semibold text-brand-purple">
              {{ transcribedCount }}/{{ includedCount }} transcribed
            </span>
          </div>
        </div>

        <div class="mt-3 flex items-center gap-3">
          <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-brand-purple-soft">
            <div
              class="h-full rounded-full bg-brand-purple transition-all"
              :style="{ width: `${lectureProgress}%` }"
            />
          </div>
          <span class="text-xs font-semibold text-text-muted">
            {{ lectureProgress }}%
          </span>
        </div>

        <div class="mt-4 table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Lecture</th>
                <th>Status</th>
                <th>Transcript</th>
                <th>Included</th>
                <th class="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="item.id">
                <td>
                  <div class="font-semibold">{{ baseName(item.path) }}</div>
                  <div class="max-w-md truncate text-xs text-text-muted">
                    {{ item.path }}
                  </div>
                </td>
                <td>
                  <div class="space-y-1.5">
                    <StatusBadge :status="item.latest_task_status" />
                    <div
                      v-if="item.latest_task_status === 'processing'"
                      class="flex items-center gap-2"
                    >
                      <div class="h-1.5 w-20 overflow-hidden rounded-full bg-brand-purple-soft">
                        <div
                          class="h-full rounded-full bg-brand-purple transition-all"
                          :style="{ width: `${item.latest_task_progress ?? 0}%` }"
                        />
                      </div>
                      <span class="text-[11px] font-semibold text-brand-purple">
                        {{ item.latest_task_progress ?? 0 }}%
                      </span>
                    </div>
                  </div>
                </td>
                <td>
                  <div
                    v-if="item.latest_task_artifacts?.length"
                    class="flex flex-wrap gap-1.5"
                  >
                    <button
                      v-for="artifact in item.latest_task_artifacts"
                      :key="artifact.id"
                      type="button"
                      class="rounded-md border border-border bg-white px-2 py-1 text-xs font-semibold text-brand-navy transition hover:border-brand-purple/40 hover:bg-brand-purple-soft"
                      :disabled="downloading === `${item.id}:${artifact.format}`"
                      :title="`Download ${artifact.filename}`"
                      :aria-label="`Download ${artifact.filename}`"
                      @click="downloadItemArtifact(item, artifact.format)"
                    >
                      <span
                        v-if="downloading === `${item.id}:${artifact.format}`"
                        class="spinner mr-1 h-3 w-3"
                      />
                      Download {{ artifact.format.toUpperCase() }}
                    </button>
                  </div>
                  <span v-else class="text-xs text-text-muted">—</span>
                </td>
                <td>
                  <input
                    type="checkbox"
                    class="h-4 w-4 accent-brand-purple"
                    :checked="item.included"
                    :disabled="locked || busy"
                    :aria-label="`Include ${baseName(item.path)}`"
                    @change="toggleIncluded(item)"
                  />
                </td>
                <td class="text-right">
                  <button
                    type="button"
                    class="btn-ghost px-2 py-1 text-xs text-danger hover:bg-danger-soft"
                    :disabled="locked || busy"
                    @click="removeItem(item)"
                  >
                    Remove
                  </button>
                </td>
              </tr>
              <tr v-if="items.length === 0">
                <td colspan="5" class="py-10 text-center text-sm text-text-muted">
                  No lectures yet. Browse the NAS to add files.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5">
          <div>
            <h3 class="text-sm font-bold">Add lectures</h3>
            <p class="text-xs text-text-muted">
              Pick supported media files from the NAS.
            </p>
          </div>
          <button
            type="button"
            class="btn-secondary"
            :disabled="locked || adding"
            @click="openNasBrowser"
          >
            <span v-if="adding" class="spinner" />
            Browse NAS
          </button>
        </div>

        <div
          v-if="addResult"
          class="mt-4 rounded-lg border border-border bg-surface-muted px-4 py-3 text-sm"
        >
          <p class="font-semibold">
            Added {{ addResult.accepted }}, rejected {{ addResult.rejected }}
          </p>
          <ul
            v-if="addResult.rejected > 0"
            class="mt-1 space-y-1 text-xs text-danger"
          >
            <li
              v-for="(result, index) in addResult.results.filter(
                (item) => !item.accepted,
              )"
              :key="`${result.path}-${index}`"
            >
              {{ result.path }} — {{ result.error }}
            </li>
          </ul>
        </div>
      </section>

      <section class="card p-5">
        <h2 class="text-base font-bold">Run history</h2>
        <p class="text-sm text-text-muted">
          Every start creates a new snapshot; previous results stay intact.
        </p>

        <div v-if="runs.length === 0" class="mt-4 rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-text-muted">
          No runs yet. Add lectures and start a transcription.
        </div>

        <div v-else class="mt-4 table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Run</th>
                <th>Status</th>
                <th>Created</th>
                <th>Finished</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="run in runs" :key="run.id">
                <td>
                  <RouterLink
                    :to="{ name: 'run', params: { id: run.id } }"
                    class="font-semibold text-brand-purple hover:underline"
                  >
                    {{ run.id.slice(0, 8) }}
                  </RouterLink>
                </td>
                <td><StatusBadge :status="run.status" /></td>
                <td class="text-text-muted">{{ formatDate(run.created_at) }}</td>
                <td class="text-text-muted">{{ formatDate(run.finished_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <div v-else class="card px-6 py-12 text-center">
      <h1 class="text-lg font-bold">Project not found</h1>
      <p class="mt-2 text-sm text-text-muted">
        It may have been deleted. Return to the project list.
      </p>
      <RouterLink to="/projects" class="btn-secondary mt-5">Back to projects</RouterLink>
    </div>

    <Teleport to="body">
      <div
        v-if="defaultsOpen"
        class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-brand-navy/40 p-4"
        @click.self="closeDefaults"
      >
        <div
          class="card my-8 w-full max-w-lg p-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="edit-defaults-title"
        >
          <div class="flex items-start justify-between gap-4">
            <div>
              <h2 id="edit-defaults-title" class="text-lg font-bold">
                Edit defaults
              </h2>
              <p class="mt-1 text-sm text-text-muted">
                These apply to future runs; existing transcripts keep their
                settings.
              </p>
            </div>
            <button
              type="button"
              class="btn-ghost -mr-2 -mt-2 px-2 py-1 text-xl leading-none"
              aria-label="Close"
              @click="closeDefaults"
            >
              ×
            </button>
          </div>

          <form class="mt-5 space-y-4" @submit.prevent="saveDefaults">
            <ProjectDefaultsForm
              v-model:language="defaultsDraft.language"
              v-model:output-formats="defaultsDraft.outputFormats"
              v-model:txt-timestamps="defaultsDraft.txtTimestamps"
              id-prefix="edit-project"
              :disabled="defaultsSaving || locked"
            />

            <div
              class="rounded-lg border border-border bg-surface-muted px-3 py-2 text-xs text-text-muted"
            >
              Model: <span class="font-semibold text-brand-navy">small</span>.
              The deployed worker image only contains this model.
            </div>

            <p
              v-if="defaultsError"
              class="rounded-lg border border-danger/20 bg-danger-soft px-3 py-2 text-sm text-danger"
              role="alert"
            >
              {{ defaultsError }}
            </p>

            <div class="flex justify-end gap-2 pt-2">
              <button
                type="button"
                class="btn-secondary"
                :disabled="defaultsSaving"
                @click="closeDefaults"
              >
                Cancel
              </button>
              <button
                type="submit"
                class="btn-primary"
                :disabled="defaultsSaving || locked"
              >
                <span v-if="defaultsSaving" class="spinner-light" />
                Save defaults
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="nasOpen"
        class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-brand-navy/40 p-4"
        @click.self="closeNasBrowser"
      >
        <div
          class="card my-8 w-full max-w-3xl p-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="nas-browser-title"
        >
          <div class="flex items-start justify-between gap-4">
            <div>
              <h2 id="nas-browser-title" class="text-lg font-bold">
                Browse NAS lectures
              </h2>
              <p class="mt-1 text-sm text-text-muted">
                Select supported media files to add to this project.
              </p>
            </div>
            <button
              type="button"
              class="btn-ghost -mr-2 -mt-2 px-2 py-1 text-xl leading-none"
              aria-label="Close"
              @click="closeNasBrowser"
            >
              ×
            </button>
          </div>

          <div class="mt-4 flex flex-wrap items-center gap-1 text-sm">
            <button
              type="button"
              class="font-semibold text-brand-purple hover:underline"
              @click="browseNas('')"
            >
              NAS
            </button>
            <template v-for="segment in nasSegments" :key="segment.path">
              <span class="text-text-muted">/</span>
              <button
                type="button"
                class="hover:text-brand-purple"
                @click="browseNas(segment.path)"
              >
                {{ segment.name }}
              </button>
            </template>
          </div>

          <p
            v-if="nasError"
            class="mt-4 rounded-lg border border-danger/20 bg-danger-soft px-3 py-2 text-sm text-danger"
            role="alert"
          >
            {{ nasError }}
          </p>

          <div v-if="nasLoading" class="flex items-center gap-3 py-10 text-sm text-text-muted">
            <span class="spinner" />
            Loading folder…
          </div>

          <div v-else class="mt-4 grid gap-4 md:grid-cols-[220px_1fr]">
            <div class="rounded-lg border border-border">
              <div class="border-b border-border bg-surface-muted px-3 py-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
                Folders
              </div>
              <div class="max-h-80 overflow-y-auto p-1">
                <button
                  v-if="nasListing && nasListing.parent !== null"
                  type="button"
                  class="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-semibold text-brand-purple hover:bg-brand-purple-soft"
                  @click="browseNas(nasListing.parent ?? '')"
                >
                  ..
                </button>
                <button
                  v-for="directory in nasListing?.directories ?? []"
                  :key="directory.path"
                  type="button"
                  class="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-semibold hover:bg-brand-purple-soft"
                  @click="browseNas(directory.path)"
                >
                  {{ directory.name }}
                </button>
                <p
                  v-if="!nasListing?.directories.length"
                  class="px-3 py-4 text-xs text-text-muted"
                >
                  No folders
                </p>
              </div>
            </div>

            <div class="rounded-lg border border-border">
              <div class="flex items-center justify-between gap-2 border-b border-border bg-surface-muted px-3 py-2">
                <span class="text-xs font-semibold uppercase tracking-wide text-text-muted">
                  Media files
                </span>
                <button
                  type="button"
                  class="text-xs font-semibold text-brand-purple hover:underline"
                  @click="selectAllNasFiles"
                >
                  {{ allNasFilesSelected ? "Clear all" : "Select all" }}
                </button>
              </div>
              <div class="max-h-80 overflow-y-auto p-1">
                <label
                  v-for="file in nasListing?.files ?? []"
                  :key="file.path"
                  class="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 hover:bg-brand-purple-soft"
                >
                  <input
                    type="checkbox"
                    class="h-4 w-4 accent-brand-purple"
                    :checked="nasSelected.includes(file.path)"
                    @change="toggleNasFile(file.path)"
                  />
                  <span class="min-w-0 flex-1">
                    <span class="block truncate text-sm font-semibold">
                      {{ file.name }}
                    </span>
                    <span class="block text-xs text-text-muted">
                      {{ formatBytes(file.size_bytes) }}
                    </span>
                  </span>
                </label>
                <p
                  v-if="!nasListing?.files.length"
                  class="px-3 py-4 text-xs text-text-muted"
                >
                  No supported media files in this folder.
                </p>
              </div>
            </div>
          </div>

          <div class="mt-5 flex flex-wrap items-center justify-between gap-3">
            <p class="text-xs text-text-muted">
              {{ nasSelected.length }} file{{ nasSelected.length === 1 ? "" : "s" }}
              selected
            </p>
            <div class="flex gap-2">
              <button
                type="button"
                class="btn-secondary"
                :disabled="adding"
                @click="closeNasBrowser"
              >
                Cancel
              </button>
              <button
                type="button"
                class="btn-primary"
                :disabled="nasSelected.length === 0 || adding"
                @click="addSelectedNas"
              >
                <span v-if="adding" class="spinner-light" />
                Add selected
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
