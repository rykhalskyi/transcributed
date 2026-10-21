<script setup lang="ts">
import { ref } from "vue";

import { usePolling } from "@/composables/usePolling";
import { getApiVersion } from "@/lib/endpoints";
import { UI_VERSION } from "@/lib/version";

const apiVersion = ref<string | null>(null);

async function loadVersion() {
  try {
    apiVersion.value = await getApiVersion();
  } catch {
    apiVersion.value = null;
  }
}

usePolling(loadVersion, {
  interval: 5000,
  enabled: () => apiVersion.value === null,
  immediate: true,
});
</script>

<template>
  <span
    class="whitespace-nowrap text-[11px] font-semibold text-text-muted"
    :title="`UI v${UI_VERSION} · API ${apiVersion ? 'v' + apiVersion : 'unavailable'}`"
  >
    UI v{{ UI_VERSION }} · API {{ apiVersion ? `v${apiVersion}` : "—" }}
  </span>
</template>
