"use strict";
// Prohlížečové kontroly jsou offline: všechny požadavky se obslouží z disku.
const fs=require("fs"),path=require("path"),assert=require("assert/strict");
const root=__dirname,site=path.join(root,"nahled-modely"),out=path.join(root,"overeni-modely");
process.env.TMPDIR=path.join(out,"tmp");fs.mkdirSync(process.env.TMPDIR,{recursive:true});
const {chromium}=require("/opt/konfigurator/node_modules/playwright");
const executablePath=path.resolve(root,"../rezie_nastroj/overeni/browser_bin/chromium-1234/chrome-linux64/chrome");
const origin="https://kufriky.test",prefix="/nahled-john/kufriky-milwaukee-modely-v1/",base=origin+prefix;
const catalog=JSON.parse(fs.readFileSync(path.join(root,"kufriky.json"))),records=catalog.records.filter(r=>r.group==="kufriky");
const mime={".html":"text/html; charset=utf-8",".js":"application/javascript; charset=utf-8",".css":"text/css; charset=utf-8",".jpg":"image/jpeg",".json":"application/json",".csv":"text/csv; charset=utf-8",".glb":"model/gltf-binary"};
async function main(){
  const browser=await chromium.launch({headless:true,executablePath,args:["--disable-background-networking","--host-resolver-rules=MAP * ~NOTFOUND","--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"]});
  const errors=[],blocked=[],requests=[],checks=[],result={status:"FAIL",mode:"offline",checks,errors,blocked,requests};
  const context=await browser.newContext({viewport:{width:1440,height:1100},serviceWorkers:"block"});
  await context.route("**/*",route=>{
    const u=new URL(route.request().url());
    if(u.origin!==origin||!u.pathname.startsWith(prefix)){blocked.push(u.href);return route.abort();}
    const filename=u.pathname.slice(prefix.length)||"index.html",file=path.resolve(site,filename);
    if(!file.startsWith(site+path.sep)||!fs.existsSync(file)){blocked.push(filename);return route.abort();}
    requests.push(filename);return route.fulfill({status:200,contentType:mime[path.extname(file)],body:fs.readFileSync(file)});
  });
  const page=await context.newPage();page.on("pageerror",e=>errors.push(e.message));page.on("console",m=>{if(m.type()==="error")errors.push(m.text());});
  const ok=s=>{checks.push(s);console.log("OK "+s);};
  try{
    await page.goto(base,{waitUntil:"load"});await page.waitForFunction(()=>window.KUFRIKY_MODELY_UI?.state().loaded);
    assert.equal(await page.locator('meta[name="robots"]').getAttribute("content"),"noindex, nofollow");
    assert.equal(await page.locator("#types .type").count(),20);assert.equal(await page.locator("#type-select option").count(),20);
    assert.equal(await page.evaluate(()=>KUFRIKY_MODELY_UI.state().current),"4932471064");
    assert.match(await page.locator(".notice").textContent(),/0 z 20/);assert.equal(await page.locator("#viewer canvas").count(),1);
    ok("Výchozí nízký organizér, 20 typů; viditelný stav 0 hotových přesných modelů.");
    for(const r of records){
      await page.selectOption("#type-select",r.sku[0]);await page.waitForFunction(sku=>KUFRIKY_MODELY_UI.state().loaded?.sku===sku,r.sku[0]);
      const state=await page.evaluate(()=>KUFRIKY_MODELY_UI.state());assert.equal(state.error,null);
      assert.deepEqual(state.loaded.localSize,[r.outer.mm.width,r.outer.mm.length,r.outer.mm.height]);assert.equal(state.loaded.isProductGeometry,false);
      assert.equal(await page.locator("#source").getAttribute("href"),r.outer.source_url);
      assert.equal(await page.locator("#model-download").getAttribute("href"),r.envelope.file);
      assert.match(await page.locator("#verification").textContent(),/Všechny vrcholy změřeny; odchylka 0,00 mm/);
      assert.ok(await page.locator("#missing li").count()>=4);
      const photo=await page.locator("#photo").evaluate(i=>({ready:i.complete&&i.naturalWidth===240}));if(!photo.ready)await page.waitForFunction(()=>document.querySelector("#photo").complete&&document.querySelector("#photo").naturalWidth===240);
    }
    ok("Všech 20 skutečně načtených GLB obálek: osy, rozměry, zdroj, fotografie a chybějící geometrie.");
    await page.fill("#search","organizér");assert.equal(await page.locator("#types .type").count(),5);
    await page.fill("#search","4932464082");assert.equal(await page.locator("#types .type").count(),1);await page.locator("#types .type").click();
    await page.waitForFunction(()=>KUFRIKY_MODELY_UI.state().loaded.sku==="4932464082");
    await page.fill("#search","nic12345");assert.equal(await page.locator("#types .type").count(),0);assert.equal(await page.locator("#empty").isVisible(),true);
    await page.fill("#search","");ok("Vyhledávání podle názvu/SKU a prázdný výsledek.");
    await page.locator('[data-view="top"]').click();assert.equal(await page.evaluate(()=>KUFRIKY_MODELY_UI.state().view),"top");
    await page.locator('[data-view="side"]').click();assert.equal(await page.evaluate(()=>KUFRIKY_MODELY_UI.state().view),"side");
    await page.locator("#reset").click();const before=await page.evaluate(()=>KUFRIKY_MODELY_UI.state().camera);
    const b=await page.locator("#viewer canvas").boundingBox();await page.mouse.move(b.x+b.width*.5,b.y+b.height*.5);await page.mouse.down();await page.mouse.move(b.x+b.width*.65,b.y+b.height*.55,{steps:12});await page.mouse.up();await page.waitForTimeout(150);
    const after=await page.evaluate(()=>KUFRIKY_MODELY_UI.state().camera);assert.notDeepEqual(after,before);
    await page.locator("#dimensions").uncheck();await page.waitForTimeout(50);assert.equal(await page.locator(".dim-label:visible").count(),0);
    await page.locator("#dimensions").check();await page.locator("#reset").click();await page.waitForTimeout(100);assert.equal(await page.locator(".dim-label:visible").count(),3);
    ok("Otáčení myší, přednastavené pohledy, návrat kamery a vypnutí/zapnutí kót.");
    await page.screenshot({path:path.join(out,"modely-desktop.png"),fullPage:true});
    await page.selectOption("#type-select","4932498651");await page.waitForFunction(()=>KUFRIKY_MODELY_UI.state().loaded.sku==="4932498651");
    assert.match(await page.locator("#conflicts").textContent(),/665 × 570 × 480/);
    await page.selectOption("#type-select","4932501784");await page.waitForFunction(()=>KUFRIKY_MODELY_UI.state().loaded.sku==="4932501784");
    assert.match(await page.locator("#sku").textContent(),/4932478162/);assert.match(await page.locator("#conflicts").textContent(),/konstrukční shodu/);
    ok("Rozpor pojízdné zásuvky a dvě odlišná SKU XL zůstávají viditelné.");
    for(const filename of ["kufriky.json","kufriky.csv","mereni.csv"]){const a=page.locator(`a[href="${filename}"]`);assert.equal(await a.count(),1);assert.notEqual(await a.getAttribute("download"),null);assert.ok(fs.statSync(path.join(site,filename)).size>0);}
    assert.equal(await page.locator(".candidate").count(),9);ok("Místní soubory ke stažení a 9 kandidátů CAD s přístupem a licencí.");
    await page.selectOption("#type-select","4932471064");await page.waitForFunction(()=>KUFRIKY_MODELY_UI.state().loaded.sku==="4932471064");
    await page.setViewportSize({width:390,height:844});await page.waitForTimeout(150);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    assert.equal(await page.locator("#type-select").isVisible(),true);await page.screenshot({path:path.join(out,"modely-mobil.png"),fullPage:true});
    ok("Mobilní náhled nepřetéká a nabízí všech 20 typů.");
    assert.equal(errors.length,0,JSON.stringify(errors));assert.equal(blocked.length,0,JSON.stringify(blocked));ok("Bez chyb a bez požadavků mimo místní statické soubory.");result.status="PASS";
  }finally{fs.writeFileSync(path.join(out,"prohlizec.json"),JSON.stringify(result,null,2)+"\n");await browser.close();}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
