import type {
  AllLabels,
  AllLabelsWithSufix,
  PredictLabel,
} from "@/types/aymurai";
import type { Paragraph } from "@/types/file";
import { includes } from "@/utils/regex";
import type { Annotation } from "./types";

export const SEARCH_MIN_LENGTH = 3;

export interface SearchMatch {
  id: string;
  paragraphId: string;
  start: number;
  end: number;
  index: number;
}

/**
 * Converts a predict label to an annotation
 * @param labels List of predict labels from the API
 * @returns List of annotations
 */
const labelToAnnotation = (labels: PredictLabel[]): Annotation[] => {
  return labels.map(
    ({ start_char, end_char, attrs, paragraphId, mentionId }) => ({
      start: start_char,
      end: end_char,
      type: "tag",
      tag: attrs.aymurai_label,
      paragraphId,
      canonical_entity_id: attrs.canonical_entity_id,
      mentionId,
    }),
  );
};

/**
 * Finds the indexes where the search string is found in the paragraph
 * @param paragraph Paragraph to search in
 * @param search Search string
 * @returns List of indexes where the search string is found
 */
const findSearchIndexes = (paragraph: string, search: string) => {
  const regex = includes(search);

  const indexes: number[] = [];
  let match = regex.exec(paragraph);

  while (match) {
    indexes.push(match.index);
    match = regex.exec(paragraph);
  }

  return indexes;
};

/**
 * Appends search annotations to the list of label annotations
 * @param arr List of label annotations
 * @param search Search string
 * @param paragraph Paragraph to search in
 * @returns List of annotations with search annotations appended
 */
const getSearchAnnotations = (
  searchMatches: SearchMatch[],
  label: AllLabels | AllLabelsWithSufix | null,
  activeSearchMatchId: string | null,
): Annotation[] => {
  return searchMatches.map(
    (match) =>
      ({
        start: match.start,
        end: match.end,
        type: "search",
        tag: label,
        paragraphId: match.paragraphId,
        searchMatchId: match.id,
        searchIndex: match.index,
        isActive: match.id === activeSearchMatchId,
      }) as Annotation,
  );
};

/**
 * Converts the predictions array into a map with the paragraph id as key
 * @param predictions List of labels predicted by AymurAI
 * @returns A map with the paragraph id as key and an array of predictions as value
 */
export const predictionsToMap = (
  predictions: PredictLabel[],
): Map<string, PredictLabel[]> => {
  const map = new Map<string, PredictLabel[]>();

  for (const token of predictions) {
    // Ignore characters
    if ([":", ",", ".", ")", "(", "-", "_"].includes(token.text)) continue;

    const paragraphPredictions = map.get(token.paragraphId);
    if (paragraphPredictions) {
      paragraphPredictions.push(token);
    } else {
      map.set(token.paragraphId, [token]);
    }
  }

  return map;
};

export const createSearchMatches = (
  paragraphs: Paragraph[],
  search: string,
): SearchMatch[] => {
  if (!search || search.length < SEARCH_MIN_LENGTH) return [];

  const matches: SearchMatch[] = [];
  paragraphs.forEach((paragraph) => {
    const indexes = findSearchIndexes(paragraph.value, search);
    indexes.forEach((start) => {
      const index = matches.length;
      matches.push({
        id: `${paragraph.id}:${start}:${index}`,
        paragraphId: paragraph.id,
        start,
        end: start + search.length,
        index,
      });
    });
  });

  return matches;
};

export const searchMatchesToMap = (
  matches: SearchMatch[],
): Map<string, SearchMatch[]> => {
  const map = new Map<string, SearchMatch[]>();

  for (const match of matches) {
    const paragraphMatches = map.get(match.paragraphId) ?? [];
    paragraphMatches.push(match);
    map.set(match.paragraphId, paragraphMatches);
  }

  return map;
};

/**
 * Transform the predictions made by AymurAI into annotations. Also append each search result as an annotation.
 * @param predictions List of AymurAI predictions
 * @param search Search string
 * @param paragraph Paragraph to analyze
 * @param searchLabel Label to assign to the search annotations
 * @returns List of annotations ready to be displayed
 */
export const createAnnotationsWithSearch = (
  predictions: PredictLabel[],
  searchMatches: SearchMatch[],
  searchLabel: AllLabels | AllLabelsWithSufix | null,
  activeSearchMatchId: string | null,
): Annotation[] => {
  const matchingAnnotations = labelToAnnotation(predictions);
  const searchAnnotations = getSearchAnnotations(
    searchMatches,
    searchLabel,
    activeSearchMatchId,
  );

  return [...matchingAnnotations, ...searchAnnotations];
};
