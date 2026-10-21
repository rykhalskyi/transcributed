<script setup lang="ts">
import { computed } from "vue";

import logo from "@/assets/brand/transcributed-logo.png";
import logo2x from "@/assets/brand/transcributed-logo@2x.png";
import mark from "@/assets/brand/transcributed-mark.png";
import mark2x from "@/assets/brand/transcributed-mark@2x.png";
import wordmark from "@/assets/brand/transcributed-wordmark.png";
import wordmark2x from "@/assets/brand/transcributed-wordmark@2x.png";

type Variant = "full" | "mark" | "wordmark";

const props = withDefaults(defineProps<{ variant?: Variant }>(), {
  variant: "full",
});

const sources = computed(() => {
  //if (props.variant === "mark") return { src: mark, srcset: `${mark} 1x, ${mark2x} 2x` };
  if (props.variant === "wordmark") {
    return { src: wordmark, srcset: `${wordmark} 1x, ${wordmark2x} 2x` };
  }
  return { src: logo, srcset: `${logo} 1x, ${logo2x} 2x` };
});

const alt = computed(() => (props.variant === "mark" ? "" : "Transcributed"));
</script>

<template>
  <img :src="sources.src" :srcset="sources.srcset" :alt="alt" />
</template>
