import {test,expect} from '@playwright/test';
test.beforeEach(async({page})=>{await page.emulateMedia({reducedMotion:'reduce'});});

for(const locale of ['en','zh-CN']){
 const prefix=`/global-market-research/${locale==='en'?'':'zh-CN/'}`;
 test(`${locale}: editorial home shows reviewed story without full payload`,async({page},info)=>{
  await page.goto(prefix);
  const home=page.locator('#robustness');
  await expect(home).toHaveCount(1,{timeout:3000});
  await expect(page.locator('main h1')).toHaveCount(1);
  await expect(home.locator('[data-home-feature]')).toHaveCount(2);
  await expect(home.locator('[data-home-market]')).toHaveCount(3);
  await expect(home.locator('canvas')).toHaveCount(0);
  await expect(page.locator('[data-robustness-facts],[data-controls-facts]')).toHaveCount(0);
  await expect(home.locator('a[data-topic=factors]')).toHaveCount(0);
  for(const theme of ['light','dark']){
   await page.locator('#theme-preference').selectOption(theme);
   await page.screenshot({path:info.outputPath(`${locale}-home-${theme}.png`),fullPage:true});
  }
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath(`${locale}-home-mobile.png`),fullPage:true});
 });

 test(`${locale}: market topics integrate prior facts without disclosures or migration links`,async({page})=>{
  await page.goto(prefix);
  const history=page.locator('#takeaways');
  await expect(page.locator('#research-history,.legacy-links,[data-legacy-link]')).toHaveCount(0);
  for(const market of ['US','HK','crypto']){
   const topic=page.locator(`[data-market-topic=${market}]`);
   await expect(topic).toBeVisible();
   await expect(topic.locator('[data-home-market]')).toBeVisible();
   expect(await topic.evaluate(n=>n.closest('details')===null)).toBe(true);
  }
  await expect(history.locator('[data-home-market]')).toHaveCount(3);
  for(const fragment of ['strategy-controls','takeaways','%74akeaways','takeaways-title','%74akeaways-title']){
   await page.goto(prefix+'#'+fragment);
   await expect(page.locator('#'+decodeURIComponent(fragment))).toBeVisible();
  }
  await page.goto(prefix+'#title-crypto');await expect(page).toHaveURL(prefix+'docs/project/#title-crypto');
  await expect(page.locator('#title-crypto')).toBeVisible();
 });
}

test('all market evidence remains directly available without JavaScript',async({browser})=>{
 const context=await browser.newContext({javaScriptEnabled:false});const page=await context.newPage();
 await page.goto('/global-market-research/');
 await expect(page.locator('[data-home-market]')).toHaveCount(3,{timeout:3000});
 await expect(page.locator('#takeaways')).toBeVisible();
 for(const market of ['US','HK','crypto'])await expect(page.locator(`[data-market-topic=${market}] [data-home-market]`)).toBeVisible();
 await expect(page.locator('.legacy-links')).toHaveCount(0);
 await context.close();
});

