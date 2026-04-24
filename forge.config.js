const path = require("node:path");
const fs = require("node:fs");

module.exports = {
  packagerConfig: {
    // This forces forge to only package already builded files
    ignore: ["^\\/public$", "^\\/src$", "^\\/node_modules$", "^\\/[.].+"],
    icon: "public/brand/logo256-text",
    name: "AymurAI",
    protocols: [
      {
        name: "AymurAI",
        schemes: ["aymurai.app"],
      },
    ],
  },
  rebuildConfig: {},
  makers: [
    {
      name: "@electron-forge/maker-squirrel",
      config: {},
    },
    {
      name: "@electron-forge/maker-zip",
      platforms: ["darwin"],
    },
    {
      name: "@electron-forge/maker-deb",
      config: {
        mimeType: ["x-scheme-handler/aymurai.app"],
      },
    },
    {
      name: "@electron-forge/maker-rpm",
      config: {},
    },
  ],
  hooks: {
    packageAfterCopy: async (
      _config,
      buildPath,
      _electronVersion,
      _platform,
      _arch,
    ) => {
      // Create logs in the root directory
      const twoAbove = path.join(buildPath, "../../");
      // const logMessage = `Build Path: ${twoAbove}\nDirname: ${__dirname}\n---\n`;
      // fs.appendFileSync(path.join(__dirname, "logs.txt"), logMessage);

      // biome-ignore lint/style/noVar: Don't know why this is needed
      var src = path.join(__dirname, "build/app/run_server.bat");
      // biome-ignore lint/style/noVar: Don't know why this is needed
      var dst = `${twoAbove}/run_server.bat`;
      fs.cpSync(src, dst, { recursive: true });
    },
  },
};
