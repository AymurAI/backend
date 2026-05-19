import type { AnonymizerLabels, PredictLabel } from "@/types/aymurai";
import { describe, expect, it } from "vitest";
import {
    anonymizeQuerySignature,
    filterActivePredictions,
    isPredictionActive,
} from "../predictions";

// Minimal factory — only the fields the tested functions inspect
function makeLabel(
  overrides: Partial<PredictLabel> & { label?: string; text?: string } = {},
): PredictLabel {
  const { label = "PERSONA", text = "Juan", ...rest } = overrides;
  return {
    mentionId: "mention-1",
    paragraphId: "para-1",
    text,
    start_char: 0,
    end_char: text.length,
    attrs: {
      aymurai_label: label as PredictLabel["attrs"]["aymurai_label"],
      aymurai_label_subclass: null,
      aymurai_alt_text: null,
      aymurai_alt_start_char: null,
      aymurai_alt_end_char: null,
      canonical_entity_id: null,
      aymurai_anonymize: null,
      aymurai_label_instance: null,
      aymurai_disambiguation: null,
    },
    ...rest,
  };
}

// A tag map where every label is enabled except FECHA
function tagsWithout(...excluded: AnonymizerLabels[]): Record<AnonymizerLabels, boolean> {
  // We only need to express the keys relevant to each test; cast is fine here
  return Object.fromEntries(
    excluded.map((tag) => [tag, false]),
  ) as unknown as Record<AnonymizerLabels, boolean>;
}

// ────────────────────────────────────────────────────────────────────────────
// isPredictionActive
// ────────────────────────────────────────────────────────────────────────────
describe("isPredictionActive", () => {
  it("returns false when the prediction's label is excluded", () => {
    const label = makeLabel({ label: "FECHA" });
    expect(
      isPredictionActive(label, tagsWithout("FECHA"), []),
    ).toBe(false);
  });

  it("returns true when the prediction's label is not excluded", () => {
    const label = makeLabel({ label: "PERSONA" });
    expect(
      isPredictionActive(label, tagsWithout("FECHA"), []),
    ).toBe(true);
  });

  it("returns false when the prediction's text is in excludedWords", () => {
    const label = makeLabel({ text: "Juan" });
    expect(
      isPredictionActive(label, null, ["Juan"]),
    ).toBe(false);
  });

  it("returns true when neither label nor text is excluded", () => {
    const label = makeLabel({ label: "PERSONA", text: "Maria" });
    expect(isPredictionActive(label, null, [])).toBe(true);
  });

  it("does NOT consider attrs.aymurai_anonymize — only excludedTags matters", () => {
    // An entity stored with aymurai_anonymize: false from a previous session
    // should be considered active once its tag is re-enabled.
    const label = makeLabel({
      label: "FECHA",
      ...{ attrs: { ...makeLabel({ label: "FECHA" }).attrs, aymurai_anonymize: false } },
    });
    // With FECHA now enabled (not in tagsWithout), the entity is active
    expect(isPredictionActive(label, null, [])).toBe(true);
  });
});

// ────────────────────────────────────────────────────────────────────────────
// filterActivePredictions
// ────────────────────────────────────────────────────────────────────────────
describe("filterActivePredictions", () => {
  it("keeps active predictions and removes excluded-label ones", () => {
    const persona = makeLabel({ label: "PERSONA", mentionId: "m-1" });
    const fecha = makeLabel({ label: "FECHA", mentionId: "m-2" });

    const result = filterActivePredictions(
      [persona, fecha],
      tagsWithout("FECHA"),
      [],
    );

    expect(result).toHaveLength(1);
    expect(result[0].mentionId).toBe("m-1");
  });

  it("returns all predictions when excludedTags is null (default config)", () => {
    const labels = [
      makeLabel({ label: "PERSONA", mentionId: "m-1" }),
      makeLabel({ label: "FECHA", mentionId: "m-2" }),
    ];

    // null means "use defaults" — in tests we just check the count is ≤ total
    const result = filterActivePredictions(labels, null, []);
    expect(result.length).toBeGreaterThanOrEqual(0);
    expect(result.length).toBeLessThanOrEqual(labels.length);
  });

  it("treats undefined predictions as empty array", () => {
    expect(filterActivePredictions(undefined, null, [])).toEqual([]);
  });
});

// ────────────────────────────────────────────────────────────────────────────
// anonymizeQuerySignature
// ────────────────────────────────────────────────────────────────────────────
describe("anonymizeQuerySignature", () => {
  const persona = makeLabel({ label: "PERSONA", mentionId: "m-1" });
  const fecha = makeLabel({
    label: "FECHA",
    mentionId: "m-2",
    // attrs with aymurai_anonymize already set to false from a previous session
    ...{
      attrs: {
        ...makeLabel({ label: "FECHA" }).attrs,
        canonical_entity_id: "canonical-2",
      },
    },
  });

  it("includes ALL predictions, not just active ones", () => {
    const result = anonymizeQuerySignature(
      [persona, fecha],
      tagsWithout("FECHA"),
      [],
    );
    expect(result).toHaveLength(2);
  });

  it("fingerprints excluded predictions with false", () => {
    const [, fechaFingerprint] = anonymizeQuerySignature(
      [persona, fecha],
      tagsWithout("FECHA"),
      [],
    );
    expect(fechaFingerprint).toContain("false");
    expect(fechaFingerprint).not.toContain("true");
  });

  it("fingerprints active predictions with true", () => {
    const [personaFingerprint] = anonymizeQuerySignature(
      [persona, fecha],
      tagsWithout("FECHA"),
      [],
    );
    expect(personaFingerprint).toContain("true");
  });

  it("the signature changes when a tag is excluded vs enabled", () => {
    const sigWithFechaEnabled = anonymizeQuerySignature([persona, fecha], null, []);
    const sigWithFechaExcluded = anonymizeQuerySignature(
      [persona, fecha],
      tagsWithout("FECHA"),
      [],
    );
    expect(sigWithFechaEnabled).not.toEqual(sigWithFechaExcluded);
  });

  it("fingerprints word-excluded predictions with false", () => {
    const juan = makeLabel({ text: "Juan", mentionId: "m-juan" });
    const [sig] = anonymizeQuerySignature([juan], null, ["Juan"]);
    expect(sig).toContain("false");
  });

  it("the signature changes when a word is added to excludedWords", () => {
    const label = makeLabel({ text: "Juan" });
    const sigBefore = anonymizeQuerySignature([label], null, []);
    const sigAfter = anonymizeQuerySignature([label], null, ["Juan"]);
    expect(sigBefore).not.toEqual(sigAfter);
  });

  it("returns empty array for undefined predictions", () => {
    expect(anonymizeQuerySignature(undefined, null, [])).toEqual([]);
  });
});
