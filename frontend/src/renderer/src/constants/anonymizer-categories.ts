import { type AnonymizerLabels, anonymizerLabels } from "@/types/aymurai";

export const FALLBACK_ANONYMIZER_CATEGORY = "Otros datos sensibles";

export const ANONYMIZER_CATEGORY_LABEL_IDS = {
  Roles: [
    "PER",
    "DENUNCIANTE",
    "ACUSADO/A",
    "TESTIGO/A",
    "NIÑO/A_ADOSLECENTE",
  ],
  Lugares: ["LOC", "DIRECCION"],
  "Datos personales": ["DNI", "EDAD", "NACIONALIDAD", "ESTUDIOS"],
  "Contacto e identificadores digitales": [
    "TELEFONO",
    "CORREO_ELECTRONICO",
    "USUARIX",
    "IP",
    "LINK",
    "NOMBRE_ARCHIVO",
  ],
  "Datos judiciales": ["NUM_EXPEDIENTE", "NUM_ACTUACION", "CAUSA", "CUIJ"],
  "Datos administrativos y registrales": [
    "CUIT_CUIL",
    "AFILIADO",
    "NUM_MATRICULA",
    "PATENTE_DOMINIO",
  ],
  "Datos bancarios": ["BANCO", "CBU", "NUM_CAJA_AHORRO"],
  Fechas: ["FECHA"],
  [FALLBACK_ANONYMIZER_CATEGORY]: [
    "MARCA_AUTOMOVIL",
    "INSTITUCION",
    "TEXTO_ANONIMIZAR",
  ],
} as const satisfies Record<string, readonly AnonymizerLabels[]>;

export const ANONYMIZER_CATEGORY_NAMES = Object.keys(
  ANONYMIZER_CATEGORY_LABEL_IDS,
);

const labelById = new Map(anonymizerLabels.map((label) => [label.id, label]));

export const ANONYMIZER_LABEL_CATEGORY = Object.fromEntries(
  Object.entries(ANONYMIZER_CATEGORY_LABEL_IDS).flatMap(
    ([category, labelIds]) => labelIds.map((labelId) => [labelId, category]),
  ),
) as Partial<Record<AnonymizerLabels, string>>;

export function getAnonymizerCategoryForLabel(labelId: string): string {
  return (
    ANONYMIZER_LABEL_CATEGORY[labelId as AnonymizerLabels] ??
    FALLBACK_ANONYMIZER_CATEGORY
  );
}

export function getAnonymizerLabelsForCategory(category: string) {
  const configuredIds = ANONYMIZER_CATEGORY_LABEL_IDS[category] ?? [];
  const configuredLabels = configuredIds
    .map((labelId) => labelById.get(labelId))
    .filter((label) => label !== undefined);

  if (category !== FALLBACK_ANONYMIZER_CATEGORY) return configuredLabels;

  const configuredIdSet = new Set(
    Object.values(ANONYMIZER_CATEGORY_LABEL_IDS).flat(),
  );
  const uncategorizedLabels = anonymizerLabels.filter(
    (label) => !configuredIdSet.has(label.id),
  );

  return [...configuredLabels, ...uncategorizedLabels];
}

export function getLabelsPrioritizingCategory(category: string) {
  const categoryLabels = getAnonymizerLabelsForCategory(category);
  const categoryIds = new Set(categoryLabels.map((label) => label.id));
  const rest = anonymizerLabels.filter((label) => !categoryIds.has(label.id));

  return [...categoryLabels, ...rest];
}
