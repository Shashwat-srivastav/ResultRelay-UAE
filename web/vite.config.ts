import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The build output is served by FastAPI from app/static/app so that a single process
// serves both the API and the UI (and so the demo needs one command).
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../app/static/app",
    emptyOutDir: true,
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
