/**
 * Extracts the extension of the given file
 * @param file File to extract its extension
 * @returns Extension string of the file (formatted as `doc | docx`)
 */
export default function getExtension(file: File) {
  return file.name.split(".").at(-1);
}
