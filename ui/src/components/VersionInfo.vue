<script setup lang="ts">
import { onMounted, ref } from "vue";

import { getApiVersion } from "@/lib/endpoints";
import { UI_VERSION } from "@/lib/version";

const apiVersion = ref<string | null>(null);

onMounted(async () => {
  try {
    apiVersion.value = await getApiVersion();
  } catch {
    apiVersion.value = null;
  }
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
