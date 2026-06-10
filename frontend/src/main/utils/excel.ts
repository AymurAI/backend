import fs from "node:fs/promises";
import { shell } from "electron";

import { EXPORTS_FOLDER } from "../env";
import filesystem from "./filesystem";

const FILENAME = "set_de_datos.xlsx";
const PATH = `${EXPORTS_FOLDER}/${FILENAME}`;

/**
 * Reads the raw data from the data_set excel file
 * @returns The `Promise<Buffer>` read from the file
 */
function read() {
  return fs.readFile(PATH).then(({ buffer }) => buffer);
}

/**
 * Writes a .xlsx file to the filesystem
 * @param buffer Data buffer to write. This is the .xlsx file
 */
async function write(arrBuffer: ArrayBuffer) {
  // Create directory if necessary
  if (!(await filesystem.exists(EXPORTS_FOLDER))) {
    await fs.mkdir(EXPORTS_FOLDER, { recursive: true });
  }

  await fs.writeFile(PATH, Buffer.from(arrBuffer));
}

/**
 * Opens the previously created .xlsx using the default app
 * @returns Message if the opening was succesfull or not
 */
function open() {
  return shell.openPath(PATH);
}

const excel = {
  read,
  write,
  open,
};
export default excel;
