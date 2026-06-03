import type { Workbook } from "exceljs";
import { downloadBlob } from "../browser/download";
import filesystemAPI from "../utils";

const DATASET_FILENAME = "set_de_datos.xlsx";

/**
 * Writes the `.xlsx` in Buffer format to the filesystem
 * @param buffer Data buffer representing the `.xlsx` file
 */
export default async function write(workbook: Workbook) {
  const buffer = await workbook.xlsx.writeBuffer();

  if (window.filesystem) {
    return filesystemAPI().excel.write(buffer);
  }

  downloadBlob(
    new Blob([buffer], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }),
    DATASET_FILENAME,
  );
}
