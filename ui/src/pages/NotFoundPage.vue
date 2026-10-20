<script setup lang="ts">
import BrandLogo from "@/components/BrandLogo.vue";
</script>

<template>
  <div class="card flex flex-col items-center px-6 py-14 text-center">
    <BrandLogo variant="mark" class="mb-6 h-14 w-auto" />
    <p class="text-xs font-bold uppercase tracking-[0.2em] text-brand-purple">404</p>
    <h1 class="mt-2 text-xl font-bold">Page not found</h1>
    <p class="mt-2 max-w-md text-sm text-text-muted">
      That page does not exist in this UI.
    </p>
    <RouterLink to="/projects" class="btn-primary mt-6">Back to projects</RouterLink>
  </div>
</template>
