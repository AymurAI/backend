import type { FormData } from "@/hooks/useForm";
import type {
  AllLabels,
  AllLabelsWithSufix,
  PredictLabel,
} from "@/types/aymurai";
import type { Paragraph } from "@/types/file";

/**
 * List of action types.
 */
export enum ActionTypes {
  ADD = "ADD",
  ADD_PREDICTIONS = "ADD_PREDICTIONS",
  ADD_PARAGRAPHS = "ADD_PARAGRAPHS",
  FILTER_UNSELECTED = "FILTER_UNSELECTED",
  FILTER_UNPROCESSED = "FILTER_UNPROCESSED",
  TOGGLE_SELECTED = "TOGGLE_SELECTED",
  REMOVE_ALL_PREDICTIONS = "REMOVE_ALL_PREDICTIONS",
  REMOVE_PREDICTIONS = "REMOVE_PREDICTIONS",
  REMOVE_ALL_FILES = "REMOVE_ALL_FILES",
  REMOVE_FILE = "REMOVE_FILE",
  REPLACE_FILE = "REPLACE_FILE",
  VALIDATE = "VALIDATE",
  APPEND_VALIDATION = "APPEND_VALIDATION",
  APPEND_PREDICTION = "APPEND_PREDICTION",
  REMOVE_PREDICTION = "REMOVE_PREDICTION",
  REMOVE_PREDICTIONS_BY_TEXT = "REMOVE_PREDICTIONS_BY_TEXT",
  UPDATE_PREDICTION_LABEL = "UPDATE_PREDICTION_LABEL",
  UPDATE_PREDICTIONS_BY_TEXT = "UPDATE_PREDICTIONS_BY_TEXT",
}

/**
 * Generic action
 */
type Action<Type, Payload = {}> = {
  type: Type;
  payload: Payload;
};

export type ToggleSelectedAction = Action<
  ActionTypes.TOGGLE_SELECTED,
  { fileName: string }
>;
/**
 * Toggles the `selected` property of the given file
 * @param fileName Name of the file to be toggled
 */
export function toggleSelected(fileName: string): ToggleSelectedAction {
  return {
    type: ActionTypes.TOGGLE_SELECTED,
    payload: { fileName },
  };
}

export type RemoveAllPredictionsAction =
  Action<ActionTypes.REMOVE_ALL_PREDICTIONS>;
/**
 * Removes all the predictions for all the files in the state
 */
export function removeAllPredictions(): RemoveAllPredictionsAction {
  return {
    type: ActionTypes.REMOVE_ALL_PREDICTIONS,
    payload: {},
  };
}

export type FilterUnselectedAction = Action<ActionTypes.FILTER_UNSELECTED>;
/**
 * Removes files from the state whose `selected` property is set on `false`
 */
export function filterUnselected(): FilterUnselectedAction {
  return {
    type: ActionTypes.FILTER_UNSELECTED,
    payload: {},
  };
}

export type AddFilesAction = Action<ActionTypes.ADD, { newFiles: File[] }>;
/**
 * Adds a new set of `File[]` to the end of the state
 * @param newFiles `File[]` to be added to the state
 */
export function addFiles(newFiles: File[]): AddFilesAction {
  return {
    type: ActionTypes.ADD,
    payload: { newFiles },
  };
}

export type RemoveAllFilesAction = Action<ActionTypes.REMOVE_ALL_FILES>;
/**
 * Removes all the files from the state
 */
export function removeAllFiles(): RemoveAllFilesAction {
  return {
    type: ActionTypes.REMOVE_ALL_FILES,
    payload: {},
  };
}

export type RemoveFileAction = Action<
  ActionTypes.REMOVE_FILE,
  { fileName: string }
>;
/**
 * Removes a single file from the array
 */
export function removeFile(fileName: string): RemoveFileAction {
  return {
    type: ActionTypes.REMOVE_FILE,
    payload: { fileName },
  };
}

export type AddPredictionsAction = Action<
  ActionTypes.ADD_PREDICTIONS,
  { fileName: string; predictions: PredictLabel[] }
>;
/**
 * Adds predictions to a specific file
 * @param fileName File to be modified
 * @param predictions `PredictLabel[]` received from the `/predict` API request
 */
export function addPredictions(
  fileName: string,
  predictions: PredictLabel[],
): AddPredictionsAction {
  return {
    type: ActionTypes.ADD_PREDICTIONS,
    payload: { fileName, predictions },
  };
}

export type RemovePredictionsAction = Action<
  ActionTypes.REMOVE_PREDICTIONS,
  { fileName: string }
>;
/**
 * Removes all the predictions from a given file
 */
export function removePredictions(fileName: string): RemovePredictionsAction {
  return {
    type: ActionTypes.REMOVE_PREDICTIONS,
    payload: { fileName },
  };
}

export type ReplaceFileAction = Action<
  ActionTypes.REPLACE_FILE,
  { fileName: string; file: File }
>;
/**
 * Replaces a file data with the given `fileName`
 * @param fileName File to be replaced on the state
 * @param file File data to be inserted in place of the given `fileName`
 */
