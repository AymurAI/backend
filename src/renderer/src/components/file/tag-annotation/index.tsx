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

  const { updateLabel, updateByText, updateByCanonicalId, isAnnotable } = useAnnotation();
  const [replaceAllLabelWithSuffix, setReplaceAllLabelWithSuffix] = useState<
    AllLabels | AllLabelsWithSufix | null
  >(null);
  const tag = annotation.tag;

  const { start, end, paragraphId, canonical_entity_id } = annotation as LabelAnnotation;
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
      >
        <SuggestionLabel isClickable label={tag} {...metadata}>
          {children}
        </SuggestionLabel>
      </AnnotationPopover>
      <ReplaceDialog
        isOpen={!!replaceAllLabelWithSuffix}
        label={replaceAllLabelWithSuffix ?? ""}
        onClose={(open) => !open && setReplaceAllLabelWithSuffix(null)}
        onConfirm={confirmReplaceAll}
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

  function confirmReplaceAll() {
    if (!annotationData || !replaceAllLabelWithSuffix) return;

    if (canonical_entity_id) {
      updateByCanonicalId(canonical_entity_id, replaceAllLabelWithSuffix);
    } else {
      updateByText(annotationData, replaceAllLabelWithSuffix);
    }
    setReplaceAllLabelWithSuffix(null);
    showToast(
      "Se reemplazó la etiqueta en todas las ocurrencias.",
      "success",
      Check,
    );
  }
}
