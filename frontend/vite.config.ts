import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.MOODPRINT_API_PROXY || "http://127.0.0.1:8001",
      },
    },
  },
  test: { include: ["src/**/*.test.ts"] },
});
