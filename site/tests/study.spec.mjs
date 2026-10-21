import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

const snapshot = JSON.parse(await readFile(new URL("../src/data/real-data-study.v1.json", import.meta.url), "utf8"));
const expected = ["US", "HK", "crypto"].flatMap(market => snapshot.results.filter(row => row.market === market));

test("study facts match the reviewed projection in both languages and themes", async ({ page }) => {
  for (const locale of ["en", "zh-CN"]) {
    await page.goto(locale === "en" ? "/2026-quant-competition/" : "/2026-quant-competition/zh-CN/");
    const rows = page.locator("#study [data-study-id]");
    await expect(rows).toHaveCount(snapshot.results.length);
    expect(await rows.evaluateAll(elements => elements.map(e => JSON.parse(e.dataset.facts)))).toEqual(expected);
    await expect(page.locator("#study h2")).toBeVisible();
    for (const theme of ["light", "dark", "system"]) {
      await page.getByLabel(locale === "en" ? "Appearance" : "外观").selectOption(theme);
      await page.setViewportSize({ width: 390, height: 844 });
      for (const details of await page.locator("#study details.market-study").all()) {
        await details.locator(":scope > summary").click();
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await expect(page.locator("#study a.report-link")).toHaveAttribute("href", new RegExp(`real-data-study${locale === "zh-CN" ? "\\.zh-CN" : ""}\\.md$`));
      for (const details of await page.locator("#study details.market-study").all()) {
        await details.locator(":scope > summary").click();
      }
    }
  }
});
