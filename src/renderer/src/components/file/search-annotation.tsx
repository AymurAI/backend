import type {
  Annotation,
  LabelAnnotation,
  Metadata,
} from "@/components/file-annotator/types";
import AnnotationPopover from "@/components/file/annotation-popover";
import { useAnnotation } from "@/context/Annotation";
import { showToast } from "@/features/showToast";
import { cva } from "@/styled/css";
import type { AllLabels } from "@/types/aymurai";
import { Check } from "phosphor-react";

const search = cva({
  base: {
    bg: "[#FCFC02]",
    fontFamily: '["Times New Roman", Times, serif]',
    fontWeight: "bold",
    textStyle: "label.md.default",
    m: "0",
  },
  variants: {
    clickable: {
      true: { cursor: "pointer" },
      false: { cursor: "unset" },
    },
  },
  defaultVariants: {
    clickable: false,
  },
});

interface SearchAnnotationProps {
  children: string;
  annotation: Annotation;
}
export default function SearchAnnotation({
  children,
  annotation,
}: SearchAnnotationProps) {
  if (annotation.type !== "search")
    throw new Error(
      `Annotation of type "search" expected but got: ${annotation.type}`,
    );

  const { add, addBySearch, createAnnotationData, isAnnotable } =
    useAnnotation();

  const metadata: Metadata = {
    "data-start": annotation.start,
    "data-end": annotation.end,
    "data-tag": annotation.tag,
  };

  if (!isAnnotable)
    return (
      <mark className={search({ clickable: false })} {...metadata}>
        {children}
      </mark>
    );

  return (
    <AnnotationPopover onClickOne={handleAddOne} onClickAll={handleAddAll}>
      <mark className={search({ clickable: true })} {...metadata}>
        {children}
      </mark>
    </AnnotationPopover>
  );

  function handleAddOne(label: AllLabels, suffix: number | null) {
    const labelWithSuffix = suffix ? (`${label}_${suffix}` as const) : label;
    const annotationData = createAnnotationData(
      children,
      annotation as LabelAnnotation,
      labelWithSuffix,
    );
    if (annotationData) {
      add(annotationData);
      showToast("Se agregó la etiqueta en esta ocurrencia.", "success", Check);
    }
  }
  function handleAddAll(label: AllLabels, suffix: number | null) {
    const labelWithSuffix = suffix ? (`${label}_${suffix}` as const) : label;
    addBySearch(children, labelWithSuffix);
    showToast(
      "Se agregó la etiqueta en todas las ocurrencias.",
      "success",
      Check,
    );
  }
}
