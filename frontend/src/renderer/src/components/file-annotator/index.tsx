import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useTransition,
} from "react";

import { SearchBar } from "./SearchBar";

import type { SelectOption } from "@/components/ui/select";
import AnnotationProvider, { useAnnotation } from "@/context/Annotation";
import { useExcludedTagsConfig } from "@/store/useLocal";
import { css } from "@/styled/css";
import { HStack } from "@/styled/jsx";
import type { AllLabels, PredictLabel } from "@/types/aymurai";
import type { DocFile, Paragraph as ParagraphType } from "@/types/file";
import { getActiveAnonymizerLabelOptions } from "@/utils/anonymizer/labels";
import { filterActivePredictions } from "@/utils/anonymizer/predictions";
import LabelManager from "../anonymizer/label-manager";
import SearchAnnotation from "../file/search-annotation";
import TagAnnotation from "../file/tag-annotation";
import * as S from "./FileAnnotator.styles";
import {
  type SearchMatch,
  createAnnotationsWithSearch,
  createSearchMatches,
  predictionsToMap,
  searchMatchesToMap,
} from "./annotations";
import { generateSplits } from "./generateSplits";

const labelManagerWrapper = css({
  display: "flex",
  h: "full",
  minH: "0",
  flexShrink: "0",
  "&[hidden]": {
    display: "none",
  },
});

interface ParagraphProps {
  children: string;
  paragraph: ParagraphType;
  predictions: PredictLabel[];
  searchMatches: SearchMatch[];
  activeSearchMatchId: string | null;
}
const Paragraph = memo(
  ({
    children,
    paragraph,
    predictions,
    searchMatches,
    activeSearchMatchId,
  }: ParagraphProps) => {
    const { label } = useAnnotation();

    const annotations = useMemo(() => {
      return createAnnotationsWithSearch(
        predictions,
        searchMatches,
        label,
        activeSearchMatchId,
      );
    }, [predictions, searchMatches, label, activeSearchMatchId]);

    const splits = generateSplits(children, annotations);

    return (
      <S.Paragraph id={paragraph.id}>
        {splits.map((s) => {
          const content = children.slice(s.start, s.end);
          const key = `${s.type}-${s.start}-${s.end}`;

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
              return (
                <span key={key} data-start={s.start}>
                  {content}
                </span>
              );
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
  const [activeSearchIndex, setActiveSearchIndex] = useState<number | null>(
    null,
  );
  const [, startTransition] = useTransition();
  const fileRef = useRef<HTMLDivElement>(null);

  const [label, setLabel] = useState<AllLabels | null>(null);
  const [labelManagerOpen, setLabelManagerOpen] = useState(isAnnotable);

  const paragraphs = file.paragraphs ?? [];
  const { tags, words } = useExcludedTagsConfig();
  const activeLabelOptions = useMemo(
    () => getActiveAnonymizerLabelOptions(tags),
    [tags],
  );

  useEffect(() => {
    if (label && !activeLabelOptions.some((option) => option.id === label)) {
      setLabel(null);
    }
  }, [activeLabelOptions, label]);

  const filteredPredictions = useMemo(
    () => filterActivePredictions(file.predictions, tags, words),
    [file.predictions, tags, words],
  );

  const predictionsMap = useMemo(
    () => predictionsToMap(filteredPredictions),
    [filteredPredictions],
  );

  const searchMatches = useMemo(
    () => createSearchMatches(paragraphs, search),
    [paragraphs, search],
  );

  const searchMatchesMap = useMemo(
    () => searchMatchesToMap(searchMatches),
    [searchMatches],
  );

  const activeSearchMatch =
    activeSearchIndex === null
      ? null
      : (searchMatches[activeSearchIndex] ?? null);
  const activeSearchMatchId = activeSearchMatch?.id ?? null;

  useEffect(() => {
    if (searchMatches.length === 0) {
      setActiveSearchIndex(null);
      return;
    }

    setActiveSearchIndex(0);
  }, [searchMatches]);

  useEffect(() => {
    if (!activeSearchMatchId) return;

    const timer = window.setTimeout(() => {
      const container = fileRef.current;
      const element = Array.from(
        container?.querySelectorAll<HTMLElement>("[data-search-match-id]") ?? [],
      ).find((el) => el.getAttribute("data-search-match-id") === activeSearchMatchId);
      if (!element || !container) return;

      const containerRect = container.getBoundingClientRect();
      const elementRect = element.getBoundingClientRect();
      const scrollOffset =
        elementRect.top -
        containerRect.top -
        containerRect.height / 2 +
        elementRect.height / 2;

      container.scrollBy({
        top: scrollOffset,
        behavior: "smooth",
      });
    }, 50);

    return () => window.clearTimeout(timer);
  }, [activeSearchMatchId]);

  const selectChangeHandler = (option?: SelectOption) => {
    setLabel((option?.id as AllLabels) ?? null);
  };

  const toggleManagerLabel = () => {
    setLabelManagerOpen(!labelManagerOpen);
  };

  const handleSearchChange = (value: string) => {
    startTransition(() => setSearch(value));
  };

  const handleSearchNext = useCallback(() => {
    setActiveSearchIndex((current) => {
      if (searchMatches.length === 0) return null;
      if (current === null) return 0;
      return Math.min(current + 1, searchMatches.length - 1);
    });
  }, [searchMatches.length]);

  const handleSearchPrevious = useCallback(() => {
    setActiveSearchIndex((current) => {
      if (searchMatches.length === 0) return null;
      if (current === null) return 0;
      return Math.max(current - 1, 0);
    });
  }, [searchMatches.length]);

  const focusDocument = useCallback(() => {
    fileRef.current?.focus();
  }, []);

  return (
    <HStack w="full" h="full" alignItems="unset" overflow="hidden">
      <S.Container>
        <SearchBar
          onSearchChange={handleSearchChange}
          onLabelChange={selectChangeHandler}
          labelValue={label ?? undefined}
          onLabelManagerToggle={toggleManagerLabel}
          isAnnotable={isAnnotable}
          isLabelManagerOpen={labelManagerOpen}
          matchesCount={searchMatches.length}
          activeIndex={activeSearchIndex}
          onNext={handleSearchNext}
          onPrevious={handleSearchPrevious}
          onFocusDocument={focusDocument}
        />
        <S.File ref={fileRef} tabIndex={-1}>
          <AnnotationProvider
            file={file}
            isAnnotable={isAnnotable}
            label={label}
          >
            {paragraphs.map((p) => (
              <Paragraph
                key={p.id}
                paragraph={p}
                predictions={predictionsMap.get(p.id) ?? []}
                searchMatches={searchMatchesMap.get(p.id) ?? []}
                activeSearchMatchId={activeSearchMatchId}
              >
                {p.value}
              </Paragraph>
            ))}
          </AnnotationProvider>
        </S.File>
      </S.Container>
      <div hidden={!labelManagerOpen} className={labelManagerWrapper}>
        <LabelManager onClose={toggleManagerLabel} />
      </div>
    </HStack>
  );
}
