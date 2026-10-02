/**
 * Vite configuration for the broadcast frontend.
 * In development, requests under /api are proxied to the FastAPI backend so the browser stays same-origin.
 * Vitest runs pure logic tests from the same configuration.
 */
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5199,
    strictPort: true,
    proxy: { "/api": { target: BACKEND_URL, changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, "") } },
  },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
