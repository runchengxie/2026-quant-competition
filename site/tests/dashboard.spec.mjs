import { test,expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
const study=JSON.parse(await readFile(new URL("../src/data/real-data-study.v1.json",import.meta.url),"utf8"));
const series=JSON.parse(await readFile(new URL("../src/data/real-data-series.v1.json",import.meta.url),"utf8"));

for(const locale of ["en","zh-CN"]){
  test(`${locale}: interactive charts retain published facts across filters and themes`,async({page})=>{
    const errors=[];
    page.on("pageerror",e=>errors.push(e.message));
    await page.goto(locale==="en"?"/2026-quant-competition/":"/2026-quant-competition/zh-CN/");
    const root=page.locator("#performance");
    await root.scrollIntoViewIfNeeded();
    await expect(root).toHaveAttribute("data-ready","true");
    await expect(root.locator("canvas")).toHaveCount(8);
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
  await page.goto("/2026-quant-competition/");
  await expect(page.locator("#performance h2")).toBeVisible();
  await expect(page.locator("#performance [data-filter=market]")).toBeDisabled();
  await expect(page.locator("[data-study-id]")).toHaveCount(318);
  await context.close();
});
