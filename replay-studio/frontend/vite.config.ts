import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Builds straight into the Python package so the API serves the dashboard.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../backend/replay_studio/static", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8787" } },
});
