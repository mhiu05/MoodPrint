import { defineConfig } from "@playwright/test";
import base from "./playwright.config";
import path from "node:path";

const artifactRoot = process.env.MOODPRINT_TEST_ARTIFACT_DIR || "evidence";

// Review-owned run: its own Vite on 5190 (never the developer's 5173) with the API
// proxy pointed at an unused port, because every request in these specs is intercepted.
export default defineConfig({
  ...base,
  globalTimeout: 1800000,
  reporter: [["list"], ["json", { outputFile: path.join(artifactRoot, "merge-readiness-results.json") }]],
  outputDir: path.join(artifactRoot, "merge-readiness-test-results"),
  use: { ...base.use, baseURL: "http://127.0.0.1:5190" },
  webServer: {
    command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5190",
    url: "http://127.0.0.1:5190",
    reuseExistingServer: false,
    env: { MOODPRINT_API_PROXY: "http://127.0.0.1:59998" },
  },
});
