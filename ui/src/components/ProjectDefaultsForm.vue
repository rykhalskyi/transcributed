<script setup lang="ts">
import {
  FORMAT_OPTIONS,
  LANGUAGE_OPTIONS,
  type Language,
  type OutputFormat,
} from "@/lib/projectDefaults";

const props = withDefaults(
  defineProps<{ idPrefix?: string; disabled?: boolean }>(),
  { idPrefix: "project", disabled: false },
);

const language = defineModel<Language>("language", { required: true });
const outputFormats = defineModel<OutputFormat[]>("output-formats", {
  required: true,
});
const txtTimestamps = defineModel<boolean>("txt-timestamps", { required: true });

function toggleFormat(format: OutputFormat) {
  if (props.disabled) return;
  if (outputFormats.value.includes(format)) {
    if (outputFormats.value.length === 1) return;
    outputFormats.value = outputFormats.value.filter((item) => item !== format);
    if (format === "txt") txtTimestamps.value = false;
    return;
  }
  outputFormats.value = [...outputFormats.value, format];
}
</script>

<template>
  <div>
    <label class="label" :for="`${props.idPrefix}-language`">Language</label>
    <select
      :id="`${props.idPrefix}-language`"
      v-model="language"
      class="input"
      :disabled="props.disabled"
    >
      <option
        v-for="option in LANGUAGE_OPTIONS"
        :key="option.value"
        :value="option.value"
      >
        {{ option.label }}
      </option>
    </select>
  </div>

  <div>
    <span class="label">Output formats</span>
    <div class="flex flex-wrap gap-2">
      <label
        v-for="format in FORMAT_OPTIONS"
        :key="format.value"
        class="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold transition"
        :class="[
          outputFormats.includes(format.value)
            ? 'border-brand-purple/30 bg-brand-purple-soft text-brand-purple'
            : 'border-border bg-white text-brand-navy hover:border-brand-purple/30',
          props.disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer',
        ]"
      >
        <input
          type="checkbox"
          class="sr-only"
          :checked="outputFormats.includes(format.value)"
          :disabled="props.disabled"
          @change="toggleFormat(format.value)"
        />
        {{ format.label }}
      </label>
    </div>
    <label
      v-if="outputFormats.includes('txt')"
      class="mt-3 inline-flex items-center gap-2 text-sm text-text-muted"
      :class="props.disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'"
    >
      <input
        v-model="txtTimestamps"
        type="checkbox"
        class="h-4 w-4 rounded border-border text-brand-purple focus:ring-brand-purple"
        :disabled="props.disabled"
      />
      Include timestamps in TXT
    </label>
  </div>
</template>
