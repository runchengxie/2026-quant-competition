import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
const snapshot=JSON.parse(await readFile(new URL('../src/data/strategy-controls.v1.json',import.meta.url),'utf8'));
const readiness=JSON.parse(await readFile(new URL('../src/data/strategy-readiness.v1.json',import.meta.url),'utf8'));
for(const locale of ['en','zh-CN'])test(`${locale}: new controls separate completion from public performance`,async({page},testInfo)=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(`/2026-quant-competition/${locale==='en'?'':'zh-CN/'}strategies/`);
 const panel=page.locator('#strategy-controls');await expect(panel).toBeVisible();
 expect(JSON.parse(await panel.getAttribute('data-controls-facts'))).toEqual(snapshot);
 await expect(panel.locator('[data-controls-conclusion]')).toBeVisible();
 await expect(panel.locator('[data-controls-count=requested]')).toHaveText(String(snapshot.coverage.requested_jobs));
 expect(JSON.parse(await page.locator('#strategy-readiness').getAttribute('data-readiness-facts'))).toEqual(readiness);
 if(snapshot.status==='readiness_only'){
  await expect(panel.locator('[data-controls-result]')).toHaveCount(0);
  await expect(panel.locator('canvas')).toHaveCount(0);
  await expect(panel.locator('[data-controls-method]')).toHaveCount(14);
 }else{
  await panel.scrollIntoViewIfNeeded();await expect(panel).toHaveAttribute('data-ready','true');
  await expect(panel.locator('canvas')).toHaveCount(4);
  for(const theme of ['dark','light']){
   await page.locator('#theme-preference').selectOption(theme);
   await expect.poll(()=>panel.evaluate(n=>JSON.parse(n.dataset.chartColors).ink===getComputedStyle(n).color)).toBe(true);
   await panel.locator('.control-charts').screenshot({path:testInfo.outputPath(`charts-${theme}.png`)});
  }
  await panel.locator('[data-controls-filter=market]').selectOption('crypto');
  const fee=panel.locator('[data-controls-filter=fee]');
  await panel.locator('.control-window-values > summary').click();
  for(const option of await fee.locator('option').allTextContents())expect(option).not.toContain('USD ');
  const facts=await panel.locator('[data-controls-result]:visible').evaluateAll(nodes=>nodes.map(n=>JSON.parse(n.dataset.controlsResult)));
  expect(facts.length).toBeGreaterThan(0);expect(facts.every(r=>r.market==='crypto'&&r.quote_currency==='USDT')).toBe(true);
 }
 for(const theme of ['dark','light','system']){
  await page.locator('#theme-preference').selectOption(theme);
  if(snapshot.status==='measured')await expect.poll(()=>panel.evaluate(n=>JSON.parse(n.dataset.chartColors).ink===getComputedStyle(n).color)).toBe(true);
 }
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 if(snapshot.status==='readiness_only')await panel.screenshot({path:testInfo.outputPath('readiness-mobile.png')});
 expect(JSON.parse(await panel.getAttribute('data-controls-facts'))).toEqual(snapshot);expect(errors).toEqual([]);
});
test('new controls remain readable without JavaScript',async({browser})=>{
 const context=await browser.newContext({javaScriptEnabled:false});const page=await context.newPage();
 await page.goto('http://127.0.0.1:4397/2026-quant-competition/strategies/');
 const panel=page.locator('#strategy-controls');await expect(panel.locator('[data-controls-conclusion]')).toBeVisible();
 await expect(panel.locator('[data-controls-result]')).toHaveCount(snapshot.results.length);
 await expect(page.locator('#strategy-readiness')).toBeVisible();await context.close();
});
