import { CanceledError } from "axios";
import { z } from "zod";

import { predictLabelSchema } from "@/schema/predict";
import type { PredictLabel } from "@/types/aymurai";
import type { Paragraph } from "@/types/file";
import api from "../api";

const validationResponseSchema = z.array(predictLabelSchema);

/**
 * Normalizes a backend DocLabel (from `/anonymizer/validation`) to a frontend
 * `PredictLabel`, applying alt-offset resolution and assigning a new `mentionId`.
 * Exported for testability.
 */
export function normalizeValidationLabel(
  l: z.infer<typeof predictLabelSchema>,
  paragraphId: string,
): PredictLabel {
  return {
    mentionId: crypto.randomUUID(),
    text: l.attrs.aymurai_alt_text ?? l.text,
    start_char: l.attrs.aymurai_alt_start_char ?? l.start_char,
    end_char: l.attrs.aymurai_alt_end_char ?? l.end_char,
    attrs: {
      aymurai_label: l.attrs
        .aymurai_label as PredictLabel["attrs"]["aymurai_label"],
      aymurai_label_subclass: l.attrs.aymurai_label_subclass ?? null,
      aymurai_alt_text: l.attrs.aymurai_alt_text ?? null,
      aymurai_alt_start_char: l.attrs.aymurai_alt_start_char ?? null,
      aymurai_alt_end_char: l.attrs.aymurai_alt_end_char ?? null,
      canonical_entity_id: l.attrs.canonical_entity_id ?? null,
      aymurai_anonymize: l.attrs.aymurai_anonymize ?? null,
      aymurai_label_instance: l.attrs.aymurai_label_instance ?? null,
      aymurai_disambiguation: l.attrs.aymurai_disambiguation ?? null,
    },
    paragraphId,
  };
}

/**
 * Retrieves manually-validated annotations for a paragraph from the backend DB
 * (`anonymization_paragraph.validation`).
 *
 * Return values:
 * - `null`  → no stored validation exists; caller should fall back to model predict
 * - `[]`    → paragraph was explicitly validated with no entities; respect the empty state
 * - `[...]` → stored manual annotations; use them as the initial UI state
 *
 * On any non-abort error (network failure, 404, etc.) the function returns `null`
 * so the workflow degrades gracefully to model predictions.
 *
 * @param paragraph  Paragraph to look up.
 * @param controller AbortController tied to the parent React Query signal.
 */
export default async function getStoredValidation(
  paragraph: Paragraph,
  controller: AbortController,
): Promise<PredictLabel[] | null> {
  try {
    const response = await api.post(
      "/anonymizer/validation",
      { text: paragraph.value },
      { signal: controller.signal },
    );

    // Backend returns a plain labels array.
    // - 404 / error → caught below → null (fall back to predict)
    // - []           → paragraph validated with no entities
    // - [...]        → restore stored annotations
    const labels = validationResponseSchema.parse(response.data);
    return labels.map((l) => normalizeValidationLabel(l, paragraph.id));
  } catch (e) {
    // Propagate request cancellations so React Query can clean up properly
    if (e instanceof CanceledError) throw e;

    // Any other error (endpoint unavailable, unexpected schema, etc.): fail open
    // and let the caller fall back to model predict.
    console.warn(
      "[validation] Could not load stored validation, falling back to predict:",
      e,
    );
    return null;
  }
}
