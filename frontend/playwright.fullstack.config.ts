import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/fullstack",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  globalTimeout: 180000,
  reporter: [
    ["list"],
    ["json", { outputFile: "evidence/fullstack-results.json" }],
  ],
  outputDir: "evidence/fullstack",
  use: {
    baseURL: "http://127.0.0.1:5174",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : {},
  },
});
