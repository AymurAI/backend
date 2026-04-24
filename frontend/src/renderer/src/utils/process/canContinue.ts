import type { ProcessState } from "./initProcessState";

export function canContinue(state: ProcessState[]) {
  const atLeastOneCompleted = state.some(
    ({ status }) => status === "completed",
  );
  const hasFinishedProcessing = !state.some(
    ({ status }) => status === "processing",
  );

  return hasFinishedProcessing && atLeastOneCompleted;
}
