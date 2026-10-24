import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
const snapshot=JSON.parse(await readFile(new URL('../src/data/strategy-robustness.v1.json',import.meta.url),'utf8'));

for(const locale of ['en','zh-CN']){
 const prefix=`/2026-quant-competition/${locale==='en'?'':'zh-CN/'}`;
 test(`${locale}: editorial home shows reviewed story without full payload`,async({page},info)=>{
  await page.goto(prefix);
  const home=page.locator('[data-editorial-facts]');
  await expect(home).toHaveCount(1,{timeout:3000});
  const facts=JSON.parse(await home.getAttribute('data-editorial-facts'));
  expect(facts.coverage).toEqual(snapshot.coverage);expect(facts.observation.observations).toBe(0);
  expect(facts.us.map(g=>g.requestedWindows)).toEqual([11,11,11]);
  expect(facts.crypto.map(g=>g.returnWins)).toEqual([6,5]);
  await expect(page.locator('main h1')).toHaveCount(1);
  await expect(home.locator('[data-editorial-pool]')).toHaveCount(3);
  for(const row of await home.locator('[data-editorial-pool]').all()){
   const group=JSON.parse(await row.getAttribute('data-editorial-pool'));
   expect(group).toEqual(facts.us.find(g=>g.poolId===group.poolId));
   const value=new Intl.NumberFormat(locale,{maximumFractionDigits:2}).format(group.medianReturnChange*100);
   await expect(row.locator('[data-editorial-value]')).toContainText(value);
  }
  await expect(home.locator('canvas')).toHaveCount(0);
  await expect(page.locator('[data-robustness-facts],[data-controls-facts]')).toHaveCount(0);
  expect(JSON.stringify(facts).length).toBeLessThan(10240);
  await expect(home.locator('a[data-topic=factors]')).toHaveAttribute('href',prefix+'factors/');
  for(const theme of ['light','dark']){
   await page.locator('#theme-preference').selectOption(theme);
   await page.screenshot({path:info.outputPath(`${locale}-home-${theme}.png`),fullPage:true});
  }
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath(`${locale}-home-mobile.png`),fullPage:true});
 });

 test(`${locale}: history preserves prior facts and local fragments reveal their targets`,async({page})=>{
  await page.goto(prefix);
  const history=page.locator('#research-history');await expect(history).toHaveCount(1,{timeout:3000});
  await history.locator(':scope > summary').focus();await page.keyboard.press('Enter');
  await expect(history).toHaveAttribute('open','');
  await expect(history.locator('[data-controls-highlight]')).toHaveCount(2);
  await expect(history.locator('[data-takeaway]')).toHaveCount(3);
  const crypto=JSON.parse(await history.locator('[data-controls-highlight=crypto]').getAttribute('data-highlight-facts'));
  expect([crypto.feeBps,crypto.windows,crypto.returnWins]).toEqual([25,12,7]);
  for(const fragment of ['strategy-controls','takeaways','%74akeaways']){
   await page.goto(prefix+'#'+fragment);await expect(page.locator('#research-history')).toHaveAttribute('open','');
   await expect(page.locator('#'+decodeURIComponent(fragment))).toBeVisible();
  }
  await page.goto(prefix+'#title-crypto');await expect(page).toHaveURL(prefix+'docs/project/#title-crypto');
  await expect(page.locator('#title-crypto')).toBeVisible();
 });
}

test('editorial facts and native history remain available without JavaScript',async({browser})=>{
 const context=await browser.newContext({javaScriptEnabled:false});const page=await context.newPage();
 await page.goto('/2026-quant-competition/');
 await expect(page.locator('[data-editorial-pool]')).toHaveCount(3,{timeout:3000});
 await page.locator('#research-history > summary').click();
 await expect(page.locator('#takeaways')).toBeVisible();
 await expect(page.locator('a[data-legacy-link=demo]')).toHaveAttribute('href','/2026-quant-competition/docs/project/#demo');
 await context.close();
});
