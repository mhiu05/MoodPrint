import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    react(),
    {
      name: "explicit-legacy-test-entry",
      transformIndexHtml(html) {
        return html.replace("/src/main.tsx", "/tests/harness/legacy-main.tsx");
      },
    },
  ],
  server: { host: "127.0.0.1", port: 5175, strictPort: true },
});
