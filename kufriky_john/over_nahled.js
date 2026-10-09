"use strict";
// Čisté testy prohlížeče: každý požadavek je obsloužen z místních souborů.
const fs=require("fs"),path=require("path"),assert=require("assert/strict");
const root=__dirname,site=path.join(root,"nahled"),out=path.join(root,"overeni");
fs.mkdirSync(out,{recursive:true});
process.env.TMPDIR=path.join(out,"tmp");fs.mkdirSync(process.env.TMPDIR,{recursive:true});
const {chromium}=require("/opt/konfigurator/node_modules/playwright");
const exe=path.resolve(root,"../rezie_nastroj/overeni/browser_bin/chromium-1234/chrome-linux64/chrome");
const base="https://kufriky.test/";
const mime={".html":"text/html; charset=utf-8",".js":"application/javascript; charset=utf-8",".css":"text/css; charset=utf-8",".jpg":"image/jpeg",".json":"application/json",".csv":"text/csv; charset=utf-8"};

async function main(){
 const browser=await chromium.launch({headless:true,executablePath:exe,args:["--disable-background-networking","--host-resolver-rules=MAP * ~NOTFOUND"]});
 const context=await browser.newContext({viewport:{width:1536,height:1100},serviceWorkers:"block",acceptDownloads:true});
 const errors=[],blocked=[],requests=[],checks=[];
 const result={status:"FAIL",mode:"offline",checks,errors,blocked,requests};
 await context.route("**/*",async route=>{
  const url=new URL(route.request().url());
  if(url.origin!==new URL(base).origin){blocked.push(url.origin);return route.abort();}
  const name=url.pathname.slice(1)||"index.html",file=path.resolve(site,name);
  if(!file.startsWith(site+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){blocked.push(name);return route.abort();}
  requests.push(name);
  return route.fulfill({status:200,body:fs.readFileSync(file),contentType:mime[path.extname(file)]});
 });
 const page=await context.newPage();
 page.on("pageerror",e=>errors.push(e.message));
 page.on("console",m=>{if(m.type()==="error")errors.push(m.text());});
 const done=s=>{checks.push(s);console.log("OK "+s);};
 try{
  await page.goto(base,{waitUntil:"load"});
  await page.waitForFunction(()=>window.KUFRIKY_UI);
  assert.equal(await page.locator('meta[name="robots"]').getAttribute("content"),"noindex, nofollow");
  assert.equal(await page.locator("tr.product").count(),20);
  assert.equal((await page.locator("tr.product").first().getAttribute("data-id")),"milwaukee-packout-4932471723");
  done("Výchozí tabulka: 20 pevných typů, řazení dle vodorovné délky.");
  await page.locator('#search').fill("zasuvkami");assert.equal(await page.locator("tr.product").count(),4);
  await page.locator('#search').fill("4932498651");assert.equal(await page.locator("tr.product").count(),1);
  assert.match(await page.locator("tr.product").textContent(),/610 × 480 × 550/);
  assert.match(await page.locator("tr.product").textContent(),/68 kg/);
  assert.match(await page.locator("tr.product").textContent(),/113 kg/);
  await page.locator(".details-toggle").click();
  assert.equal(await page.locator(".row-detail:visible").count(),1);
  assert.match(await page.locator(".row-detail:visible").textContent(),/665 × 570 × 480/);
  done("Vyhledávání bez diakritiky i podle SKU, rozbalení rozporu rozměrů a dvou nosností.");
  await page.locator("#search").fill("4058546340957");assert.equal(await page.locator("tr.product").count(),1);
  assert.match(await page.locator("tr.product").textContent(),/4932501784/);
  assert.match(await page.locator("tr.product").textContent(),/4932478162/);
  assert.equal(await page.locator("tr.product .sale").count(),4);
  done("EAN starého XL dohledá společný řádek; čtyři nabídky mají vlastní SKU.");
  await page.locator("#reset").click();await page.locator('#sort').selectOption("length-down");
  assert.equal(await page.locator("tr.product").first().getAttribute("data-id"),"milwaukee-packout-4932478161");
  await page.locator('#category').selectOption("Zásuvky");assert.equal(await page.locator("tr.product").count(),4);
  await page.locator('#country').selectOption("oba");assert.equal(await page.locator("tr.product").count(),4);
  await page.locator("#search").fill("nenalezeno123");assert.equal(await page.locator("tr.product").count(),0);
  assert.equal(await page.locator("#empty").isVisible(),true);
  done("Řazení sestupně, filtr zásuvek, oba trhy a prázdný výsledek.");
  await page.locator("#reset").click();await page.locator('[data-group="ostatni"]').click();assert.equal(await page.locator("tr.product").count(),14);
  await page.locator('[data-group="vse"]').click();assert.equal(await page.locator("tr.product").count(),34);
  // Načíst všechny místní miniatury, včetně řádků pod oknem.
  await page.evaluate(()=>document.querySelectorAll(".picture img").forEach(i=>i.loading="eager"));
  await page.waitForFunction(()=>[...document.querySelectorAll(".picture img")].every(i=>i.complete&&i.naturalWidth===240));
  assert.equal(await page.locator('.picture img').count(),34);
  await page.locator('.picture').first().click();assert.equal(await page.locator('#photo-dialog').isVisible(),true);
  await page.keyboard.press("Escape");assert.equal(await page.locator('#photo-dialog').isVisible(),false);
  done("Všech 34 skutečných miniatur se načetlo lokálně; zvětšení a klávesa Escape fungují.");
  await page.locator("#reset").click();
  await page.screenshot({path:path.join(out,"tabulka-desktop.png")});
  for(const filename of ["kufriky.csv","kufriky.json"]){
    const a=page.locator(`.downloads a[href="${filename}"]`);
    assert.equal(await a.count(),1);assert.notEqual(await a.getAttribute("download"),null);
    const source=JSON.parse(fs.readFileSync(path.join(root,"kufriky.json"))).stage===2?path.join(root,"zdroje","etapa1-"+filename):path.join(root,filename);
    assert.deepEqual(fs.readFileSync(path.join(site,filename)),fs.readFileSync(source));
  }
  done("Odkazy ke stažení míří na místní CSV a JSON; soubory odpovídají katalogu.");
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1));
  assert.ok(await page.locator(".table-scroll").evaluate(e=>e.scrollWidth>e.clientWidth));
  await page.screenshot({path:path.join(out,"tabulka-mobil.png")});
  done("Mobil: stránka nepřetéká; široká tabulka se posouvá uvnitř.");
  await page.locator(".scope-details").first().locator("summary").click();
  assert.equal(await page.locator("#excluded table tbody tr").count(),8);
  assert.equal(errors.length,0,JSON.stringify(errors));assert.equal(blocked.length,0,JSON.stringify(blocked));
  done("Vyřazené varianty jsou viditelné; žádné chyby ani požadavky mimo místní náhled.");
  result.status="PASS";
 }finally{
  fs.writeFileSync(path.join(out,"prohlizec.json"),JSON.stringify(result,null,2)+"\n");
  await browser.close();
 }
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
