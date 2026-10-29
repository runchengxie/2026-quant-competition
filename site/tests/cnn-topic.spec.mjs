import { test, expect } from '@playwright/test';

test('CNN chart stays inside a mobile page while resize callbacks are delayed',async({page})=>{
 await page.addInitScript(()=>{
  const original=window.addEventListener.bind(window);
  window.addEventListener=(type,listener,options)=>original(type,type==='resize'&&typeof listener==='function'?(event)=>setTimeout(()=>listener(event),1000):listener,options);
 });
 await page.setViewportSize({width:1440,height:1000});
 await page.goto('/2026-quant-competition/research/cnn-chart/');
 await expect(page.locator('[data-cnn-curve]')).toHaveAttribute('data-ready','true');
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

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

for (const locale of ['en','zh-CN']) {
 const prefix=`/2026-quant-competition/${locale==='en'?'':'zh-CN/'}`;
 test(`${locale}: crypto CNN research keeps assumptions and scenario results visible`,async({browser})=>{
  const context=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});
  const page=await context.newPage();
  await page.goto(`${prefix}markets/#market-crypto`);
  await page.locator('[data-crypto-cnn-link]').click();
  await expect(page).toHaveURL(`${prefix}research/crypto-cnn/`);
  await expect(page.locator('main h1')).toHaveCount(1);
  await expect(page.locator('[data-crypto-cnn-table]')).toContainText('-9.17%');
  await expect(page.locator('[data-crypto-cnn-table]')).toContainText('-4.03%');
  await expect(page.locator('[data-crypto-cnn-limit]')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await context.close();
 });
}

test('crypto CNN curve changes window, cost, delay and strategy',async({page})=>{
 await page.goto('/2026-quant-competition/zh-CN/research/crypto-cnn/');
 const chart=page.locator('[data-chart]');
 await expect(chart).toBeVisible();
 await expect(chart).toHaveAttribute('data-selection','0/35/0/cnn_weekly');
 await expect(chart.locator('[data-min]')).toHaveText('2024-03-01');
 await expect(chart.locator('[data-curve-summary]')).toContainText('USDT');
 await expect(chart.locator('[data-base]')).toHaveAttribute('stroke','var(--bid)');
 const before=await chart.locator('[data-choice]').getAttribute('d');
 await page.locator('[data-window]').selectOption('1');
 await page.locator('[data-fee]').selectOption('50');
 await page.locator('[data-delay]').selectOption('1');
 await page.locator('[data-strategy]').selectOption('image_daily');
 await expect(chart).toHaveAttribute('data-selection','1/50/1/image_daily');
 await expect(chart.locator('[data-min]')).toHaveText('2024-05-31');
 await expect(chart.locator('[data-curve-summary]')).toContainText('CNN');
 expect(await chart.locator('[data-choice]').getAttribute('d')).not.toBe(before);
});

for (const locale of ['en','zh-CN']) {
 const prefix=`/2026-quant-competition/${locale==='en'?'':'zh-CN/'}`;
 test(`${locale}: later crypto windows and sentiment limits remain readable without JS`,async({browser})=>{
  const context=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});
  const page=await context.newPage();await page.goto(`${prefix}research/crypto-cnn/`);
  await expect(page.locator('[data-crypto-followup]')).toContainText('2026-01-06');
  await expect(page.locator('[data-crypto-followup]')).toContainText('-38.50%');
  await expect(page.locator('[data-sentiment-availability]')).toContainText('2026-10-14');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await context.close();
 });
}
