// PRAVIDLO (Robert 2026-09-21): "pravidlo horniho bloku: nic nesmi prekrocit
// vysku nohou." Kontrola nad CELYM katalogem, ne jen nad dnesni davkou.
const THREE=require("three"); const fs=require("fs");
const {partMesh}=require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");
const R=require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const BLOK=/^(podelnik|pricka-spodni|pricka-horni|pricka-police|vypln-|dvirka)/i;
const LEG=/^(predni-svislice|cap)(\b|-|$)/i;
const asms=JSON.parse(fs.readFileSync(process.argv[2],"utf8"));
let mereno=0,dilu=0,nemer=0; const vada=[];
for(const a of asms){
  const wb=[]; let bad=false;
  for(const p of a.parts.filter(p=>!R.jeKaroserie(p.part_id))){
    dilu++; let m=null; try{m=partMesh(p);}catch(e){}
    if(!m){nemer++;bad=true;continue;}
    wb.push({p,box:new THREE.Box3().setFromObject(m)});
  }
  const blok=wb.filter(x=>BLOK.test(x.p.role||""));
  const legs=wb.filter(x=>LEG.test(x.p.role||""));
  if(bad||!blok.length||!legs.length) continue;
  mereno++;
  const legTop=Math.max(...legs.map(x=>x.box.max.y));
  const nad=blok.filter(x=>x.box.max.y>legTop+0.5);
  if(!nad.length) continue;
  const max=Math.max(...nad.map(x=>x.box.max.y))-legTop;
  vada.push({id:a.id,kod:a.kod,ok:a.ok,pres:+max.toFixed(1),dilu:nad.length,
    role:[...new Set(nad.map(x=>(x.p.role||"").replace(/\d+/g,"N")))],
    name:(a.name||"").replace(/[🟠\s]+/g," ").slice(0,40)});
}
console.log(`ROZSAH: ${asms.length} sestav s hornim blokem, zmereno ${mereno}, ${dilu} dilu, ${nemer} nemeritelnych`);
console.log(`\nPORUSUJE "nic nesmi prekrocit vysku nohou": ${vada.length} sestav\n`);
const per={}; vada.forEach(r=>(per[r.kod]=per[r.kod]||[]).push(r));
Object.keys(per).sort().forEach(k=>{
  const rs=per[k].sort((a,b)=>b.pres-a.pres);
  console.log(`  kod ${k}: ${rs.length} sestav, prevyseni ${rs[rs.length-1].pres}-${rs[0].pres}mm, schvalenych ${rs.filter(r=>r.ok).length}`);
  rs.slice(0,5).forEach(r=>console.log(`     #${r.id} +${r.pres}mm (${r.dilu} dilu: ${r.role.join(",")})  ${r.name}`));
});
fs.writeFileSync(process.argv[3],JSON.stringify(vada,null,1));
