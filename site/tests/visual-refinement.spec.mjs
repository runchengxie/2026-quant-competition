import {test,expect} from '@playwright/test';

for(const locale of ['en','zh-CN'])for(const route of ['', 'markets/', 'research/cnn-chart/']) {
 const prefix=`/2026-quant-competition/${locale==='en'?'':'zh-CN/'}`;
 test(`${locale} ${route||'home'} keeps a readable hierarchy across sizes and themes`,async({page},info)=>{
  await page.goto(prefix+route);
  await expect(page.locator('main h1')).toHaveCount(1);
  await expect(page.locator('main')).toBeVisible();
  for(const theme of ['light','dark']) {
   await page.locator('#theme-preference').selectOption(theme);
   for(const width of [1440,390]) {
    await page.setViewportSize({width,height:900});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    const heading=page.locator('main h1');
    const box=await heading.boundingBox();expect(box.width).toBeLessThanOrEqual(width);
    if(locale==='zh-CN')await page.screenshot({path:info.outputPath(`${route.replaceAll('/','-')||'home'}-${theme}-${width}.png`),fullPage:true});
   }
  }
 });
}
