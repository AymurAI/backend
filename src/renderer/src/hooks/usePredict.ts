import { useState } from "react";

import { useFileDispatch } from "@/hooks";
import { addPredictions, removePredictions } from "@/reducers/file/actions";
import predict from "@/services/aymurai/predict";
import { predictParagraph } from "@/services/aymurai/queries";
import type { Workflows } from "@/types/aymurai";
import type { DocFile } from "@/types/file";
import { useQueries, useQueryClient } from "@tanstack/react-query";

export type PredictStatus = "processing" | "error" | "stopped" | "completed";

type FilePredict = {
  progress: number;
  status: PredictStatus;
  abort: () => void;
};

/**
 * Runs predictions for all paragraphs across all given files in parallel via
 * React Query. Dispatches results to the Redux file store as each paragraph
 * resolves. Returns a per-filename map of `{ progress, status, abort }`.
 *
 * Abort uses `queryClient.cancelQueries` so there are no manual AbortController
 * references to track or clean up.
 */
export function usePredict(
  files: DocFile[],
  workflow: Workflows,
): Record<string, FilePredict> {
  const dispatch = useFileDispatch();
  const queryClient = useQueryClient();
  const [abortedFiles, setAbortedFiles] = useState<Set<string>>(new Set());

  // Flatten all (file, paragraph) pairs — one React Query entry each
  const pairs = files.flatMap((file) =>
    (file.paragraphs ?? []).map((paragraph) => ({ file, paragraph })),
  );

  const queries = useQueries({
    queries: pairs.map(({ file, paragraph }) => ({
      // Use the factory for the query key and shared defaults (staleTime, retry)
      ...predictParagraph(paragraph, workflow, file.data.name),
      enabled: !abortedFiles.has(file.data.name),
      // Override queryFn to dispatch to Redux as each paragraph arrives.
      // Defined inline to avoid TS's `queryFn?: ...` optionality on the factory type.
      queryFn: async ({ signal }: { signal?: AbortSignal }) => {
        const controller = new AbortController();
        signal?.addEventListener("abort", () => controller.abort());
        const predictions = await predict(paragraph, controller, workflow);
        dispatch(addPredictions(file.data.name, predictions));
        return predictions;
      },
    })),
  });

  // Build per-file { progress, status, abort } from the flat query results
  const result: Record<string, FilePredict> = {};

  for (const file of files) {
    const fileName = file.data.name;
    const total = (file.paragraphs ?? []).length;

    // Collect only the queries that belong to this file
    const fileQueries = pairs.reduce<(typeof queries)[number][]>(
      (acc, pair, i) => {
        if (pair.file.data.name === fileName) acc.push(queries[i]);
        return acc;
      },
      [],
    );

    const successCount = fileQueries.filter((q) => q.isSuccess).length;
    const errorCount = fileQueries.filter((q) => q.isError).length;
    const progress = total > 0 ? successCount / total : 0;
    const isAborted = abortedFiles.has(fileName);

    const status: PredictStatus = isAborted
      ? "stopped"
      : errorCount > 0
        ? "error"
        : total === 0 || successCount === total
          ? "completed"
          : "processing";

    result[fileName] = {
      progress,
      status,
      abort: () => {
        // Cancel all in-flight paragraph queries for this file via RQ's own
        // cancellation mechanism — no manual controller refs to clean up
        queryClient.cancelQueries({
          queryKey: ["predict", workflow, fileName],
          exact: false,
        });
        dispatch(removePredictions(fileName));
        setAbortedFiles((prev) => new Set([...prev, fileName]));
      },
    };
  }

  return result;
}
