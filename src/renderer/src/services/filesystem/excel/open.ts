import logger from "@/utils/logger";
import filesystemAPI from "../utils";

/**
 * Opens the Excel file
 */
export default async function open() {
  const result = await filesystemAPI().excel.open();

  // If we get some string as a result from opening the file, we have an error
  if (result !== "")
    logger.error("There was an error while opening the XLSX file!: ", result);
}
