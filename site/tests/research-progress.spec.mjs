import {test,expect} from '@playwright/test';

for(const locale of ['en','zh-CN']) {
  test(`${locale}: governance progress remains readable on mobile without JavaScript`,async({browser},info)=>{
    const context=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});
    const page=await context.newPage();
    const prefix=`/global-market-research/${locale==='en'?'':'zh-CN/'}`;
    await page.goto(`${prefix}research/progress/`);
    await expect(page.locator('main h1')).toHaveCount(1);
    await expect(page.locator('main li')).toHaveCount(6);
    const facts=JSON.parse(await page.locator('main').getAttribute('data-next-stage-facts'));
    expect(facts.accepted_research).toBe(false);
    expect(facts.future_authorized_fit_cap).toBe(0);
    expect(facts.retrospective_model_blocks).toBe(16);
    await expect(page.locator('[data-site-nav=progress]')).toHaveAttribute('aria-current','page');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.screenshot({path:info.outputPath(`${locale}-research-progress-mobile.png`),fullPage:true});
    await page.locator(`a[href="${prefix}docs/research-model-catalog/"]`).click();
    await expect(page.locator('main')).toContainText('Elastic Net');
    await context.close();
  });
}
