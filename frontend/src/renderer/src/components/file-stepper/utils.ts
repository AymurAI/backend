import type { DocFile } from "@/types/file";

/**
 * Check if the stepper can move to the left
 * @param cur Current `selected` index
 * @param state State array of files
 * @returns `true` if the stepper can move to the left (or to a previous file), `false` otherwise
 */
export function canMoveLeft(cur: number, state: DocFile[]) {
  const sliced = state.slice(0, cur);

  // Check if we find any file that is not validated yet
  return !!sliced.find((file) => !file.validated);
}

/**
 * Check if the stepper can move to the right
 * @param cur Current `selected` index
 * @param state State array of files
 * @returns `true` if the stepper can move to the right (or to a next file), `false` otherwise
 */
export function canMoveRight(cur: number, state: DocFile[]) {
  const sliced = state.slice(cur + 1, state.length);

  // Check if we find any file that is not validated yet
  return !!sliced.find((file) => !file.validated);
}
