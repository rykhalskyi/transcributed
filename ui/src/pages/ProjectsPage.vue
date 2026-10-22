<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import EmptyState from "@/components/EmptyState.vue";
import ProjectDefaultsForm from "@/components/ProjectDefaultsForm.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { createProject, listProjects } from "@/lib/endpoints";
import { messageOf } from "@/lib/errors";
import { defaultsSummary, formatDate } from "@/lib/format";
import {
  projectDefaultsFromDraft,
  type Language,
  type OutputFormat,
} from "@/lib/projectDefaults";
import type { Project } from "@/lib/types";

const router = useRouter();

const projects = ref<Project[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const dialogOpen = ref(false);
const dialogError = ref<string | null>(null);
const submitting = ref(false);

const form = reactive({
  name: "",
  description: "",
  language: "auto" as Language,
  outputFormats: ["txt"] as OutputFormat[],
  txtTimestamps: false,
});

const canSubmit = computed(
  () => form.name.trim().length > 0 && form.outputFormats.length > 0,
);

async function load() {
  try {
    projects.value = await listProjects();
    error.value = null;
  } catch (err) {
    error.value = messageOf(err);
  } finally {
    loading.value = false;
  }
}

function resetForm() {
  form.name = "";
  form.description = "";
  form.language = "auto";
  form.outputFormats = ["txt"];
  form.txtTimestamps = false;
}

function openDialog() {
  dialogError.value = null;
  resetForm();
  dialogOpen.value = true;
}

function closeDialog() {
  if (submitting.value) return;
  dialogOpen.value = false;
}

async function submit() {
  if (!canSubmit.value || submitting.value) return;
  submitting.value = true;
  dialogError.value = null;
  try {
    const project = await createProject({
      name: form.name.trim(),
      description: form.description.trim() || null,
      defaults: projectDefaultsFromDraft(form),
    });
    dialogOpen.value = false;
    resetForm();
    await router.push({ name: "project", params: { id: project.id } });
  } catch (err) {
    dialogError.value = messageOf(err);
  } finally {
    submitting.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="space-y-6">
    <header class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold tracking-tight">Projects</h1>
        <p class="mt-1 text-sm text-text-muted">
          Saved lecture lists, their transcription runs, and results.
        </p>
      </div>
      <button type="button" class="btn-primary" @click="openDialog">
        New project
      </button>
    </header>

    <div
      v-if="error"
      class="rounded-lg border border-danger/20 bg-danger-soft px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {{ error }}
    </div>

    <div v-if="loading" class="flex items-center gap-3 py-12 text-sm text-text-muted">
      <span class="spinner" />
      Loading projects…
    </div>

    <EmptyState v-else-if="projects.length === 0">
      <button type="button" class="btn-primary mt-6" @click="openDialog">
        Create your first project
      </button>
    </EmptyState>

    <div v-else class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <RouterLink
        v-for="project in projects"
        :key="project.id"
        :to="{ name: 'project', params: { id: project.id } }"
        class="card group flex flex-col p-5 transition hover:-translate-y-0.5 hover:border-brand-purple/30 hover:shadow-md"
      >
        <div class="flex items-start justify-between gap-3">
          <h2 class="text-base font-bold group-hover:text-brand-purple">
            {{ project.name }}
          </h2>
          <StatusBadge :status="project.status" />
        </div>

        <p class="mt-2 line-clamp-2 min-h-10 text-sm text-text-muted">
          {{ project.description || "No description" }}
        </p>

        <div
          class="mt-4 flex items-center justify-between gap-3 border-t border-border pt-3 text-xs text-text-muted"
        >
          <span class="truncate">{{ defaultsSummary(project.defaults) }}</span>
          <span class="shrink-0">{{ formatDate(project.updated_at) }}</span>
        </div>
      </RouterLink>
    </div>

    <Teleport to="body">
      <div
        v-if="dialogOpen"
        class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-brand-navy/40 p-4"
        @click.self="closeDialog"
      >
        <div
          class="card my-8 w-full max-w-lg p-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="new-project-title"
        >
          <div class="flex items-start justify-between gap-4">
            <div>
              <h2 id="new-project-title" class="text-lg font-bold">New project</h2>
              <p class="mt-1 text-sm text-text-muted">
                Defaults apply to every lecture unless you override them per item.
              </p>
            </div>
            <button
              type="button"
              class="btn-ghost -mr-2 -mt-2 px-2 py-1 text-xl leading-none"
              aria-label="Close"
              @click="closeDialog"
            >
              ×
            </button>
          </div>

          <form class="mt-5 space-y-4" @submit.prevent="submit">
            <div>
              <label class="label" for="project-name">Name</label>
              <input
                id="project-name"
                v-model="form.name"
                class="input"
                type="text"
                maxlength="200"
                placeholder="Lectures set 1"
                autofocus
                required
              />
            </div>

            <div>
              <label class="label" for="project-description">
                Description <span class="normal-case tracking-normal">(optional)</span>
              </label>
              <textarea
                id="project-description"
                v-model="form.description"
                class="input resize-y"
                rows="2"
                placeholder="Spring semester, week 1"
              />
            </div>

            <ProjectDefaultsForm
              v-model:language="form.language"
              v-model:output-formats="form.outputFormats"
              v-model:txt-timestamps="form.txtTimestamps"
              id-prefix="new-project"
              :disabled="submitting"
            />

            <div
              class="rounded-lg border border-border bg-surface-muted px-3 py-2 text-xs text-text-muted"
            >
              Model: <span class="font-semibold text-brand-navy">small</span>.
              The deployed worker image only contains this model.
            </div>

            <p
              v-if="dialogError"
              class="rounded-lg border border-danger/20 bg-danger-soft px-3 py-2 text-sm text-danger"
              role="alert"
            >
              {{ dialogError }}
            </p>

            <div class="flex justify-end gap-2 pt-2">
              <button
                type="button"
                class="btn-secondary"
                :disabled="submitting"
                @click="closeDialog"
              >
                Cancel
              </button>
              <button
                type="submit"
                class="btn-primary"
                :disabled="!canSubmit || submitting"
              >
                <span v-if="submitting" class="spinner-light" />
                Create project
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </div>
</template>
