import type { DocFile } from "@/types/file";

/**
 * Finds the next available index and returns it
 * @param cur Current `selected` index
 * @param state State array of files
 * @returns The next available index
 */
export function movePrevious(cur: number, state: DocFile[]) {
  let index = cur;

  do {
    index--;

    if (index < 0) return undefined;
  } while (state[index].validated);

  return index;
}

/**
 * Finds the previous available index and returns it
 * @param cur Current `selected` index
 * @param state State array of files
 * @returns The previous available index
 */
export function moveNext(cur: number, state: DocFile[]) {
  let index = cur;

  do {
    index++;

    if (index === state.length) return undefined;
  } while (state[index].validated);

  return index;
}
