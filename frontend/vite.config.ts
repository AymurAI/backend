/**
 * Vite config for building the renderer as a standalone web app (no Electron).
 * Used by the `dev:web` and `build:web` scripts.
 *
 * Since `root` is set to `src/renderer`, `envDir` points back to the project
 * root so that `.env` files are resolved from there.
 */
import { resolve } from "node:path";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    tanstackRouter({
      target: "react",
      autoCodeSplitting: true,
    }),
    react(),
  ],
  root: "src/renderer",
  envDir: resolve("."),
  server: {
    port: 3000,
  },
  build: {
    outDir: "../../out/renderer",
  },
  resolve: {
    alias: {
      "@": resolve("src/renderer/src"),
    },
  },
});
