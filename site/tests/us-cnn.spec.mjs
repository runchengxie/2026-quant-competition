import { test, expect } from '@playwright/test';

for (const locale of ['en', 'zh-CN']) {
  const prefix = `/2026-quant-competition/${locale === 'en' ? '' : 'zh-CN/'}`;
  test(`${locale}: US CNN findings and comparisons are accessible`, async ({ page }) => {
    await page.goto(`${prefix}markets/#market-us`);
    await page.locator('[data-us-cnn-link]').first().click();
    await expect(page).toHaveURL(`${prefix}research/us-cnn/`);
    await expect(page.locator('[data-us-cnn-results]')).toContainText('5.30%');
    await page.locator('[data-exposure]').selectOption('40');
    await expect(page.locator('[data-us-cnn-results]')).toContainText('2.12%');
    await page.locator('[data-fee]').selectOption('40');
    await expect(page.locator('[data-us-cnn-results]')).toHaveAttribute('data-selection', '40/40');
    await page.setViewportSize({width:390,height:844});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
  test(`${locale}: US CNN results remain readable without JavaScript`, async ({ browser }) => {
    const context=await browser.newContext({javaScriptEnabled:false});
    const page=await context.newPage();
    await page.goto(`${prefix}research/us-cnn/`);
    await expect(page.locator('[data-us-cnn-results]')).toContainText('5.30%');
    await expect(page.locator('[data-us-cnn-controls]')).toBeHidden();
    await context.close();
  });
}
