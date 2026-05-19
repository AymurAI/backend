import type {
  LabelAnnotation,
  SearchAnnotation,
} from "@/components/file-annotator/types";
import ManualEntityResolutionDialog, {
  type ManualEntityResolutionRequest,
} from "@/components/file/manual-entity-resolution-dialog";
import { getAnonymizerCategoryForLabel } from "@/constants/anonymizer-categories";
import { EXCLUDED_TAGS } from "@/constants/excluded-tags";
import { showToast } from "@/features/showToast";
import { useEntityGroups, useFileDispatch, useFiles } from "@/hooks";
import {
  appendPrediction,
  removePrediction,
  removePredictionsByText,
  updatePredictionLabel,
  updatePredictionsByCanonicalId,
  updatePredictionsByText,
} from "@/reducers/file/actions";
import { useHoverState } from "@/store/useHoverState";
import {
  useExcludedTagsConfig,
  useGroupOrder,
  useGroupOrderActions,
} from "@/store/useLocal";
import type {
  AllLabels,
  AllLabelsWithSufix,
  AnonymizerLabels,
  PredictLabel,
} from "@/types/aymurai";
import { anonymizerLabels } from "@/types/aymurai";
import type { DocFile, Paragraph } from "@/types/file";
import {
  type ManualEntityResolution,
  findSimilarEntityGroups,
  normalizeEntityText,
  stripEntityLabelSuffix,
} from "@/utils/anonymizer/entity-similarity";
import { findNormalizedOccurrenceRanges } from "@/utils/anonymizer/occurrences";
import { filterActivePredictions } from "@/utils/anonymizer/predictions";
import { Check, WarningCircle } from "phosphor-react";
import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import { findSearchIndexes, getSelectionAnnotationRange } from "./utils";

interface AnnotationContextValues {
  isAnnotable: boolean;
  label: AllLabels | null;
  add: (prediction: PredictLabel) => void;
  remove: (prediction: PredictLabel) => void;
  removeByText: (prediction: PredictLabel) => void;
  updateLabel: (
    prediction: PredictLabel,
    newLabel: AllLabels | AllLabelsWithSufix,
  ) => void;
  updateByText: (
    prediction: PredictLabel,
    newLabel: AllLabels | AllLabelsWithSufix,
  ) => void;
  updateByCanonicalId: (
    canonicalId: string,
    newLabel: AllLabels | AllLabelsWithSufix,
  ) => void;
  addBySearch: (search: string, label: AllLabels) => void;
}

/**
 * Provides the token received through OAuth2 login to the whole app
 */
export const AnnotationContext = createContext<AnnotationContextValues>({
  isAnnotable: false,
  label: null,
  add: () => {},
  remove: () => {},
  removeByText: () => {},
  updateLabel: () => {},
  updateByText: () => {},
  updateByCanonicalId: () => {},
  addBySearch: () => {},
});
AnnotationContext.displayName = "AnnotationContext";

interface Props {
  children?: ReactNode;
  file: DocFile;
  isAnnotable?: boolean;
  label: AllLabels | null;
}

type PendingManualResolution = ManualEntityResolutionRequest & {
  predictions: PredictLabel[];
  selectedLabel: AllLabels;
};

const ANONYMIZER_LABEL_IDS = new Set<string>(
  anonymizerLabels.map((item) => item.id),
);

function toBaseLabel(label: AllLabels | AllLabelsWithSufix): AllLabels {
  return stripEntityLabelSuffix(String(label)) as AllLabels;
}

function isKnownAnonymizerLabel(label: string): label is AnonymizerLabels {
  return ANONYMIZER_LABEL_IDS.has(label);
}

function isLabelEnabled(
  label: AllLabels,
  excludedTags: Record<AnonymizerLabels, boolean> | null,
): boolean {
  const baseLabel = stripEntityLabelSuffix(String(label));
  if (!isKnownAnonymizerLabel(baseLabel)) return true;
  return (excludedTags ?? EXCLUDED_TAGS)[baseLabel] !== false;
}

function isExcludedMention(text: string, excludedWords: string[]): boolean {
  const normalizedText = normalizeEntityText(text);
  return excludedWords.some(
    (word) => normalizeEntityText(word) === normalizedText,
  );
}

function withCanonicalEntity(
  prediction: PredictLabel,
  canonicalId: string,
  label: AllLabels | AllLabelsWithSufix,
): PredictLabel {
  return {
    ...prediction,
    attrs: {
      ...prediction.attrs,
      aymurai_label: label,
      canonical_entity_id: canonicalId,
    },
  };
}

