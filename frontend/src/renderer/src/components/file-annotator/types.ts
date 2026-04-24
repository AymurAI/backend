import type { AllLabels, AllLabelsWithSufix } from "@/types/aymurai";

export interface BaseAnnotation {
  start: number;
  end: number;
}

export interface LabelAnnotation extends BaseAnnotation {
  type: "tag" | "search";
  paragraphId: string;
  tag?: AllLabels | AllLabelsWithSufix;
}
export interface TextAnnotation extends BaseAnnotation {
  type: "text";
}

export type Annotation = LabelAnnotation | TextAnnotation;
export type Split = Annotation;

export interface Metadata {
  "data-start": number;
  "data-end": number;
  "data-tag"?: string;
}
