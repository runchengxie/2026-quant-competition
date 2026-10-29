import { test, expect } from '@playwright/test';

for (const locale of ['en', 'zh-CN']) {
  const prefix = `/2026-quant-competition/${locale === 'en' ? '' : 'zh-CN/'}`;
  test(`${locale}: research type filter can be changed and reset`, async ({ page }) => {
    await page.goto(`${prefix}markets/`);
    const filter = page.locator('[data-research-filter]');
    await expect(filter).toBeVisible();
    await filter.selectOption('factor');
    await expect(page.locator('[data-research-kind="factor"]')).toHaveCount(3);
    await expect(page.locator('[data-research-kind="factor"]').first()).toBeVisible();
    await expect(page.locator('[data-research-kind="strategy"]').first()).toBeHidden();
    await filter.selectOption('strategy');
    await expect(page.locator('[data-research-kind="factor"]').first()).toBeHidden();
    await expect(page.locator('[data-research-kind="strategy"]').first()).toBeVisible();
    await filter.selectOption('all');
    await expect(page.locator('[data-research-kind="factor"]').first()).toBeVisible();
    await expect(page.locator('[data-research-kind="strategy"]').first()).toBeVisible();
  });
}
