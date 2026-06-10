import type { Annotation, Split } from "./types";

const addTrailingText = (splits: Split[], i: number, { start }: Annotation) => {
  if (start > i) {
    splits.push({
      end: start,
      start: i,
      type: "text",
    });
  }
};
const addLeadingText = (splits: Split[], i: number, { length }: string) => {
  if (i < length) {
    splits.push({
      end: length,
      start: i,
      type: "text",
    });
  }
};

const sortTokens = (tokens: Annotation[]) => {
  return tokens.sort((a, b) => a.start - b.start);
};
const rangesOverlap = (a: Annotation, b: Annotation) => {
  return a.start < b.end && b.start < a.end;
};
const isRightConflicting = (splits: Split[], token: Annotation) => {
  return (splits.at(-1)?.end ?? 0) > token.start;
};

const isLeftConflicting = (token: Annotation, next: Annotation | undefined) => {
  if (!next) return false;

  return (
    token.type === "search" && next.type === "tag" && token.end > next.start
  );
};

const mergeSearchIntoTags = (tokens: Annotation[]): Annotation[] => {
  const tags = tokens.filter((token) => token.type === "tag");
  const searches = tokens.filter((token) => token.type === "search");
  const overlappingSearchIds = new Set<string>();

  const enrichedTags = tags.map((tag) => {
    const overlappingSearches = searches.filter((search) =>
      rangesOverlap(tag, search),
    );
    if (overlappingSearches.length === 0) return tag;

    for (const search of overlappingSearches) {
      if (search.searchMatchId) overlappingSearchIds.add(search.searchMatchId);
    }

    const activeSearch =
      overlappingSearches.find((search) => search.isActive) ??
      overlappingSearches[0];

    return {
      ...tag,
      searchMatchId: activeSearch?.searchMatchId,
      searchIndex: activeSearch?.searchIndex,
      isActive: activeSearch?.isActive ?? false,
    };
  });

  const visibleSearches = searches.filter(
    (search) =>
      !search.searchMatchId || !overlappingSearchIds.has(search.searchMatchId),
  );

  return [...enrichedTags, ...visibleSearches];
};

/**
 * Generates a list of splits from a paragraph and a list of annotations
 * @param paragraph Paragraph text to split
 * @param tokens List of annotations
 * @returns List of splits
 */
export const generateSplits = (
  paragraph: string,
  tokens: Annotation[],
): Split[] => {
  if (!tokens.length)
    return [
      {
        start: 0,
        end: paragraph.length,
        type: "text",
      },
    ];

  const sortedTokens = sortTokens(mergeSearchIntoTags(tokens));
  const splits: Split[] = [];
  // Represents the last index used to split
  let i = 0;

  sortedTokens.forEach((token, tokenIndex) => {
    // Avoid token superposition on search tokens
    if (
      isRightConflicting(splits, token) ||
      isLeftConflicting(token, sortedTokens[tokenIndex + 1])
    )
      return;

    // Add trailing text split if necessary
    addTrailingText(splits, i, token);

    splits.push(token);
    // Move the cursor to the last position
    i = token.end;
  });

  // Add a remaining split if the `i` has not reached the end
  addLeadingText(splits, i, paragraph);

  return splits;
};
