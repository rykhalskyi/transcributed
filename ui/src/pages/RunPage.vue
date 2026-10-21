<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import StatusBadge from "@/components/StatusBadge.vue";
import { usePolling } from "@/composables/usePolling";
import { downloadArtifact } from "@/lib/api";
import {
  cancelRun as cancelRunRequest,
  cancelTask as cancelTaskRequest,
  getRun,
} from "@/lib/endpoints";
import { messageOf } from "@/lib/errors";
import { formatDate } from "@/lib/format";
import { isLiveStatus } from "@/lib/status";
import type { RunDetail, Task } from "@/lib/types";

const props = defineProps<{ id: string }>();

const run = ref<RunDetail | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const actionError = ref<string | null>(null);
const busy = ref(false);
const downloading = ref<string | null>(null);

const tasks = computed(() => run.value?.tasks ?? []);
const finished = computed(
  () =>
    tasks.value.filter((task) =>
      ["succeeded", "failed", "cancelled"].includes(task.status),
    ).length,
);
const succeeded = computed(
  () => tasks.value.filter((task) => task.status === "succeeded").length,
);
const progress = computed(() => {
  if (!tasks.value.length) return 0;
  const total = tasks.value.reduce(
    (sum, task) =>
      sum +
      (["succeeded", "failed", "cancelled"].includes(task.status)
        ? 100
        : (task.progress ?? 0)),
    0,
  );
  return Math.round(total / tasks.value.length);
});
const live = computed(() => isLiveStatus(run.value?.status));
const spec = computed(() => run.value?.spec ?? {});

async function load() {
  try {
    run.value = await getRun(props.id);
    error.value = null;
  } catch (err) {
    error.value = messageOf(err);
  } finally {
    loading.value = false;
  }
}

usePolling(load, {
  interval: 2000,
  enabled: () => live.value,
  immediate: false,
});

async function runAction(action: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true;
  actionError.value = null;
  try {
    await action();
  } catch (err) {
    actionError.value = messageOf(err);
  } finally {
    busy.value = false;
  }
}

async function cancelRun() {
  if (!live.value) return;
  if (!window.confirm("Cancel every queued and processing task in this run?")) {
    return;
  }
  await runAction(async () => {
    await cancelRunRequest(props.id);
    await load();
  });
}

async function cancelTask(task: Task) {
  if (!window.confirm("Cancel this task?")) return;
  await runAction(async () => {
    await cancelTaskRequest(task.id);
    await load();
  });
}

async function download(task: Task, format: string) {
  const key = `${task.id}:${format}`;
  downloading.value = key;
  actionError.value = null;
  try {
    await downloadArtifact(
      task.id,
      format,
      `transcript-${task.id.slice(0, 8)}.${format}`,
    );
  } catch (err) {
    actionError.value = messageOf(err);
  } finally {
    downloading.value = null;
  }
}

function canCancelTask(task: Task): boolean {
  return task.status === "queued" || task.status === "processing";
}

onMounted(load);
</script>

