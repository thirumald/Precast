import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: Object.fromEntries(["/api", "/docs", "/openapi.json"].map((p) => [p, process.env.PRECAST_API ?? "http://localhost:8000"])) },
  build: { chunkSizeWarningLimit: 1500 },
});
