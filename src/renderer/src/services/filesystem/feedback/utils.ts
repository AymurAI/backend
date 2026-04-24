import type { AllLabels } from "@/types/aymurai";
import type { PredictionFeedback } from "@/types/feedback";
import type { DocFile } from "@/types/file";
import { flatValidation } from "@/utils/file";

/**
 * Creates a new Feedback object with a specific name and value
 * @param name Name of the entity's label
 * @param value Feedbakc value for that specific label
 * @returns A new feedback object containing the specified feedback value
 */
function newLabel(
  name: AllLabels,
  value: PredictionFeedback["validationText"],
): PredictionFeedback {
  return {
    paragraphId: "",
    text: null,
    start_char: null,
    end_char: null,
    validationText: value,
    attrs: {
      aymurai_label: name,
      aymurai_label_subclass: null,
      aymurai_alt_text: null,
      aymurai_alt_start_char: null,
      aymurai_alt_end_char: null,
    },
  };
}

/**
 * Creates a `PredictionFeedback` array containing the AI response and the validated content
 * @param predictions Predictions made by the AI
 * @param validationObject Validated information
 * @returns An array of objects with the predictions and the validations
 */
export function joinValidation({
  predictions,
  validationObject,
}: DocFile): PredictionFeedback[] {
  const result: PredictionFeedback[] = [];

  const flat = flatValidation(validationObject);

  flat.forEach((val) => {
    // First, add the predictions to the result array
    // We are sure predictions is !undefined becasue this step is post file processing
    predictions!.forEach((pred) => {
      result.push({
        ...pred,
        validationText: val[pred.attrs.aymurai_label] ?? null,
      });
    });

    // Get the labels from `validationObject` that aren't present on `predictions`
    const filtered = (Object.keys(flat) as AllLabels[]).filter((key) => {
      return !predictions!.find((pred) => pred.attrs.aymurai_label === key);
    });

    filtered.forEach((label) =>
      result.push(newLabel(label, val[label] ?? null)),
    );
  });

  return result;
}
