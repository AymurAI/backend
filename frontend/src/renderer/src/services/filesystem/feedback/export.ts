import type { DocFile } from "@/types/file";
import { downloadBlob } from "../browser/download";
import filesystemAPI from "../utils";
import { joinValidation } from "./utils";

function getDate() {
  const now = new Date(Date.now());
  const [date, time] = now.toISOString().split("T");

  return `${date}-${time.split(".")[0].replace(/:/g, "_")}`;
}

function formatName(fileName: string) {
  const formattedName = fileName.replace(/\.docx/g, "").replace(/\s/g, "_");

  return `aymurai--${formattedName}`;
}

function exportFeedbackFromBrowser(fileName: string, content: object) {
  const json = JSON.stringify(content);
  const filename = `${formatName(fileName)}--${getDate()}.json`;

  downloadBlob(new Blob([json], { type: "application/json" }), filename);
}

/**
 * Exports the file validation and predictions as a JSON file
 * @param file File to be exported
 */
export default async function exportFeedback(files: DocFile[]) {
  for (const file of files) {
    const { name } = file.data;

    const feedback = joinValidation(file);

    if (window.filesystem) {
      await filesystemAPI().feedback.export(name, feedback);
    } else {
      exportFeedbackFromBrowser(name, feedback);
    }
  }
}
