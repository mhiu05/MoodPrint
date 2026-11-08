import { defineConfig, devices } from "@playwright/test";

const managed = process.env.E2E_STACK_MANAGED === "1";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:5178",
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "demo",
      testIgnore: ["**/*-real.spec.ts", "**/workspace-separation.spec.ts"],
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "real",
      testMatch: ["**/*-real.spec.ts", "**/workspace-separation.spec.ts"],
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: managed
    ? undefined
    : {
        command:
          "npm run dev -- --config e2e/vite.demo.config.ts --mode test --port 5178 --strictPort",
        url: "http://127.0.0.1:5178",
        reuseExistingServer: false,
        env: {
          VITE_PUBLIC_SUPABASE_URL: "",
          VITE_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "",
          VITE_PUBLIC_API_BASE_URL: "",
        },
        timeout: 30000,
      },
});
