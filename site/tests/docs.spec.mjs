import { test,expect } from "@playwright/test";

test("hourly factor pilot keeps blocked facts equal across languages without private metrics",async({page,browser})=>{
 let canonical;
 for(const locale of ["en","zh-CN"]){
  const prefix=`/2026-quant-competition/${locale==="en"?"":"zh-CN/"}`;
  await page.goto(`${prefix}factors/`);
  const panel=page.locator("#dex-factor-pilot");
  await expect(panel).toBeVisible();
  const facts=JSON.parse(await panel.getAttribute("data-dex-facts"));
  expect(facts.status).toBe("readiness_only");
  expect(facts.blockers).toContain("DEX_ACQUISITION_BLOCKED");
  expect(facts).not.toHaveProperty("metrics");expect(facts).not.toHaveProperty("coverage");
  if(canonical) expect(facts).toEqual(canonical); else canonical=facts;
  await expect(panel.locator("[data-dex-signal]")).toHaveCount(4);
  await expect(panel.locator("[data-dex-metric]")).toHaveCount(0);
  for(const theme of ["light","dark","system"]){await page.getByLabel(locale==="en"?"Appearance":"外观").selectOption(theme);}
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 }
 const context=await browser.newContext({javaScriptEnabled:false});const nojs=await context.newPage();
 await nojs.goto("/2026-quant-competition/factors/");await expect(nojs.locator("#dex-factor-pilot")).toBeVisible();
 expect(JSON.parse(await nojs.locator("#dex-factor-pilot").getAttribute("data-dex-facts"))).toEqual(canonical);
 await context.close();
});

test("old nested demo and summary anchors retain their targets",async({page})=>{
 for(const [fragment,target] of [["title-stock","title-stock"],["title-crypto","title-crypto"],["research-summary-title","research-summary-title"]]){
  await page.goto(`/2026-quant-competition/#${fragment}`);
  await expect(page).toHaveURL(`/2026-quant-competition/docs/project/#${target}`);
  await expect(page.locator(`#${target}`)).toBeVisible();
 }
});

test("research pages separate results, factor evidence and offline guides",async({page,browser})=>{
 for(const locale of ["en","zh-CN"]){
  const prefix=`/2026-quant-competition/${locale==="en"?"":"zh-CN/"}`;
  await page.goto(prefix);await page.locator('#research-history > summary').click();await expect(page.locator("#takeaways")).toBeVisible();await expect(page.locator("#demo,#performance,#ablation")).toHaveCount(0);
  await page.locator("[data-site-nav=strategies]").click();await expect(page).toHaveURL(`${prefix}strategies/`);
  await expect(page.locator("[data-study-id]")).toHaveCount(318);await expect(page.locator("[data-ablation-id]")).toHaveCount(678);
  await page.locator("[data-site-nav=factors]").click();await expect(page.locator("[data-factor-signal]")).toHaveCount(4);await expect(page.locator("[data-factor-status]")).toHaveCount(4);await expect(page.locator("[data-factor-score]")).toHaveCount(0);
  await page.getByRole("navigation",{name:locale==="en"?"Language":"语言选择",exact:true}).getByRole("link",{name:locale==="en"?"简体中文":"English",exact:true}).click();await expect(page).toHaveURL(new RegExp(`/${locale==="en"?"zh-CN/":""}factors/$`));
  await page.goto(`${prefix}docs/project/`);await expect(page.locator("#demo")).toBeVisible();await expect(page.locator("#engineering")).toBeVisible();await expect(page.locator("[data-result-id]")).toHaveCount(24);await page.locator("label[for=path-crypto]").click();await expect(page.locator(".panel-crypto")).toBeVisible();
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.goto(`${prefix}#demo`);await expect(page).toHaveURL(`${prefix}docs/project/#demo`);
 }
 const context=await browser.newContext({javaScriptEnabled:false});const p=await context.newPage();await p.goto('/2026-quant-competition/');await expect(p.locator('a[data-legacy-link=demo]')).toHaveAttribute('href','/2026-quant-competition/docs/project/#demo');await context.close();
});

test("curated documentation is integrated and language switches retain the article",async({page})=>{
  for(const slug of ["architecture","quickstart","datasets","study","strategies","strategy-controls","execution-evidence","observation-registry","strategy-robustness","data-refresh","native-process-diagnostics"]){
    await page.goto(`/2026-quant-competition/docs/${slug}/`);
    await expect(page.locator("main article h1").first()).toBeVisible();
    await page.getByLabel("Appearance").selectOption("dark");
    await page.getByRole("navigation",{name:"Language",exact:true}).getByRole("link",{name:"简体中文",exact:true}).click();
    await expect(page).toHaveURL(new RegExp(`/zh-CN/docs/${slug}/$`));
    await expect(page.getByLabel("外观")).toHaveValue("dark");
    await expect(page.locator("main article h1").first()).toBeVisible();
    await page.setViewportSize({width:390,height:844});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  }
  await page.goto("/2026-quant-competition/docs/");
  await expect(page.locator("main [data-doc-slug]")).toHaveCount(12);
  const response=await page.goto("/2026-quant-competition/docs/internal-secret/");
  expect(response.status()).toBe(404);
});
