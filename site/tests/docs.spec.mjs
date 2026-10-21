import { test,expect } from "@playwright/test";

test("curated documentation is integrated and language switches retain the article",async({page})=>{
  for(const slug of ["architecture","quickstart","datasets","study","strategies"]){
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
  await expect(page.locator("main [data-doc-slug]")).toHaveCount(5);
  const response=await page.goto("/2026-quant-competition/docs/internal-secret/");
  expect(response.status()).toBe(404);
});
