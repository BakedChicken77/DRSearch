import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const base = path.resolve(__dirname);
const payloads = [1,2,3].map(n =>
  JSON.parse(fs.readFileSync(path.join(base, `payload${n}.json`), 'utf-8'))
);
const traces = [1,2,3].map(n =>
  fs.readFileSync(path.join(base, 'traces', `trace${n}.sse`), 'utf-8')
);

function finalOutput(trace: string): string {
  const regex = /"final_output".*?\"(?:output\"\:\")?([^\"]+)/gs;
  let m: RegExpExecArray | null;
  let last = '';
  while ((m = regex.exec(trace))) {
    last = m[1];
  }
  return last;
}

test.describe('trace replays', () => {
  payloads.forEach((payload, idx) => {
    const trace = traces[idx];
    const expectedTail = finalOutput(trace).slice(-20);

    test(`payload ${idx + 1}`, async ({ page }) => {
      const errors: any[] = [];
      page.on('pageerror', err => errors.push(err));

      await page.route('**/chat/stream_log', async route => {
        const sent = JSON.parse(route.request().postData() || '{}');
        expect(sent).toEqual(payload);
        await route.continue();
      });

      await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
      await page.getByRole('combobox').selectOption(payload.input.index_name);
      await page.getByRole('textbox').fill(payload.input.question);
      await page.getByLabel('Send').click();

      const answer = page.locator('div.whitespace-pre-wrap').last();
      await expect(answer).toContainText(expectedTail, { timeout: 15000 });
      expect(errors).toEqual([]);
    });
  });
});
