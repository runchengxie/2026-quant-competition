import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

const snapshot = JSON.parse(await readFile(new URL("../src/data/strategy-expansion.v1.json", import.meta.url), "utf8"));

test("both languages present the same published research facts", async ({ page }) => {
  const expected = [...snapshot.daily_results, ...snapshot.equity_results, ...snapshot.maker_results];
  let canonical;
  for (const path of ["/2026-quant-competition/", "/2026-quant-competition/zh-CN/"]) {
    await page.goto(path);
    const rows = page.locator("#expansion [data-expansion-id]");
    await expect(rows).toHaveCount(expected.length);
    const facts = await rows.evaluateAll(elements => elements.map(e => JSON.parse(e.dataset.facts)));
    expect(facts).toEqual(expected);
    if (canonical) expect(facts).toEqual(canonical);
    canonical = facts;
    await expect(page.locator("#expansion h2")).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
});
