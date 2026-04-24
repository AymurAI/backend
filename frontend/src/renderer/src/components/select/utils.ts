import type { Necessary } from "@/types/utils";
import { removeUndefined } from "@/utils/filtering";
import { includes } from "@/utils/regex";
import type { SelectOption, Suggestion } from ".";

/**
 * Returns a `SelectOption` based on the given `id`
 * @param id ID to use as a filter
 * @param options Current `SelectOption[]` array
 * @returns Returns the already existent option in the array or `undefined` if it doesn't exist on the array
 */
export function findById(
  id: SelectOption["id"] | undefined,
  options: SelectOption[],
) {
  return options.find((op) => op.id === id);
}

/**
 * Makes sure the text of the suggestion is defined in any way
 * @param suggestion Suggestion to analyze
 * @param options Options array from the JSON file
 * @returns Same `Suggestion` format
 */
export function secureSuggestion(
  suggestion: Suggestion | undefined,
  options: SelectOption[],
): Necessary<Suggestion, "text"> | undefined {
  if (suggestion) {
    const { text, id } = suggestion;

    if (text) return { id, text };

    const option = findById(id, options);
    return option;
  }
  return undefined;
}

/**
 * Re-orders the options array
 * @param options Options array from the JSON file
 * @param priority `id[]` of the options to prioritize
 * @returns A reordered array with the priority options placed on first place
 */
export function orderByPriority(
  options: SelectOption[],
  priority: SelectOption["id"][] = [],
) {
  // Remove priority options from the array
  const filtered = options.filter(({ id }) => !priority.find((p) => p === id));

  // Find preferred { id, text } on the original options array
  const preferred = priority
    .map((p) => options.find(({ id }) => p === id))
    .filter(removeUndefined);

  // Add the preferred options
  return [...preferred, ...filtered];
}

/**
 * Filters the options array based on the given word
 * @param options Options array from the JSON file
 * @param word Word to use as a filter
 * @returns Returns the options that match the given word
 */
export function filterOptions(options: SelectOption[], word: string) {
  return options.filter(({ text }) => text.match(includes(word)));
}
