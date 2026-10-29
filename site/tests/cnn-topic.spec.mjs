import { test, expect } from '@playwright/test';

for (const locale of ['en','zh-CN']) {
 const prefix=`/2026-quant-competition/${locale==='en'?'':'zh-CN/'}`;
 test(`${locale}: CNN topic has interactive history and retains the source note`,async({page},info)=>{
  await page.goto(`${prefix}markets/#market-hk`);
  await page.locator('[data-topic-market=hk] a[href$="research/cnn-chart/"]').first().click();
  await expect(page).toHaveURL(`${prefix}research/cnn-chart/`);
  await expect(page.locator('main h1')).toHaveCount(1);
  await expect(page.locator('[data-cnn-image]')).toHaveCount(2);
  await expect(page.locator('[data-cnn-curve]')).toHaveAttribute('data-ready','true');
  await expect(page.locator('[data-cnn-fallback]')).toBeHidden();
  await page.locator('[data-cnn-select]').selectOption('image_cnn_top5');
  await expect(page.locator('[data-cnn-curve]')).toHaveAttribute('data-selection','image_cnn_top5');
  await expect(page.locator('[data-cnn-results]')).toContainText('59.47%');
  await expect(page.locator('a[data-cnn-source]')).toHaveAttribute('href',`${prefix}docs/cnn-chart-research/`);
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath(`${locale}-cnn-mobile.png`),fullPage:true});
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:info.outputPath(`${locale}-cnn-desktop.png`),fullPage:true});
 });
 test(`${locale}: CNN evidence stays readable without JavaScript`,async({browser})=>{
  const context=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});
  const page=await context.newPage();await page.goto(`${prefix}research/cnn-chart/`);
  await expect(page.locator('[data-cnn-fallback]')).toBeVisible();
  await expect(page.locator('[data-cnn-results]')).toContainText('91.70%');
  await expect(page.locator('[data-cnn-controls]')).toBeHidden();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await context.close();
 });
}
