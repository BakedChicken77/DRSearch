import { test, expect } from "@playwright/test";
import { extractFinalOutput } from "./trace_utils";
import path from "path";

const tracesDir = path.resolve(
  __dirname,
  "../../drsearch_backend/testing_full_app/traces",
);
const slowExpected = extractFinalOutput(path.join(tracesDir, "trace3.sse"));

const baseURL = process.env.FRONTEND_BASE_URL || "http://localhost:3000";

async function askQuestion(page, indexName: string) {
  await page.goto(baseURL);
  const select = page.getByTestId("index-select");
  await select.waitFor();
  await page.waitForFunction((val) => {
    const sel = document.querySelector('select[data-testid="index-select"]');
    return Array.from(sel?.options || []).some((o) => o.value === val);
  }, indexName);
  await select.selectOption(indexName);
  await page.getByTestId("chat-input").waitFor();
  await page.getByTestId("chat-input").fill("Why?");
  await page.getByTestId("chat-send-btn").click();
}

test.describe.skip("negative scenarios", () => {
  test("ERROR_500 displays error", async ({ page }) => {
    await askQuestion(page, "ERROR_500");
    await expect(page.locator("text=/backend failure/i")).toBeVisible();
  });

  test("SLOW_STREAM completes within default timeout", async ({ page }) => {
    await askQuestion(page, "SLOW_STREAM");
    await expect(page.getByTestId("chat-stream")).toContainText(
      slowExpected.slice(-20),
      { timeout: 30000 },
    );
  });

  test("MALFORMED_SSE has no console errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await askQuestion(page, "MALFORMED_SSE");
    await expect(page.getByTestId("chat-stream")).toBeVisible({
      timeout: 30000,
    });
    expect(errors).toEqual([]);
  });
});
