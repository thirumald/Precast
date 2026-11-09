// Static edition: one classic (non-module) IIFE bundle + CSS with fonts inlined, so pages work from file://
// and from any static host (GitHub Pages, SharePoint, S3). Data comes from static/data/snapshot.js.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  define: { "process.env.NODE_ENV": '"production"' },
  publicDir: false,
  build: {
    outDir: "../static/assets",
    emptyOutDir: true,
    chunkSizeWarningLimit: 4000,
    lib: { entry: "src/main.tsx", formats: ["iife"], name: "Precast", fileName: () => "precast.js", cssFileName: "precast" },
  },
});
