import { electronAPI } from "@electron-toolkit/preload";
import { contextBridge, ipcRenderer } from "electron";

// Custom APIs for renderer
const api = {};

// Use `contextBridge` APIs to expose Electron APIs to
// renderer only if context isolation is enabled, otherwise
// just add to the DOM global.
if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld("filesystem", {
      feedback: {
        export: (fileName: string, object: object) =>
          ipcRenderer.invoke("EXPORT_FEEDBACK", fileName, object),
      },
      excel: {
        read: () => ipcRenderer.invoke("EXCEL_READ"),
        write: (buffer: Buffer) => ipcRenderer.invoke("EXCEL_WRITE", buffer),
        open: () => ipcRenderer.invoke("EXCEL_OPEN"),
      },
    });

    contextBridge.exposeInMainWorld("taskbar", {
      notify: () => ipcRenderer.invoke("TASKBAR_NOTIFY"),
    });

    contextBridge.exposeInMainWorld("electronAPI", {
      runBatch: (result: unknown) => ipcRenderer.invoke("RUN_BATCH", result),
    });
  } catch (error) {
    console.error(error);
  }
} else {
  // @ts-ignore (define in dts)
  window.electron = electronAPI;
  // @ts-ignore (define in dts)
  window.api = api;
}
