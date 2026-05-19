export interface EntityMentionDraft {
  text: string;
  normalizedText?: string;
  label: string;
  paragraphId?: string;
  start_char?: number;
  end_char?: number;
}

export interface SimilarityOptions {
  threshold?: number;
  maxCandidates?: number;
}

export interface EntityGroupForSimilarity {
  canonicalId: string;
  renderBase: string;
  renderToken: string;
  uniqueTexts: string[];
  displayTexts: string[][];
  firstAppearance: { paragraphIndex: number; start_char: number };
}

export interface SimilarEntityGroupCandidate {
  group: EntityGroupForSimilarity;
  score: number;
  labelMatches: boolean;
  matchedText: string;
}

export type ManualEntityResolution =
  | { type: "existing"; candidate: SimilarEntityGroupCandidate }
  | { type: "new" };

const DEFAULT_THRESHOLD = 80;
const DEFAULT_MAX_CANDIDATES = 5;
const FIRST_COMBINING_MARK = 0x0300;
const LAST_COMBINING_MARK = 0x036f;

export function stripEntityLabelSuffix(label: string): string {
  return label.replace(/_\d+$/, "");
}

export function normalizeEntityText(text: string): string {
  const withoutDiacritics = Array.from(text.normalize("NFD"))
    .filter((char) => {
      const code = char.charCodeAt(0);
      return code < FIRST_COMBINING_MARK || code > LAST_COMBINING_MARK;
    })
    .join("");

  return withoutDiacritics
    .normalize("NFD")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function tokenize(text: string): string[] {
  const normalized = normalizeEntityText(text);
  if (!normalized) return [];
  return [...new Set(normalized.split(" "))].sort();
}

function levenshteinRatio(a: string, b: string): number {
  if (a === b) return 100;
  if (!a || !b) return 0;

  const previous = Array.from({ length: b.length + 1 }, (_, i) => i);
  const current = new Array<number>(b.length + 1);

  for (let i = 1; i <= a.length; i += 1) {
    current[0] = i;
    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      current[j] = Math.min(
        current[j - 1] + 1,
        previous[j] + 1,
        previous[j - 1] + cost,
      );
    }
    previous.splice(0, previous.length, ...current);
  }

  const distance = previous[b.length] ?? 0;
  return Math.round((1 - distance / Math.max(a.length, b.length)) * 100);
}

function bigrams(text: string): string[] {
  if (text.length <= 1) return text ? [text] : [];
  const result: string[] = [];
  for (let i = 0; i < text.length - 1; i += 1) {
    result.push(text.slice(i, i + 2));
  }
  return result;
}

function bigramRatio(a: string, b: string): number {
  if (a === b) return 100;
  if (!a || !b) return 0;

  const aBigrams = bigrams(a);
  const bBigrams = bigrams(b);
  const counts = new Map<string, number>();
  for (const gram of aBigrams) counts.set(gram, (counts.get(gram) ?? 0) + 1);

  let overlap = 0;
  for (const gram of bBigrams) {
    const count = counts.get(gram) ?? 0;
    if (count > 0) {
      overlap += 1;
      counts.set(gram, count - 1);
    }
  }

  return Math.round((2 * overlap * 100) / (aBigrams.length + bBigrams.length));
}

function stringRatio(a: string, b: string): number {
  return Math.max(levenshteinRatio(a, b), bigramRatio(a, b));
}

function sortedTokenText(tokens: string[]): string {
  return tokens.join(" ");
}

export function computeEntitySimilarity(a: string, b: string): number {
  const aTokens = tokenize(a);
  const bTokens = tokenize(b);

  if (aTokens.length === 0 || bTokens.length === 0) return 0;

  const aSet = new Set(aTokens);
  const bSet = new Set(bTokens);
  const intersection = aTokens.filter((token) => bSet.has(token));
  const diffA = aTokens.filter((token) => !bSet.has(token));
  const diffB = bTokens.filter((token) => !aSet.has(token));

  const intersectionText = sortedTokenText(intersection);
  const combinedA = sortedTokenText([...intersection, ...diffA].sort());
  const combinedB = sortedTokenText([...intersection, ...diffB].sort());

  if (!intersectionText) return stringRatio(combinedA, combinedB);

  return Math.max(
    stringRatio(intersectionText, combinedA),
    stringRatio(intersectionText, combinedB),
    stringRatio(combinedA, combinedB),
  );
}

interface GroupCandidateText {
  comparisonText: string;
  displayText: string;
}

function groupCandidateTexts(
  group: EntityGroupForSimilarity,
): GroupCandidateText[] {
  const texts: GroupCandidateText[] = [];
  const seenDisplayTexts = new Set<string>();

  group.uniqueTexts.forEach((uniqueText, index) => {
    const verbatims = group.displayTexts[index] ?? [];

    if (verbatims.length === 0) {
      texts.push({ comparisonText: uniqueText, displayText: uniqueText });
      return;
    }

    for (const verbatim of verbatims) {
      if (seenDisplayTexts.has(verbatim)) continue;
      seenDisplayTexts.add(verbatim);
      texts.push({ comparisonText: verbatim, displayText: verbatim });
    }
  });

  return texts;
}

export function findSimilarEntityGroups(
  newMention: EntityMentionDraft,
  groups: EntityGroupForSimilarity[],
  options: SimilarityOptions = {},
): SimilarEntityGroupCandidate[] {
  const threshold = options.threshold ?? DEFAULT_THRESHOLD;
  const maxCandidates = options.maxCandidates ?? DEFAULT_MAX_CANDIDATES;
  const selectedLabel = stripEntityLabelSuffix(newMention.label);
  const mentionText = newMention.normalizedText ?? newMention.text;

  const candidates = groups
    .map((group) => {
      let bestScore = 0;
      let bestText = "";

      for (const text of groupCandidateTexts(group)) {
        const score = computeEntitySimilarity(mentionText, text.comparisonText);
        if (score > bestScore) {
          bestScore = score;
          bestText = text.displayText;
        }
      }

      return {
        group,
        score: bestScore,
        labelMatches:
          selectedLabel === stripEntityLabelSuffix(String(group.renderBase)),
        matchedText: bestText,
      } satisfies SimilarEntityGroupCandidate;
    })
    .filter((candidate) => candidate.score >= threshold);

  return candidates
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      if (a.labelMatches !== b.labelMatches) return a.labelMatches ? -1 : 1;
      const aFirst = a.group.firstAppearance;
      const bFirst = b.group.firstAppearance;
      if (aFirst.paragraphIndex !== bFirst.paragraphIndex) {
        return aFirst.paragraphIndex - bFirst.paragraphIndex;
      }
      return aFirst.start_char - bFirst.start_char;
    })
    .slice(0, maxCandidates);
}
