/// <reference types="vite/client" />

import { homedir } from "node:os";
import path from "node:path";
import { is } from "@electron-toolkit/utils";

// ------------------------
// CONFIG VARIABLES
// ------------------------

/**
 * Port for the development app
 */
export const DEV_PORT = 3000;

/**
 * Custom URI scheme name
 */
export const URI_SCHEME = "aymurai.app";

/**
 * Exports folder
 */
export const EXPORTS_FOLDER = path.resolve(homedir(), "Documents/AymurAI");

/**
 * URLs that must be opened in a native browser tab
 */
export const EXTERNAL_URLS = [
  "https://www.datagenero.org/",
  "https://accounts.google.com/o/oauth2/v2/auth",
  "https://docs.google.com/spreadsheets",
  "https://www.aymurai.info",
];

/**
 * Is the app in development mode?
 */
export const isDebug = is.dev;

/**
 * Is the app in production mode?
 */
export const isProduction = !is.dev;

/**
 * Is the app running on Windows?
 */
export const isWindows = process.platform === "win32";

/**
 * Is the app running on macOS?
 */
export const isMac = process.platform === "darwin";
