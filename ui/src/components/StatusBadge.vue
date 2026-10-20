<script setup lang="ts">
import { computed } from "vue";

import {
  statusClasses,
  statusLabel,
  statusTone,
} from "@/lib/status";

const props = defineProps<{ status?: string | null }>();

const classes = computed(() => statusClasses(props.status));
const tone = computed(() => statusTone(props.status));
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold"
    :class="classes"
  >
    <span v-if="status === 'processing'" class="spinner h-3 w-3" />
    <span
      v-else
      class="h-1.5 w-1.5 rounded-full"
      :class="tone === 'neutral' ? 'bg-text-muted' : 'bg-current'"
    />
    {{ statusLabel(status) }}
  </span>
</template>
