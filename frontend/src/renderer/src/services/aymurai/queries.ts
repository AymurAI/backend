import { disambiguateSchema } from "@/schema/disambiguate";
import { documentExtractSchema } from "@/schema/extract";
import type { AnonymizerLabels, PredictLabel, Workflows } from "@/types/aymurai";
import type { DocFile, Paragraph } from "@/types/file";
import { EXCLUDED_TAGS } from "@/constants/excluded-tags";
import { mutationOptions, queryOptions } from "@tanstack/react-query";
import api from "../api";
import predict from "./predict";

interface Body {
  data: {
    document: string;
    labels: PredictLabel[];
  }[];
  label_policies?: Record<string, { anonymize: boolean }>;
}

/**
 * Query factory for a single paragraph prediction.
 * Uses React Query's native cancellation signal — no manual AbortController needed.
 */
export const predictParagraph = (
  paragraph: Paragraph,
  workflow: Workflows,
  fileName: string,
) =>
  queryOptions({
    queryKey: ["predict", workflow, fileName, paragraph.id],
    queryFn: ({ signal }) => {
      const controller = new AbortController();
      signal?.addEventListener("abort", () => controller.abort());
      return predict(paragraph, controller, workflow);
    },
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });

const body = (
  file: DocFile,
  excludedTags: Record<AnonymizerLabels, boolean> | null,
  excludedWords: string[],
): Body => {
  const effectiveTags = excludedTags ?? EXCLUDED_TAGS;
  const paragraphs = file.paragraphs ?? [];
  const labels = file.predictions ?? [];

  const label_policies = Object.fromEntries(
    Object.entries(effectiveTags)
      .filter(([, enabled]) => !enabled)
      .map(([id]) => [id, { anonymize: false }]),
  ) as Record<string, { anonymize: boolean }>;

  return {
    data: paragraphs.map((p) => ({
      document: p.value,
      labels: labels
        .filter((l) => l.paragraphId === p.id)
        .map((l) => {
          const isExcluded = excludedWords.some(
            (w) => l.text.toLowerCase() === w.toLowerCase(),
          );
          return isExcluded
            ? { ...l, attrs: { ...l.attrs, aymurai_anonymize: false } }
            : l;
        }),
    })),
    ...(Object.keys(label_policies).length > 0 && { label_policies }),
  };
};

export const anonymize = (
  file: DocFile,
  excludedTags: Record<AnonymizerLabels, boolean> | null,
  excludedWords: string[],
) =>
  queryOptions({
    queryKey: ["anonymize", file.data.name],
    queryFn: async () => {
      const formData = new FormData();
      formData.append("file", file.data);
      formData.append("annotations", JSON.stringify(body(file, excludedTags, excludedWords)));

      const response = await api.post<Blob>(
        "/anonymizer/anonymize-document",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
            Accept: "application/octet-stream",
          },
          responseType: "blob",
        },
      );

      return response.data;
    },
    // select: (data) => URL.createObjectURL(data),
  });

export const disambiguate = (file: DocFile) =>
  queryOptions({
    queryKey: ["disambiguate", file.data.name],
    queryFn: async (): Promise<PredictLabel[]> => {
      if (!file.paragraphs)
        throw new Error("File with no paragraphs tried to disambiguate");
      if (!file.predictions)
        throw new Error("File with no predictions tried to disambiguate");

      const { paragraphs, predictions } = file;

      const response = await api.post("/anonymizer/disambiguate", {
        paragraphs: paragraphs.map((p) => ({
          document: p.value,
          labels: predictions.filter((l) => l.paragraphId === p.id),
        })),
      });

      const parsed = disambiguateSchema.parse(response.data);

      // Flatten all paragraph labels into a single PredictLabel[] and map back
      // to the internal paragraphId (paragraph.id) using document_id as the key
      return parsed.data.flatMap((item) => {
        const paragraph = paragraphs.find(
          (p) => p.document_id === item.document,
        );

        return item.labels.map((l) => ({
          text: l.attrs.aymurai_alt_text ?? l.text,
          start_char: l.attrs.aymurai_alt_start_char ?? l.start_char,
          end_char: l.attrs.aymurai_alt_end_char ?? l.end_char,
          attrs: {
            aymurai_label: l.attrs
              .aymurai_label as PredictLabel["attrs"]["aymurai_label"],
            aymurai_label_subclass: l.attrs.aymurai_label_subclass,
            aymurai_alt_text: l.attrs.aymurai_alt_text ?? null,
            aymurai_alt_start_char: l.attrs.aymurai_alt_start_char ?? null,
            aymurai_alt_end_char: l.attrs.aymurai_alt_end_char ?? null,
            canonical_entity_id: l.attrs.canonical_entity_id ?? null,
          },
          paragraphId: paragraph?.id ?? item.document,
        }));
      });
    },
  });

export const fileParser = (file: File) =>
  queryOptions({
    queryKey: ["file-parser", file.name, file.size],
    queryFn: async () => {
      const formData = new FormData();
      formData.append("file", file);
      const response = await api.post("/misc/document-extract", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return documentExtractSchema.parse(response.data);
    },
    retry: false,
    retryOnMount: false,
  });

export const odtToPdf = () =>
  mutationOptions({
    mutationFn: async (file: Blob) => {
      const formData = new FormData();
      formData.append("file", file, "document.odt");

      const response = await api.post<Blob>(
        "/convert/odt/pdf",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
            Accept: "application/octet-stream",
          },
          responseType: "blob",
        },
      );

      return response.data;
    },
  });

export const pdfToOdt = () =>
  mutationOptions({
    mutationFn: async (file: Blob) => {
      const formData = new FormData();
      formData.append("file", file, "document.pdf");

      const response = await api.post<Blob>(
        "/convert/pdf/odt",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
            Accept: "application/octet-stream",
          },
          responseType: "blob",
        },
      );

      return response.data;
    },
  });
