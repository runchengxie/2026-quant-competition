import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
const snapshot=JSON.parse(await readFile(new URL('../src/data/strategy-robustness.v1.json',import.meta.url),'utf8'));

test('robustness comparisons keep exact bilingual facts across fees, windows and themes',async({page},testInfo)=>{
 for(const locale of ['en','zh-CN']){
  await page.setViewportSize({width:1360,height:1000});
  const prefix=`/global-market-research/${locale==='en'?'':'zh-CN/'}`;
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
 await page.setViewportSize({width:1360,height:1000});await page.goto('/global-market-research/strategies/');
 const root=page.locator('#robustness');await root.scrollIntoViewIfNeeded();await expect(root).toHaveAttribute('data-ready','true');
 await page.setViewportSize({width:390,height:844});
 await expect.poll(()=>root.locator('[data-robustness-chart=paired]').evaluate(node=>{
  const canvas=node.querySelector('canvas');
  return canvas&&Math.abs(canvas.getBoundingClientRect().width-node.clientWidth)<2;
 })).toBe(true);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

// Inspect actual ECharts instances from the shared built module, without adding
// production debug globals or depending on hashed asset names/export letters.
async function chartState(page,selector,seed=false){
 return page.evaluate(async({selector,seed})=>{
  const url=performance.getEntriesByType('resource').map(r=>r.name).find(url=>/\/installCanvasRenderer\.[^/]+\.js/.test(url));
  const module=await import(url);
  const init=Object.values(module).find(value=>typeof value==='function'&&value.toString().includes('afterinit')&&value.toString().includes('.ssr'));
  if(!init)throw new Error('Cannot locate the shared ECharts init export');
  const chart=init(document.querySelector(selector));
  if(seed){
   chart.dispatchAction({type:'dataZoom',start:25,end:70});
   const name=chart.getOption().series[0].name;
   if(name)chart.dispatchAction({type:'legendUnSelect',name});
  }
  const option=chart.getOption();
  const probe=document.createElement('span');probe.style.color='var(--ink)';document.body.append(probe);
  const paletteMatches=option.textStyle.color===getComputedStyle(probe).color;probe.remove();
  return {paletteMatches,zoom:option.dataZoom.map(({start,end})=>({start,end})),legend:option.legend?.map(({selected})=>selected)??[]};
 },{selector,seed});
}

const targets=[['#robustness','[data-robustness-chart=windows]'],['#strategy-controls','[data-controls-chart=paired]'],['#ablation','[data-ablation-chart=paired]'],['#performance','[data-chart=comparison]']];
for(const [root,chart] of targets)for(const blockedStorage of [false,true])test(`${root} retains interactions across appearance changes (blocked storage: ${blockedStorage})`,async({page})=>{
 if(blockedStorage)await page.addInitScript(()=>{Storage.prototype.setItem=()=>{throw new Error('Storage unavailable');};});
 await page.emulateMedia({colorScheme:'light',reducedMotion:'reduce'});
 await page.goto('/global-market-research/strategies/');
  await page.locator(root).scrollIntoViewIfNeeded();
  await expect(page.locator(root)).toHaveAttribute('data-ready','true');
  const selector=`${root} ${chart}`,before=await chartState(page,selector,true);
  expect(before.paletteMatches).toBe(true);
  expect(before.zoom[0]).toEqual({start:25,end:70});
  await page.locator('#theme-preference').selectOption('dark');
  await expect.poll(()=>chartState(page,selector)).toEqual(before);
  await page.locator('#theme-preference').selectOption('system');
  await expect.poll(()=>chartState(page,selector)).toEqual(before);
  await page.emulateMedia({colorScheme:'dark'});
  await expect.poll(()=>chartState(page,selector)).toEqual(before);
  await page.emulateMedia({colorScheme:'light'});
  await page.locator('#theme-preference').selectOption('light');
});

test('without JavaScript the complete reviewed table remains available',async({browser})=>{
 const context=await browser.newContext({javaScriptEnabled:false});const page=await context.newPage();
 await page.goto('/global-market-research/zh-CN/strategies/');
 const root=page.locator('#robustness');
 await expect(root.locator('[data-robustness-row]')).toHaveCount(114);
 await expect(root.locator('canvas')).toHaveCount(0);
 await context.close();
});