for(const locale of ['en','zh-CN'])test(`${locale}: editorial topic pages retain navigation, evidence and readable contrast`,async({page},info)=>{
 const prefix=`/global-market-research/${locale==='en'?'':'zh-CN/'}`;
 for(const route of ['', 'strategies/','factors/','docs/','docs/project/','docs/strategy-robustness/']){
  await page.setViewportSize({width:1440,height:1000});await page.goto(prefix+route);
  await expect(page.locator('main h1')).toHaveCount(1,{timeout:3000});
  if(route==='strategies/'){
   await expect(page.locator('.section-nav a')).toHaveCount(7);
   await expect(page.locator('.section-nav a').first()).toHaveAttribute('href','#comparison-crypto');
   await expect(page.locator('#holding-equity')).toHaveAttribute('data-lt-ready','true');
   await page.locator('[data-market-link=crypto]').click();
   await page.locator('#comparison-crypto').scrollIntoViewIfNeeded();
   await expect(page.locator('#comparison-crypto')).toHaveAttribute('data-comparison-ready','true');
   await page.locator('#incremental-crypto').scrollIntoViewIfNeeded();
   await expect(page.locator('#incremental-crypto')).toHaveAttribute('data-incremental-ready','true');
   await page.locator('#robustness').scrollIntoViewIfNeeded();
   await expect(page.locator('#robustness')).toHaveAttribute('data-ready','true');
   await page.evaluate(()=>window.scrollTo(0,0));
   expect(await page.evaluate(()=>scrollY)).toBe(0);
   const core=await page.locator('#holding-crypto [data-lt-chart]').first().boundingBox();
   expect(core.y).toBeLessThan(800);
   await expect(page.locator('[data-study-id]')).toHaveCount(318);
   await expect(page.locator('[data-ablation-id]')).toHaveCount(678);
  }
  if(route==='factors/'){
   await expect(page.locator('[data-factor-score],[data-dex-metric]')).toHaveCount(0);
   expect(JSON.parse(await page.locator('[data-dex-facts]').getAttribute('data-dex-facts')).status).toBe('readiness_only');
  }
  if(route==='docs/')await expect(page.locator('main [data-doc-slug]')).toHaveCount(16);
  for(const theme of ['light','dark']){
   await page.locator('#theme-preference').selectOption(theme);
   await expect(page.locator('body')).toHaveCSS('background-color',theme==='light'?'rgb(246, 244, 239)':'rgb(23, 27, 32)');
   const failures=await page.evaluate(()=>{
    const rgb=c=>c.match(/[\d.]+/g).slice(0,3).map(Number);
    const luminance=c=>rgb(c).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
    const ratio=(a,b)=>{const [hi,lo]=[luminance(a),luminance(b)].sort((a,b)=>b-a);return (hi+.05)/(lo+.05);};
    const background=el=>{for(let n=el;n;n=n.parentElement){const c=getComputedStyle(n).backgroundColor;if(c!=='rgba(0, 0, 0, 0)')return c;}return 'rgb(255,255,255)';};
    const failures=[];
    for(const el of document.querySelectorAll('.editorial-dek,.editorial-scope,.figure-condition,.editorial-figure-note,.topic-index,.topic-stat span,.edition-line,.doc-note,.doc-cards p,.project-nav a,.theme-control,main select')){
     if(!el.checkVisibility())continue;const r=ratio(getComputedStyle(el).color,background(el));
     if(r<4.5)failures.push(el.className+': '+r.toFixed(2));
    }
    for(const el of document.querySelectorAll('.bar-fill'))if(el.checkVisibility()){
     const r=ratio(getComputedStyle(el).backgroundColor,background(el.parentElement));if(r<3)failures.push('bar: '+r.toFixed(2));
    }
    return failures;
   });
   expect(failures).toEqual([]);
   await page.evaluate(()=>window.scrollTo(0,0));
   await page.screenshot({path:info.outputPath(`${locale}-${route.replaceAll('/','-')||'home'}-${theme}.png`)});
  }
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath(`${locale}-${route.replaceAll('/','-')||'home'}-mobile.png`)});
 }
});

test('long localized market labels and unavailable storage retain a usable homepage',async({page})=>{
 await page.addInitScript(()=>{Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked');}});});
 await page.setViewportSize({width:390,height:844});await page.goto('/global-market-research/zh-CN/');
 await page.locator('[data-home-market]').first().evaluate(el=>el.textContent+='较长的研究标签'.repeat(15));
 await page.locator('#theme-preference').selectOption('dark');
 await expect(page.locator('body')).toHaveCSS('background-color','rgb(23, 27, 32)');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.locator('#theme-preference').focus();
 expect(await page.locator('#theme-preference').evaluate(el=>getComputedStyle(el).outlineStyle)).not.toBe('none');
});
