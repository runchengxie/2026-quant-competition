import {test,expect} from '@playwright/test';

test('incremental evidence keeps selectors charts tables and locales consistent',async({page},testInfo)=>{
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 for(const locale of ['en','zh-CN']){
  const prefix=`/global-market-research/${locale==='en'?'':'zh-CN/'}`;
  await page.goto(`${prefix}factors/`);
  const equity=page.locator('#incremental-equity');
  await equity.scrollIntoViewIfNeeded();
  await expect(equity).toHaveAttribute('data-incremental-ready','true');
  await equity.locator('[data-model]').selectOption('shallow_tree');
  await equity.locator('[data-period]').selectOption('2');
  await expect(equity).toHaveAttribute('data-chart-model','shallow_tree');
  await expect(equity).toHaveAttribute('data-chart-period','2');
  await expect(equity.locator('[data-equity-row]:visible')).toHaveCount(7);
  await expect(equity.locator('[data-stratum-row]:visible')).not.toHaveCount(0);
  const facts=await equity.getAttribute('data-incremental-facts');
  expect(JSON.parse(facts).equity.fit_attempts).toBe(45);
  await page.setViewportSize({width:390,height:844});
  await page.getByLabel(locale==='en'?'Appearance':'外观').selectOption('dark');
  await expect(equity).toHaveAttribute('data-chart-ink','rgb(233, 231, 224)');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await equity.screenshot({path:testInfo.outputPath(`incremental-equity-${locale}.png`)});
  await page.goto(`${prefix}strategies/#incremental-crypto`);
  const crypto=page.locator('#incremental-crypto');
  await crypto.scrollIntoViewIfNeeded();
  await expect(crypto).toHaveAttribute('data-incremental-ready','true');
  await crypto.locator('[data-fee]').selectOption('50');
  await crypto.locator('[data-window]').selectOption('2023-09-10');
  await expect(crypto.locator('[data-crypto-row]:visible')).toHaveCount(5);
  await expect(crypto).toHaveAttribute('data-chart-fee','50');
  expect(await crypto.getAttribute('data-incremental-facts')).toBe(facts);
  expect(errors).toEqual([]);
 }
});
