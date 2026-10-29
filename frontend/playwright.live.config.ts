import { artifactPath } from "./tests/artifacts";
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/live",
  workers: 1,
  timeout: 240000,
  globalTimeout: 500000,
  expect: { timeout: 45000 },
  reporter: [["list"], ["json", { outputFile: artifactPath("live-ai-results.json") }]],
  outputDir: artifactPath("live-ai"),
  use: {
    baseURL: "http://127.0.0.1:5177",
    trace: "off", screenshot: "off", video: "off",
    viewport: { width: 1440, height: 1000 },
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
          args: process.env.MOODPRINT_TEST_AUDIO ? ["--use-fake-device-for-media-stream", `--use-file-for-fake-audio-capture=${process.env.MOODPRINT_TEST_AUDIO}`] : [] }
      : { args: process.env.MOODPRINT_TEST_AUDIO ? ["--use-fake-device-for-media-stream", `--use-file-for-fake-audio-capture=${process.env.MOODPRINT_TEST_AUDIO}`] : [] },
  },
});
