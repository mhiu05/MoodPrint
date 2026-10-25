import { defineConfig } from "@playwright/test";
import fullstack from "./playwright.fullstack.config";

export default defineConfig({
  ...fullstack,
  testDir: "tests/provider-smoke",
  timeout: 180000,
  globalTimeout: 240000,
  reporter: [["list"]],
  outputDir: ".cache/local-mvp/provider",
});