<template>
  <div class="space-y-6">
    <nav class="flex items-center gap-2 text-sm text-text-muted" aria-label="Breadcrumb">
      <RouterLink to="/projects" class="hover:text-brand-purple">Projects</RouterLink>
      <span>/</span>
      <RouterLink
        v-if="run"
        :to="{ name: 'project', params: { id: run.project_id } }"
        class="hover:text-brand-purple"
      >
        Project
      </RouterLink>
      <span v-if="run">/</span>
      <span v-if="run" class="text-brand-navy">Run {{ run.id.slice(0, 8) }}</span>
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
      Loading run…
    </div>

    <template v-else-if="run">
      <header class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div class="flex flex-wrap items-center gap-2">
            <h1 class="text-2xl font-bold tracking-tight">
              Run {{ run.id.slice(0, 8) }}
            </h1>
            <StatusBadge :status="run.status" />
            <span
              v-if="live"
              class="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-purple"
            >
              <span class="spinner h-3 w-3" />
              Live
            </span>
          </div>
          <p class="mt-2 text-xs text-text-muted">
            Created {{ formatDate(run.created_at) }} · Started
            {{ formatDate(run.started_at) }} · Finished
            {{ formatDate(run.finished_at) }}
          </p>
        </div>

        <button
          v-if="live"
          type="button"
          class="btn-danger"
          :disabled="busy"
          @click="cancelRun"
        >
          Cancel run
        </button>
      </header>

      <div
        v-if="actionError"
        class="rounded-lg border border-danger/20 bg-danger-soft px-4 py-3 text-sm text-danger"
        role="alert"
      >
        {{ actionError }}
      </div>

      <section class="card p-5">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p class="text-sm font-bold">
              {{ finished }} of {{ tasks.length }} tasks finished
            </p>
            <p class="text-xs text-text-muted">
              {{ succeeded }} succeeded · {{ progress }}% complete
            </p>
          </div>
          <div class="flex flex-wrap gap-2 text-xs">
            <span class="rounded-full border border-border bg-surface-muted px-2.5 py-1 font-semibold text-text-muted">
              {{ spec.language ?? "auto" }}
            </span>
            <span class="rounded-full border border-border bg-surface-muted px-2.5 py-1 font-semibold text-text-muted">
              {{ spec.model ?? "small" }}
            </span>
            <span class="rounded-full border border-border bg-surface-muted px-2.5 py-1 font-semibold text-text-muted">
              {{ Array.isArray(spec.output_formats) ? spec.output_formats.join(", ") : "txt" }}
            </span>
          </div>
        </div>
        <div class="mt-4 h-2 overflow-hidden rounded-full bg-brand-purple-soft">
          <div
            class="h-full rounded-full bg-brand-purple transition-all"
            :style="{ width: `${progress}%` }"
          />
        </div>
      </section>

      <section class="card p-5">
        <h2 class="text-base font-bold">Tasks</h2>
        <p class="text-sm text-text-muted">
          One task per lecture. Downloads appear when a transcript artifact exists.
        </p>

        <div v-if="tasks.length === 0" class="mt-4 rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-text-muted">
          This run has no tasks.
        </div>

        <div v-else class="mt-4 table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Worker</th>
                <th>Started</th>
                <th>Finished</th>
                <th>Artifacts</th>
                <th class="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in tasks" :key="task.id">
                <td>
                  <div class="font-semibold">{{ task.id.slice(0, 8) }}</div>
                  <div class="max-w-[10rem] truncate text-xs text-text-muted">
                    {{ task.error || task.video_id }}
                  </div>
                </td>
                <td><StatusBadge :status="task.status" /></td>
                <td class="w-32">
                  <div class="flex items-center gap-2">
                    <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-brand-purple-soft">
                      <div
                        class="h-full rounded-full bg-brand-purple transition-all"
                        :style="{ width: `${task.progress ?? 0}%` }"
                      />
                    </div>
                    <span class="text-xs font-semibold text-brand-purple">
                      {{ task.progress ?? 0 }}%
                    </span>
                  </div>
                </td>
                <td>
                  <div class="text-xs font-semibold">
                    {{ task.worker_node || "—" }}
                  </div>
                  <div class="max-w-[10rem] truncate text-xs text-text-muted">
                    {{ task.worker_pod || "" }}
                  </div>
                </td>
                <td class="whitespace-nowrap text-xs text-text-muted">
                  {{ formatDate(task.started_at) }}
                </td>
                <td class="whitespace-nowrap text-xs text-text-muted">
                  {{ formatDate(task.finished_at) }}
                </td>
                <td>
                  <div v-if="task.artifacts?.length" class="flex flex-wrap gap-1.5">
                    <button
                      v-for="artifact in task.artifacts ?? []"
                      :key="artifact.id"
                      type="button"
                      class="rounded-md border border-border bg-white px-2 py-1 text-xs font-semibold text-brand-navy transition hover:border-brand-purple/40 hover:bg-brand-purple-soft"
                      :disabled="downloading === `${task.id}:${artifact.format}`"
                      :title="`Download ${artifact.filename}`"
                      :aria-label="`Download ${artifact.filename}`"
                      @click="download(task, artifact.format)"
                    >
                      <span
                        v-if="downloading === `${task.id}:${artifact.format}`"
                        class="spinner mr-1 h-3 w-3"
                      />
                      Download {{ artifact.format.toUpperCase() }}
                    </button>
                  </div>
                  <span v-else class="text-xs text-text-muted">—</span>
                </td>
                <td class="text-right">
                  <button
                    v-if="canCancelTask(task)"
                    type="button"
                    class="btn-ghost px-2 py-1 text-xs text-danger hover:bg-danger-soft"
                    :disabled="busy"
                    @click="cancelTask(task)"
                  >
                    Cancel
                  </button>
                  <span v-else class="text-xs text-text-muted">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <div v-else class="card px-6 py-12 text-center">
      <h1 class="text-lg font-bold">Run not found</h1>
      <p class="mt-2 text-sm text-text-muted">
        It may have been removed with its project.
      </p>
      <RouterLink to="/projects" class="btn-secondary mt-5">Back to projects</RouterLink>
    </div>
  </div>
</template>
