import { useEffect } from "react";

import { useFileDispatch } from "@/hooks";
import { addParagraphs } from "@/reducers/file/actions";
import { documentExtractSchema } from "@/schema/extract";

import api from "../api";
import { useSchemedQuery } from "../utils";

export function useFileParser(file: File) {
  const dispatch = useFileDispatch();

  const query = useSchemedQuery({
    queryKey: ["file-parser", file.name, file.size],
    queryFn: async () => {
      const formData = new FormData();
      formData.append("file", file);

      const response = await api.post("/misc/document-extract", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      return response.data;
    },
    schema: documentExtractSchema,
    retry: false,
    retryOnMount: false,
  });

  useEffect(() => {
    if (query.isSuccess && query.data) {
      // TODO: remove redux in the future
      dispatch(
        addParagraphs(
          // Convert structure for backwards compatibility
          query.data.document.map((p) => ({
            value: p,
            document_id: query.data.document_id,
            id: p,
          })),
          file.name,
        ),
      );
    }
  }, [query.isSuccess]);

  return query;
}
