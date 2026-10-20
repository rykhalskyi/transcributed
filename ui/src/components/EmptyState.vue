<script setup lang="ts">
import { RouterLink } from "vue-router";

import BrandLogo from "@/components/BrandLogo.vue";
</script>

<template>
  <div class="card flex flex-col items-center px-6 py-14 text-center">
    <BrandLogo variant="full" class="mb-6 w-64 max-w-full" />
    <h1 class="text-xl font-bold">No projects yet</h1>
    <p class="mt-2 max-w-md text-sm text-text-muted">
      Create a project, add lecture paths from the NAS, then start a transcription
      run.
    </p>
    <slot />
  </div>
</template>
