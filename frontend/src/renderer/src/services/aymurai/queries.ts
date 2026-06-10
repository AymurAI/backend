import { EXCLUDED_TAGS } from "@/constants/excluded-tags";
import { disambiguateSchema } from "@/schema/disambiguate";
import { documentExtractSchema } from "@/schema/extract";
import type {
  AnonymizerLabels,
  PredictLabel,
  Workflows,
} from "@/types/aymurai";
import type { DocFile, Paragraph } from "@/types/file";
import { assertValidAnonymizerExportState } from "@/utils/anonymizer/export-validation";
import {
  anonymizeQuerySignature,
  filterActivePredictions,
  isPredictionActive,
} from "@/utils/anonymizer/predictions";
import { mutationOptions, queryOptions } from "@tanstack/react-query";
import api from "../api";
import predict from "./predict";

export type SuffixMode = "always" | "when_multiple" | "never";

interface Body {
  data: {
    document: string;
    labels: PredictLabel[];
  }[];
  label_policies?: Record<string, { anonymize: boolean }>;
  render_policy?: { suffix_mode: SuffixMode };
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
    queryKey: ["predict", api.defaults.baseURL, workflow, fileName, paragraph.id],
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
  suffixMode: SuffixMode = "always",
): Body => {
  const effectiveTags = excludedTags ?? EXCLUDED_TAGS;
  const paragraphs = file.paragraphs ?? [];

  // Run the pre-flight validation only on active (to-be-anonymized) predictions
  // so the validator doesn't complain about excluded entities.
  const activeLabels = filterActivePredictions(
    file.predictions,
    excludedTags,
    excludedWords,
  );
  assertValidAnonymizerExportState(file, activeLabels);

  // Send ALL predictions to the backend — excluded ones are marked with
  // aymurai_anonymize: false so they are persisted in
  // anonymization_paragraph.validation and can be recovered if the exclusion
  // is reversed in a future session.
  const allLabels = (file.predictions ?? []).map((l) => ({
    ...l,
    attrs: {
      ...l.attrs,
      aymurai_anonymize: isPredictionActive(l, excludedTags, excludedWords),
    },
  }));

  const label_policies = Object.fromEntries(
    Object.entries(effectiveTags)
      .filter(([, enabled]) => !enabled)
      .map(([id]) => [id, { anonymize: false }]),
  ) as Record<string, { anonymize: boolean }>;

  return {
    data: paragraphs.map((p) => ({
      document: p.value,
      labels: allLabels.filter((l) => l.paragraphId === p.id),
    })),
    ...(Object.keys(label_policies).length > 0 && { label_policies }),
    render_policy: { suffix_mode: suffixMode },
  };
};

