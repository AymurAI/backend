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
    const normalized = labels.map((l) => normalizeValidationLabel(l, paragraph.id));

    // Defensive: validate that stored offsets are still consistent with the
    // current paragraph text.
    const active = normalized.filter((l) => l.attrs.aymurai_anonymize !== false);
    const isValid = active.every(
      (l) =>
        Number.isFinite(l.start_char) &&
        Number.isFinite(l.end_char) &&
        l.start_char >= 0 &&
        l.end_char <= paragraph.value.length &&
        l.start_char < l.end_char &&
        paragraph.value.slice(l.start_char, l.end_char) === l.text,
    );
    // If any active label fails basic offset checks, discard the stored data
    // and fall back to fresh model predict + disambiguation.
    if (!isValid) {
      console.warn(
        "[validation] Stored offsets do not match paragraph text — falling back to predict.",
        { paragraphId: paragraph.id },
      );
      return null;
    }

    return normalized;
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
