import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/supabase",
  workers: 1,
  fullyParallel: false,
  timeout: 480000,
  globalTimeout: 510000,
  expect: { timeout: 20000 },
  reporter: [["list"], ["json", { outputFile: process.env.MOODPRINT_HOSTED_REPORT || "evidence/supabase-results.json" }]],
  outputDir: "evidence/supabase",
  use: {
    baseURL: "http://127.0.0.1:5176",
    trace: "off",
    screenshot: "off",
    video: "off",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {},
  },
});
