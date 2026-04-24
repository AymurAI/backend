import type { DocFile } from "@/types/file";

/**
 * Checks if a file has been at least partially validated
 * @param selectedFile Current selected file
 * @returns `true` if the file has any validation made, `false` otherwise
 */
export default function isFileValidated(selectedFile: DocFile) {
  return Object.keys(selectedFile.validationObject).length > 0;
}
