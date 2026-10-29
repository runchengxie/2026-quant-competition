import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
const predictive=JSON.parse(await readFile(new URL('../src/data/equity-predictive.v1.json',import.meta.url),'utf8'));

for(const locale of ['en','zh-CN'])test(`${locale}: fee cells select actual windows and capital units survive appearance changes`,async({page})=>{
 await page.goto(`/global-market-research/${locale==='zh-CN'?'zh-CN/':''}strategies/`);
 const root=page.locator('#performance');await root.scrollIntoViewIfNeeded();await expect(root).toHaveAttribute('data-ready','true');
 await expect(root.locator('[data-chart=heatmap] canvas').first()).toBeVisible();
 const cell=root.locator('[data-fee-cell]').first();const job=await cell.getAttribute('data-job');
 await cell.focus();await page.keyboard.press('Enter');
 expect(JSON.parse(await root.locator('[data-dashboard-selected]').getAttribute('data-facts')).job_id).toBe(job);
 const points=JSON.parse(await root.locator('[data-chart=nav]').getAttribute('data-points'));
 await root.locator('[data-capital-view]').check();
 const capital=JSON.parse(await root.locator('[data-chart=nav]').getAttribute('data-capital'));
 expect(capital.points[0].net_capital).toBe(points[0].net_nav*10000);expect(capital.currency).toBe('USD');
 await page.getByLabel(locale==='en'?'Appearance':'外观').selectOption('dark');
 await page.emulateMedia({colorScheme:'dark'});await expect(root.locator('[data-capital-view]')).toBeChecked();
 expect(JSON.parse(await root.locator('[data-dashboard-selected]').getAttribute('data-facts')).job_id).toBe(job);
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await root.locator('[data-reset]').click();await expect(root.locator('[data-capital-view]')).not.toBeChecked();
});

test('predictive evidence preserves null scores, locales and no-JS tables',async({page,browser},testInfo)=>{
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 for(const locale of ['en','zh-CN']){
  await page.goto(`/global-market-research/${locale==='zh-CN'?'zh-CN/':''}factors/`);
  const root=page.locator('#equity-predictive');await root.scrollIntoViewIfNeeded();
  expect(JSON.parse(await root.getAttribute('data-predictive-facts'))).toEqual(predictive);
  await expect(root).toHaveAttribute('data-predictive-ready','true');
  await expect(root.locator('tbody tr')).toHaveCount(12);
  await expect(root.locator('tbody tr').nth(1).locator('td').nth(1)).toHaveText(locale==='en'?'Undefined':'无法计算');
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.getByLabel(locale==='en'?'Appearance':'外观').selectOption('dark');
  await expect(root).toHaveAttribute('data-chart-ink','rgb(233, 231, 224)');
  await root.screenshot({path:testInfo.outputPath(`predictive-${locale}.png`)});
 }
 expect(errors).toEqual([]);
 const context=await browser.newContext({javaScriptEnabled:false});const plain=await context.newPage();
 await plain.goto('/global-market-research/factors/');await expect(plain.locator('#equity-predictive tbody tr')).toHaveCount(12);
 await plain.goto('/global-market-research/strategies/');await expect(plain.locator('#performance [data-reader-cells] tr')).toHaveCount(11);
 await context.close();
});
