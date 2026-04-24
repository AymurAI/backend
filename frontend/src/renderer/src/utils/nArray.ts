/**
 * Creates an ordered array with a length of `n`
 * @param n Amount of values
 * @param base Value to store on each element of the array
 * @returns A `number[]` of `n` length
 */

export default function nArray<T = undefined>(n: number, value: T) {
  const array = Array.from(Array(n).keys()).map(() => {
    if (typeof value === "object") return Object.create(value);
    return value;
  });

  return array;
}
