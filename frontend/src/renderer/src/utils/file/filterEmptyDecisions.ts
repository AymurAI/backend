import type { FormData } from "@/hooks/useForm";

type Decision = Exclude<FormData["DECISIONES"], undefined>[number];

/**
 * Checks for the contents of a `Decision`
 * @param decision Decision to analyze
 * @returns `true` if the decision is empty, `false otherwise`
 */
function isDecisionEmpty(decision: Decision) {
  const copy = { ...decision };

  // Loop through the object, deleting undefined entries
  for (const key in copy) {
    if (!copy[key as keyof typeof copy]) delete copy[key as keyof typeof copy];
  }

  return !Object.keys(copy).length;
}

/**
 * Filters the decisions array to remove any empty decision
 * @param decisions `Decision[]` to analyze
 * @returns A filtered array of the original `Decision[]`
 */
export default function filterEmptyDecisions(
  decisions: Decision[] | undefined,
) {
  if (decisions) return decisions.filter((dec) => !isDecisionEmpty(dec));
  return [];
}
