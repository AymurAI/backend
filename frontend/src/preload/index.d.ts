declare global {
  interface Window {
    filesystem?: {
      feedback: {
        export: (fileName: string, data: object) => Promise<void>;
      };
      excel: {
        read: () => Promise<ArrayBuffer>;
        write: (arrBuffer: ArrayBuffer) => Promise<void>;
        open: () => Promise<string>;
      };
    };
    taskbar?: {
      notify: () => Promise<void>;
    };
    electronAPI?: {
      runBatch: () => Promise<void>;
    };
  }
}

export {};
