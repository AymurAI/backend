import type { PredictLabel } from "@/types/aymurai";

export default function countDecisiones(
  predictions: PredictLabel[] | undefined,
) {
  if (!predictions) return 0;

  const amount = predictions.reduce((prev, label) => {
    const subclass = label.attrs.aymurai_label_subclass ?? [];

    // If we found this subclass, it means we are facing a decision
    if (subclass.some((text) => text === "hace_lugar")) return prev + 1;
    return prev;
  }, 0);

  // Default the decisions to 1 if no decision was found
  // This is because we always have at least 1 decision active per file, no matter the predictions array
  return amount === 0 ? 1 : amount;
}
