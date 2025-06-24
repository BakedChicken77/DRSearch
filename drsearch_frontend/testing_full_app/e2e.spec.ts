import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const root = path.resolve(__dirname);
const payloads = [1,2,3].map(i => JSON.parse(fs.readFileSync(path.join(root, `payload${i}.json`), 'utf8')));
const traces = [1,2,3].map(i => fs.readFileSync(path.join(root, 'traces', `trace${i}.sse`), 'utf8'));

function extractTail(trace: string): string {
  const lines = trace.trim().split(/\r?\n/).reverse();
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      try {
        const obj = JSON.parse(line.slice(6));
        for (const op of obj.ops || []) {
          if (typeof op.path === 'string' && op.path.endsWith('final_output')) {
            const out = op.value?.output;
            if (typeof out === 'string') {
              return out.slice(-20);
            }
          }
        }
      } catch {
        // ignore malformed lines
      }
    }
  }
  return '';
}

const expectedTails = traces.map(extractTail);

test.describe('trace replay', () => {
  payloads.forEach((payload, idx) => {
    test(`payload ${idx + 1}`, async ({ page }) => {
      const consoleErrors: string[] = [];
      page.on('pageerror', e => consoleErrors.push(e.message));

      await page.route('**/chat/stream_log', async (route, request) => {
        const body = JSON.parse(request.postData() || 'null');
        expect(body).toEqual(payload);
        await route.continue();
      });

      await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
      await page.waitForLoadState('networkidle');  // ensures all fetches/requests settle

      // Select index first to enable the textarea
      const select = page.locator('select');
      await select.waitFor({ state: 'visible' });
      await select.selectOption(payload.input.index_name);

      // Configure num_docs_retrieved if needed
      if (payload.input.num_docs_retrieved !== 3) {
        const settingsBtn = page.locator('button[aria-label="Open settings"]');
        await settingsBtn.waitFor({ state: 'visible', timeout: 5000 });
        await expect(settingsBtn).toBeEnabled();
        await settingsBtn.click();

        const numInput = page.locator('input[type="number"]');
        await numInput.waitFor({ state: 'visible' });
        await expect(numInput).toBeEnabled();
        await numInput.fill(String(payload.input.num_docs_retrieved));
        await page.click('button[aria-label="Close"]');
      }


      // Now that the index is selected, textarea should be active
      const input = page.locator('textarea[placeholder]:not([aria-hidden])');
      await input.waitFor({ state: 'visible' });
      await expect(input).toBeEnabled();
      await input.fill(payload.input.question);

      await page.click('button[aria-label="Send"]');

      await expect(page.locator('div.whitespace-pre-wrap').last())
        .toContainText(expectedTails[idx], { timeout: 15000 });

      expect(consoleErrors).toEqual([]);
    });
  });
});
