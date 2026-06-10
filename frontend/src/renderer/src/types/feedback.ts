import type { PredictLabel } from "./aymurai";
import type { Nullable } from "./utils";

/**
 * Type for the object stored into the exported JSON file
 */
export type PredictionFeedback = Nullable<
  PredictLabel & {
    validationText: string | boolean;
  }
>;
