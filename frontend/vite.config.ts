import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  // Absolute: index.html is also served for deep links such as /auth/callback.
  base: "/",
  build: {
    // Keep scripts (the audio worklet) as same-origin files, allowed by script-src 'self'.
    assetsInlineLimit: (file) => (file.endsWith(".js") ? false : undefined),
  },
  server: {
    // Playwright traces contain HTML. Watching them reloads the app while a
    // different browser is using it, interrupting real sessions and screenshots.
    watch: { ignored: ["**/evidence/**", "**/.cache/**"] },
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
