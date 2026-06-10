import type { AllLabels, AllLabelsWithSufix } from "@/types/aymurai";

export interface BaseAnnotation {
  start: number;
  end: number;
}

interface BaseLabelAnnotation extends BaseAnnotation {
  paragraphId: string;
  tag?: AllLabels | AllLabelsWithSufix;
  canonical_entity_id?: string | null;
  mentionId?: string;
  searchMatchId?: string;
  searchIndex?: number;
  isActive?: boolean;
}

export interface LabelAnnotation extends BaseLabelAnnotation {
  type: "tag";
}

export interface SearchAnnotation extends BaseLabelAnnotation {
  type: "search";
}

export interface TextAnnotation extends BaseAnnotation {
  type: "text";
}

export type Annotation = LabelAnnotation | SearchAnnotation | TextAnnotation;
export type Split = Annotation;

export interface Metadata {
  "data-start": number;
  "data-end": number;
  "data-tag"?: string;
  "data-search-match-id"?: string;
  "data-search-active"?: string;
}
