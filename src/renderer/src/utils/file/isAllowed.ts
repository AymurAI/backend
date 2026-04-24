import { WHITELISTED_EXTENSIONS } from "@/utils/config";
import getExtension from "./getExtension";

/**
 * Runs a check on a file, validating its extension
 * @param file `File` to check
 * @returns `true` if the file is allowed, `false` otherwise
 */
export default function isAllowed(file: File) {
  return !!WHITELISTED_EXTENSIONS.find((ext) => ext === getExtension(file));
}
