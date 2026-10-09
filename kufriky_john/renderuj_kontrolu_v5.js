"use strict";
// Offline renderer: all page requests are fulfilled from disk. No server/network.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const root=__dirname,site=path.join(root,'nahled-modely-v5'),out=path.join(root,'overeni-tvar-v5');
process.env.TMPDIR=path.join(out,'tmp');fs.mkdirSync(process.env.TMPDIR,{recursive:true});
const {chromium}=require('/opt/konfigurator/node_modules/playwright');
const executablePath=path.resolve(root,'../rezie_nastroj/overeni/browser_bin/chromium-1234/chrome-linux64/chrome');
const origin='https://kufriky.test',prefix='/nahled-john/kufriky-milwaukee-modely-v5/',base=origin+prefix;
const catalog=JSON.parse(fs.readFileSync(path.join(root,'kufriky.json'))),records=catalog.model_order.map(id=>catalog.records.find(r=>r.id===id));
const mime={'.html':'text/html; charset=utf-8','.js':'application/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.png':'image/png','.json':'application/json','.csv':'text/csv; charset=utf-8','.glb':'model/gltf-binary'};
async function main(){
 const browser=await chromium.launch({headless:true,executablePath,args:['--disable-background-networking','--host-resolver-rules=MAP * ~NOTFOUND','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const context=await browser.newContext({viewport:{width:1440,height:1100},serviceWorkers:'block'}),errors=[];
 await context.route('**/*',route=>{
  const u=new URL(route.request().url());assert.equal(u.origin,origin);assert.ok(u.pathname.startsWith(prefix));
  const filename=u.pathname.slice(prefix.length)||'index.html',file=path.resolve(site,filename);assert.ok(file.startsWith(site+path.sep));
  if(!fs.existsSync(file)&&(filename.startsWith('porovnani/')||filename.startsWith('kontrola/')))return route.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9m0AAAAASUVORK5CYII=','base64')});
  assert.ok(fs.existsSync(file),filename);return route.fulfill({status:200,contentType:mime[path.extname(file)],body:fs.readFileSync(file)});
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 const reportPath=path.join(out,'renderovani.json');
 const result=(process.env.KUFRIKY_RENDER_SKU||process.env.KUFRIKY_RENDER_BOTTOM_ONLY)&&fs.existsSync(reportPath)?JSON.parse(fs.readFileSync(reportPath)).renders.filter(r=>!process.env.KUFRIKY_RENDER_SKU?.split(',').includes(r.sku)):[];
 try{
  await page.goto(base,{waitUntil:'load'});await page.waitForFunction(()=>window.KUFRIKY_MODELY_UI?.state().loaded);
  for(const record of records.filter(r=>!process.env.KUFRIKY_RENDER_SKU||process.env.KUFRIKY_RENDER_SKU.split(',').includes(r.sku[0]))){
   const sku=record.sku[0];
   for(const version of ['v4','v5']){
    const folder=version==='v4'?'modely-v4':'modely',binary=fs.readFileSync(path.join(root,folder,sku+'.glb')).toString('base64');
    await page.evaluate(({sku,binary})=>{window.KUFRIKY_MODEL_PAYLOADS[sku]=binary;KUFRIKY_MODELY_UI.select(sku);},{sku,binary});
    await page.waitForFunction(s=>KUFRIKY_MODELY_UI.state().loaded?.sku===s,sku);
    await page.evaluate(()=>KUFRIKY_MODELY_UI.renderClean());
    // Specialist source shows an open case; use the same open direction.
    if(['4932499703','4932499704'].includes(sku))await page.locator('#open').check();
    await page.waitForTimeout(200);
    const filename=sku+(version==='v4'?'-v4':'')+'.png';
    await page.locator('#viewer canvas').screenshot({path:path.join(site,'porovnani',filename)});
    if(['4932499703','4932499704'].includes(sku))await page.locator('#open').uncheck();
    for(const view of (process.env.KUFRIKY_RENDER_BOTTOM_ONLY?['bottom']:(record.name.toLowerCase().includes('organiz')?['front','back','side','sideOther','top','bottom','isoFrontRight','isoFrontLeft','isoBackRight','isoBackLeft']:['front','side','sideOther','top','bottom']))){
     await page.evaluate(v=>KUFRIKY_MODELY_UI.captureView(v),view);await page.waitForTimeout(70);
     const controlFile=sku+(version==='v4'?'-v4':'')+'-'+view+'.png';
     await page.locator('#viewer canvas').screenshot({path:path.join(site,'kontrola',controlFile)});if(record.name.toLowerCase().includes('organiz')){await page.evaluate(()=>KUFRIKY_MODELY_UI.colorParts(true));await page.evaluate(v=>KUFRIKY_MODELY_UI.captureView(v),view);await page.locator('#viewer canvas').screenshot({path:path.join(site,'kontrola',controlFile.replace('.png','-casti.png'))});await page.evaluate(()=>KUFRIKY_MODELY_UI.colorParts(false));}
    }
    result.push({sku,version,render_file:'porovnani/'+filename,camera_after_controls:await page.evaluate(()=>KUFRIKY_MODELY_UI.state().camera),last_control_view:'bottom'});
   }
   console.log(sku+' – vlastní porovnávací rendery v4/v5 a oba boky / čelo / shora / zespodu');
  }
  assert.equal(errors.length,0,JSON.stringify(errors));
 }finally{fs.writeFileSync(path.join(out,'renderovani.json'),JSON.stringify({status:errors.length?'FAIL':'PASS',mode:'offline',renders:result,errors},null,2)+'\n');await browser.close();}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
