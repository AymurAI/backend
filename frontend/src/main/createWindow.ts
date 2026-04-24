import { join } from "node:path";
import { is } from "@electron-toolkit/utils";
import { BrowserWindow, shell } from "electron";

import { DEV_PORT, EXTERNAL_URLS, isDebug, isProduction } from "./env";
import { resolveHTMLPath } from "./utils";

export let mainWindow: BrowserWindow | null;

/**
 * Configures the main `BrowserWindow` with features and handlers
 * @param window Main window created on the main process
 */
function configureWindow(window: BrowserWindow | null) {
  if (!window) {
    throw new Error('"mainWindow" is not defined');
  }
  if (isDebug) {
    window.webContents.openDevTools();
  }
  if (isProduction) {
    window.maximize();
  }

  window.loadURL(resolveHTMLPath());

  // window.webContents.openDevTools();

  /**
   * HANDLERS
   */
  window.on("ready-to-show", () => {
    window.show();
  });

  window.webContents.on("new-window", (e, url) => {
    // Check if the url is in the 'whitelist'
    if (EXTERNAL_URLS.find((val) => url.includes(val))) {
      e.preventDefault();
      shell.openExternal(url);
    }
  });

  // and handlers
  mainWindow?.on("closed", () => {
    mainWindow = null;
  });
}

export default function createWindow() {
  // Creates the browser window.
  mainWindow = new BrowserWindow({
    width: 1366,
    height: 768,
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      sandbox: false,
    },
  });

  // Add configuration
  configureWindow(mainWindow);

  // HMR for renderer base on electron-vite cli.
  // Load the remote URL for development or the local html file for production.
  if (is.dev) {
    mainWindow.loadURL(`http://localhost:${DEV_PORT}`);
  } else {
    mainWindow.loadFile(join(__dirname, "../renderer/index.html"));
  }

  return mainWindow;
}
