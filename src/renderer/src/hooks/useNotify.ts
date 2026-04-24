import taskbar from "@/services/taskbar";
import type {
  ProcessState,
  initProcessState,
} from "@/utils/process/initProcessState";
import { useEffect, useState } from "react";

/**
 * Checks if the prediction process is completed
 * @param state Current files state
 * @returns `true` if the prediction process is completed, `false` otherwise
 */
function isPredictionCompleted(state: ProcessState[]) {
  return !state.some(({ status }) => status === "processing");
}

export default function useNotify(
  process: ReturnType<typeof initProcessState>,
) {
  const [isToastVisible, setIsToastVisible] = useState(false);

  const hideToast = () => setIsToastVisible(false);

  // Not ideal to use an useEffect to change an state, but doing it ina proper way
  // requires refactor to change state based on process state
  useEffect(() => {
    if (isPredictionCompleted(process) && !isToastVisible) {
      taskbar.notify();
      setIsToastVisible(true);
    }
  }, [isPredictionCompleted(process)]);

  return { isToastVisible, hideToast };
}
