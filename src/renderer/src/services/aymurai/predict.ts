import { CanceledError } from "axios";

import { predictSchema } from "@/schema/predict";
import type { PredictLabel, Workflows } from "@/types/aymurai";
import type { Paragraph } from "@/types/file";
import api from "../api";

/**
 * Realiza una petición a la AI para poder obtener predicciones en base a un párrafo
 * @param paragraph Párrafo a analizar
 * @param controller `AbortController` encargado de mandar una señal de cancelación a `axios`
 * @param serverUrl String with the URL of the AyMurAI api
 * @returns Una lista de `PredictLabel` con las predicciones
 */
export default async function predict(
  paragraph: Paragraph,
  controller: AbortController,
  route: Workflows = "datapublic",
): Promise<PredictLabel[]> {
  try {
    const path =
      route === "datapublic"
        ? `/datapublic/predict/${paragraph.document_id}`
        : "/anonymizer/predict";

    const response = await api.post(
      path,
      {
        text: paragraph.value,
      },
      {
        signal: controller.signal,
      },
    );
    const parsed = predictSchema.parse(response.data);

    const data = parsed.labels.map((l) => {
      const altStart = l.attrs.aymurai_alt_start_char;
      const altEnd = l.attrs.aymurai_alt_end_char;
      // Only apply alt offsets when both are present and form a valid range.
      // The NER pipeline can emit inverted alt offsets (altStart > altEnd) for
      // non-alphanumeric entities like "∙" — using them would produce an
      // invalid_range error at export time.
      const useAlt = altStart != null && altEnd != null && altStart < altEnd;
      return {
        ...l,
        mentionId: crypto.randomUUID(),
        start_char: useAlt ? altStart : l.start_char,
        end_char: useAlt ? altEnd : l.end_char,
        text: useAlt && l.attrs.aymurai_alt_text ? l.attrs.aymurai_alt_text : l.text,
        paragraphId: paragraph.id,
      } as PredictLabel;
    });

    return data;
  } catch (e) {
    // If the POST is cancelled by the controller, just return an empty prediction
    if (e instanceof CanceledError) {
      return [];
    }

    // Otherwise, throw again the same error
    console.error(e);
    throw e;
  }
}
