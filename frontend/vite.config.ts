import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The build output is served by FastAPI from backend/app/static/app so that a single process
// serves both the API and the UI (and so the demo needs one command).
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../backend/app/static/app",
    emptyOutDir: true,
    // three.js is one lazy chunk (525 kB raw / 131 kB gzip) that no user pays for until the 3-D
    // scene mounts. The initial app chunk is ~246 kB, which is the number that matters.
    chunkSizeWarningLimit: 560,
    rollupOptions: {
      output: {
        // three.js and GSAP are large and change rarely; splitting them keeps the app chunk small and
        // lets the 3-D scene arrive after first paint (it is also lazily imported).
        manualChunks: { three: ["three"], motion: ["gsap"] },
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
