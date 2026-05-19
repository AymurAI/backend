import { useMemo } from "react";

import type { PredictLabel } from "@/types/aymurai";
import type { DocFile } from "@/types/file";
import {
  normalizeEntityText,
  stripEntityLabelSuffix,
} from "@/utils/anonymizer/entity-similarity";

// ─── Public types ─────────────────────────────────────────────────────────────

export interface EntityGroup {
  /** The canonical_entity_id that identifies this group. */
  canonicalId: string;
  /** aymurai_label with numeric suffix stripped (e.g. "PER", "DNI"). */
  renderBase: string;
  /** 1-indexed position among all groups sharing the same renderBase, ordered
   *  by first appearance (paragraphIndex then start_char). */
  suffixIndex: number;
  /** Human-readable render token shown to the user (e.g. "PER_1"). */
  renderToken: string;
  /** All individual mention predictions belonging to this group. */
  mentions: PredictLabel[];
  /** Deduplicated normalised texts, sorted alphabetically. Used internally for matching. */
  uniqueTexts: string[];
  /** Verbatim texts corresponding 1-to-1 with {@link uniqueTexts}. Each inner array holds all distinct
   * surface forms that share the same normalised text (e.g. ["PUERTO BELGRANO", "Puerto Belgrano"]).
   * Use for display; use {@link uniqueTexts} for matching/removal. */
  displayTexts: string[][];
  /** Location of the earliest mention, for ordering and UX. */
  firstAppearance: { paragraphIndex: number; start_char: number };
  /** Whether the group should be anonymised (majority vote from mentions). */
  anonymize: boolean;
  /** True when another group has the same renderBase and uniqueTexts set. */
  isDuplicate: boolean;
  /** canonicalId of the earliest group that is identical to this one. */
  duplicateOf: string | null;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Strip a numeric suffix like `_1`, `_12` from a label string. */
export function stripSuffix(label: string): string {
  return stripEntityLabelSuffix(label);
}

// ─── Main hook ────────────────────────────────────────────────────────────────

/**
 * Derives a flat array of {@link EntityGroup} objects from all predictions
 * across the provided files.
 *
 * Groups are identified by `canonical_entity_id`. Mentions without a
 * canonical id are silently skipped (they are raw predict results that haven't
 * been through the disambiguate step yet).
 *
 * Suffix indices are assigned by first-appearance order per `renderBase`.
 * Duplicate detection compares `(renderBase, uniqueTexts)`.
 */
export function useEntityGroups(files: DocFile[]): EntityGroup[] {
  return useMemo(() => {
    // Build a paragraphId → index map across all files so we can order
    // mentions by paragraph position.
    const paragraphIndexByParagraphId = new Map<string, number>();
    for (const file of files) {
      for (const [i, p] of (file.paragraphs ?? []).entries()) {
        if (!paragraphIndexByParagraphId.has(p.id)) {
          paragraphIndexByParagraphId.set(p.id, i);
        }
      }
    }

    // Accumulate mentions per canonicalId, plus track renderBase and first appearance.
    const byCanonicalId = new Map<
      string,
      {
        mentions: PredictLabel[];
        renderBase: string;
        firstAppearance: { paragraphIndex: number; start_char: number };
      }
    >();

    for (const file of files) {
      for (const pred of file.predictions ?? []) {
        const { canonical_entity_id, aymurai_label } = pred.attrs;
        if (!canonical_entity_id) continue;

        const renderBase = stripSuffix(String(aymurai_label));
        const paragraphIndex =
          paragraphIndexByParagraphId.get(pred.paragraphId) ?? 0;

        if (!byCanonicalId.has(canonical_entity_id)) {
          byCanonicalId.set(canonical_entity_id, {
            mentions: [],
            renderBase,
            firstAppearance: {
              paragraphIndex,
              start_char: pred.start_char,
            },
          });
        }

        const entry = byCanonicalId.get(canonical_entity_id);
        if (!entry) continue;
        entry.mentions.push(pred);

        // Keep the earliest appearance
        const fa = entry.firstAppearance;
        if (
          paragraphIndex < fa.paragraphIndex ||
          (paragraphIndex === fa.paragraphIndex &&
            pred.start_char < fa.start_char)
        ) {
          fa.paragraphIndex = paragraphIndex;
          fa.start_char = pred.start_char;
        }
      }
    }

    // Sort canonicalIds by first appearance so suffix numbering is stable and
    // matches the document reading order (same as backend behaviour).
    const sorted = [...byCanonicalId.entries()].sort(([, a], [, b]) => {
      const aPara = a.firstAppearance.paragraphIndex;
      const bPara = b.firstAppearance.paragraphIndex;
      if (aPara !== bPara) return aPara - bPara;
      return a.firstAppearance.start_char - b.firstAppearance.start_char;
    });

    // Assign suffix indices per renderBase.
    const suffixCounter = new Map<string, number>();
    const suffixByCanonicalId = new Map<string, number>();
    for (const [canonicalId, { renderBase }] of sorted) {
      const next = (suffixCounter.get(renderBase) ?? 0) + 1;
      suffixCounter.set(renderBase, next);
      suffixByCanonicalId.set(canonicalId, next);
    }

    // Build EntityGroup objects.
    const groups: EntityGroup[] = sorted.map(
      ([canonicalId, { mentions, renderBase, firstAppearance }]) => {
        // Build normalised → first distinct verbatim form seen for that normalisation.
        // We intentionally keep only ONE display representative per normalised bucket:
        // multiple document spans may share the same alias and we don't want to show
        // the same alias chip multiple times. Verbatim comparison uses NFC so that
        // Unicode-composed and decomposed forms of the same visible character are
        // treated as identical.
        const normalizedToVerbatims = new Map<string, string[]>();
        for (const m of mentions) {
          const norm = normalizeEntityText(m.text);
          if (!norm) continue;
          const existing = normalizedToVerbatims.get(norm);
          if (!existing) {
            normalizedToVerbatims.set(norm, [m.text]);
          } else if (
            !existing.some(
              (v) =>
                v.normalize("NFC") === m.text.normalize("NFC"),
            )
          ) {
            existing.push(m.text);
          }
        }
        const uniqueTexts = [...normalizedToVerbatims.keys()].sort();
        const displayTexts = uniqueTexts.map(
          (t) => normalizedToVerbatims.get(t) ?? [],
        );

        const anonymizeCount = mentions.filter(
          (m) => m.attrs.aymurai_anonymize !== false,
        ).length;
        const anonymize = anonymizeCount >= mentions.length / 2;

        const suffixIndex = suffixByCanonicalId.get(canonicalId) ?? 1;

        return {
          canonicalId,
          renderBase,
          suffixIndex,
          renderToken: `${renderBase}_${suffixIndex}`,
          mentions,
          uniqueTexts,
          displayTexts,
          firstAppearance,
          anonymize,
          isDuplicate: false,
          duplicateOf: null,
        };
      },
    );

    // Duplicate / overlap detection: any two groups under the same renderBase
    // that share at least one normalised mention text are flagged as merge
    // candidates.
    //
    // The detection key uses a SORTED-TOKEN fingerprint of the normalised text
    // so that name variants differing only in token order
    // (e.g. "Pérez, Laura Beatriz" vs "Laura Beatriz Pérez") are recognised as
    // the same alias and trigger a merge suggestion.
    //
    // Primary rule: the group with MORE unique texts is primary (it's more
    // "established"). Ties are broken by first-appearance order (already the
    // iteration order). When a later group turns out to have more texts than
    // the registered primary, they swap roles.

    /** Sorted-token fingerprint — collapses token-order variants of a name. */
    const sortedFingerprint = (normText: string): string =>
      [...new Set(normText.split(" "))].sort().join(" ");

    const textToGroup = new Map<string, string>(); // key → primary canonicalId
    const groupById = new Map(groups.map((g) => [g.canonicalId, g]));

    for (const group of groups) {
      let conflictPrimaryId: string | null = null;

      for (const normText of group.uniqueTexts) {
        const key = `${group.renderBase}\x01${sortedFingerprint(normText)}`;
        const existing = textToGroup.get(key);
        if (existing && existing !== group.canonicalId) {
          conflictPrimaryId = existing;
          break;
        }
      }

      if (conflictPrimaryId !== null) {
        const primaryGroup = groupById.get(conflictPrimaryId);
        if (!primaryGroup) continue;

        if (group.uniqueTexts.length > primaryGroup.uniqueTexts.length) {
          // Current group has more texts → it becomes the new primary;
          // old primary is demoted to duplicate.
          primaryGroup.isDuplicate = true;
          primaryGroup.duplicateOf = group.canonicalId;
          // Re-register all previously-registered keys under new primary.
          for (const normText of primaryGroup.uniqueTexts) {
            textToGroup.set(
              `${primaryGroup.renderBase}\x01${sortedFingerprint(normText)}`,
              group.canonicalId,
            );
          }
          for (const normText of group.uniqueTexts) {
            textToGroup.set(
              `${group.renderBase}\x01${sortedFingerprint(normText)}`,
              group.canonicalId,
            );
          }
        } else {
          // Existing primary has equal or more texts → current is duplicate.
          group.isDuplicate = true;
          group.duplicateOf = conflictPrimaryId;
          // Register any new texts under the existing primary.
          for (const normText of group.uniqueTexts) {
            const key = `${group.renderBase}\x01${sortedFingerprint(normText)}`;
            if (!textToGroup.has(key)) textToGroup.set(key, conflictPrimaryId);
          }
        }
      } else {
        // No conflict — register all own texts as primary.
        for (const normText of group.uniqueTexts) {
          textToGroup.set(
            `${group.renderBase}\x01${sortedFingerprint(normText)}`,
            group.canonicalId,
          );
        }
      }
    }

    return groups;
  }, [files]);
}
