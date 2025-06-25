import { test, expect } from "@playwright/test";
import fs from "fs";
import path from "path";
import { extractFinalOutput } from "./trace_utils";

const root = path.resolve(__dirname);
const payloads = [1, 2, 3].map((i) =>
  JSON.parse(fs.readFileSync(path.join(root, `payload${i}.json`), "utf8")),
);
const tracesDir = path.resolve(
  __dirname,
  "../../drsearch_backend/testing_full_app/traces",
);
const expectedOutputs = [1, 2, 3].map((i) =>
  extractFinalOutput(path.join(tracesDir, `trace${i}.sse`)),
);

const baseURL = process.env.FRONTEND_BASE_URL || "http://localhost:3000";

test.describe("trace replay happy path", () => {
  payloads.forEach((payload, idx) => {
    test(`payload ${idx + 1}`, async ({ page }) => {
      const consoleErrors: string[] = [];
      page.on("pageerror", (e) => consoleErrors.push(e.message));
      page.on("console", (msg) => {
        if (msg.type() === "error") consoleErrors.push(msg.text());
      });

      await page.route("**/chat/stream_log", async (route, request) => {
        const body = JSON.parse(request.postData() || "null");
        expect(body).toEqual(payload);
        await route.continue();
      });

      await page.goto(baseURL);

      const select = page.getByTestId("index-select");
      await select.waitFor();
      await page.waitForFunction((val) => {
        const sel = document.querySelector(
          'select[data-testid="index-select"]',
        );
        return Array.from(sel?.options || []).some((o) => o.value === val);
      }, payload.input.index_name);
      await select.selectOption(payload.input.index_name);

      if (payload.input.num_docs_retrieved !== 3) {
        await page.getByRole("button", { name: "Open settings" }).click();
        const num = page.getByRole("spinbutton", {
          name: "Documents to retrieve",
        });
        await num.fill(String(payload.input.num_docs_retrieved));
        await page.click('button[aria-label="Close"]');
      }

      await page.getByTestId("chat-input").fill(payload.input.question);
      await page.getByTestId("chat-send-btn").click();

      const stream = page.getByTestId("chat-stream");
      await expect(stream).toContainText(expectedOutputs[idx].slice(-20), {
        timeout: 15000,
      });

      expect(consoleErrors).toEqual([]);
    });
  });
});
