// Opt-in stable screenshot capture for design review (18). Not part of `npm run test:e2e`.
// Output goes to the git-ignored docs/ux-redesign/evidence/redesign folder by default.
export default {
  testDir: "tests/visual",
  testMatch: ["capture.spec.ts"],
  workers: 1,
  timeout: 120000,
  reporter: [["list"]],
  outputDir: "evidence/visual-results",
  use: {
    baseURL: "http://127.0.0.1:5173",
    reducedMotion: "reduce",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : {},
  },
  webServer: {
    command: "node node_modules/vite/bin/vite.js --host 127.0.0.1",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
  },
};
