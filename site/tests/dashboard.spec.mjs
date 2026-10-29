import { test,expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
const study=JSON.parse(await readFile(new URL("../src/data/real-data-study.v1.json",import.meta.url),"utf8"));
const series=JSON.parse(await readFile(new URL("../src/data/real-data-series.v1.json",import.meta.url),"utf8"));

for(const locale of ["en","zh-CN"]){
  test(`${locale}: interactive charts retain published facts across filters and themes`,async({page})=>{
    const errors=[];
    page.on("pageerror",e=>errors.push(e.message));
    await page.goto(locale==="en"?"/2026-quant-competition/strategies/":"/2026-quant-competition/zh-CN/strategies/");
    const root=page.locator("#performance");
    await root.scrollIntoViewIfNeeded();
    await expect(root).toHaveAttribute("data-ready","true");
    await expect(root.locator('[data-chart]')).toHaveCount(10);
    for(const chart of await root.locator('[data-chart]').all())await expect(chart.locator('canvas').first()).toBeVisible();
    await root.locator("[data-filter=market]").selectOption("crypto");
    await root.locator("[data-filter=strategy]").selectOption("trend_200d");
    await root.locator("[data-filter=fee]").selectOption("10");
    const selected=await root.locator("[data-dashboard-selected]").getAttribute("data-facts").then(JSON.parse);
    expect(selected).toEqual(study.results.find(r=>r.job_id===selected.job_id));
    expect(selected.market).toBe("crypto");expect(selected.cost_bps).toBe(10);
    expect(selected.quote_currency).toBe("USDT");
    const actual=await root.locator("[data-chart=nav]").getAttribute("data-points").then(JSON.parse);
    expect(actual).toEqual(series.series.find(r=>r.job_id===selected.job_id).points);
    const windows=await root.locator("[data-filter=window] option").evaluateAll(nodes=>nodes.map(n=>n.value));
    await root.locator("[data-filter=window]").selectOption(windows.at(-1));
    const changed=await root.locator("[data-dashboard-selected]").getAttribute("data-facts").then(JSON.parse);
    expect(changed.start).toBe(windows.at(-1));
    await root.locator("[data-toggle-gross]").uncheck();
    await expect(root).toHaveAttribute("data-gross-visible","false");
    await root.locator("[data-zoom-window]").focus();
    await page.keyboard.press("Home");
    await expect(root).toHaveAttribute("data-zoom","20");
    await root.locator("[data-reset]").click();
    await expect(root).toHaveAttribute("data-zoom","100");
    await root.locator("[data-filter=strategy]").selectOption("benchmark_buy_hold");
    await expect(root.locator("[data-curve-unavailable]")).toBeVisible();
    await expect(root.locator("[data-chart=nav]")).toHaveAttribute("data-points","[]");
    for(const theme of ["light","dark","system"]){
      await page.getByLabel(locale==="en"?"Appearance":"外观").selectOption(theme);
      await page.setViewportSize({width:390,height:844});
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    }
    expect(errors).toEqual([]);
    await expect(root.locator("a[data-documentation]")).toHaveAttribute("href",locale==="en"?"/2026-quant-competition/docs/":"/2026-quant-competition/zh-CN/docs/");
  });
}
test("published evidence remains readable without JavaScript",async({browser})=>{
  const context=await browser.newContext({javaScriptEnabled:false});
  const page=await context.newPage();
  await page.goto("/2026-quant-competition/strategies/");
  await expect(page.locator("#performance h2")).toBeVisible();
  await expect(page.locator("#performance [data-filter=market]")).toBeDisabled();
  await expect(page.locator("[data-study-id]")).toHaveCount(318);
  await context.close();
});

test('research summaries expose fixed assumptions and localized stable statistics',async({page})=>{
 let canonical;
 for(const locale of ['en','zh-CN']){
  await page.goto(locale==='en'?'/2026-quant-competition/strategies/':'/2026-quant-competition/zh-CN/strategies/');
  await page.goto(locale==='en'?'/2026-quant-competition/docs/project/':'/2026-quant-competition/zh-CN/docs/project/');
  await expect(page.locator('[data-market-summary]')).toHaveCount(3);
  const facts=await page.locator('[data-summary-facts]').evaluateAll(nodes=>nodes.map(n=>JSON.parse(n.dataset.summaryFacts)));
  if(canonical)expect(facts).toEqual(canonical);else canonical=facts;
  for(const fact of facts){expect(fact.feeBps).toBe({US:20,HK:30,crypto:10}[fact.market]);const rows=study.results.filter(r=>r.market===fact.market&&r.strategy===fact.strategy&&r.cost_bps===fact.feeBps);expect(fact.count).toBe(rows.length);expect(fact.worstNetReturn).toBe(Math.min(...rows.map(r=>r.net_return)));}
  await page.goto(locale==='en'?'/2026-quant-competition/strategies/':'/2026-quant-competition/zh-CN/strategies/');
  const root=page.locator('#performance');await root.scrollIntoViewIfNeeded();await expect(root).toHaveAttribute('data-ready','true');
  await expect(root.locator('[data-stability]')).toHaveAttribute('data-count','11');
  await root.locator('[data-filter=market]').selectOption('crypto');
  await root.locator('[data-filter=strategy]').selectOption('equal_weight');
  await expect(root.locator('[data-strategy-description]')).toContainText(locale==='en'?'drift':'漂移');
  await expect(root.locator('[data-stability]')).toHaveAttribute('data-count',String(study.results.filter(r=>r.market==='crypto'&&r.strategy==='equal_weight'&&r.cost_bps===10).length));
  await root.locator('[data-toggle-gross]').uncheck();
  await page.getByLabel(locale==='en'?'Appearance':'外观').selectOption('dark');
  await expect(root.locator('[data-toggle-gross]')).not.toBeChecked();
 }
});


test('legend choice and panned curve range survive a theme change',async({page})=>{
 await page.goto('/2026-quant-competition/strategies/');const root=page.locator('#performance');await root.scrollIntoViewIfNeeded();await expect(root).toHaveAttribute('data-ready','true');
 const canvas=root.locator('[data-chart=nav] canvas');const box=await canvas.boundingBox();
 await canvas.click({position:{x:box.width/2+40,y:12}});
 await expect(root.locator('[data-toggle-gross]')).not.toBeChecked();
 await root.locator('[data-zoom-window]').fill('40');await root.locator('[data-zoom-window]').dispatchEvent('input');
 await canvas.scrollIntoViewIfNeeded();
 const b=await canvas.boundingBox();const width=b.width-80;
 await page.mouse.move(b.x+58+width*.8,b.y+286);await page.mouse.down();await page.mouse.move(b.x+58+width*.5,b.y+286,{steps:5});await page.mouse.up();
 await expect.poll(async()=>JSON.parse(await root.locator('[data-chart=nav]').getAttribute('data-range')).end).toBeLessThan(72);
 const range=await root.locator('[data-chart=nav]').getAttribute('data-range');expect(range).not.toBeNull();expect(JSON.parse(range).end).toBeLessThan(99);
 await page.getByLabel('Appearance').selectOption('dark');
 await expect(root.locator('[data-chart=nav]')).toHaveAttribute('data-range',range);
 await expect(root.locator('[data-toggle-gross]')).not.toBeChecked();
});

test('matched strategy comparison and fee robustness preserve published conditions in both locales',async({page})=>{
 let canonical;
 for(const locale of ['en','zh-CN']){
  await page.goto(locale==='en'?'/2026-quant-competition/strategies/':'/2026-quant-competition/zh-CN/strategies/');
  const root=page.locator('#performance');await root.scrollIntoViewIfNeeded();await expect(root).toHaveAttribute('data-ready','true');
  await expect(root.locator('[data-comparison-row]')).toHaveCount(2);
  await root.locator('[data-compare=third]').selectOption('momentum_20d');await expect(root.locator('[data-comparison-row]')).toHaveCount(3);
  const rows=await root.locator('[data-comparison-row]').evaluateAll(ns=>ns.map(n=>JSON.parse(n.dataset.facts)));
  for(const row of rows){expect(row).toEqual(study.results.find(r=>r.job_id===row.job_id));expect(row.start).toBe(rows[0].start);expect(row.end).toBe(rows[0].end);expect(row.cost_bps).toBe(20);}
  await root.locator('[data-filter=market]').selectOption('crypto');await root.locator('[data-filter=strategy]').selectOption('trend_200d');
  await root.locator('[data-compare=second]').selectOption('equal_weight');await root.locator('[data-compare=third]').selectOption('momentum_63d');
  await expect(root.locator('[data-comparison-row]')).toHaveCount(3);
  const feeFacts=await root.locator('[data-fee-row]').evaluateAll(ns=>ns.map(n=>JSON.parse(n.dataset.feeFacts)));
  expect(feeFacts.map(f=>f.feeBps)).toEqual([0,10,25]);expect(feeFacts.map(f=>f.summary.count)).toEqual([12,12,12]);
  if(canonical)expect(feeFacts).toEqual(canonical);else canonical=feeFacts;
  for(const fact of feeFacts){const rows=study.results.filter(r=>r.market==='crypto'&&r.strategy==='trend_200d'&&r.cost_bps===fact.feeBps);expect(fact.positiveNetCount).toBe(rows.filter(r=>r.net_return>0).length);}
  await expect(root.locator('[data-strategy-guide]')).toHaveAttribute('href',`${locale==='en'?'/2026-quant-competition/':'/2026-quant-competition/zh-CN/'}docs/strategies/#trend-200d`);
  await root.locator('[data-strategy-guide]').click();await expect(page.locator('main article h1')).toBeVisible();
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 }
});

test("both languages lead with traceable conclusions and retain evidence without JavaScript",async({browser})=>{
 const context=await browser.newContext({javaScriptEnabled:false});const page=await context.newPage();
 for(const locale of ["en","zh-CN"]){
  await page.goto(locale==="en"?"/2026-quant-competition/":"/2026-quant-competition/zh-CN/");
  await expect(page.locator("main > :first-child")).toHaveAttribute("id","robustness");
  await expect(page.locator("#takeaways [data-home-market]")).toHaveCount(3);
  await expect(page.locator("[data-home-feature]")).toHaveCount(2);
  expect(await page.locator("main > [id]").evaluateAll(ns=>ns.map(n=>n.id))).toEqual(["robustness"]);
  await expect(page.locator("[data-scope]")).toBeVisible();
  await page.goto(locale==="en"?"/2026-quant-competition/docs/project/":"/2026-quant-competition/zh-CN/docs/project/");
  await expect(page.locator("#evidence")).toContainText(locale==="en"?"10 US stocks":"10 只美股");
  await page.goto(locale==="en"?"/2026-quant-competition/strategies/":"/2026-quant-competition/zh-CN/strategies/");
  await expect(page.locator("[data-study-id]")).toHaveCount(318);await expect(page.locator("[data-ablation-id]")).toHaveCount(678);

 }
 await context.close();
});
