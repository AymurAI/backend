import { promises as fs } from "node:fs";

import { EXPORTS_FOLDER } from "../env";
import filesystem from "./filesystem";

const FEEDBACK_FOLDER = `${EXPORTS_FOLDER}/feedback`;

/**
 * Gets the current date and time in the format `YYYY-MM-DD-HH_MM_SS`
 */
function getDate() {
  const now = new Date(Date.now());
  const [date, time] = now.toISOString().split("T");

  const fileDate = `${date}-${
    time // Time in format xx:yy:zz.zzz
      .split(".")[0] // We are left with xx:yy:zz
      .replace(/:/g, "_") // Transform it into xx_yy_zz
  }`;

  return fileDate;
}

function formatName(fileName: string) {
  // Remove extension and spaces from the name
  const formattedName = fileName
    .replace(/\.docx/g, "") // Remove extension
    .replace(/\s/g, "_"); // Remove whitespace

  return `aymurai--${formattedName}`;
}

async function mkdir() {
  await fs.mkdir(FEEDBACK_FOLDER, { recursive: true });
}

/**
 * Parses a validation object into a JSON that is written into a feedback file
 * @param fileName Name of the file
 * @param content Validation object
 */
async function exportFeedback(fileName: string, content: object) {
  const date = getDate();
  const name = formatName(fileName);
  const json = JSON.stringify(content);

  // Create directory if necessary
  if (!(await filesystem.exists(FEEDBACK_FOLDER))) {
    await mkdir();
  }

  // Create file
  await fs.writeFile(`${FEEDBACK_FOLDER}/${name}--${date}.json`, json, {
    flag: "w",
  });
}

const feedback = {
  export: exportFeedback,
};
export default feedback;
