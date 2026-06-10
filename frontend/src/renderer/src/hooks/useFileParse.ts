import { useEffect, useState } from "react";

import { useFileDispatch } from "@/hooks";
import { addParagraphs } from "@/reducers/file/actions";
import { fileParser } from "@/services/aymurai/queries";
import type { DocFile } from "@/types/file";
import { useQueries, useQueryClient } from "@tanstack/react-query";

import type { PredictStatus } from "./usePredict";

export function useFileParse(
  files: DocFile[],
): Record<string, { status: PredictStatus; abort: () => void }> {
  const dispatch = useFileDispatch();
  const queryClient = useQueryClient();
  const [abortedFiles, setAbortedFiles] = useState<Set<string>>(new Set());

  const queries = useQueries({
    queries: files.map((file) => ({
      ...fileParser(file.data),
      enabled: !abortedFiles.has(file.data.name),
    })),
  });

  useEffect(() => {
    queries.forEach((query, fileIndex) => {
      const file = files[fileIndex];
      // Use the Redux state as the guard: if paragraphs are already set, skip.
      // This correctly re-dispatches when the same file is reloaded after a replace.
      if (!query.isSuccess || !query.data || file.paragraphs !== undefined)
        return;
      dispatch(
        addParagraphs(
          query.data.document.map((p, paragraphIndex) => ({
            value: p,
            document_id: query.data.document_id,
            id: `${query.data.document_id}:${paragraphIndex}`,
          })),
          file.data.name,
        ),
      );
    });
  });

  const result: Record<string, { status: PredictStatus; abort: () => void }> =
    {};
  files.forEach((file, i) => {
    const q = queries[i];
    const fileName = file.data.name;
    const isAborted = abortedFiles.has(fileName);
    result[fileName] = {
      status: isAborted
        ? "stopped"
        : q.isError
          ? "error"
          : q.isSuccess
            ? "completed"
            : "processing",
      abort: () => {
        queryClient.cancelQueries({
          queryKey: ["file-parser", fileName],
          exact: false,
        });
        setAbortedFiles((prev) => new Set([...prev, fileName]));
      },
    };
  });
  return result;
}
