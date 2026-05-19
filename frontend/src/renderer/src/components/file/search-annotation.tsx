import type {
  Annotation,
  Metadata,
  SearchAnnotation as SearchAnnotationType,
} from "@/components/file-annotator/types";
import AnnotationPopover from "@/components/file/annotation-popover";
import { useAnnotation } from "@/context/Annotation";
import { cva, cx } from "@/styled/css";
import type { AllLabels } from "@/types/aymurai";

const search = cva({
  base: {
    bg: "[#FFF2A8]",
    fontFamily: '["Times New Roman", Times, serif]',
    textStyle: "label.md.default",
    m: "0",
    userSelect: "text",
    boxDecorationBreak: "clone",
  },
  variants: {
    clickable: {
      true: { cursor: "pointer" },
      false: { cursor: "unset" },
    },
    active: {
      true: {
        bg: "[#FFE066]",
        boxShadow: "[inset 0 -2px 0 #D89B00]",
      },
      false: {},
    },
  },
  defaultVariants: {
    clickable: false,
    active: false,
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
  const searchAnnotation = annotation as SearchAnnotationType;
  const searchMetadata =
    searchAnnotation.searchMatchId !== undefined
      ? {
          "data-search-match-id": searchAnnotation.searchMatchId,
          "data-search-active": searchAnnotation.isActive ? "true" : "false",
        }
      : {};
  const className = cx(
    "search",
    search({
      clickable: isAnnotable,
      active: searchAnnotation.isActive ?? false,
    }),
  );

  if (!isAnnotable)
    return (
      <mark className={className} {...metadata} {...searchMetadata}>
        {children}
      </mark>
    );

  return (
    <AnnotationPopover onClickOne={handleAddOne} onClickAll={handleAddAll}>
      <mark className={className} {...metadata} {...searchMetadata}>
        {children}
      </mark>
    </AnnotationPopover>
  );

  function handleAddOne(label: AllLabels) {
    const annotationData = createAnnotationData(
      children,
      searchAnnotation,
      label,
    );
    if (annotationData) {
      add(annotationData);
    }
  }
  function handleAddAll(label: AllLabels) {
    addBySearch(children, label);
  }
}
