import {
  ActionTypes,
  type AddFilesAction,
  type AddParagraphsAction,
  type AddPredictionsAction,
  type AppendPrediction,
  type AppendValidationAction,
  type FilterUnprocessedAction,
  type FilterUnselectedAction,
  type RemoveAllFilesAction,
  type RemoveAllPredictionsAction,
  type RemoveFileAction,
  type RemovePrediction,
  type RemovePredictionsAction,
  type RemovePredictionsByText,
  type ReplaceFileAction,
  type ToggleSelectedAction,
  type UpdatePredictionLabel,
  type UpdatePredictionsByText,
  type ValidateAction,
} from "./actions";
import {
  addFiles,
  comparePrediction,
  replaceFile,
  updateFromState,
} from "./utils";

import type { AllLabels, AllLabelsWithSufix } from "@/types/aymurai";
import type { DocFile } from "@/types/file";

type State = DocFile[];

export type Action =
  | AddFilesAction
  | AddPredictionsAction
  | ToggleSelectedAction
  | RemoveAllPredictionsAction
  | RemoveAllFilesAction
  | RemoveFileAction
  | RemovePredictionsAction
  | ReplaceFileAction
  | FilterUnselectedAction
  | ValidateAction
  | AppendValidationAction
  | FilterUnprocessedAction
  | AddParagraphsAction
  | AppendPrediction
  | RemovePrediction
  | RemovePredictionsByText
  | UpdatePredictionLabel
  | UpdatePredictionsByText;

/**
 * Reducer function for `DocFile[]` state
 * @param state Current state
 * @param action Action to perform
 * @returns A new state
 */
export default function reducer(state: State, action: Action): State {
  const { type, payload } = action;

  // Update/replace/delete utility function
  const update = updateFromState(state);

  switch (type) {
    // ----------------
    // ADD
    // ----------------
    case ActionTypes.ADD: {
      const { newFiles } = payload;

      // Performs some checkings on the file
      return addFiles(newFiles, state);
    }
    // ----------------
    // ADD PREDICTIONS
    // ----------------
    case ActionTypes.ADD_PREDICTIONS: {
      const { fileName, predictions } = payload;

      return update(fileName, (current) => ({
        ...current,
        // Appends the predictions to the already created array
        predictions: [...(current.predictions ?? []), ...predictions],
      }));
    }
    // ----------------
    // TOGGLE SELECTED
    // ----------------
    case ActionTypes.TOGGLE_SELECTED: {
      const { fileName } = payload;

      return update(fileName, (current) => ({
        ...current,
        selected: !current.selected,
      }));
    }
    // ----------------
    // REMOVE ALL PREDICTIONS
    // ----------------
    case ActionTypes.REMOVE_ALL_PREDICTIONS: {
      return state.map((file) => ({ ...file, predictions: undefined }));
    }
    // ----------------
    // REMOVE PREDICTIONS
    // ----------------
    case ActionTypes.REMOVE_PREDICTIONS: {
      const { fileName } = payload;

      return update(fileName, (current) => ({
        ...current,
        predictions: undefined,
      }));
    }
    // ----------------
    // REMOVE ALL FILES
    // ----------------
    case ActionTypes.REMOVE_ALL_FILES: {
      return [];
    }
    case ActionTypes.REMOVE_FILE: {
      const { fileName } = payload;

      return state.filter((file) => file.data.name !== fileName);
    }
    // ----------------
    // REPLACE FILE
    // ----------------
    case ActionTypes.REPLACE_FILE: {
      const { fileName, file } = payload;
      return replaceFile(fileName, file, state);
    }
    // ----------------
    // FILTER UNSELECTED
    // ----------------
    case ActionTypes.FILTER_UNSELECTED: {
      return state.filter((file) => file.selected);
    }

    // ----------------
    // FILTER UNSELECTED
    // ----------------
    case ActionTypes.FILTER_UNPROCESSED: {
      return state.filter((file) => file.predictions);
    }
    // ----------------
    // VALIDATE
    // ----------------
    case ActionTypes.VALIDATE: {
      const { fileName } = payload;
      return update(fileName, (cur) => ({ ...cur, validated: true }));
    }
    // ----------------
    // APPEND VALIDATION
    // ----------------
    case ActionTypes.APPEND_VALIDATION: {
      const { fileName, validation } = payload;

      return update(fileName, (cur) => ({
        ...cur,
        // Append to the already created object
        validationObject: { ...cur.validationObject, ...validation },
      }));
    }

    // ----------------
    // ADD PARAGRAPHS
    // ----------------
    case ActionTypes.ADD_PARAGRAPHS: {
      const { fileName, paragraphs } = payload;

      return update(fileName, (cur) => ({
        ...cur,
        paragraphs: paragraphs,
      }));
    }

    // ----------------
    // APPEND PREDICTION
    // ----------------
    case ActionTypes.APPEND_PREDICTION: {
      const { fileName, prediction } = payload;

      return update(fileName, (cur) => ({
        ...cur,
        predictions: [...(cur.predictions ?? []), prediction],
      }));
    }

    // ----------------
    // REMOVE PREDICTION
    // ----------------
    case ActionTypes.REMOVE_PREDICTION: {
      const { fileName, prediction } = payload;

      return update(fileName, (cur) => ({
        ...cur,
        predictions: cur.predictions?.filter(
          (p) => !comparePrediction(prediction, p),
        ),
      }));
    }

    // ----------------
    // REMOVE PREDICTIONS BY TEXT
    // ----------------
    case ActionTypes.REMOVE_PREDICTIONS_BY_TEXT: {
      const { fileName, text } = payload;

      return update(fileName, (cur) => ({
        ...cur,
        predictions: cur.predictions?.filter(
          (p) => p.text.toLowerCase() !== text.toLowerCase(),
        ),
      }));
    }

    // ----------------
    // UPDATE PREDICTION LABEL
    // ----------------
    case ActionTypes.UPDATE_PREDICTION_LABEL: {
      const { fileName, prediction, newLabel } = action.payload;
      return state.map((file) => {
        if (file.data.name !== fileName) return file;

        return {
          ...file,
          predictions: file.predictions?.map((p) => {
            if (
              p.text === prediction.text &&
              p.start_char === prediction.start_char &&
              p.end_char === prediction.end_char
            ) {
              return {
                ...p,
                attrs: {
                  ...p.attrs,
                  aymurai_label: newLabel as AllLabels | AllLabelsWithSufix,
                },
              };
            }
            return p;
          }),
        };
      });
    }

    // ----------------
    // UPDATE PREDICTIONS BY TEXT
    // ----------------
    case ActionTypes.UPDATE_PREDICTIONS_BY_TEXT: {
      const { fileName, text, newLabel } = action.payload;
      return state.map((file) => {
        if (file.data.name !== fileName) return file;

        return {
          ...file,
          predictions: file.predictions?.map((p) => {
            if (p.text.toLowerCase() === text.toLowerCase()) {
              return {
                ...p,
                attrs: {
                  ...p.attrs,
                  aymurai_label: newLabel,
                },
              };
            }
            return p;
          }),
        };
      });
    }

    // ----------------
    // ADD PARAGRAPHS
    // ----------------
    default:
      return state;
  }
}
