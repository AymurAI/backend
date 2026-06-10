import { z } from "zod";

const disambiguateLabelSchema = z.object({
  text: z.string(),
  start_char: z.number(),
  end_char: z.number(),
  attrs: z.object({
    aymurai_label: z.string(),
    aymurai_label_subclass: z.array(z.string()).nullable(),
    aymurai_alt_text: z.string().nullable(),
    aymurai_alt_start_char: z.number().nullable(),
    aymurai_alt_end_char: z.number().nullable(),
    aymurai_method: z.string().nullish(),
    aymurai_score: z.number().nullish(),
    aymurai_label_instance: z.number().nullish(),
    aymurai_disambiguation: z.string().nullish(),
    aymurai_anonymize: z.boolean().nullish(),
    canonical_entity_id: z.string().nullish(),
  }),
});

export const disambiguateSchema = z.object({
  data: z.array(
    z.object({
      document: z.string(),
      labels: z.array(disambiguateLabelSchema),
    }),
  ),
  // label_policies is intentionally omitted
});
