import type { DocFile } from "@/types/file";

/**
 * Searches for a specific `DocFile` into an array or state of files
 * @param fileName File to be searched into the array
 * @param files Array or state of `DocFiles`
 * @returns The `DocFile` with the given name
 */
export default function getByName(fileName: string, files: DocFile[]) {
  return files.find(({ data }) => data.name === fileName);
}