function compareAppearance(
  a: { paragraphIndex: number; start_char: number },
  b: { paragraphIndex: number; start_char: number },
) {
  if (a.paragraphIndex !== b.paragraphIndex) {
    return a.paragraphIndex - b.paragraphIndex;
  }
  return a.start_char - b.start_char;
}

function rangesOverlap(
  a: { start_char: number; end_char: number },
  b: { start_char: number; end_char: number },
) {
  return a.start_char < b.end_char && b.start_char < a.end_char;
}

function hasInternalOverlap(predictions: PredictLabel[]) {
  const byParagraph = new Map<string, PredictLabel[]>();
  for (const prediction of predictions) {
    const paragraphPredictions = byParagraph.get(prediction.paragraphId) ?? [];
    paragraphPredictions.push(prediction);
    byParagraph.set(prediction.paragraphId, paragraphPredictions);
  }

  for (const paragraphPredictions of byParagraph.values()) {
    const sorted = [...paragraphPredictions].sort(
      (a, b) => a.start_char - b.start_char,
    );
    for (let i = 1; i < sorted.length; i += 1) {
      const previous = sorted[i - 1];
      const current = sorted[i];
      if (previous && current && rangesOverlap(previous, current)) return true;
    }
  }

  return false;
}

export default function AnnotationProvider({
  children,
  file,
  isAnnotable = false,
  label,
}: Props) {
  const dispatch = useFileDispatch();
  const files = useFiles();
  const { tags, words } = useExcludedTagsConfig();
  const { groupOrder } = useGroupOrder();
  const { setGroupOrder } = useGroupOrderActions();
  const setLastEditedCanonicalId = useHoverState(
    (s) => s.setLastEditedCanonicalId,
  );
  const [pendingResolution, setPendingResolution] =
    useState<PendingManualResolution | null>(null);

  const activeFiles = useMemo(
    () =>
      files.map((item) => ({
        ...item,
        predictions: filterActivePredictions(item.predictions, tags, words),
      })),
    [files, tags, words],
  );
  const groups = useEntityGroups(activeFiles);
  const activePredictionsByParagraph = useMemo(() => {
    const result = new Map<string, PredictLabel[]>();
    const activePredictions = filterActivePredictions(
      file.predictions,
      tags,
      words,
    );

    for (const prediction of activePredictions) {
      const paragraphPredictions = result.get(prediction.paragraphId) ?? [];
      paragraphPredictions.push(prediction);
      result.set(prediction.paragraphId, paragraphPredictions);
    }

    return result;
  }, [file.predictions, tags, words]);

  const paragraphIndexById = useMemo(() => {
    const result = new Map<string, number>();
    for (const currentFile of files) {
      for (const [index, paragraph] of (
        currentFile.paragraphs ?? []
      ).entries()) {
        if (!result.has(paragraph.id)) result.set(paragraph.id, index);
      }
    }
    return result;
  }, [files]);

  const getFirstAppearance = useCallback(
    (predictions: PredictLabel[]) => {
      return predictions.reduce(
        (earliest, prediction) => {
          const current = {
            paragraphIndex: paragraphIndexById.get(prediction.paragraphId) ?? 0,
            start_char: prediction.start_char,
          };
          return compareAppearance(current, earliest) < 0 ? current : earliest;
        },
        {
          paragraphIndex: Number.POSITIVE_INFINITY,
          start_char: Number.POSITIVE_INFINITY,
        },
      );
    },
    [paragraphIndexById],
  );

  const updateGroupOrderForNewGroup = useCallback(
    (
      canonicalId: string,
      selectedLabel: AllLabels,
      predictions: PredictLabel[],
    ) => {
      const category = getAnonymizerCategoryForLabel(String(selectedLabel));
      const existingOrder = groupOrder?.[category];
      if (!existingOrder) return;

      const firstAppearance = getFirstAppearance(predictions);
      const categoryGroups = groups
        .filter(
          (group) =>
            getAnonymizerCategoryForLabel(group.renderBase) === category,
        )
        .sort((a, b) =>
          compareAppearance(a.firstAppearance, b.firstAppearance),
        );
      const nextOrder = existingOrder.filter((id) => id !== canonicalId);
      const insertBefore = categoryGroups.find(
        (group) =>
          compareAppearance(firstAppearance, group.firstAppearance) < 0,
      );

      if (!insertBefore) {
        nextOrder.push(canonicalId);
      } else {
        const index = nextOrder.indexOf(insertBefore.canonicalId);
        if (index === -1) nextOrder.push(canonicalId);
        else nextOrder.splice(index, 0, canonicalId);
      }

      setGroupOrder({ ...groupOrder, [category]: nextOrder });
    },
    [getFirstAppearance, groupOrder, groups, setGroupOrder],
  );

  const commitPredictions = useCallback(
    (
      predictions: PredictLabel[],
      canonicalId: string,
      resolvedLabel: AllLabels | AllLabelsWithSufix,
    ) => {
      for (const prediction of predictions) {
        dispatch(
          appendPrediction(
            file.data.name,
            withCanonicalEntity(prediction, canonicalId, resolvedLabel),
          ),
        );
      }
      setLastEditedCanonicalId(canonicalId);
      showToast(
        predictions.length > 1
          ? "Se agregaron las etiquetas al grupo de entidad."
          : "Se agregó la etiqueta al grupo de entidad.",
        "success",
        Check,
      );
    },
    [dispatch, file.data.name, setLastEditedCanonicalId],
  );

  const commitNewGroup = useCallback(
    (predictions: PredictLabel[], selectedLabel: AllLabels) => {
      const canonicalId = crypto.randomUUID();
      commitPredictions(predictions, canonicalId, selectedLabel);
      updateGroupOrderForNewGroup(canonicalId, selectedLabel, predictions);
    },
    [commitPredictions, updateGroupOrderForNewGroup],
  );

  const queueManualPredictions = useCallback(
    (
      predictions: PredictLabel[],
      selectedLabel: AllLabels | AllLabelsWithSufix,
    ) => {
      if (predictions.length === 0) return;

      const baseLabel = toBaseLabel(selectedLabel);
      const text = predictions[0]?.text ?? "";
      if (!normalizeEntityText(text)) return;

      if (hasInternalOverlap(predictions)) {
        showToast(
          "No se pueden agregar ocurrencias solapadas entre sí.",
          "error",
          WarningCircle,
        );
        return;
      }

      const overlappingPrediction = predictions.find((prediction) =>
        (activePredictionsByParagraph.get(prediction.paragraphId) ?? []).some(
          (activePrediction) => rangesOverlap(prediction, activePrediction),
        ),
      );
      if (overlappingPrediction) {
        showToast(
          "La selección se solapa con una entidad activa. Eliminá o editá la entidad existente antes de crear otra.",
          "error",
          WarningCircle,
        );
        return;
      }

      if (!isLabelEnabled(baseLabel, tags)) {
        showToast(
          "La categoría seleccionada está desactivada en Configuración.",
          "error",
          WarningCircle,
        );
        return;
      }

      if (isExcludedMention(text, words)) {
        showToast(
          "El término seleccionado está en la lista de términos excluidos.",
          "error",
          WarningCircle,
        );
        return;
      }

      const candidates = findSimilarEntityGroups(
        {
          text,
          normalizedText: normalizeEntityText(text),
          label: String(baseLabel),
          paragraphId: predictions[0]?.paragraphId,
          start_char: predictions[0]?.start_char,
          end_char: predictions[0]?.end_char,
        },
        groups,
      );

      if (candidates.length === 0) {
        commitNewGroup(predictions, baseLabel);
        return;
      }

      setPendingResolution({
        text,
        label: String(baseLabel),
        count: predictions.length,
        candidates,
        predictions,
        selectedLabel: baseLabel,
      });
    },
    [activePredictionsByParagraph, commitNewGroup, groups, tags, words],
  );

  const add = useCallback(
    (prediction: PredictLabel) => {
      queueManualPredictions([prediction], prediction.attrs.aymurai_label);
    },
    [queueManualPredictions],
  );

  const remove = useCallback(
    (prediction: PredictLabel) => {
      dispatch(removePrediction(file.data.name, prediction));
    },
    [dispatch, file.data.name],
  );

  const removeByText = useCallback(
    (prediction: PredictLabel) => {
      dispatch(removePredictionsByText(file.data.name, prediction.text));
    },
    [dispatch, file.data.name],
  );

  const updateLabel = useCallback(
    (prediction: PredictLabel, newLabel: AllLabels | AllLabelsWithSufix) => {
      dispatch(updatePredictionLabel(file.data.name, prediction, newLabel));
    },
    [dispatch, file.data.name],
  );

  const updateByText = useCallback(
    (prediction: PredictLabel, newLabel: AllLabels | AllLabelsWithSufix) => {
      const normalizedText = normalizeEntityText(prediction.text);
      if (!normalizedText) return;

      const sourceBaseLabel = toBaseLabel(prediction.attrs.aymurai_label);
      const nextBaseLabel = toBaseLabel(newLabel);
      const sourceCanonicalId = prediction.attrs.canonical_entity_id ?? null;
      const targetCanonicalId =
        sourceCanonicalId && sourceBaseLabel === nextBaseLabel
          ? sourceCanonicalId
          : crypto.randomUUID();
      const missingPredictions: PredictLabel[] = [];
      let skippedOverlaps = 0;

      file.paragraphs?.forEach((paragraph: Paragraph) => {
        const ranges = findNormalizedOccurrenceRanges(
          paragraph.value,
          prediction.text,
        );

        ranges.forEach((range) => {
          const draftRange = {
            start_char: range.start,
            end_char: range.end,
          };
          const activeOverlaps = (
            activePredictionsByParagraph.get(paragraph.id) ?? []
          ).filter((activePrediction) =>
            rangesOverlap(draftRange, activePrediction),
          );
          const hasEquivalentActiveOverlap = activeOverlaps.some(
            (activePrediction) =>
              normalizeEntityText(activePrediction.text) === normalizedText,
          );

          if (hasEquivalentActiveOverlap) return;

          if (activeOverlaps.length > 0) {
            skippedOverlaps += 1;
            return;
          }

          missingPredictions.push({
            mentionId: crypto.randomUUID(),
            start_char: range.start,
            end_char: range.end,
            paragraphId: paragraph.id,
            text: range.text,
            attrs: {
              aymurai_label: newLabel,
              aymurai_label_subclass: null,
              aymurai_alt_text: null,
              aymurai_alt_start_char: range.start,
              aymurai_alt_end_char: range.end,
            },
          });
        });
      });

      dispatch(
        updatePredictionsByText(
          file.data.name,
          prediction.text,
          newLabel,
          targetCanonicalId,
        ),
      );

      for (const missingPrediction of missingPredictions) {
        dispatch(
          appendPrediction(
            file.data.name,
            withCanonicalEntity(missingPrediction, targetCanonicalId, newLabel),
          ),
        );
      }

      const createdNewGroup =
        !sourceCanonicalId || sourceBaseLabel !== nextBaseLabel;
      if (createdNewGroup) {
        updateGroupOrderForNewGroup(
          targetCanonicalId,
          nextBaseLabel,
          missingPredictions.length > 0 ? missingPredictions : [prediction],
        );
      }

      setLastEditedCanonicalId(targetCanonicalId);

      if (skippedOverlaps > 0) {
        showToast(
          "Algunas ocurrencias no se agregaron porque se solapan con entidades activas.",
          "error",
          WarningCircle,
        );
      }
    },
    [
      activePredictionsByParagraph,
      dispatch,
      file.data.name,
      file.paragraphs,
      setLastEditedCanonicalId,
      updateGroupOrderForNewGroup,
    ],
  );

  const updateByCanonicalId = useCallback(
    (canonicalId: string, newLabel: AllLabels | AllLabelsWithSufix) => {
      dispatch(updatePredictionsByCanonicalId(canonicalId, newLabel));
    },
    [dispatch],
  );

  const addBySearch = useCallback(
    (search: string, label: AllLabels) => {
      if (!search || search.length < 3) return;

      const normalizedSearch = normalizeEntityText(search);
      const predictions: PredictLabel[] = [];
      let skippedOverlaps = 0;
      const reusableCanonicalId = [...activePredictionsByParagraph.values()]
        .flat()
        .find(
          (prediction) =>
            normalizeEntityText(prediction.text) === normalizedSearch &&
            prediction.attrs.canonical_entity_id,
        )?.attrs.canonical_entity_id;

      file.paragraphs?.forEach((paragraph: Paragraph) => {
        const normalizedRanges = findNormalizedOccurrenceRanges(
          paragraph.value,
          search,
        );
        const ranges =
          normalizedRanges.length > 0
            ? normalizedRanges
            : findSearchIndexes(paragraph.value, search).map((start) => ({
                start,
                end: start + search.length,
                text: paragraph.value.slice(start, start + search.length),
                normalizedText: normalizeEntityText(search),
              }));
        ranges.forEach((range) => {
          const draftRange = {
            start_char: range.start,
            end_char: range.end,
          };
          const activeOverlaps = (
            activePredictionsByParagraph.get(paragraph.id) ?? []
          ).filter((activePrediction) =>
            rangesOverlap(draftRange, activePrediction),
          );
          const hasEquivalentActiveOverlap = activeOverlaps.some(
            (activePrediction) =>
              normalizeEntityText(activePrediction.text) === normalizedSearch,
          );

          if (hasEquivalentActiveOverlap) return;

          if (activeOverlaps.length > 0) {
            skippedOverlaps += 1;
            return;
          }

          const prediction: PredictLabel = {
            mentionId: crypto.randomUUID(),
            start_char: range.start,
            end_char: range.end,
            paragraphId: paragraph.id,
            text: range.text,
            attrs: {
              aymurai_label: label,
              aymurai_label_subclass: null,
              aymurai_alt_text: null,
              aymurai_alt_start_char: range.start,
              aymurai_alt_end_char: range.end,
            },
          };
          predictions.push(prediction);
        });
      });

      if (predictions.length === 0 && skippedOverlaps > 0) {
        showToast(
          "No se agregaron ocurrencias porque todas se solapan con entidades activas.",
          "error",
          WarningCircle,
        );
        return;
      }

      if (reusableCanonicalId) {
        dispatch(
          updatePredictionsByText(
            file.data.name,
            search,
            label,
            reusableCanonicalId,
          ),
        );

        for (const prediction of predictions) {
          dispatch(
            appendPrediction(
              file.data.name,
              withCanonicalEntity(prediction, reusableCanonicalId, label),
            ),
          );
        }

        setLastEditedCanonicalId(reusableCanonicalId);
        if (skippedOverlaps > 0) {
          showToast(
            "Algunas ocurrencias no se agregaron porque se solapan con entidades activas.",
            "error",
            WarningCircle,
          );
        }
        return;
      }

      queueManualPredictions(predictions, label);
    },
    [
      activePredictionsByParagraph,
      dispatch,
      file.data.name,
      file.paragraphs,
      queueManualPredictions,
      setLastEditedCanonicalId,
    ],
  );

  const selectHandler = () => {
    // If the user hasn't selected any tag to search, do nothing
    if (!label) return;

    const selection = window.getSelection();
    if (!selection) return;
    const selectedRange = getSelectionAnnotationRange(selection);
    if (!selectedRange) return;

    add({
      mentionId: crypto.randomUUID(),
      start_char: selectedRange.start,
      end_char: selectedRange.end,
      paragraphId: selectedRange.paragraphId,
      text: selectedRange.text,
      attrs: {
        aymurai_label: label,
        aymurai_label_subclass: null,
        aymurai_alt_text: null,
        aymurai_alt_start_char: selectedRange.start,
        aymurai_alt_end_char: selectedRange.end,
      },
    });
  };

  const handleResolveManualEntity = (resolution: ManualEntityResolution) => {
    if (!pendingResolution) return;

    if (resolution.type === "existing") {
      commitPredictions(
        pendingResolution.predictions,
        resolution.candidate.group.canonicalId,
        resolution.candidate.group.renderBase as AllLabels | AllLabelsWithSufix,
      );
    } else {
      commitNewGroup(
        pendingResolution.predictions,
        pendingResolution.selectedLabel,
      );
    }

    setPendingResolution(null);
  };

  return (
    <AnnotationContext.Provider
      value={{
        isAnnotable,
        label,
        add,
        remove,
        removeByText,
        updateLabel,
        updateByText,
        updateByCanonicalId,
        addBySearch,
      }}
    >
      <div onMouseUp={selectHandler}>{children}</div>
      <ManualEntityResolutionDialog
        request={pendingResolution}
        onClose={() => setPendingResolution(null)}
        onResolve={handleResolveManualEntity}
      />
    </AnnotationContext.Provider>
  );
}

export const useAnnotation = () => {
  const {
    add,
    remove,
    removeByText,
    isAnnotable,
    label,
    updateLabel,
    updateByText,
    updateByCanonicalId,
    addBySearch,
  } = useContext(AnnotationContext);

  const createAnnotationData = (
    text: string,
    annotation: LabelAnnotation | SearchAnnotation,
    labelOverride?: AllLabels | AllLabelsWithSufix,
  ) => {
    const { start, end, paragraphId, tag } = annotation;
    const resolvedTag = labelOverride ?? tag;
    if (!resolvedTag) return null;
    return {
      mentionId: crypto.randomUUID(),
      text,
      start_char: start,
      end_char: end,
      paragraphId: paragraphId,
      attrs: {
        aymurai_label: resolvedTag,
        aymurai_label_subclass: null,
        aymurai_alt_text: null,
        aymurai_alt_start_char: start,
        aymurai_alt_end_char: end,
      },
    } satisfies PredictLabel;
  };

  return {
    add,
    remove,
    removeByText,
    isAnnotable,
    label,
    updateLabel,
    updateByText,
    updateByCanonicalId,
    addBySearch,
    createAnnotationData,
  };
};
