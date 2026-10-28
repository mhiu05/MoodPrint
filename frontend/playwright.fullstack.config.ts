import { artifactPath } from "./tests/artifacts";
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/fullstack",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  globalTimeout: 900000,
  reporter: [
    ["list"],
    ["json", { outputFile: artifactPath("fullstack-results.json") }],
  ],
  outputDir: artifactPath("fullstack"),
  use: {
    baseURL: "http://127.0.0.1:5174",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : {},
  },
});
