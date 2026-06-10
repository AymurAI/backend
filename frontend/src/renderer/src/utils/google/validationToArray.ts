import type { AllLabels, AllLabelsWithSufix } from "@/types/aymurai";
import type { DocFile } from "@/types/file";
import { excelStructure, flatValidation } from "@/utils/file";
import {
  treatFRASES_AGRESION,
  treatORAL_ESCRITA,
  treatVIOLENCIA_FISICA,
  treateV_X,
} from "./utils";

/**
 * Converts the validation object into an ordered array
 * @param object Validation object containing all the validations made in the `/validation` page
 * @returns An ordered array with the values from the `validationObject`
 */
export default function validationToArray(object: DocFile["validationObject"]) {
  const flat = flatValidation(object);

  return flat.map((obj) => {
    return excelStructure.map((key) => {
      // Special cases

      switch (key) {
        case "VIOLENCIA_DE_GENERO":
          return treatVIOLENCIA_FISICA(obj);
        case "V_AMB":
        case "V_ECON":
        case "V_FISICA":
        case "V_POLIT":
        case "V_PSIC":
        case "V_SEX":
        case "V_SIMB":
        case "V_SOC":
          return treateV_X(obj, key);
        case "FRASES_AGRESION":
          return treatFRASES_AGRESION(obj);
        case "ORAL_ESCRITA":
          return treatORAL_ESCRITA(obj);
        default:
          // Generic case, just return the value
          // Treat the case as a defined LabelType | LabelDecisiones. In case its not, just return the undefined
          // as this case won't create a value on the dataset as expected
          return obj[key as AllLabels | AllLabelsWithSufix];
      }
    });
  });
}
