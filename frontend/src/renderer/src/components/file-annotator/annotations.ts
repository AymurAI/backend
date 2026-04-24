import type {
  AllLabels,
  AllLabelsWithSufix,
  PredictLabel,
} from "@/types/aymurai";
import type { Paragraph } from "@/types/file";
import { includes } from "@/utils/regex";
import type { Annotation } from "./types";

export const SEARCH_MIN_LENGTH = 3;

/**
 * Converts a predict label to an annotation
 * @param labels List of predict labels from the API
 * @returns List of annotations
 */
const labelToAnnotation = (labels: PredictLabel[]): Annotation[] => {
  return labels.map(({ start_char, end_char, attrs, paragraphId }) => ({
    start: start_char,
    end: end_char,
    type: "tag",
    tag: attrs.aymurai_label!,
    paragraphId,
  }));
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
  search: string,
  paragraph: Paragraph,
  label: AllLabels | AllLabelsWithSufix | null,
): Annotation[] => {
  if (!search || search.length < SEARCH_MIN_LENGTH) return [];

  const indexes = findSearchIndexes(paragraph.value, search);
  return indexes.map(
    (el) =>
      ({
        start: el,
        end: el + search.length,
        type: "search",
        tag: label,
        paragraphId: paragraph.id,
      }) as Annotation,
  );
};

/**
 * Converts the predictions array into a map with the paragraph id as key
 * @param predictions List of labels predicted by AymurAI
 * @returns A map with the paragraph id as key and an array of predictions as value
 */
const predictionsToMap = (
  predictions: PredictLabel[],
): Map<string, PredictLabel[]> => {
  const map = new Map<string, PredictLabel[]>();

  for (const token of predictions) {
    // Ignore characters
    if ([":", ",", ".", ")", "(", "-", "_"].includes(token.text)) continue;

    if (map.has(token.paragraphId)) {
      map.get(token.paragraphId)!.push(token);
    } else {
      map.set(token.paragraphId, [token]);
    }
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
  search: string,
  paragraph: Paragraph,
  searchLabel: AllLabels | AllLabelsWithSufix | null,
): Annotation[] => {
  const matchingLabels = predictionsToMap(predictions).get(paragraph.id) ?? [];
  const matchingAnnotations = labelToAnnotation(matchingLabels);
  const searchAnnotations = getSearchAnnotations(
    search,
    paragraph,
    searchLabel,
  );

  return [...matchingAnnotations, ...searchAnnotations];
};
