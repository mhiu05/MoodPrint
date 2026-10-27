import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests/e2e",
  testMatch: ["real.spec.ts", "social.spec.ts", "activities.spec.ts", "admin.spec.ts", "chat-history.spec.ts", "discovery.spec.ts", "states.spec.ts", "auth.spec.ts", "ux-redesign.spec.ts", "motion.spec.ts"],
  globalTimeout: 600000,
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  expect: { timeout: 7000 },
  reporter: [
    ["list"],
    ["json", { outputFile: "evidence/e2e-results.json" }],
    ["html", { outputFolder: "evidence/playwright-report", open: "never" }],
  ],
  outputDir: "evidence/test-results",
  use: {
    baseURL: "http://127.0.0.1:5173",
    viewport: { width: 1280, height: 900 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : {},
  },
  webServer: {
    command: "node node_modules/vite/bin/vite.js --host 127.0.0.1",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
  },
});
