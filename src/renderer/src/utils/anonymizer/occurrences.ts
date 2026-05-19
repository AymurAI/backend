import { normalizeEntityText } from "./entity-similarity";

export interface NormalizedOccurrenceRange {
  start: number;
  end: number;
  text: string;
  normalizedText: string;
}

interface NormalizedToken {
  start: number;
  end: number;
  normalizedText: string;
}

const TOKEN_REGEX = /[\p{L}\p{N}]+/gu;

function normalizedTokens(text: string): NormalizedToken[] {
  const tokens: NormalizedToken[] = [];

  for (const match of text.matchAll(TOKEN_REGEX)) {
    const source = match[0];
    const start = match.index ?? 0;
    const normalizedText = normalizeEntityText(source);
    if (!normalizedText) continue;

    tokens.push({
      start,
      end: start + source.length,
      normalizedText,
    });
  }

  return tokens;
}

export function isNormalizedTextMatch(a: string, b: string): boolean {
  const normalizedA = normalizeEntityText(a);
  return normalizedA !== "" && normalizedA === normalizeEntityText(b);
}

export function findNormalizedOccurrenceRanges(
  text: string,
  search: string,
): NormalizedOccurrenceRange[] {
  const normalizedSearch = normalizeEntityText(search);
  if (!normalizedSearch) return [];

  const searchTokens = normalizedSearch.split(" ");
  const tokens = normalizedTokens(text);
  const ranges: NormalizedOccurrenceRange[] = [];

  for (let i = 0; i <= tokens.length - searchTokens.length; i += 1) {
    const candidate = tokens.slice(i, i + searchTokens.length);
    const candidateText = candidate
      .map((token) => token.normalizedText)
      .join(" ");

    if (candidateText !== normalizedSearch) continue;

    const start = candidate[0]?.start;
    const end = candidate.at(-1)?.end;
    if (start === undefined || end === undefined) continue;

    ranges.push({
      start,
      end,
      text: text.slice(start, end),
      normalizedText: normalizedSearch,
    });
  }

  return ranges;
}
