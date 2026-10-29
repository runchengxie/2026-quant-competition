import {test,expect} from '@playwright/test';

for(const locale of ['en','zh-CN']) {
 const prefix=`/global-market-research/${locale==='en'?'':'zh-CN/'}`;
 test(`${locale}: a concise home and all CNN entry points lead to the topic`,async({browser},info)=>{
  const context=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});
  const page=await context.newPage();
  await page.goto(prefix);
  await expect(page.locator('main h1')).toHaveCount(1);
  await expect(page.locator('[data-site-nav=home]')).toHaveCount(0);
  await expect(page.locator('[data-site-nav=markets],[data-site-nav=docs]')).toHaveCount(2);
  for(const market of ['us','hk','crypto']) await expect(page.locator(`[data-home-market=${market}]`)).toHaveAttribute('href',`${prefix}markets/#market-${market}`);
  await expect(page.locator('[data-home-feature]')).toHaveCount(2);
  await expect(page.locator('[data-editorial-pool],[data-controls-highlight],[data-takeaway]')).toHaveCount(0);
  await expect(page.locator('[data-cnn-note]')).toHaveAttribute('href',`${prefix}research/cnn-chart/`);
  await expect(page.locator('#research-progress-title')).toHaveAttribute('href',`${prefix}strategies/#research-progress-title`);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath(`${locale}-home-mobile.png`),fullPage:true});
  await page.goto(`${prefix}docs/project/#demo`);
  await expect(page.locator('[data-cnn-note]')).toHaveAttribute('href',`${prefix}research/cnn-chart/`);
  await page.goto(`${prefix}docs/`);
  await expect(page.locator('[data-doc-slug=cnn-chart-research]')).toHaveAttribute('href',`${prefix}research/cnn-chart/`);
  await page.goto(`${prefix}docs/cnn-chart-research/`);
  await expect(page.locator('[data-cnn-topic-link]')).toHaveAttribute('href',`${prefix}research/cnn-chart/`);
  await context.close();
 });
}
