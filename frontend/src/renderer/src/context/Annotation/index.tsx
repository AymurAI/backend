import type { LabelAnnotation } from "@/components/file-annotator/types";
import { useFileDispatch } from "@/hooks";
import {
  appendPrediction,
  removePrediction,
  removePredictionsByText,
  updatePredictionLabel,
  updatePredictionsByCanonicalId,
  updatePredictionsByText,
} from "@/reducers/file/actions";
import type {
  AllLabels,
  AllLabelsWithSufix,
  PredictLabel,
} from "@/types/aymurai";
import type { DocFile, Paragraph } from "@/types/file";
import { type ReactNode, createContext, useCallback, useContext } from "react";
import {
  findSearchIndexes,
  getBoundaries,
  isValidNode,
  paragraphIdFromSelection,
  selectionHasNodes,
} from "./utils";

interface AnnotationContextValues {
  isAnnotable: boolean;
  label: AllLabels | null;
  suffix: number | null;
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
  addBySearch: (search: string, label: AllLabels | AllLabelsWithSufix) => void;
}

/**
 * Provides the token received through OAuth2 login to the whole app
 */
export const AnnotationContext = createContext<AnnotationContextValues>({
  isAnnotable: false,
  label: null,
  suffix: null,
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
  suffix: number | null;
}
export default function AnnotationProvider({
  children,
  file,
  isAnnotable = false,
  label,
  suffix,
}: Props) {
  const searchTag: AllLabels | AllLabelsWithSufix | null = label
    ? suffix
      ? `${label}_${suffix}`
      : label
    : null;
  const dispatch = useFileDispatch();

  const add = useCallback(
    (prediction: PredictLabel) => {
      dispatch(appendPrediction(file.data.name, prediction));
    },
    [dispatch, file.data.name],
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
      dispatch(
        updatePredictionsByText(file.data.name, prediction.text, newLabel),
      );
    },
    [dispatch, file.data.name],
  );

  const updateByCanonicalId = useCallback(
    (canonicalId: string, newLabel: AllLabels | AllLabelsWithSufix) => {
      dispatch(updatePredictionsByCanonicalId(canonicalId, newLabel));
    },
    [dispatch],
  );

  const addBySearch = useCallback(
    (search: string, label: AllLabels | AllLabelsWithSufix) => {
      if (!search || search.length < 3) return;

      const canonical_entity_id = crypto.randomUUID();

      file.paragraphs?.forEach((paragraph: Paragraph) => {
        const indexes = findSearchIndexes(paragraph.value, search);
        indexes.forEach((start: number) => {
          const prediction: PredictLabel = {
            start_char: start,
            end_char: start + search.length,
            paragraphId: paragraph.id,
            text: search,
            attrs: {
              aymurai_label: label,
              aymurai_label_subclass: null,
              aymurai_alt_text: null,
              aymurai_alt_start_char: start,
              aymurai_alt_end_char: start + search.length,
              canonical_entity_id,
            },
          };
          dispatch(appendPrediction(file.data.name, prediction));
        });
      });
    },
    [dispatch, file.data.name, file.paragraphs],
  );

  const selectHandler = () => {
    // If the user hasn't selected any tag to search, do nothing
    if (!searchTag) return;

    const selection = window.getSelection();
    if (!selection || selection.type !== "Range") return;
    const text = selection.getRangeAt(0).toString();

    if (selectionHasNodes(selection)) return;
    const node = selection.anchorNode;

    if (!isValidNode(node)) return;
    const span = node.parentElement as HTMLSpanElement;

    const offset = Number(
      span.attributes.getNamedItem("data-start")?.value ?? 0,
    );
    const [start, end] = getBoundaries(selection);

    const aymurayLabel: AllLabels | AllLabelsWithSufix = searchTag;

    add({
      start_char: start + offset,
      end_char: end + offset,
      paragraphId: paragraphIdFromSelection(selection),
      text,
      attrs: {
        aymurai_label: aymurayLabel,
        aymurai_label_subclass: null,
        aymurai_alt_text: null,
        aymurai_alt_start_char: start + offset,
        aymurai_alt_end_char: end + offset,
      },
    });
  };

  return (
    <AnnotationContext.Provider
      value={{
        isAnnotable,
        label,
        suffix,
        add,
        remove,
        removeByText,
        updateLabel,
        updateByText,
        updateByCanonicalId,
        addBySearch,
      }}
    >
      <div onClick={selectHandler}>{children}</div>
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
    suffix,
    updateLabel,
    updateByText,
    updateByCanonicalId,
    addBySearch,
  } = useContext(AnnotationContext);

  const createAnnotationData = (
    text: string,
    annotation: LabelAnnotation,
    labelOverride?: AllLabels | AllLabelsWithSufix,
  ) => {
    const { start, end, paragraphId, tag } = annotation;
    const resolvedTag = labelOverride ?? tag;
    if (!resolvedTag) return null;
    return {
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
        canonical_entity_id: crypto.randomUUID(),
      },
    } satisfies PredictLabel;
  };

  return {
    add,
    remove,
    removeByText,
    isAnnotable,
    label,
    suffix,
    updateLabel,
    updateByText,
    updateByCanonicalId,
    addBySearch,
    createAnnotationData,
  };
};
