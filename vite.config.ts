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
