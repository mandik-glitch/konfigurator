"use strict";
// Čtení vlastní veřejné stránky: povolené jsou pouze GET v její složce.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const root=__dirname,out=path.join(root,'overeni-tvar-v6');
process.env.TMPDIR=path.join(out,'tmp');
const {chromium}=require('/opt/konfigurator/node_modules/playwright');
const executablePath=path.resolve(root,'../rezie_nastroj/overeni/browser_bin/chromium-1234/chrome-linux64/chrome');
const base='https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/';
async function main(){
 const browser=await chromium.launch({headless:true,executablePath,args:['--disable-background-networking','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const errors=[],blocked=[],responses=[],organizers=[];
 const result={status:'FAIL',mode:'public_get',url:base,errors,blocked,responses,organizers};
 const context=await browser.newContext({viewport:{width:1440,height:1100},serviceWorkers:'block'});
 await context.route('**/*',route=>{
  const r=route.request();
  if(r.method()!=='GET'||!r.url().startsWith(base)){blocked.push(r.url());return route.abort();}
  return route.continue();
 });
 const page=await context.newPage();page.setDefaultTimeout(30000);
 page.on('pageerror',e=>errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 page.on('response',r=>{responses.push({file:r.url().slice(base.length),status:r.status()});if(r.status()>=400)errors.push('HTTP '+r.status());});
 try{
  const response=await page.goto(base,{waitUntil:'load'});assert.equal(response.status(),200);
  await page.waitForFunction(()=>window.KUFRIKY_MODELY_UI?.state().loaded);
  assert.equal(await page.locator('meta[name="robots"]').getAttribute('content'),'noindex, nofollow');
  assert.equal(await page.locator('#status-rows tr').count(),20);
  for(const sku of ['4932471064','4932464082','4932471065','4932478625','4932498323']){
   await page.selectOption('#type-select',sku);
   await page.waitForFunction(s=>KUFRIKY_MODELY_UI.state().loaded?.sku===s,sku);
   assert.equal(await page.evaluate(()=>KUFRIKY_MODELY_UI.state().error),null);
   assert.equal(await page.locator('#control-views img').count(),10);assert.equal(await page.locator('#photo-model-pairs .photo-model-pair').count(),6);
   await page.locator('#control-views').scrollIntoViewIfNeeded();
   await page.waitForFunction(()=>[...document.querySelectorAll('#control-views img')].every(i=>i.complete&&i.naturalWidth>0));
   await page.locator('#viewer').scrollIntoViewIfNeeded();
   await page.locator('[data-view="sideOther"]').click();
   assert.equal(await page.evaluate(()=>KUFRIKY_MODELY_UI.state().view),'sideOther');
   await page.locator('#parts-colors').check();assert.ok(await page.locator('#parts-legend li').count()>50);
   await page.locator('#parts-colors').uncheck();
   organizers.push(await page.evaluate(()=>KUFRIKY_MODELY_UI.state().loaded));
  }
  await page.screenshot({path:path.join(out,'verejny-desktop.png'),fullPage:true});await page.goto(base+'srovnani.html',{waitUntil:'load'});assert.equal(await page.locator('.photo-model-pair').count(),30);assert.equal(await page.locator('img[src^=http]').count(),0);for(const i of await page.locator('img').all()){await i.scrollIntoViewIfNeeded();}await page.waitForFunction(()=>[...document.images].every(i=>i.complete&&i.naturalWidth>0));
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.equal(errors.length,0,JSON.stringify(errors));assert.equal(blocked.length,0,JSON.stringify(blocked));
  result.status='PASS';result.checked_at=new Date().toISOString();
  console.log('Veřejný prohlížeč PASS: všech pět organizérů, 30 dvojic, všechny srovnávací obrázky a mobil; bez chyb a cizích požadavků.');
 }finally{fs.writeFileSync(path.join(out,'verejny-prohlizec.json'),JSON.stringify(result,null,2)+'\n');await browser.close();}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
