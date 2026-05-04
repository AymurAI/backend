import { type AnonymizerLabels, anonymizerLabels } from "@/types/aymurai";

const entries = anonymizerLabels.map((label) => [label.id, true] as const);

export const EXCLUDED_TAGS = Object.fromEntries(entries) as Record<
  AnonymizerLabels,
  boolean
>;
