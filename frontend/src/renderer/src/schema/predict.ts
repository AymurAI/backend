import { z } from "zod";

/**
 * Schema for a single label as returned by `/anonymizer/predict` or
 * `/anonymizer/validation`. Tolerant to nullish extended fields so it also
 * handles already-disambiguated validation data stored in the DB.
 */
export const predictLabelSchema = z.object({
  text: z.string(),
  start_char: z.number(),
  end_char: z.number(),
  attrs: z.object({
    aymurai_alt_start_char: z.number().nullish(),
    aymurai_alt_end_char: z.number().nullish(),
    aymurai_alt_text: z.string().nullish(),
    aymurai_label: z.string(),
    aymurai_label_subclass: z.array(z.string()).nullish(),
    aymurai_anonymize: z.boolean().nullish(),
    canonical_entity_id: z.string().nullish(),
    aymurai_label_instance: z.number().nullish(),
    aymurai_disambiguation: z.string().nullish(),
  }),
});

export const predictLabelsSchema = z.array(predictLabelSchema);

export const predictSchema = z.object({
  document: z.string(),
  labels: predictLabelsSchema,
});
