
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Vitest runs component tests without opening a browser.
// jsdom simulates the browser environment for React tests.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
  server: {
    proxy: {
      "/agent": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/auth": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
