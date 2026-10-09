"use strict";
// Offline browser verification. Every resource is served directly from disk.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const root=__dirname,site=path.join(root,'nahled-modely-v2'),out=path.join(root,'overeni-tvar-v2');fs.mkdirSync(out,{recursive:true});
process.env.TMPDIR=path.join(out,'tmp');fs.mkdirSync(process.env.TMPDIR,{recursive:true});
const {chromium}=require('/opt/konfigurator/node_modules/playwright');
const executablePath=path.resolve(root,'../rezie_nastroj/overeni/browser_bin/chromium-1234/chrome-linux64/chrome');
const origin='https://kufriky.test',prefix='/nahled-john/kufriky-milwaukee-modely-v2/',base=origin+prefix;
const catalog=JSON.parse(fs.readFileSync(path.join(root,'kufriky.json'))),records=catalog.model_order.map(id=>catalog.records.find(r=>r.id===id));
const mime={'.html':'text/html; charset=utf-8','.js':'application/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.jpg':'image/jpeg','.json':'application/json','.csv':'text/csv; charset=utf-8','.glb':'model/gltf-binary'};
async function main(){
 const browser=await chromium.launch({headless:true,executablePath,args:['--disable-background-networking','--host-resolver-rules=MAP * ~NOTFOUND','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const errors=[],blocked=[],requests=[],checks=[],models=[],result={status:'FAIL',mode:'offline',checks,models,errors,blocked,requests};
 const context=await browser.newContext({viewport:{width:1440,height:1100},serviceWorkers:'block'});
 await context.route('**/*',route=>{
  const u=new URL(route.request().url());if(u.origin!==origin||!u.pathname.startsWith(prefix)){blocked.push(u.href);return route.abort();}
  const filename=u.pathname.slice(prefix.length)||'index.html',file=path.resolve(site,filename);
  if(!file.startsWith(site+path.sep)||!fs.existsSync(file)){blocked.push(filename);return route.abort();}
  requests.push(filename);return route.fulfill({status:200,contentType:mime[path.extname(file)],body:fs.readFileSync(file)});
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 const ok=s=>{checks.push(s);console.log('OK '+s);};
 async function select(sku){await page.selectOption('#type-select',sku);await page.waitForFunction(s=>KUFRIKY_MODELY_UI.state().loaded?.sku===s,sku);await page.waitForTimeout(80);}
 try{
  await page.goto(base,{waitUntil:'load'});await page.waitForFunction(()=>window.KUFRIKY_MODELY_UI?.state().loaded);
  assert.equal(await page.locator('meta[name="robots"]').getAttribute('content'),'noindex, nofollow');assert.equal(await page.locator('#types .type').count(),20);assert.equal(await page.locator('#status-rows tr').count(),20);assert.match(await page.locator('.notice').textContent(),/20 z 20/);
  ok('20 typů, viditelný stav detailu, fotografická rekonstrukce a hranice přesnosti.');
  for(const r of records){
   await select(r.sku[0]);const s=await page.evaluate(()=>KUFRIKY_MODELY_UI.state());assert.equal(s.error,null);assert.equal(s.loaded.isProductGeometry,true);assert.equal(s.loaded.detailLevel,'realny_tvar');assert.ok(s.loaded.parts>25);
   const target=[r.outer.mm.width,r.outer.mm.length,r.outer.mm.height];assert.ok(Math.max(...target.map((v,i)=>Math.abs(v-s.loaded.localSize[i])))<.01);
   assert.equal(await page.locator('#source').getAttribute('href'),r.outer.source_url);assert.equal(await page.locator('#model-download').getAttribute('href'),r.model_file);assert.match(await page.locator('#detail-badge').textContent(),/Reálný tvar/);
   await page.waitForFunction(()=>document.querySelector('#photo').complete&&document.querySelector('#photo').naturalWidth>0);models.push(s.loaded);
   await page.locator('#viewer').screenshot({path:path.join(out,r.sku[0]+'-zavreno.png')});
   if(!(await page.locator('#open').isDisabled())){await page.locator('#open').check();const a=await page.evaluate(()=>KUFRIKY_MODELY_UI.state());assert.equal(a.opened,true);assert.ok(a.groups.some(g=>Math.abs(g.rotation[1])>.1||Math.abs(g.rotation[2])>.1||g.kind.startsWith('drawer-')));await page.waitForTimeout(90);await page.locator('#viewer').screenshot({path:path.join(out,r.sku[0]+'-otevreno.png')});await page.locator('#open').uncheck();}
   if(!(await page.locator('#hide-lid').isDisabled())){await page.locator('#hide-lid').check();assert.ok((await page.evaluate(()=>KUFRIKY_MODELY_UI.state().groups)).some(g=>!g.visible));await page.locator('#hide-lid').uncheck();}
  }
  ok('Všech 20 GLB se načte, rozměry souhlasí, modely obsahují skutečné díly; otevírání a skrývání funguje.');
  await select('4932471064');await page.locator('[data-view="top"]').click();await page.waitForTimeout(80);await page.locator('#viewer').screenshot({path:path.join(out,'organizer-shora.png')});
  await page.locator('#bottom').check();assert.equal(await page.evaluate(()=>KUFRIKY_MODELY_UI.state().view),'bottom');await page.locator('#viewer').screenshot({path:path.join(out,'organizer-zespodu.png')});await page.locator('#bottom').uncheck();
  await page.locator('#outline').check();await page.locator('#outline').uncheck();await page.locator('#dimensions').uncheck();await page.waitForTimeout(50);assert.equal(await page.locator('.dim-label:visible').count(),0);await page.locator('#dimensions').check();
  const before=await page.evaluate(()=>KUFRIKY_MODELY_UI.state().camera),box=await page.locator('#viewer canvas').boundingBox();await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.65,box.y+box.height*.54,{steps:10});await page.mouse.up();await page.waitForTimeout(120);assert.notDeepEqual(await page.evaluate(()=>KUFRIKY_MODELY_UI.state().camera),before);
  await page.locator('#reset').click();await page.locator('#photo').click();assert.equal(await page.locator('#photo-dialog').isVisible(),true);await page.locator('#close-photo').click();
  ok('Otáčení, kóty, horní/spodní pohled, kontrolní obálka a zvětšení fotografie.');
  await page.fill('#search','organizér');assert.equal(await page.locator('#types .type').count(),5);await page.fill('#search','4932464082');assert.equal(await page.locator('#types .type').count(),1);await page.fill('#search','nic12345');assert.equal(await page.locator('#empty').isVisible(),true);await page.fill('#search','');
  await select('4932498651');assert.match(await page.locator('#conflicts').textContent(),/665 × 570 × 480/);await select('4932501784');assert.match(await page.locator('#sku').textContent(),/4932478162/);
  ok('Vyhledávání a zachované rozpory zdrojů / verze XL.');
  await select('4932471064');await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});await page.setViewportSize({width:390,height:844});await page.waitForTimeout(160);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(out,'mobil.png'),fullPage:true});
  assert.equal(errors.length,0,JSON.stringify(errors));assert.equal(blocked.length,0,JSON.stringify(blocked));ok('Mobil bez přetékání; žádné chyby ani přístupy mimo místní statické soubory.');result.status='PASS';
 }finally{fs.writeFileSync(path.join(out,'prohlizec.json'),JSON.stringify(result,null,2)+'\n');await browser.close();}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
