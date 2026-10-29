import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';

const facts=JSON.parse(readFileSync(new URL('../src/data/strategy-comparison.v1.json',import.meta.url),'utf8'));
for(const locale of ['en','zh-CN'])for(const market of ['equity','crypto']){
 test(`${locale} ${market}: costs and timing retain exact facts, missing cells and readable charts`,async({page},testInfo)=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  const prefix=`/global-market-research/${locale==='en'?'':'zh-CN/'}`,topic=market==='equity'?'factors':'strategies';
  await page.goto(`${prefix}${topic}/#comparison-${market}`);
  const root=page.locator(`#comparison-${market}`);
  await root.scrollIntoViewIfNeeded();
  await expect(root).toHaveAttribute('data-comparison-ready','true');
  const original=await root.getAttribute('data-comparison-facts');
  expect(JSON.parse(original)).toEqual(facts);
  const windows=[...new Set(facts[market].accounts.map(row=>row.window))].sort(),high=market==='equity'?40:50;
  for(const [window,fee,delay] of [[windows[0],0,0],[windows[0],high,1],[windows.at(-1),high,0],[windows.at(-1),high,1]]){
   await root.locator('[data-cmp-window]').selectOption(window);
   await root.locator('[data-cmp-fee]').selectOption(String(fee));
   await root.locator('[data-cmp-delay]').selectOption(String(delay));
   await expect(root).toHaveAttribute('data-comparison-window',window);
   await expect(root).toHaveAttribute('data-comparison-fee',String(fee));
   await expect(root).toHaveAttribute('data-comparison-delay',String(delay));
   const visible=root.locator('[data-cmp-row]:visible');
   await expect(visible).toHaveCount(4);
   const selected=facts[market].accounts.filter(row=>row.window===window&&row.fee_bps===fee&&row.delay===delay);
   for(let i=0;i<4;i++){
    const text=await visible.nth(i).innerText();
    expect(text).toContain(`${selected[i].valid_dates}/${selected[i].requested_dates}`);
    if(selected[i].status==='blocked')expect(await visible.nth(i).locator('td').nth(3).innerText()).toBe(locale==='en'?'Unavailable':'无法比较');
   }
  }
  await root.locator('[data-cmp-chart="returns"] canvas').first().hover();
  await root.locator('[data-cmp-window]').selectOption(windows[0]);
  await root.locator('[data-cmp-delay]').selectOption('0');
  await root.locator('.comparison-plots').screenshot({path:testInfo.outputPath(`${market}-${locale}-desktop.png`)});
  await page.setViewportSize({width:390,height:844});
  await page.getByLabel(locale==='en'?'Appearance':'外观').selectOption('dark');
  await expect(root).toHaveAttribute('data-comparison-ink','rgb(233, 231, 224)');
  expect(await root.getAttribute('data-comparison-facts')).toBe(original);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await root.locator('.comparison-plots').screenshot({path:testInfo.outputPath(`${market}-${locale}-mobile-dark.png`)});
  await root.getByRole('link',{name:locale==='en'?'Read the data and comparison method':'查看数据检查和比较方法'}).click();
  await expect(page).toHaveURL(new RegExp('/docs/strategy-comparison/$'));
  await expect(page).not.toHaveTitle(/undefined/);
  expect(errors).toEqual([]);
 });
}

test('both languages retain every comparison and its reason without JavaScript',async({browser})=>{
 const context=await browser.newContext({javaScriptEnabled:false});
 const page=await context.newPage();
 for(const locale of ['en','zh-CN'])for(const market of ['equity','crypto']){
  await page.goto(`/global-market-research/${locale==='en'?'':'zh-CN/'}${market==='equity'?'factors':'strategies'}/`);
  const root=page.locator(`#comparison-${market}`);
  await expect(root.locator('[data-cmp-row]')).toHaveCount(facts[market].accounts.length);
  await expect(root.locator('[data-cmp-chart] canvas')).toHaveCount(0);
  if(market==='equity')await expect(root).toContainText(locale==='en'?'Constant forecast cannot rank candidates':'预测值相同，无法排序');
 }
 await context.close();
});
