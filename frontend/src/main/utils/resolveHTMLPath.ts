import path from "node:path";
import { URL } from "node:url";

import { DEV_PORT, isDebug } from "../env";

/**
 * Retrieves the HMTL path to the requested file
 * @param fileName Name of the file, default to `index.html`
 * @returns An HTML path to the file, wether on the file system or the web
 */
export default function resolveHTMLPath(fileName = "index.html") {
  if (isDebug) {
    const url = new URL(`http://localhost:${DEV_PORT}`);

    return url.href;
  }

  const pathToFile = path.resolve(__dirname, "../app", fileName);
  return `file://${pathToFile}`;
}
