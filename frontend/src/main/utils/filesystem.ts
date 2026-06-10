import fs from "node:fs/promises";

/**
 * Check for the existence of a specific director or file
 * @param path Path to check
 * @returns `true` if the directory/file exists, `false` otherwise
 */
async function exists(path: string) {
  try {
    await fs.access(path, fs.constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

const filesystem = {
  exists,
};
export default filesystem;
