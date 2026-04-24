import type { Suggestion } from "@/components/select";
import type {
  AllLabels,
  AllLabelsWithSufix,
  PredictLabel,
} from "@/types/aymurai";

export type Prediction<T> = Partial<Record<AllLabels | AllLabelsWithSufix, T>>;
export type PropertyCallback<T> = (prediction: PredictLabel) => T;

type TextSuggestion<T> = Partial<{ suggestion: T }>;
export type InputSuggestion = TextSuggestion<string>;
export type SelectSuggestion = TextSuggestion<Suggestion> &
  Partial<{ priorityOrder: string[] }>;

export type BooleanSuggestion = Partial<{ checked: boolean }>;
