import { defineConfig, devices } from "@playwright/test";

const managed = process.env.E2E_STACK_MANAGED === "1";
const offset = Number(process.env.MOODPRINT_PORT_OFFSET ?? 0);
const port = Number(process.env.E2E_PORT ?? 5178 + offset);
if (!Number.isInteger(port) || port < 1024 || port > 65535) {
  throw new Error("Invalid E2E_PORT");
}
const testURL = process.env.E2E_BASE_URL ?? `http://127.0.0.1:${port}`;
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: testURL,
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
        command: `npm run dev -- --config e2e/vite.demo.config.ts --mode test --port ${port} --strictPort`,
        url: testURL,
        reuseExistingServer: false,
        env: {
          VITE_PUBLIC_SUPABASE_URL: "",
          VITE_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "",
          VITE_PUBLIC_API_BASE_URL: "",
        },
        timeout: 30000,
      },
});
