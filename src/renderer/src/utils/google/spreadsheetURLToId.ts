import type { SpreadsheetId } from "@/types/spreadsheet";

/**
 * Converts an spreadsheet URL into an `SpreadsheetId`
 * @param url DataSet URL
 * @returns The `SpreadsheetId` of the dataset
 */
export default function spreadsheetURLToId(url: string): SpreadsheetId {
  const split = url.split("/");
  const pageIndex = split.indexOf("spreadsheets");

  // + 1 equals to the '/d/' in the url
  // + 2 equals to the id we are looking for
  const id = split[pageIndex + 2];

  return id;
}
