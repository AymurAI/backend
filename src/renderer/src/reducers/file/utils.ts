import type { PredictLabel } from "@/types/aymurai";
import type { DocFile } from "@/types/file";
import { isAllowed, isAlreadyLoaded } from "@/utils/file";

/**
 * Util function used along with `filter()` array function to mantain the types
 * @param file File to check
 * @returns `true` if the file is defined, `false` otherwise
 */
function removeUndefined(file: DocFile | undefined): file is DocFile {
  return !!file;
}

type ModifyFunction = (file: DocFile) => DocFile | undefined;
/**
 * Updates/replaces/deletes a file content in the array. The function was created
 * in a way that is not necessary to pass the `state` on every call.
 * @param state Current `DocFile[]` state
 * @param fileName Identifier of the file to replace
 * @param modify Modify function that alters the content of the affected `DocFile`
 * @returns A new function which accepts as parameters `fileName` and `modify`
 */
export function updateFromState(state: DocFile[]) {
  return (fileName: string, modify: ModifyFunction) => {
    // Modify/update the desired file
    const newState = state.map((file) => {
      if (file.data.name === fileName) return modify(file);
      return file;
    });

    // Remove any `undefined` value inserted into the array
    // This way we can remove a file from the array more easely
    const filtered: DocFile[] = newState.filter(removeUndefined);

    return filtered;
  };
}

/**
 * Adds an array of `File` to the current files state
 * @param files Files to be added
 * @param state Current files state
 * @returns A new state with the files added
 */
export function addFiles(files: File[], state: DocFile[]) {
  // Check for whitelisted extensions and already loaded files
  const filtered = files.filter(
    (file) => isAllowed(file) && !isAlreadyLoaded(file.name, state),
  );

  // Add necessary fields to the object
  const newFiles: DocFile[] = filtered.map((file) => ({
    data: file,
    selected: true,
    validationObject: {},
  }));

  return [...state, ...newFiles];
}

/**
 * Replaces a file by the given name on the files state
 * @param fileName Name of the file to be replaced
 * @param newFile File to be inserted into the state
 * @param state Current files state
 * @returns A new array containing the file replaced
 */
export function replaceFile(fileName: string, newFile: File, state: DocFile[]) {
  if (isAllowed(newFile) && !isAlreadyLoaded(newFile.name, state)) {
    const replaced = state.map((file) =>
      file.data.name === fileName
        ? {
            data: newFile,
            selected: true,
            predictions: undefined,
            validationObject: {},
          }
        : file,
    );
    return replaced;
  }
  return state;
}

/**
 * Compares two predictions to check if they are equal
 * @param a First prediction to compare
 * @param b Second prediction to compare
 * @returns `true` if the predictions are equal, `false` otherwise.
 */
export function comparePrediction(a: PredictLabel, b: PredictLabel) {
  return (
    a.start_char === b.start_char &&
    a.end_char === b.end_char &&
    a.text === b.text &&
    a.attrs.aymurai_label === b.attrs.aymurai_label
  );
}
