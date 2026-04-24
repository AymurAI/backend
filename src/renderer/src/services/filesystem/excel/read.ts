import { Workbook } from "exceljs";

import logger from "@/utils/logger";
import filesystemAPI from "../utils";

/**
 * Read the `.xlsx` and loads its data into a Workbook instance
 * @returns A ExcelJS `Workbook` instance if the `.xlsx` file can be opened, `null` otherwise
 */
export default async function read() {
  try {
    const buffer = await filesystemAPI().excel.read();

    const workbook = new Workbook();
    const loaded = await workbook.xlsx.load(buffer);

    return loaded;
  } catch (e) {
    logger.error("An error ocurred while trying to read the XLSX file: ", e);
    return null;
  }
}
