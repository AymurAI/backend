import { electronApp, optimizer } from "@electron-toolkit/utils";
import { BrowserWindow, app, ipcMain } from "electron";

import createWindow from "./createWindow";
import { installExtensions } from "./extensions";
import { excel, feedback, subprocess, taskbar } from "./utils";

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(async () => {
  // Set app user model id for windows
  electronApp.setAppUserModelId("com.electron");

  // Default open or close DevTools by F12 in development
  // and ignore CommandOrControl + R in production.
  // see https://github.com/alex8088/electron-toolkit/tree/master/packages/utils
  app.on("browser-window-created", (_, window) => {
    optimizer.watchWindowShortcuts(window);
  });

  ipcMain.handle("EXPORT_FEEDBACK", (_, fileName: string, data: object) =>
    feedback.export(fileName, data),
  );
  ipcMain.handle("EXCEL_READ", excel.read);
  ipcMain.handle("EXCEL_WRITE", (_, buffer: ArrayBuffer) =>
    excel.write(buffer),
  );
  ipcMain.handle("EXCEL_OPEN", excel.open);

  // TASKBAR
  ipcMain.handle("TASKBAR_NOTIFY", taskbar.notify);

  ipcMain.handle("RUN_BATCH", subprocess.run);

  await installExtensions();
  createWindow();

  app.on("activate", () => {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on("window-all-closed", async () => {
  subprocess.stop();
  if (process.platform !== "darwin") {
    app.quit();
  }
});
