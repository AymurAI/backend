import type { PredictStatus } from "@/hooks/usePredict";
import type { DocFile } from "@/types/file";

export type ProcessState = { name: string; status: PredictStatus };

/**
 * Creates the initial state for the `/process` page
 * @param files `DocFile[]` state
 * @returns An `ProcessState[]` array containing the name of each file and its processing state
 */
export function initProcessState(files: DocFile[]): ProcessState[] {
  return files.map(({ data }) => ({ name: data.name, status: "processing" }));
}
