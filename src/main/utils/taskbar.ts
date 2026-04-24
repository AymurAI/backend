import { app } from "electron";
import { mainWindow } from "../createWindow";
import { isMac, isWindows } from "../env";

/**
 * Notify the user through the taskbar
 */
const notify = () => {
  if (isWindows) {
    if (!mainWindow) return;

    // Flash taskbar icon (windows)
    mainWindow.flashFrame(true);

    mainWindow.once("focus", () => mainWindow?.flashFrame(false));
  } else if (isMac) {
    if (!app || !app.dock) return;

    // Bounce dock icon (macOS)
    app.dock.bounce("informational");
  }
};

const taskbar = {
  notify,
};
export default taskbar;
