/**
 * Checks the type of an object. This util function is meant to be used along the `.filter()` array function
 * @example array.filter(removeUndefined);
 * @param obj Object to analyze
 * @returns `true` if the object is not undefined, `false` otherwise
 */
export function removeUndefined<T>(obj: T | undefined): obj is T {
  return obj !== undefined;
}
