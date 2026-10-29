import {test, expect} from '@playwright/test';

for (const locale of ['en','zh-CN']) {
  const prefix = `/2026-quant-competition/${locale === 'en' ? '' : 'zh-CN/'}`;
  test(`${locale}: market directory works without JavaScript and preserves evidence links`, async ({browser}, info) => {
    const context = await browser.newContext({javaScriptEnabled:false, viewport:{width:390,height:844}});
    const page = await context.newPage();
    await page.goto(prefix);
    await expect(page.locator('[data-site-nav=markets]')).toHaveAttribute('href', `${prefix}markets/`);
    await page.locator('[data-topic=HK]').click();
    await expect(page).toHaveURL(`${prefix}markets/#market-hk`);
    for (const market of ['us','hk','crypto']) {
      const topic = page.locator(`[data-topic-market=${market}]`);
      await expect(topic).toBeVisible();
      await expect(topic.locator(`a[href="${prefix}factors/#market-${market}"]`)).toHaveCount(2);
      await expect(topic.locator(`a[href="${prefix}strategies/#market-${market}"]`)).toHaveCount(2);
    }
    await expect(page.locator('[data-topic-market=hk] a[href$="research/cnn-chart/"]')).toHaveCount(2);
    await expect(page.locator('[data-site-nav=strategies],[data-site-nav=factors]')).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({path:info.outputPath(`${locale}-market-mobile.png`),fullPage:true});
    await page.setViewportSize({width:1440,height:1000});
    await page.screenshot({path:info.outputPath(`${locale}-market-desktop.png`),fullPage:true});
    await expect(page.locator('.language a').first()).toHaveAttribute('href', '/2026-quant-competition/markets/');
    await expect(page.locator('.language a').nth(1)).toHaveAttribute('href', '/2026-quant-competition/zh-CN/markets/');
    await context.close();
  });
}
