import type { PredictLabel } from "@/types/aymurai";
import type { DocFile, Paragraph } from "@/types/file";
import { stripEntityLabelSuffix } from "./entity-similarity";

type ExportValidationIssueCode =
  | "missing_offsets"
  | "invalid_range"
  | "paragraph_not_found"
  | "range_out_of_bounds"
  | "text_mismatch"
  | "missing_canonical_entity_id"
  | "duplicate_range"
  | "overlapping_range"
  | "mixed_group_labels";

export interface ExportEntityDebugInfo {
  entityId: string;
  canonicalEntityId: string | null;
  label: string;
  start: number | null;
  end: number | null;
  text: string;
  source: "manual" | "automatic";
  groupId: string | null;
  isDeleted: boolean;
  isManual: boolean;
  paragraphId: string;
}

export interface ExportValidationIssue {
  code: ExportValidationIssueCode;
  message: string;
  entity: ExportEntityDebugInfo;
  relatedEntity?: ExportEntityDebugInfo;
}

export class AnonymizerExportValidationError extends Error {
  issues: ExportValidationIssue[];

  constructor(issues: ExportValidationIssue[]) {
    super(
      "No se puede exportar: hay entidades con offsets inválidos, duplicados o solapados.",
    );
    this.name = "AnonymizerExportValidationError";
    this.issues = issues;
  }
}

function buildDebugInfo(prediction: PredictLabel): ExportEntityDebugInfo {
  const isManual = !prediction.attrs.aymurai_disambiguation;
  return {
    entityId: prediction.mentionId,
    canonicalEntityId: prediction.attrs.canonical_entity_id ?? null,
    label: String(prediction.attrs.aymurai_label),
    start: Number.isFinite(prediction.start_char)
      ? prediction.start_char
      : null,
    end: Number.isFinite(prediction.end_char) ? prediction.end_char : null,
    text: prediction.text,
    source: isManual ? "manual" : "automatic",
    groupId: prediction.attrs.canonical_entity_id ?? null,
    isDeleted: false,
    isManual,
    paragraphId: prediction.paragraphId,
  };
}

function issue(
  code: ExportValidationIssueCode,
  message: string,
  entity: PredictLabel,
  relatedEntity?: PredictLabel,
): ExportValidationIssue {
  return {
    code,
    message,
    entity: buildDebugInfo(entity),
    ...(relatedEntity && { relatedEntity: buildDebugInfo(relatedEntity) }),
  };
}

function paragraphById(file: DocFile): Map<string, Paragraph> {
  return new Map(
    (file.paragraphs ?? []).map((paragraph) => [paragraph.id, paragraph]),
  );
}

function validateGroupLabels(labels: PredictLabel[]): ExportValidationIssue[] {
  const issues: ExportValidationIssue[] = [];
  const groupLabels = new Map<string, { label: string; first: PredictLabel }>();

  for (const label of labels) {
    const canonicalId = label.attrs.canonical_entity_id;
    if (!canonicalId) continue;

    const baseLabel = stripEntityLabelSuffix(String(label.attrs.aymurai_label));
    const existing = groupLabels.get(canonicalId);
    if (!existing) {
      groupLabels.set(canonicalId, { label: baseLabel, first: label });
      continue;
    }

    if (existing.label !== baseLabel) {
      issues.push(
        issue(
          "mixed_group_labels",
          `El grupo ${canonicalId} contiene labels incompatibles: ${existing.label} y ${baseLabel}.`,
          label,
          existing.first,
        ),
      );
    }
  }

  return issues;
}

function validateParagraphRanges(
  paragraph: Paragraph,
  labels: PredictLabel[],
): ExportValidationIssue[] {
  const issues: ExportValidationIssue[] = [];
  const sorted = [...labels].sort((a, b) => {
    if (a.start_char !== b.start_char) return a.start_char - b.start_char;
    return b.end_char - a.end_char;
  });
  const rangeOwners = new Map<string, PredictLabel>();
  let previous: PredictLabel | null = null;

  for (const label of sorted) {
    const key = `${label.start_char}:${label.end_char}`;
    const duplicate = rangeOwners.get(key);
    if (duplicate) {
      issues.push(
        issue(
          "duplicate_range",
          `Hay más de una entidad activa en el rango ${key}.`,
          label,
          duplicate,
        ),
      );
    } else {
      rangeOwners.set(key, label);
    }

    const textAtRange = paragraph.value.slice(label.start_char, label.end_char);
    if (textAtRange !== label.text) {
      issues.push(
        issue(
          "text_mismatch",
          "El texto de la entidad no coincide con el texto original en sus offsets.",
          label,
        ),
      );
    }

    if (previous && label.start_char < previous.end_char) {
      issues.push(
        issue(
          "overlapping_range",
          "Hay entidades activas con rangos solapados.",
          label,
          previous,
        ),
      );
    }

    if (!previous || label.end_char > previous.end_char) previous = label;
  }

  return issues;
}

export function validateAnonymizerExportState(
  file: DocFile,
  labels: PredictLabel[],
): ExportValidationIssue[] {
  const issues: ExportValidationIssue[] = [];
  const paragraphs = paragraphById(file);
  const labelsByParagraph = new Map<string, PredictLabel[]>();

  for (const label of labels) {
    const paragraph = paragraphs.get(label.paragraphId);

    if (
      !Number.isFinite(label.start_char) ||
      !Number.isFinite(label.end_char)
    ) {
      issues.push(
        issue("missing_offsets", "La entidad no tiene offsets válidos.", label),
      );
      continue;
    }

    if (label.start_char >= label.end_char) {
      issues.push(
        issue(
          "invalid_range",
          "La entidad tiene start mayor o igual a end.",
          label,
        ),
      );
      continue;
    }

    if (!paragraph) {
      issues.push(
        issue(
          "paragraph_not_found",
          "La entidad apunta a un párrafo inexistente.",
          label,
        ),
      );
      continue;
    }

    if (label.start_char < 0 || label.end_char > paragraph.value.length) {
      issues.push(
        issue(
          "range_out_of_bounds",
          "La entidad tiene offsets fuera del texto original.",
          label,
        ),
      );
      continue;
    }

    if (!label.attrs.canonical_entity_id) {
      issues.push(
        issue(
          "missing_canonical_entity_id",
          "La entidad activa no tiene canonical_entity_id.",
          label,
        ),
      );
    }

    const paragraphLabels = labelsByParagraph.get(label.paragraphId) ?? [];
    paragraphLabels.push(label);
    labelsByParagraph.set(label.paragraphId, paragraphLabels);
  }

  for (const [paragraphId, paragraphLabels] of labelsByParagraph) {
    const paragraph = paragraphs.get(paragraphId);
    if (!paragraph) continue;
    issues.push(...validateParagraphRanges(paragraph, paragraphLabels));
  }

  issues.push(...validateGroupLabels(labels));

  return issues;
}

export function assertValidAnonymizerExportState(
  file: DocFile,
  labels: PredictLabel[],
) {
  const issues = validateAnonymizerExportState(file, labels);
  if (issues.length === 0) return;

  console.error("Invalid anonymizer export annotations", {
    fileName: file.data.name,
    issues,
  });
  throw new AnonymizerExportValidationError(issues);
}