export const anonymize = (
  file: DocFile,
  excludedTags: Record<AnonymizerLabels, boolean> | null,
  excludedWords: string[],
  suffixMode: SuffixMode = "always",
) =>
  queryOptions({
    // Normalise null → EXCLUDED_TAGS so the key is stable when the user hasn't
    // touched the config (both resolve to "all tags enabled").
    queryKey: [
      "anonymize",
      file.data.name,
      file.data.size,
      (file.paragraphs ?? []).map((p) => [p.id, p.value].join("\u001f")),
      anonymizeQuerySignature(file.predictions, excludedTags, excludedWords),
      excludedTags ?? EXCLUDED_TAGS,
      excludedWords,
      suffixMode,
    ],
    queryFn: async () => {
      const formData = new FormData();
      formData.append("file", file.data);
      formData.append(
        "annotations",
        JSON.stringify(body(file, excludedTags, excludedWords, suffixMode)),
      );

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
    queryKey: ["disambiguate", api.defaults.baseURL, file.data.name],
    queryFn: async (): Promise<PredictLabel[]> => {
      if (!file.paragraphs)
        throw new Error("File with no paragraphs tried to disambiguate");
      if (!file.predictions)
        throw new Error("File with no predictions tried to disambiguate");

      const { paragraphs, predictions } = file;

      // Build a lookup from paragraphId → list of original predictions so we
      // can reuse the stable mentionId even after the backend round-trip.
      const byParagraphId = new Map<string, PredictLabel[]>();
      for (const p of predictions) {
        const list = byParagraphId.get(p.paragraphId) ?? [];
        list.push(p);
        byParagraphId.set(p.paragraphId, list);
      }

      const response = await api.post("/anonymizer/disambiguate", {
        paragraphs: paragraphs.map((p) => ({
          document: p.value,
          labels: predictions.filter((l) => l.paragraphId === p.id),
        })),
      });

      const parsed = disambiguateSchema.parse(response.data);

      // Build a consumption queue per paragraph text so we can match response
      // items by content instead of array index. This tolerates backend
      // reordering and count drops. Duplicate paragraph texts are matched in
      // the order they appear in the original paragraphs array.
      const paragraphQueue = new Map<string, Paragraph[]>();
      for (const p of paragraphs) {
        const q = paragraphQueue.get(p.value) ?? [];
        q.push(p);
        paragraphQueue.set(p.value, q);
      }
      const consumed = new Map<string, number>();
      const matchedParagraphIds = new Set<string>();

      const disambiguated = parsed.data.flatMap((item) => {
        const queue = paragraphQueue.get(item.document) ?? [];
        const nextIdx = consumed.get(item.document) ?? 0;
        const paragraph = queue[nextIdx];
        consumed.set(item.document, nextIdx + 1);

        if (!paragraph) return [];

        matchedParagraphIds.add(paragraph.id);

        // Build a lookup from (start_char, end_char) → original mention so we
        // can reuse the stable mentionId.
        const origByPos = new Map<string, PredictLabel>();
        for (const orig of byParagraphId.get(paragraph.id) ?? []) {
          origByPos.set(`${orig.start_char}:${orig.end_char}`, orig);
        }

        return item.labels.map((l) => {
          const altStart = l.attrs.aymurai_alt_start_char;
          const altEnd = l.attrs.aymurai_alt_end_char;
          const useAlt = altStart !== null && altEnd !== null && altStart < altEnd;
          const resolvedText = useAlt && l.attrs.aymurai_alt_text ? l.attrs.aymurai_alt_text : l.text;
          const resolvedStart = useAlt ? altStart : l.start_char;
          const resolvedEnd = useAlt ? altEnd : l.end_char;

          // Prefer original mentionId so downstream D&D state stays stable.
          const orig = origByPos.get(`${l.start_char}:${l.end_char}`);

          return {
            mentionId: orig?.mentionId ?? crypto.randomUUID(),
            text: resolvedText,
            start_char: resolvedStart,
            end_char: resolvedEnd,
            attrs: {
              aymurai_label: l.attrs
                .aymurai_label as PredictLabel["attrs"]["aymurai_label"],
              aymurai_label_subclass: l.attrs.aymurai_label_subclass,
              aymurai_alt_text: l.attrs.aymurai_alt_text ?? null,
              aymurai_alt_start_char: l.attrs.aymurai_alt_start_char ?? null,
              aymurai_alt_end_char: l.attrs.aymurai_alt_end_char ?? null,
              canonical_entity_id: l.attrs.canonical_entity_id ?? null,
              aymurai_anonymize: l.attrs.aymurai_anonymize ?? null,
              aymurai_label_instance: l.attrs.aymurai_label_instance ?? null,
              aymurai_disambiguation: l.attrs.aymurai_disambiguation ?? null,
            },
            paragraphId: paragraph.id,
          } satisfies PredictLabel;
        });
      });

      // Preserve raw predictions for any paragraph the backend did not return,
      // so a backend count drop never silently erases annotations.
      const unmatched = predictions.filter(
        (p) => !matchedParagraphIds.has(p.paragraphId),
      );

      return [...disambiguated, ...unmatched];
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

      const response = await api.post<Blob>("/convert/odt/pdf", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
          Accept: "application/octet-stream",
        },
        responseType: "blob",
      });

      return response.data;
    },
  });

export const pdfToOdt = () =>
  mutationOptions({
    mutationFn: async (file: Blob) => {
      const formData = new FormData();
      formData.append("file", file, "document.pdf");

      const response = await api.post<Blob>("/convert/pdf/odt", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
          Accept: "application/octet-stream",
        },
        responseType: "blob",
      });

      return response.data;
    },
  });
