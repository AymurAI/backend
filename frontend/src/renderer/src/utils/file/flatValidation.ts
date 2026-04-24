import type { FlatFormData } from "@/hooks/useForm";
import type { DocFile } from "@/types/file";
import filterEmptyDecisions from "./filterEmptyDecisions";

/**
 * This method flattens the `DECISIONES` array inside the `validationObject` so we have as result an array of `FormData`
 * @example
 * // BEFORE:
 * // validation = {
 * // ...,
 * // DECISIONES: [{...}],
 * // }
 *
 * flatValidation(object);
 * // AFTER:
 * // validation = [
 * // {...},
 * // ]
 *
 * @param validation Object to flatten
 * @returns An array of flat formatted `FormData`
 */
export default function flatValidation(
  validation: DocFile["validationObject"],
): FlatFormData[] {
  // Set a default value for the `DECISIONES` array
  const decisiones = filterEmptyDecisions(validation.DECISIONES);

  // Make a copy of the whole object, removing the `DECISIONES` key
  const copy = { ...validation };
  delete copy.DECISIONES;

  if (decisiones.length > 0) {
    // For each decision made, return the whole validation object plus the current decision
    return decisiones.map((dec) => ({
      ...dec,
      ...copy,
    }));
  }

  // We have no decision, just return the copy (without the `DECISIONES` array)
  return [copy];
}
