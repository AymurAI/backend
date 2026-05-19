import { describe, expect, it } from "vitest";
import { normalizeValidationLabel } from "../validation";

describe("normalizeValidationLabel", () => {
  const base = {
    text: "original",
    start_char: 10,
    end_char: 18,
    attrs: {
      aymurai_label: "PERSONA",
      aymurai_label_subclass: null,
      aymurai_alt_text: null,
      aymurai_alt_start_char: null,
      aymurai_alt_end_char: null,
      aymurai_anonymize: null,
      canonical_entity_id: null,
      aymurai_label_instance: null,
      aymurai_disambiguation: null,
    },
  };

  it("assigns a new UUID mentionId", () => {
    const result = normalizeValidationLabel(base, "para-1");
    expect(result.mentionId).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );
  });

  it("uses alt_text / alt_chars when present", () => {
    const label = {
      ...base,
      attrs: {
        ...base.attrs,
        aymurai_alt_text: "redacted",
        aymurai_alt_start_char: 5,
        aymurai_alt_end_char: 13,
      },
    };
    const result = normalizeValidationLabel(label, "para-1");
    expect(result.text).toBe("redacted");
    expect(result.start_char).toBe(5);
    expect(result.end_char).toBe(13);
  });

  it("falls back to original text / chars when alt fields are absent", () => {
    const result = normalizeValidationLabel(base, "para-1");
    expect(result.text).toBe("original");
    expect(result.start_char).toBe(10);
    expect(result.end_char).toBe(18);
  });

  it("sets paragraphId from parameter", () => {
    const result = normalizeValidationLabel(base, "para-42");
    expect(result.paragraphId).toBe("para-42");
  });

  it("preserves canonical_entity_id from stored validation", () => {
    const label = {
      ...base,
      attrs: { ...base.attrs, canonical_entity_id: "abc-123" },
    };
    const result = normalizeValidationLabel(label, "para-1");
    expect(result.attrs.canonical_entity_id).toBe("abc-123");
  });

  it("preserves aymurai_anonymize flag when false", () => {
    const label = {
      ...base,
      attrs: { ...base.attrs, aymurai_anonymize: false },
    };
    const result = normalizeValidationLabel(label, "para-1");
    expect(result.attrs.aymurai_anonymize).toBe(false);
  });

  it("preserves aymurai_anonymize flag when true", () => {
    const label = {
      ...base,
      attrs: { ...base.attrs, aymurai_anonymize: true },
    };
    const result = normalizeValidationLabel(label, "para-1");
    expect(result.attrs.aymurai_anonymize).toBe(true);
  });

  it("maps null aymurai_anonymize to null (not treated as false)", () => {
    const result = normalizeValidationLabel(base, "para-1");
    expect(result.attrs.aymurai_anonymize).toBeNull();
  });

  it("maps nullish optional attrs to null", () => {
    const result = normalizeValidationLabel(base, "para-1");
    expect(result.attrs.aymurai_disambiguation).toBeNull();
    expect(result.attrs.aymurai_label_instance).toBeNull();
  });
});
