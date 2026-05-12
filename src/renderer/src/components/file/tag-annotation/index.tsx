import { Check } from "phosphor-react";
import { useState } from "react";

import type {
  Annotation,
  LabelAnnotation,
  Metadata,
} from "@/components/file-annotator/types";
import { useAnnotation } from "@/context/Annotation";
import { showToast } from "@/features/showToast";

import type { AllLabels, AllLabelsWithSufix } from "@/types/aymurai";
import AnnotationPopover from "../annotation-popover";
import SuggestionLabel from "../suggestion-label";
import RemoveDialog from "./remove-dialog";
import ReplaceDialog from "./replace-dialog";

interface TagAnnotationProps {
  children: string;
  annotation: Annotation;
}
export default function TagAnnotation({
  children,
  annotation,
}: TagAnnotationProps) {
  if (annotation.type !== "tag")
    throw new Error(
      `Annotation of type "tag" expected but got: ${annotation.type}`,
    );

  const { updateLabel, updateByText, remove, removeByText, isAnnotable } = useAnnotation();
  const [removeAllOpen, setRemoveAllOpen] = useState(false);
  const [replaceAllLabelWithSuffix, setReplaceAllLabelWithSuffix] = useState<
    AllLabels | AllLabelsWithSufix | null
  >(null);
  const tag = annotation.tag;

  const { start, end, paragraphId } = annotation as LabelAnnotation;
  const annotationData = annotation.tag
    ? {
        text: children,
        start_char: start,
        end_char: end,
        paragraphId,
        attrs: {
          aymurai_label: annotation.tag,
          aymurai_label_subclass: null,
          aymurai_alt_text: null,
          aymurai_alt_start_char: start,
          aymurai_alt_end_char: end,
        },
      }
    : null;

  const metadata: Metadata = {
    "data-start": annotation.start,
    "data-end": annotation.end,
    "data-tag": annotation.tag,
  };

  if (!isAnnotable)
    return (
      <SuggestionLabel label={tag} {...metadata}>
        {children}
      </SuggestionLabel>
    );

  return (
    <>
      <AnnotationPopover
        onClickOne={handleReplaceOne}
        onClickAll={handleReplaceAll}
        onDeleteOne={handleDeleteOne}
        onDeleteAll={handleDeleteAll}
      >
        <SuggestionLabel isClickable label={tag} {...metadata}>
          {children}
        </SuggestionLabel>
      </AnnotationPopover>
      <ReplaceDialog
        isOpen={!!replaceAllLabelWithSuffix}
        text={children}
        label={replaceAllLabelWithSuffix ?? ""}
        onClose={(open) => !open && setReplaceAllLabelWithSuffix(null)}
        onConfirm={confirmReplaceAll}
      />
      <RemoveDialog
        isOpen={removeAllOpen}
        text={children}
        onClose={(open) => !open && setRemoveAllOpen(false)}
        onConfirm={confirmRemoveAll}
      />
    </>
  );

  function handleReplaceOne(label: AllLabels, suffix: number | null) {
    console.log({ annotationData, label });
    if (!annotationData || !label) return;

    const labelWithSuffix = suffix ? (`${label}_${suffix}` as const) : label;
    updateLabel(annotationData, labelWithSuffix);
    showToast("Se reemplazó la etiqueta en esta ocurrencia.", "success", Check);
  }

  function handleReplaceAll(label: AllLabels, suffix: number | null) {
    const labelWithSuffix = suffix ? (`${label}_${suffix}` as const) : label;
    setReplaceAllLabelWithSuffix(labelWithSuffix);
  }

  function handleDeleteOne() {
    if (!annotationData) return;
    remove(annotationData);
    showToast("Se eliminó la anotación.", "success", Check);
  }

  function handleDeleteAll() {
    setRemoveAllOpen(true);
  }

  function confirmRemoveAll() {
    if (!annotationData) return;
    removeByText(annotationData);
    setRemoveAllOpen(false);
    showToast("Se eliminaron todas las ocurrencias.", "success", Check);
  }

  function confirmReplaceAll() {
    if (!annotationData || !replaceAllLabelWithSuffix) return;
    updateByText(annotationData, replaceAllLabelWithSuffix);
    setReplaceAllLabelWithSuffix(null);
    showToast(
      "Se reemplazó la etiqueta en todas las ocurrencias.",
      "success",
      Check,
    );
  }
}
