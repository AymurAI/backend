import { z } from "zod";

export const predictSchema = z.object({
  document: z.string(),
  labels: z.array(
    z.object({
      text: z.string(),
      start_char: z.number(),
      end_char: z.number(),
      attrs: z.object({
        aymurai_alt_start_char: z.number().nullable(),
        aymurai_alt_end_char: z.number().nullable(),
        aymurai_alt_text: z.string().nullable(),
        aymurai_label: z.string(),
        aymurai_label_subclass: z.array(z.string()).nullable(),
      }),
    }),
  ),
});
