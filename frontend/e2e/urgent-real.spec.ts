import { test, expect } from "./helpers/fixtures";

test("E-URG-01: urgent help stays public with the actual API process stopped", async ({
  page,
}) => {
  test.skip(
    process.env.E2E_URGENT_BACKEND_STOPPED !== "1",
    "The harness runs this test after stopping its own API child",
  );
  const api = new URL(process.env.E2E_API_URL!);
  expect(api.hostname).toBe("127.0.0.1");
  expect(Number(api.port)).toBe(
    8008 + Number(process.env.SAFEVOICE_PORT_OFFSET ?? 0),
  );
  let reachable = false;
  try {
    await fetch(`${process.env.E2E_API_URL}/health`);
    reachable = true;
  } catch {
    /* Expected: API child is stopped. */
  }
  expect(reachable).toBe(false);
  await page.goto("/support/urgent");
  await expect(page).toHaveURL(/\/support\/urgent$/);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator('a[href="tel:111"]')).toBeVisible();
});
