import type { DocFile } from "@/types/file";

/**
 * Checks if the file validation process is completed
 * @param state Current files state
 * @returns `true` if the validation process is completed, `false` otherwise
 */
export default function isValidationCompleted(state: DocFile[]) {
  // If we find any file with no predictions, return false
  const uncompleted = state.find((file) => !file.validated);

  return !uncompleted;
}
