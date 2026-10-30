import {test,expect} from '@playwright/test';
for(const prefix of ['', 'zh-CN/']) for(const view of ['strategies','factors']) {
 test(`${prefix}${view} tree study retains matched evidence`,async({page},info)=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto(`/global-market-research/${prefix}${view}/#tree-study`);
  const section=page.locator('#tree-study');
  await expect(section).toBeAttached();
  await expect(section).toHaveAttribute('data-tree-ready','true');
  await expect(section.locator('[data-tree-context]:visible')).toHaveCount(0);
  await expect(section.locator('[data-tree-row]:visible')).toHaveCount(view==='strategies'?9:2);
  await section.locator('[data-tree-filter="window"]').selectOption('2026-07-27');
  await section.locator('[data-tree-filter="horizon"]').selectOption('20');
  if(view==='strategies') {
    await section.locator('[data-tree-filter="fee_bps"]').selectOption('40');
    await section.locator('[data-tree-filter="delay"]').selectOption('1');
    await section.locator('[data-tree-filter="buffer"]').selectOption('20');
  }
  const visible=section.locator('[data-tree-row]:visible');
  await expect(visible).toHaveCount(view==='strategies'?9:2);
  for(const row of await visible.all()) {
    await expect(row).toHaveAttribute('data-window','2026-07-27');
    await expect(row).toHaveAttribute('data-horizon','20');
  }
  await section.screenshot({path:info.outputPath('tree-study-desktop.png')});
  await page.setViewportSize({width:390,height:844});
  await expect(section.locator('[data-tree-context-summary]')).toContainText('2026-07-27');
  if(view==='factors') {
    await expect(section.locator('[data-tree-row]:visible th').first()).toHaveCSS('white-space','nowrap');
    const ic=await section.locator('[data-tree-ic]:visible').first().boundingBox();
    expect(ic.x+ic.width).toBeLessThanOrEqual(390);
  }
  await page.locator('#theme-preference').selectOption('dark');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await section.screenshot({path:info.outputPath('tree-study-mobile-dark.png')});
  expect(errors).toEqual([]);
 });
 test(`${prefix}${view} tree study works without JavaScript`,async({browser})=>{
  const context=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});
  const page=await context.newPage();
  await page.goto(`/global-market-research/${prefix}${view}/#tree-study`);
  const section=page.locator('#tree-study');
  await expect(section.locator('[data-tree-row]')).toHaveCount(view==='strategies'?432:8);
  await expect(section.locator('[data-tree-row][hidden]')).toHaveCount(0);
  await expect(section.locator('[data-tree-controls]')).toBeHidden();
  expect(await section.locator('[data-tree-context]:visible').count()).toBeGreaterThan(0);
  await expect(section.locator('[data-tree-gaps] li')).toHaveCount(6);
  await context.close();
 });
}
