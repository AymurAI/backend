import { useEffect, useRef } from "react";

import { useFileDispatch } from "@/hooks";
import { addPredictions, removePredictions } from "@/reducers/file/actions";
import { disambiguate } from "@/services/aymurai/queries";
import type { DocFile } from "@/types/file";
import { useQueries } from "@tanstack/react-query";

import type { PredictStatus } from "./usePredict";

type FileDisambiguate = { status: PredictStatus };

/**
 * Runs disambiguation for each file **after all its predictions have arrived**.
 * When `enabled` is false (e.g. datapublic flow) every file resolves to
 * `"completed"` immediately and no requests are made.
 *
 * Aligned index-wise with `files`: `queries[i]` corresponds to `files[i]`.
 */
export function useDisambiguate(
  files: DocFile[],
  predictStatuses: Record<
    string,
    { status: PredictStatus; fromValidation?: boolean }
  >,
  enabled: boolean,
): Record<string, FileDisambiguate> {
  const dispatch = useFileDispatch();
  // Track which files have already had their disambiguated predictions dispatched
  const dispatchedRef = useRef(new Set<string>());

  const queries = useQueries({
    queries: files.map((file) => ({
      ...disambiguate(file),
      // Fire only when this step is enabled, predict is fully done, AND the
      // predictions were not loaded from stored DB validation (which is already
      // post-disambiguation data and must not be overwritten).
      enabled:
        enabled &&
        predictStatuses[file.data.name]?.status === "completed" &&
        !predictStatuses[file.data.name]?.fromValidation,
    })),
  });

  // Dispatch disambiguated predictions exactly once per file on success
  useEffect(() => {
    queries.forEach((query, i) => {
      const fileName = files[i].data.name;
      if (!query.isSuccess || dispatchedRef.current.has(fileName)) return;

      dispatchedRef.current.add(fileName);
      // Replace raw predictions with the disambiguated ones
      dispatch(removePredictions(fileName));
      dispatch(addPredictions(fileName, query.data));
    });
  });

  const result: Record<string, FileDisambiguate> = {};

  files.forEach((file, i) => {
    const fileName = file.data.name;
    const query = queries[i];
    const predictDone = predictStatuses[fileName]?.status === "completed";

    result[fileName] = {
      status: !enabled
        ? "completed" // this step is skipped for non-anonymizer flows
        : predictStatuses[fileName]?.fromValidation
          ? "completed" // predictions came from DB validation; disambiguation not needed
          : !predictDone
            ? "processing" // still waiting on predict
            : query.isError
              ? "error"
              : query.isSuccess
                ? "completed"
                : "processing",
    };
  });

  return result;
}
