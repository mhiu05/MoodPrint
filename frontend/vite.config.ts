import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  // Absolute: index.html is also served for deep links such as /auth/callback.
  base: "/",
  // Keep third-party license headers (GSAP's terms forbid removing its notice).
  esbuild: { legalComments: "inline" },
  build: {
    // Keep scripts (the audio worklet) as same-origin files, allowed by script-src 'self'.
    assetsInlineLimit: (file) => (file.endsWith(".js") ? false : undefined),
  },
  // The orb is imported lazily; pre-bundling it keeps a fresh dev server from
  // reloading the page the first time an AI run shows it.
  optimizeDeps: { include: ["thinking-orbs"] },
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
