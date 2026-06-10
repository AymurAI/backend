import type { FormValue } from "@/hooks/useForm";

/**
 * Spreadsheet's unique identifier
 */
export type SpreadsheetId = string;

/**
 * Type of data that can be written to the dataset
 */
export type WriteValue = FormValue | null;

/**
 * Properties of the whole spreadsheet extracted from the metadata
 */
export type SpreadsheetProperties = {
  title: string;
  locale: string;
  timeZone: string;
};
/**
 * Properties of a single sheet extracted from the metadata
 */
export type SheetProperties = {
  properties: {
    index: number;
    sheetId: number;
    sheetType: string;
    title: string;
    gridProperties: {
      columnCount: number;
      rowCount: number;
    };
  };
};
/**
 * Spreadsheet metadata
 */
export type SpreadsheetMetadata = {
  spreadsheetId: SpreadsheetId;
  spreadsheetUrl: string;
  properties: SpreadsheetProperties;
  sheets: SheetProperties[];
};

/**
 * Response from the `read` endpoint
 */
export type SpreadsheetRange = {
  range: string;
  majorDimension: string;
  values?: string[][];
};

/**
 * Response from the `append` endpoint
 */
export type SpreadsheetAppend = {
  spreadsheetId: SpreadsheetId;
  tableRange: string;
  updates: {
    spreadsheetId: SpreadsheetId;
    updatedRange: string;
    updatedRows: number;
    updatedColumns: number;
    updatedCells: number;
  };
};
