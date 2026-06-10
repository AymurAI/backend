import type { FormValue } from "@/hooks/useForm";
import filesystem from "@/services/filesystem";
import type { Workbook } from "exceljs";

/**
 * Writes the validated data to the filesystem, creating new rows on the already existent dataset
 * In case there is no dataset, we create a new empty one
 * @param validations Validations to write to the filesystem
 * @returns Returns the recently submitted Workbook
 */
function getWritableWorkbook(workbook: Workbook | null) {
  if (!workbook || workbook.worksheets.length === 0) {
    return filesystem.excel.create();
  }

  return workbook;
}

export default async function offline(validations: FormValue[][]) {
  // Opens an already existent Workbook or creates a new one
  const workbook = getWritableWorkbook(await filesystem.excel.read());

  const worksheet = workbook.worksheets[0];
  worksheet.addRows(validations);

  await filesystem.excel.write(workbook);

  return workbook;
}
