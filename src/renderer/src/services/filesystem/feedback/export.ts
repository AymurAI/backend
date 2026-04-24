import type { DocFile } from "@/types/file";
import filesystemAPI from "../utils";
import { joinValidation } from "./utils";

/**
 * Exports the file validation and predictions as a JSON file
 * @param file File to be exported
 */
export default async function exportFeedback(files: DocFile[]) {
  for (const file of files) {
    const { name } = file.data;

    const feedback = joinValidation(file);

    await filesystemAPI().feedback.export(name, feedback);
  }
}
