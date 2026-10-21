<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

import ApiStatus from "./ApiStatus.vue";
import BrandLogo from "./BrandLogo.vue";
import VersionInfo from "./VersionInfo.vue";

const route = useRoute();

const section = computed(() => {
  if (route.name === "run") return "Run";
  if (route.name === "project") return "Project";
  if (route.name === "workers") return "Workers";
  return "Projects";
});

const projectsActive = computed(
  () => route.name === "projects" || route.name === "project",
);
const workersActive = computed(() => route.name === "workers");
</script>

<template>
  <div class="min-h-screen bg-white text-brand-navy md:flex">
    <aside
      class="hidden w-60 shrink-0 flex-col border-r border-border bg-white md:flex"
    >
      <RouterLink
        to="/projects"
        class="flex items-center px-5 py-5"
        aria-label="Transcributed projects"
      >
        <BrandLogo variant="wordmark" class="h-5 w-auto" />
      </RouterLink>

      <nav class="flex-1 px-3 py-2">
        <RouterLink
          to="/projects"
          class="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition"
          :class="
            projectsActive
              ? 'bg-brand-purple-soft text-brand-purple'
              : 'text-brand-navy hover:bg-surface-muted'
          "
        >
          <span class="h-1.5 w-1.5 rounded-full bg-current" />
          Projects
        </RouterLink>

        <RouterLink
          to="/workers"
          class="mt-1 flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition"
          :class="
            workersActive
              ? 'bg-brand-purple-soft text-brand-purple'
              : 'text-brand-navy hover:bg-surface-muted'
          "
        >
          <span class="h-1.5 w-1.5 rounded-full bg-current" />
          Workers
        </RouterLink>
      </nav>

      <div class="border-t border-border px-5 py-4 text-xs leading-relaxed text-text-muted">
        <p class="font-semibold text-brand-navy">Transcributed</p>
        <p>Lecture transcription control plane</p>
      </div>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col">
      <header
        class="flex h-16 items-center justify-between gap-4 border-b border-border px-4 sm:px-6"
      >
        <div class="flex items-center gap-3">
          <div>
            <p class="text-xs font-semibold uppercase tracking-wide text-text-muted">
              {{ section }}
            </p>
            <p class="text-base font-bold leading-tight">Transcributed</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <VersionInfo />
          <ApiStatus />
        </div>
      </header>

      <main class="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <slot />
      </main>
    </div>
  </div>
</template>
