import type { ProjectDefaults } from "./types";

export type Language = "en" | "ru" | "de" | "auto";
export type OutputFormat = "txt" | "vtt" | "json";

export interface DefaultsDraft {
  language: Language;
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

function isLanguage(value: unknown): value is Language {
  return typeof value === "string" && LANGUAGES.has(value as Language);
}

function isOutputFormat(value: unknown): value is OutputFormat {
  return typeof value === "string" && FORMATS.has(value as OutputFormat);
}

export function defaultsFromProject(
  defaults: Record<string, unknown>,
): DefaultsDraft {
  const language = isLanguage(defaults.language) ? defaults.language : "auto";
  const formats = Array.isArray(defaults.output_formats)
    ? defaults.output_formats.filter(isOutputFormat)
    : [];
  return {
    language,
    outputFormats: formats.length ? [...new Set(formats)] : ["txt"],
    txtTimestamps: defaults.txt_timestamps === true,
  };
}

export function projectDefaultsFromDraft(
  draft: DefaultsDraft,
): ProjectDefaults {
  return {
    language: draft.language,
    model: "small",
    output_formats: [...draft.outputFormats],
    txt_timestamps: draft.txtTimestamps,
  };
}
