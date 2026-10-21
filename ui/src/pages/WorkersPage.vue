<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { usePolling } from "@/composables/usePolling";
import { cancelTask, listWorkers } from "@/lib/endpoints";
import { messageOf } from "@/lib/errors";
import { baseName, formatDate } from "@/lib/format";
import type { WorkersResponse } from "@/lib/types";

const route = useRoute();

const workers = ref<WorkersResponse | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const actionError = ref<string | null>(null);
const busy = ref(false);

const projectId = computed(() =>
  typeof route.query.project_id === "string" ? route.query.project_id : undefined,
);

async function load() {
  try {
    workers.value = await listWorkers(projectId.value);
    error.value = null;
  } catch (err) {
    error.value = messageOf(err);
  } finally {
    loading.value = false;
  }
}

usePolling(load, {
  interval: 3000,
  enabled: () => true,
  immediate: true,
});

watch(projectId, load);

async function cancelWorker(taskId: string) {
  if (busy.value) return;
  if (!window.confirm("Cancel this worker's task?")) return;
  busy.value = true;
  actionError.value = null;
  try {
    await cancelTask(taskId);
    await load();
  } catch (err) {
    actionError.value = messageOf(err);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="space-y-6">
    <nav class="flex items-center gap-2 text-sm text-text-muted" aria-label="Breadcrumb">
      <RouterLink to="/projects" class="hover:text-brand-purple">Projects</RouterLink>
      <span>/</span>
      <span class="text-brand-navy">Workers</span>
    </nav>

    <header class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold tracking-tight">Workers</h1>
        <p class="mt-1 text-sm text-text-muted">
          Active worker pods and tasks waiting in the queue.
        </p>
      </div>

      <div v-if="workers" class="flex gap-2 text-xs font-semibold">
        <span
          class="rounded-full border border-brand-purple/15 bg-brand-purple-soft px-2.5 py-1 text-brand-purple"
        >
          {{ workers.active }} active
        </span>
        <span
          class="rounded-full border border-warning/20 bg-warning-soft px-2.5 py-1 text-warning"
        >
          {{ workers.queued }} queued
        </span>
      </div>
    </header>

    <div
      v-if="error"
      class="rounded-lg border border-danger/20 bg-danger-soft px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {{ error }}
    </div>

    <div
      v-if="actionError"
      class="rounded-lg border border-danger/20 bg-danger-soft px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {{ actionError }}
    </div>

    <div v-if="loading" class="flex items-center gap-3 py-12 text-sm text-text-muted">
      <span class="spinner" />
      Loading workers…
    </div>

    <section v-else class="card p-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 class="text-base font-bold">Active workers</h2>
          <p class="text-sm text-text-muted">
            One worker pod processes one lecture at a time.
          </p>
        </div>
        <span
          v-if="workers"
          class="text-xs font-semibold text-text-muted"
        >
          {{ workers.active }} running · {{ workers.queued }} queued
        </span>
      </div>

      <div v-if="workers?.workers.length" class="mt-4 table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Worker</th>
              <th>Node</th>
              <th>Project</th>
              <th>Lecture</th>
              <th>Progress</th>
              <th>Started</th>
              <th class="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="worker in workers.workers" :key="worker.task_id">
              <td>
                <div class="font-semibold">
                  {{ worker.pod || "Unknown pod" }}
                </div>
                <div class="text-xs text-text-muted">
                  {{ worker.task_id.slice(0, 8) }}
                </div>
              </td>
              <td class="text-text-muted">{{ worker.node || "—" }}</td>
              <td>
                <RouterLink
                  :to="{ name: 'project', params: { id: worker.project_id } }"
                  class="font-semibold text-brand-purple hover:underline"
                >
                  {{ worker.project_name }}
                </RouterLink>
              </td>
              <td>
                <div class="font-semibold">{{ baseName(worker.path) }}</div>
                <div class="max-w-xs truncate text-xs text-text-muted">
                  {{ worker.path }}
                </div>
              </td>
              <td class="w-32">
                <div class="flex items-center gap-2">
                  <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-brand-purple-soft">
                    <div
                      class="h-full rounded-full bg-brand-purple transition-all"
                      :style="{ width: `${worker.progress}%` }"
                    />
                  </div>
                  <span class="text-xs font-semibold text-brand-purple">
                    {{ worker.progress }}%
                  </span>
                </div>
              </td>
              <td class="whitespace-nowrap text-text-muted">
                {{ formatDate(worker.started_at) }}
              </td>
              <td class="text-right">
                <button
                  type="button"
                  class="btn-ghost px-2 py-1 text-xs text-danger hover:bg-danger-soft"
                  :disabled="busy"
                  @click="cancelWorker(worker.task_id)"
                >
                  Cancel
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p
        v-else
        class="mt-4 rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-text-muted"
      >
        No worker is processing a task right now.
      </p>
    </section>
  </div>
</template>