export function replaceFile(fileName: string, file: File): ReplaceFileAction {
  return {
    type: ActionTypes.REPLACE_FILE,
    payload: { fileName, file },
  };
}

export type ValidateAction = Action<ActionTypes.VALIDATE, { fileName: string }>;
/**
 * Sets the validated status to the given file to `true`
 * @param fileName Name of the file to be toggled
 */
export function validate(fileName: string): ValidateAction {
  return {
    type: ActionTypes.VALIDATE,
    payload: { fileName },
  };
}

export type AppendValidationAction = Action<
  ActionTypes.APPEND_VALIDATION,
  { fileName: string; validation: FormData }
>;
/**
 * Builds the `validation` progressively
 * @param fileName Name of the file to be modified
 * @param validation Validation object to be appended
 */
export function appendValidation(
  fileName: string,
  validation: FormData,
): AppendValidationAction {
  return {
    type: ActionTypes.APPEND_VALIDATION,
    payload: { fileName, validation },
  };
}

export type FilterUnprocessedAction = Action<ActionTypes.FILTER_UNPROCESSED>;
/**
 * Removes files from the state whose `predictions` property is set on `undefined`
 */
export function filterUnprocessed(): FilterUnprocessedAction {
  return {
    type: ActionTypes.FILTER_UNPROCESSED,
    payload: {},
  };
}

export type AddParagraphsAction = Action<
  ActionTypes.ADD_PARAGRAPHS,
  {
    paragraphs: Paragraph[];
    fileName: string;
  }
>;
/**
 * Adds paragraphs to the state from the endpoint `/document-extract`
 * @param paragraphs List of paragraphs to be added
 * @param fileName Name of the file to be modified
 */
export function addParagraphs(
  paragraphs: Paragraph[],
  fileName: string,
): AddParagraphsAction {
  return {
    type: ActionTypes.ADD_PARAGRAPHS,
    payload: { paragraphs, fileName },
  };
}

export type AppendPrediction = Action<
  ActionTypes.APPEND_PREDICTION,
  {
    prediction: PredictLabel;
    fileName: string;
  }
>;
/**
 * Appends a new user made prediction to the file
 * @param prediction User made prediction on the file. Should only be used when anonymizing.
 * @param fileName Name of the file to be modified
 */
export function appendPrediction(
  fileName: string,
  prediction: PredictLabel,
): AppendPrediction {
  return {
    type: ActionTypes.APPEND_PREDICTION,
    payload: { prediction, fileName },
  };
}

export type RemovePrediction = Action<
  ActionTypes.REMOVE_PREDICTION,
  {
    prediction: PredictLabel;
    fileName: string;
  }
>;
/**
 * Removes a user made prediction from the file
 * @param predictionId ID of the prediction to be removed
 * @param fileName Name of the file to be modified
 */
export function removePrediction(
  fileName: string,
  prediction: PredictLabel,
): RemovePrediction {
  return {
    type: ActionTypes.REMOVE_PREDICTION,
    payload: { prediction, fileName },
  };
}

export type RemovePredictionsByText = Action<
  ActionTypes.REMOVE_PREDICTIONS_BY_TEXT,
  {
    text: string;
    fileName: string;
  }
>;
/**
 * Removes all predictions with the same text from the file
 * @param text Text of the predictions to be removed
 * @param fileName Name of the file to be modified
 */
export function removePredictionsByText(
  fileName: string,
  text: string,
): RemovePredictionsByText {
  return {
    type: ActionTypes.REMOVE_PREDICTIONS_BY_TEXT,
    payload: { text, fileName },
  };
}

export type UpdatePredictionLabel = Action<
  ActionTypes.UPDATE_PREDICTION_LABEL,
  {
    fileName: string;
    prediction: PredictLabel;
    newLabel: string;
  }
>;

/**
 * Updates the label of a prediction in a file
 * @param fileName Name of the file containing the prediction
 * @param prediction The prediction to update
 * @param newLabel The new label to set
 */
export function updatePredictionLabel(
  fileName: string,
  prediction: PredictLabel,
  newLabel: string,
): UpdatePredictionLabel {
  return {
    type: ActionTypes.UPDATE_PREDICTION_LABEL,
    payload: { fileName, prediction, newLabel },
  };
}

export type UpdatePredictionsByText = Action<
  ActionTypes.UPDATE_PREDICTIONS_BY_TEXT,
  {
    text: string;
    fileName: string;
    newLabel: AllLabels | AllLabelsWithSufix;
  }
>;

/**
 * Updates all predictions with the same text to a new label
 * @param fileName Name of the file containing the predictions
 * @param text Text of the predictions to update
 * @param newLabel The new label to set
 */
export function updatePredictionsByText(
  fileName: string,
  text: string,
  newLabel: AllLabels | AllLabelsWithSufix,
): UpdatePredictionsByText {
  return {
    type: ActionTypes.UPDATE_PREDICTIONS_BY_TEXT,
    payload: { fileName, text, newLabel },
  };
}
