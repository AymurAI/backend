import { describe, expect, it, vi } from "vitest";
import getStoredValidation, {
  normalizeValidationLabel,
} from "../validation";

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function makeController() {
  return new AbortController();
}

function makeParagraph(value: string) {
  return {
    id: value,
    value,
    document_id: "doc-1",
  };
}

function makeRawLabel(
  overrides: Partial<{
    text: string;
    start_char: number;
    end_char: number;
    aymurai_anonymize: boolean | null;
    aymurai_alt_text: string | null;
    aymurai_alt_start_char: number | null;
    aymurai_alt_end_char: number | null;
    canonical_entity_id: string | null;
  }> = {},
) {
  return {
    text: overrides.text ?? "Juan",
    start_char: overrides.start_char ?? 4,
    end_char: overrides.end_char ?? 8,
    attrs: {
      aymurai_label: "PERSONA",
      aymurai_label_subclass: null,
      aymurai_alt_text: overrides.aymurai_alt_text ?? null,
      aymurai_alt_start_char: overrides.aymurai_alt_start_char ?? null,
      aymurai_alt_end_char: overrides.aymurai_alt_end_char ?? null,
      aymurai_anonymize: overrides.aymurai_anonymize ?? true,
      canonical_entity_id: overrides.canonical_entity_id ?? "canon-1",
      aymurai_label_instance: null,
      aymurai_disambiguation: null,
    },
  };
}

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

// ---------------------------------------------------------------------------
// getStoredValidation — offset integrity guard
// ---------------------------------------------------------------------------

vi.mock("@/services/api", () => ({
  default: {
    post: vi.fn(),
    defaults: { baseURL: "http://localhost" },
  },
}));

describe("getStoredValidation — offset integrity guard", () => {
  // The paragraph text is "Sr. Juan fue aquí" (18 chars).
  // "Juan" sits at [4, 8].
  const PARA_TEXT = "Sr. Juan fue aquí";
  const paragraph = makeParagraph(PARA_TEXT);

  async function setupApiResponse(labels: ReturnType<typeof makeRawLabel>[]) {
    const { default: api } = await import("@/services/api");
    vi.mocked(api.post).mockResolvedValueOnce({ data: labels });
  }

  it("returns normalized labels when all active offsets match paragraph text", async () => {
    await setupApiResponse([makeRawLabel()]);

    const result = await getStoredValidation(paragraph, makeController());
    expect(result).not.toBeNull();
    expect(result).toHaveLength(1);
    expect(result![0].text).toBe("Juan");
    expect(result![0].start_char).toBe(4);
    expect(result![0].end_char).toBe(8);
  });

  it("returns null when an active label has a text mismatch (PDF drift scenario)", async () => {
    // offset [4,8] would slice "Juan" from the original text, but the stored
    // label says "Jüan" — simulates the backend having a slightly different PDF
    // extraction that caused the stored text to drift.
    await setupApiResponse([makeRawLabel({ text: "Jüan" })]);

    const result = await getStoredValidation(paragraph, makeController());
    expect(result).toBeNull();
  });

  it("returns null when an active label has out-of-bounds end_char", async () => {
    await setupApiResponse([
      makeRawLabel({ end_char: PARA_TEXT.length + 5 }),
    ]);
    const result = await getStoredValidation(paragraph, makeController());
    expect(result).toBeNull();
  });

  it("returns null when an active label has start_char >= end_char", async () => {
    await setupApiResponse([makeRawLabel({ start_char: 8, end_char: 4 })]);
    const result = await getStoredValidation(paragraph, makeController());
    expect(result).toBeNull();
  });

  it("does NOT apply the offset check to excluded labels (aymurai_anonymize: false)", async () => {
    // An excluded label whose text slice would not match — but since it's
    // excluded it should not block the stored validation from being returned.
    await setupApiResponse([
      makeRawLabel({ aymurai_anonymize: false, text: "ghost" }),
    ]);
    const result = await getStoredValidation(paragraph, makeController());
    // No active labels → every() vacuously true → return the labels
    expect(result).not.toBeNull();
  });

  it("returns [] when the backend returns an empty array (no entities stored)", async () => {
    await setupApiResponse([]);
    const result = await getStoredValidation(paragraph, makeController());
    expect(result).toEqual([]);
  });

  it("returns null on network error (graceful fallback)", async () => {
    const { default: api } = await import("@/services/api");
    vi.mocked(api.post).mockRejectedValueOnce(new Error("Network error"));

    const result = await getStoredValidation(paragraph, makeController());
    expect(result).toBeNull();
  });
});
