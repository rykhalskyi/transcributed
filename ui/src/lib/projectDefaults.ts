import type { ProjectDefaults } from "./types";

export type Language = "en" | "ru" | "de" | "auto";
export type Model = "tiny" | "base" | "small" | "medium" | "large-v3";
export type OutputFormat = "txt" | "vtt" | "json";

export interface DefaultsDraft {
  language: Language;
  model: Model;
  outputFormats: OutputFormat[];
  txtTimestamps: boolean;
}

export const LANGUAGE_OPTIONS: { value: Language; label: string }[] = [
  { value: "auto", label: "Auto-detect" },
  { value: "en", label: "English" },
  { value: "ru", label: "Russian" },
  { value: "de", label: "German" },
];

export const FORMAT_OPTIONS: { value: OutputFormat; label: string }[] = [
  { value: "txt", label: "TXT" },
  { value: "vtt", label: "VTT" },
  { value: "json", label: "JSON" },
];

const LANGUAGES = new Set<Language>(LANGUAGE_OPTIONS.map((item) => item.value));
const FORMATS = new Set<OutputFormat>(FORMAT_OPTIONS.map((item) => item.value));
const MODELS = new Set<Model>([
  "tiny",
  "base",
  "small",
  "medium",
  "large-v3",
]);

function isLanguage(value: unknown): value is Language {
  return typeof value === "string" && LANGUAGES.has(value as Language);
}

function isOutputFormat(value: unknown): value is OutputFormat {
  return typeof value === "string" && FORMATS.has(value as OutputFormat);
}

function isModel(value: unknown): value is Model {
  return typeof value === "string" && MODELS.has(value as Model);
}

export function defaultsFromProject(
  defaults: Record<string, unknown>,
): DefaultsDraft {
  const language = isLanguage(defaults.language) ? defaults.language : "auto";
  const model = isModel(defaults.model) ? defaults.model : "small";
  const formats = Array.isArray(defaults.output_formats)
    ? defaults.output_formats.filter(isOutputFormat)
    : [];
  const outputFormats: OutputFormat[] = formats.length
    ? [...new Set(formats)]
    : ["txt"];
  return {
    language,
    model,
    outputFormats,
    txtTimestamps:
      defaults.txt_timestamps === true && outputFormats.includes("txt"),
  };
}

export function projectDefaultsFromDraft(
  draft: DefaultsDraft,
): ProjectDefaults {
  return {
    language: draft.language,
    model: draft.model,
    output_formats: [...draft.outputFormats],
    txt_timestamps: draft.outputFormats.includes("txt") && draft.txtTimestamps,
  };
}
