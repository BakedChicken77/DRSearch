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

      if (payload.input.num_docs_retrieved !== 3) {
        await page.click('button[aria-label="Open settings"]');
        const numInput = page.locator('input[type="number"]');
        await numInput.fill(String(payload.input.num_docs_retrieved));
        await page.click('button[aria-label="Close"]');
      }

      await page.fill('textarea', payload.input.question);
      await page.selectOption('select', payload.input.index_name);
      await page.click('button[aria-label="Send"]');

      await expect(page.locator('div.whitespace-pre-wrap').last()).toContainText(expectedTails[idx], { timeout: 15000 });
      expect(consoleErrors).toEqual([]);
    });
  });
});
