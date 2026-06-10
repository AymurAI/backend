import type { FlatFormData } from "@/hooks/useForm";
import { LabelDecisiones } from "@/types/aymurai";

/**
 * Treats the special case to return the correct value
 * @param obj Current `FlatFormData` to analyze
 * @returns The value for the current label
 */
export function treatVIOLENCIA_FISICA(obj: FlatFormData) {
  const si = obj[LabelDecisiones.VIOLENCIA_DE_GENERO_SI];
  const no = obj[LabelDecisiones.VIOLENCIA_DE_GENERO_NO];

  if (si) return "si";
  if (no) return "no";
  return undefined;
}

/**
 * Treats the special case to return the correct value
 * @param obj Current `FlatFormData` to analyze
 * @returns The value for the current label
 */
export function treateV_X(
  obj: FlatFormData,
  key: keyof typeof LabelDecisiones,
) {
  if (obj[key] === true) return "si";
  if (obj[key] === false) return "no";
  return undefined;
}

/**
 * Treats the special case to return the correct value
 * @param obj Current `FlatFormData` to analyze
 * @returns The value for the current label
 */
export function treatFRASES_AGRESION(obj: FlatFormData) {
  // Find related fields. This retrieves any field named in the format `FRASES_AGRESIONx`
  const frases = Object.keys(obj).filter((objectKey) =>
    objectKey.includes(LabelDecisiones.FRASES_AGRESION),
  );
  // Join the phrases by commas
  const joined = frases
    .map((frase) => obj[frase as LabelDecisiones.FRASES_AGRESION])
    .join(", ");

  return joined;
}

/**
 * Treats the special case to return the correct value
 * @param obj Current `FlatFormData` to analyze
 * @returns The value for the current label
 */
export function treatORAL_ESCRITA(obj: FlatFormData) {
  const oral = obj[LabelDecisiones.TIPO_DE_AUDIENCIA_ORAL];
  const escrita = obj[LabelDecisiones.TIPO_DE_AUDIENCIA_ESCRITA];

  if (oral) return "oral";
  if (escrita) return "escrita";
  return "no_corresponde";
}
