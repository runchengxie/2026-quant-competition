import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
const snapshot=JSON.parse(await readFile(new URL('../src/data/strategy-robustness.v1.json',import.meta.url),'utf8'));

test('robustness comparisons keep exact bilingual facts across fees, windows and themes',async({page},testInfo)=>{
 for(const locale of ['en','zh-CN']){
  await page.setViewportSize({width:1360,height:1000});
  const prefix=`/2026-quant-competition/${locale==='en'?'':'zh-CN/'}`;
  await page.goto(prefix+'strategies/');
  const root=page.locator('#robustness');await root.scrollIntoViewIfNeeded();
  await expect(root).toHaveAttribute('data-ready','true');
  expect(JSON.parse(await root.getAttribute('data-robustness-facts'))).toEqual(snapshot);
  await root.locator('[data-robustness-table-summary]').click();
  await expect(root.locator('[data-robustness-row]:visible')).toHaveCount(33);
  await root.locator('[data-robustness-table-summary]').click();
  await root.locator('[data-robustness-filter=market]').selectOption('crypto');
  await root.locator('[data-robustness-filter=fee]').selectOption('50');
  expect(JSON.parse(await root.getAttribute('data-selection-facts')).groups[0].returnWins).toBe(5);
  const windows=await root.locator('[data-robustness-filter=window] option').evaluateAll(ns=>ns.map(n=>n.value));
  await root.locator('[data-robustness-filter=window]').selectOption(windows.at(-1));
  expect(JSON.parse(await root.getAttribute('data-selection-facts')).groups[0].requestedWindows).toBe(1);
  await root.locator('[data-robustness-filter=window]').selectOption('');
  await root.locator('[data-robustness-notional]').selectOption('1000000');
  await expect(root.locator('[data-capacity-summary]')).toContainText('6');
  for(const theme of ['light','dark']){
   await page.locator('#theme-preference').selectOption(theme);
   await root.screenshot({path:testInfo.outputPath(`${locale}-${theme}.png`)});
  }
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:testInfo.outputPath(`${locale}-mobile.png`)});
  await page.goto(prefix);
  expect(await page.locator('#robustness').evaluate(n=>n.hasAttribute('data-robustness-facts'))).toBe(false);
  await expect(page.locator('#robustness canvas')).toHaveCount(0);
 }
});

test('robustness charts cannot widen mobile pages while resize callbacks are delayed',async({page})=>{
 await page.addInitScript(()=>{window.ResizeObserver=class {observe(){} disconnect(){} unobserve(){}};});
 await page.setViewportSize({width:1360,height:1000});await page.goto('/2026-quant-competition/strategies/');
 const root=page.locator('#robustness');await root.scrollIntoViewIfNeeded();await expect(root).toHaveAttribute('data-ready','true');
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test('without JavaScript the complete reviewed table remains available',async({browser})=>{
 const context=await browser.newContext({javaScriptEnabled:false});const page=await context.newPage();
 await page.goto('/2026-quant-competition/zh-CN/strategies/');
 const root=page.locator('#robustness');
 await expect(root.locator('[data-robustness-row]')).toHaveCount(114);
 await expect(root.locator('canvas')).toHaveCount(0);
 await context.close();
});
