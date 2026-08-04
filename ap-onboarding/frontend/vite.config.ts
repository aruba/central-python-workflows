import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  base: "/static/",
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  build: {
    outDir: "../static",
    emptyOutDir: true,
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
});
