<script setup lang="ts">
import { computed } from "vue";

import { useApiHealth } from "@/composables/useApiHealth";

const { health, check } = useApiHealth();

const label = computed(() => {
  switch (health.value) {
    case "ok":
      return "API online";
    case "degraded":
      return "API degraded";
    case "down":
      return "API offline";
    default:
      return "Checking API";
  }
});

const dotClass = computed(() => {
  switch (health.value) {
    case "ok":
      return "bg-success";
    case "degraded":
      return "bg-warning";
    case "down":
      return "bg-danger";
    default:
      return "bg-warning animate-pulse";
  }
});
</script>

<template>
  <button
    type="button"
    class="inline-flex items-center gap-2 rounded-full border border-border bg-white px-2.5 py-1 text-xs font-semibold text-text-muted transition hover:border-brand-purple/40 hover:text-brand-navy"
    :title="label"
    @click="check"
  >
    <span class="h-2 w-2 rounded-full" :class="dotClass" />
    <span class="hidden sm:inline">{{ label }}</span>
  </button>
</template>
