import type { FormValue } from "@/hooks/useForm";
import filesystem from "@/services/filesystem";

/**
 * Writes the validated data to the filesystem, creating new rows on the already existent dataset
 * In case there is no dataset, we create a new empty one
 * @param validations Validations to write to the filesystem
 * @returns Returns the recently submitted Workbook
 */
export default async function offline(validations: FormValue[][]) {
  // Opens an already existent Workbook or creates a new one
  const workbook = (await filesystem.excel.read()) ?? filesystem.excel.create();

  const worksheet = workbook.worksheets[0];
  worksheet.addRows(validations);

  await filesystem.excel.write(workbook);

  return workbook;
}
