import {test,expect} from "@playwright/test";
import {readFile} from "node:fs/promises";
for(const section of ["ablation","performance"])test(`${section}: charts cannot widen the mobile page while resize callbacks are delayed`,async({page})=>{
 await page.addInitScript(()=>{
  const Native=window.ResizeObserver;
  window.ResizeObserver=class extends Native{constructor(callback){super((entries,observer)=>setTimeout(()=>callback(entries,observer),1000));}};
 });
 await page.goto('/global-market-research/strategies/');
 const root=page.locator('#'+section);await root.scrollIntoViewIfNeeded();await expect(root).toHaveAttribute('data-ready','true');
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
for(const locale of ["en","zh-CN"]){
 test(`${locale}: post_hoc_badge_survives_every_filter_and_locale`,async({page})=>{
  const errors=[];page.on("pageerror",e=>errors.push(e.message));
  await page.goto(locale==="en"?"/global-market-research/strategies/":"/global-market-research/zh-CN/strategies/");
  const root=page.locator("#ablation");await expect(root).toBeVisible();await root.scrollIntoViewIfNeeded();await expect(root).toHaveAttribute("data-ready","true");
  await expect(root.locator("canvas")).toHaveCount(2);
  await root.locator("[data-ablation-filter=market]").selectOption("crypto");
  await root.locator("details[data-ablation-market=crypto] > summary").click();
  await root.locator("[data-ablation-filter=variant]").selectOption("fixed_exposure_60pct");
  await expect(root.locator("[data-ablation-role-note]")).toBeVisible();
  for(const fee of ["0","10","25"]){
   await root.locator("[data-ablation-filter=fee]").selectOption(fee);
   const rows=await root.locator("[data-ablation-id]:visible").evaluateAll(ns=>ns.map(n=>JSON.parse(n.dataset.facts)));
   expect(rows.length).toBeGreaterThan(0);expect(rows.every(r=>r.evidence_role==="post_hoc_diagnostic"&&r.cost_bps===Number(fee))).toBe(true);
   await expect(root.locator("[data-ablation-role=post_hoc_diagnostic]:visible").first()).toHaveText(locale==="en"?"Post-hoc diagnostic":"事后诊断");
  }
  const facts=await root.locator("[data-ablation-id]").evaluateAll(ns=>ns.map(n=>JSON.parse(n.dataset.facts)));
  const original=JSON.parse(await readFile(new URL("../src/data/real-data-study.v1.json",import.meta.url),"utf8"));
  expect(await page.locator("[data-study-id]").evaluateAll(ns=>ns.map(n=>JSON.parse(n.dataset.facts)).sort((a,b)=>a.job_id.localeCompare(b.job_id)))).toEqual([...original.results].sort((a,b)=>a.job_id.localeCompare(b.job_id)));
  for(const theme of ["dark","light","system"]){
   await page.locator("#theme-preference").selectOption(theme);await expect(root).toHaveAttribute("data-ready","true");
   await expect(root).toHaveAttribute("data-chart-colors",/rgb\(/);
   await expect.poll(async()=>root.evaluate(n=>JSON.parse(n.dataset.chartColors).ink===getComputedStyle(n).color)).toBe(true);
  }
  expect(await root.locator("[data-ablation-id]").evaluateAll(ns=>ns.map(n=>JSON.parse(n.dataset.facts)))).toEqual(facts);
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  expect(errors).toEqual([]);
 });
}
test("no JavaScript retains every ablation fact and explicit evidence label",async({browser})=>{
 const context=await browser.newContext({javaScriptEnabled:false});const page=await context.newPage();
 await page.goto("http://127.0.0.1:4397/global-market-research/strategies/");
 const root=page.locator("#ablation");await expect(root.getByText("Post-hoc diagnostic",{exact:true}).first()).toBeVisible();
 const snapshot=JSON.parse(await readFile(new URL("../src/data/ablation-study.v1.json",import.meta.url),"utf8"));
 await expect(root.locator("[data-ablation-id]")).toHaveCount(snapshot.results.length);
 await context.close();
});
