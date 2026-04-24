import type {
  AllLabels,
  AllLabelsWithSufix,
  LabelDecisiones,
  LabelType,
} from "@/types/aymurai";

/**
 * Any value the form can take
 */
export type FormValue = string | boolean | undefined;
/**
 * Data structure of the whole form
 */
export type FormData = Partial<
  Record<LabelType, FormValue> & {
    DECISIONES: Partial<Record<LabelDecisiones, FormValue>>[];
  }
>;
/**
 * Flat form of the `FormData` structure
 */
export type FlatFormData = Partial<
  Record<AllLabels | AllLabelsWithSufix, FormValue>
>;

/**
 * Type of the reference for any componente
 */
export type ComponentRef = { value: string | boolean | undefined } | null;

export type RegisterFunction = (
  name: AllLabels | AllLabelsWithSufix,
  decision?: number,
) => (ref: ComponentRef) => void;
export type SubmitFunction = (data: FormData) => void;
