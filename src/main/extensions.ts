import installer, {
  REACT_DEVELOPER_TOOLS,
  EMBER_INSPECTOR,
} from "electron-devtools-installer";

export const installExtensions = async (): Promise<unknown> => {
  const extensions = [EMBER_INSPECTOR, REACT_DEVELOPER_TOOLS];

  return installer(extensions, {
    forceDownload: true,
    loadExtensionOptions: {
      allowFileAccess: true,
    },
  })
    .then(console.log)
    .catch(console.error);
};
