import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
const facts=JSON.parse(readFileSync(new URL('../src/data/low-turnover.v1.json',import.meta.url),'utf8'));
const latest=JSON.parse(readFileSync(new URL('../src/data/evidence-followup.v1.json',import.meta.url),'utf8'));

for(const locale of ['en','zh-CN'])test(`${locale}: latest progress is readable on both research views`,async({page})=>{
 const prefix=`/2026-quant-competition/${locale==='en'?'':'zh-CN/'}`;
 for(const topic of ['strategies/','factors/']){
  await page.goto(prefix+topic);
  const section=page.locator('[data-progress-facts]');await expect(section).toHaveCount(1);
  const value=JSON.parse(await section.getAttribute('data-progress-facts'));
  expect(value.scientific).toEqual(latest.scientific);expect(value.completed).toBe(156);expect(value.blocked).toBe(12);
  expect(value.accepted_observations).toBe(0);expect(value.accepted_stocks).toBe(0);
  expect(value.warmup_end).toBe('2026-10-24');expect(value.new_attempts).toBe(40);
  await expect(section.locator('[data-followup-model]')).toHaveCount(topic==='factors/'?8:0);
  await expect(section.locator('[data-followup-account]')).toHaveCount(topic==='strategies/'?6:0);
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 }
});

for(const locale of ['en','zh-CN'])for(const topic of ['strategies','factors'])test(`${locale} ${topic}: market sections and current research retain exact facts`,async({page},info)=>{
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 const prefix=`/2026-quant-competition/${locale==='en'?'':'zh-CN/'}`;
 await page.goto(`${prefix}${topic}/`);
 const main=page.locator('main');await expect(main).toHaveAttribute('data-market-ready','true');
 await expect(page.locator('[data-market-navigation] [role=tab]')).toHaveCount(3);
 await expect(main).toHaveAttribute('data-current-market','US');
 const stock=page.locator('#holding-equity');await stock.scrollIntoViewIfNeeded();
 await expect(stock).toHaveAttribute('data-lt-ready','true');
 expect(JSON.parse(await stock.getAttribute('data-lt-facts'))).toEqual(facts);
 await stock.locator('[data-lt-horizon]').selectOption('20');
 await expect(stock).toHaveAttribute('data-lt-horizon','20');
 await expect(stock.locator(topic==='strategies'?'[data-lt-account]:visible':'[data-lt-model]:visible')).toHaveCount(topic==='strategies'?4:2);
 await page.locator('[data-market-link=HK]').click();
 await expect(page.locator('#market-hk')).toBeVisible();await expect(page.locator('#market-us')).toBeHidden();
 await page.locator('[data-market-link=crypto]').click();
 await expect(page.locator('#market-crypto')).toBeVisible();
 if(topic==='strategies'){
  const crypto=page.locator('#holding-crypto');await crypto.scrollIntoViewIfNeeded();await expect(crypto).toHaveAttribute('data-lt-ready','true');
  await crypto.locator('[data-lt-fee]').selectOption('50');await crypto.locator('[data-lt-delay]').selectOption('1');
  await expect(crypto.locator('[data-lt-account]:visible')).toHaveCount(4);
 }else await expect(page.locator('#dex-factor-pilot')).toBeVisible();
 await page.setViewportSize({width:390,height:844});await page.locator('#theme-preference').selectOption('dark');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:info.outputPath(`${locale}-${topic}-crypto-mobile.png`)});
 await page.locator('[data-market-link=US]').click();await expect(stock).toHaveAttribute('data-lt-horizon','20');
 await stock.scrollIntoViewIfNeeded();await stock.locator('[data-lt-chart]').first().screenshot({path:info.outputPath(`${locale}-${topic}-stock-dark.png`)});
 expect(errors).toEqual([]);
});

test('homepage stays lean and has no market-panel initialization error',async({page})=>{
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto('/2026-quant-competition/',{waitUntil:'networkidle'});
 await expect(page.locator('canvas')).toHaveCount(0);await expect(page.locator('[data-lt-facts]')).toHaveCount(0);
 expect(errors).toEqual([]);
});

test('market tabs support keyboard, deep links and browser history',async({page})=>{
 await page.goto('/2026-quant-competition/strategies/#holding-crypto');
 await expect(page.locator('main')).toHaveAttribute('data-current-market','crypto');
 const us=page.locator('[data-market-link=US]');await us.focus();await us.press('ArrowLeft');
 await expect(page.locator('main')).toHaveAttribute('data-current-market','HK');
 await page.locator('[data-market-link=HK]').press('End');await expect(page.locator('main')).toHaveAttribute('data-current-market','crypto');
 await page.goBack();await expect(page.locator('main')).toHaveAttribute('data-current-market','HK');
 await page.goto('/2026-quant-competition/factors/#dex-factor-pilot');
 await expect(page.locator('main')).toHaveAttribute('data-current-market','crypto');await expect(page.locator('#dex-factor-pilot')).toBeVisible();
});

test('Back to the hashless page restores its default market',async({page})=>{
 await page.goto('/2026-quant-competition/strategies/');
 await expect(page.locator('main')).toHaveAttribute('data-current-market','US');
 await page.locator('[data-market-link=crypto]').click();
 await expect(page.locator('main')).toHaveAttribute('data-current-market','crypto');
 await page.goBack();
 await expect(page.locator('main')).toHaveAttribute('data-current-market','US');
});

test('without JavaScript all markets and complete current evidence remain readable',async({browser})=>{
 const context=await browser.newContext({javaScriptEnabled:false});const page=await context.newPage();
 for(const locale of ['en','zh-CN']){
  const prefix=`/2026-quant-competition/${locale==='en'?'':'zh-CN/'}`;
  await page.goto(`${prefix}strategies/`);
  for(const market of ['hk','us','crypto'])await expect(page.locator(`#market-${market}`)).toBeVisible();
  await expect(page.locator('#holding-equity [data-lt-account]')).toHaveCount(168);await expect(page.locator('#holding-crypto [data-lt-account]')).toHaveCount(288);
  await page.goto(`${prefix}factors/`);await expect(page.locator('#holding-equity [data-lt-model]')).toHaveCount(8);await expect(page.locator('#dex-factor-pilot')).toBeVisible();
 }
 await context.close();
});
