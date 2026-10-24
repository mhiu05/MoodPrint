import { defineConfig } from "@playwright/test";
import current from "./playwright.config";

export default defineConfig({
  ...current,
  testMatch: ["journeys.spec.ts"],
  outputDir: "evidence/legacy",
  reporter: [
    ["list"],
    ["json", { outputFile: "evidence/legacy-results.json" }],
  ],
  use: { ...current.use, baseURL: "http://127.0.0.1:5175" },
  webServer: {
    command:
      "node node_modules/vite/bin/vite.js --config tests/harness/vite.legacy.config.ts",
    url: "http://127.0.0.1:5175",
    reuseExistingServer: false,
  },
});
