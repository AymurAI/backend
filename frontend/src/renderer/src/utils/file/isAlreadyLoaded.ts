import type { DocFile } from "@/types/file";

/**
 * Looks in the file state if an specific file is already loaded
 * @param fileName Name of the file to analyze
 * @param state State to check
 * @returns `true` if the file is already in the state, `false` otherwise
 */
export default function isAlreadyLoaded(fileName: string, state: DocFile[]) {
  return !!state.find((file) => file.data.name === fileName);
}
