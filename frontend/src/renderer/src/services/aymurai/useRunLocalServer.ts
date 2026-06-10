import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import api, { setApiBaseUrl } from "../api";
import { healthcheckSchema } from "./schema";

interface UseRunLocalServerProps {
  onSuccess?: () => void;
}
export const useRunLocalServer = ({ onSuccess }: UseRunLocalServerProps) => {
  const queryClient = useQueryClient();
  const serverStatus = queryClient.getQueryData<boolean>(["run-local-server"]);

  const {
    mutateAsync: checkServerStatus,
    isPending: isRunning,
    isSuccess,
  } = useMutation({
    mutationFn: () =>
      api
        .get("/server/healthcheck")
        .then((r) => r.data)
        .then(healthcheckSchema.parse),
    retryDelay: 1000,
    retry: 10,
    onMutate: () => {
      queryClient.setQueryData(["run-local-server"], false);
    },
    onSuccess: () => {
      queryClient.setQueryData(["run-local-server"], true);
      onSuccess?.();
    },
  });

  const run = useCallback(async () => {
    setApiBaseUrl();
    if (serverStatus === undefined) {
      console.log("Running local server");
      if (!window.electronAPI)
        throw new Error(
          "Electron API not available. Check your preload script.",
        );
      await window.electronAPI.runBatch();
    } else if (serverStatus === true) {
      console.log("Server is already running");
    } else {
      console.log("Server is not running yet");
    }
    await checkServerStatus(undefined);
  }, [serverStatus]);

  return {
    isRunning,
    isSuccess,
    run,
  };
};
