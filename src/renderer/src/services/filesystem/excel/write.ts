import type { Workbook } from "exceljs";
import filesystemAPI from "../utils";

/**
 * Writes the `.xlsx` in Buffer format to the filesystem
 * @param buffer Data buffer representing the `.xlsx` file
 */
export default async function write(workbook: Workbook) {
  const buffer = await workbook.xlsx.writeBuffer();

  return filesystemAPI().excel.write(buffer);
}
