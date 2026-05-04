import { memo, useMemo, useState, useTransition } from "react";

import { SearchBar } from "./SearchBar";

import type { SelectOption } from "@/components/ui/select";
import { EXCLUDED_TAGS } from "@/constants/excluded-tags";
import AnnotationProvider, { useAnnotation } from "@/context/Annotation";
import { useExcludedTagsConfig } from "@/store/useLocal";
import { HStack } from "@/styled/jsx";
import type {
  AllLabels,
  AllLabelsWithSufix,
  AnonymizerLabels,
  PredictLabel,
} from "@/types/aymurai";
import type { DocFile, Paragraph as ParagraphType } from "@/types/file";
import LabelManager from "../anonymizer/label-manager";
import SearchAnnotation from "../file/search-annotation";
import TagAnnotation from "../file/tag-annotation";
import * as S from "./FileAnnotator.styles";
import { createAnnotationsWithSearch, predictionsToMap } from "./annotations";
import { generateSplits } from "./generateSplits";

interface ParagraphProps {
  children: string;
  search: string;
  paragraph: ParagraphType;
  predictions: PredictLabel[];
}
const Paragraph = memo(
  ({ children, search, paragraph, predictions }: ParagraphProps) => {
    const { label, suffix } = useAnnotation();
    const searchTag = label
      ? suffix
        ? (`${label}_${suffix}` as AllLabelsWithSufix)
        : label
      : null;

    const annotations = useMemo(() => {
      return createAnnotationsWithSearch(
        predictions,
        search,
        paragraph,
        searchTag,
      );
    }, [predictions, search, paragraph, searchTag]);

    const splits = generateSplits(children, annotations);

    return (
      <S.Paragraph id={paragraph.id}>
        {splits.map((s) => {
          const content = children.slice(s.start, s.end);
          const key = `${s.start}-${s.end}`;

          switch (s.type) {
            case "search":
              return (
                <SearchAnnotation key={key} annotation={s}>
                  {content}
                </SearchAnnotation>
              );
            case "tag":
              return (
                <TagAnnotation key={key} annotation={s}>
                  {content}
                </TagAnnotation>
              );
            case "text":
            default:
              return <span key={key}>{content}</span>;
          }
        })}
      </S.Paragraph>
    );
  },
);

interface Props {
  file: DocFile;
  isAnnotable?: boolean;
}
export default function FileAnnotator({ file, isAnnotable = false }: Props) {
  const [search, setSearch] = useState("");
  const [, startTransition] = useTransition();

  const [label, setLabel] = useState<AllLabels | null>(null);
  const [suffix, setSuffix] = useState<number | null>(0);
  const [labelManagerOpen, setLabelManagerOpen] = useState(false);

  const paragraphs = file.paragraphs!;
  const { tags, words } = useExcludedTagsConfig();
  const effectiveTags = tags ?? EXCLUDED_TAGS;

  const filteredPredictions = useMemo(
    () =>
      (file.predictions ?? []).filter((label) => {
        const tag = label.attrs.aymurai_label as AnonymizerLabels;
        if (effectiveTags[tag] === false) return false;
        if (words.some((w) => label.text.toLowerCase() === w.toLowerCase()))
          return false;
        return true;
      }),
    [file.predictions, effectiveTags, words],
  );

  const predictionsMap = useMemo(
    () => predictionsToMap(filteredPredictions),
    [filteredPredictions],
  );

  const selectChangeHandler = (option?: SelectOption) => {
    setLabel((option?.id as AllLabels) ?? null);
  };

  const toggleManagerLabel = () => {
    setLabelManagerOpen(!labelManagerOpen);
  };

  const handleSearchChange = (value: string) => {
    startTransition(() => setSearch(value));
  };

  return (
    <HStack w="full" h="full" alignItems="unset" overflow="hidden">
      <S.Container>
        <SearchBar
          onSearchChange={handleSearchChange}
          onLabelChange={selectChangeHandler}
          onLabelSufixChange={setSuffix}
          onLabelManagerToggle={toggleManagerLabel}
          isAnnotable={isAnnotable}
          isLabelManagerOpen={labelManagerOpen}
        />
        <S.File>
          <AnnotationProvider
            file={file}
            isAnnotable={isAnnotable}
            label={label}
            suffix={suffix}
          >
            {paragraphs.map((p) => (
              <Paragraph
                key={p.id}
                search={search}
                paragraph={p}
                predictions={predictionsMap.get(p.id) ?? []}
              >
                {p.value}
              </Paragraph>
            ))}
          </AnnotationProvider>
        </S.File>
      </S.Container>
      {labelManagerOpen && <LabelManager onClose={toggleManagerLabel} />}
    </HStack>
  );
}
