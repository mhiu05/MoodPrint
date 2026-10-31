import { artifactPath } from "./tests/artifacts";
import { defineConfig } from "@playwright/test";

const port = process.env.PLAYWRIGHT_PORT || "5173";
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "tests/e2e",
  testMatch: ["eligibility.spec.ts", "journal.spec.ts", "real.spec.ts", "social.spec.ts", "activities.spec.ts", "admin.spec.ts", "chat-history.spec.ts", "discovery.spec.ts", "states.spec.ts", "auth.spec.ts", "ux-redesign.spec.ts", "motion.spec.ts", "merge-readiness.spec.ts", "landing.spec.ts", "guest.spec.ts", "guest-expiry.spec.ts", "session-reliability.spec.ts", "feedback.spec.ts", "feedback-admin.spec.ts", "onboarding.spec.ts", ...(process.env.MOODPRINT_TOUR_COMPATIBILITY === "1" ? ["onboarding-compatibility.spec.ts"] : [])],
  globalTimeout: 600000,
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  expect: { timeout: 7000 },
  reporter: [
    ["list"],
    ["json", { outputFile: artifactPath("e2e-results.json") }],
    ["html", { outputFolder: artifactPath("playwright-report"), open: "never" }],
  ],
  outputDir: artifactPath("test-results"),
  use: {
    baseURL,
    viewport: { width: 1280, height: 900 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : {},
  },
  webServer: {
    command: `node node_modules/vite/bin/vite.js --host 127.0.0.1 --port ${port}`,
    url: baseURL,
    reuseExistingServer: !process.env.PLAYWRIGHT_PORT,
  },
});
