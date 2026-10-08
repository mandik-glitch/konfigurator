const THREE=require("three"); const fs=require("fs");
const {partMesh}=require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");
const {parseGlbMesh}=require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R=require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const KAT="/opt/konfigurator/webapp/katalog/car_bodies/";
const cw={};
function stred(base,suf){const k=base+suf;
  if(!(k in cw)){try{const m=parseGlbMesh(KAT+base+suf+".glb");m.updateMatrixWorld(true);
    const b=new THREE.Box3().setFromObject(m);cw[k]=(b.min.x+b.max.x)/2;}catch(e){cw[k]=null;}}
  return cw[k];}
const asms=JSON.parse(fs.readFileSync(process.argv[2],"utf8"));
let zmereno=0,bezKaroserie=0,bezDilu=0; const v=[];
for(const a of asms){
  if(!a.carBodyBase){bezKaroserie++;continue;}
  const L=stred(a.carBodyBase,"_L"),P=stred(a.carBodyBase,"_R_D");
  if(L==null||P==null){bezKaroserie++;continue;}
  const stredVozu=(L+P)/2;
  const xs=[];
  for(const p of a.parts.filter(p=>!R.jeKaroserie(p.part_id))){
    let m=null;try{m=partMesh(p);}catch(e){}
    if(!m)continue;const b=new THREE.Box3().setFromObject(m);xs.push((b.min.x+b.max.x)/2);}
  if(!xs.length){bezDilu++;continue;}
  const x=xs.reduce((s,q)=>s+q,0)/xs.length;
  const odchylka=x-stredVozu;
  zmereno++;
  v.push({id:a.id,ted:a.umisteni_kod,zmereno:odchylka<0?"RL":"RP",odchylka:+odchylka.toFixed(0),
          ok:a.ok,name:(a.name||"").replace(/[🟠\s]+/g," ").slice(0,40)});
}
const nesedi=v.filter(r=>r.ted!==r.zmereno);
const slaby=v.filter(r=>Math.abs(r.odchylka)<100);
console.log(`ROZSAH: ${asms.length} sestav | zmereno ${zmereno} | bez karoserie ${bezKaroserie} | bez meritelnych dilu ${bezDilu}`);
console.log(`\nSTITEK NESEDI se zmerenou polohou: ${nesedi.length}`);
const perK={}; nesedi.forEach(r=>{const k=r.ted+"->"+r.zmereno;(perK[k]=perK[k]||[]).push(r);});
Object.entries(perK).forEach(([k,rs])=>console.log(`   ${k}: ${rs.length} sestav (schvalenych ${rs.filter(x=>x.ok).length})`));
console.log(`\nnejednoznacnych (|odchylka| < 100 mm): ${slaby.length}`);
slaby.slice(0,5).forEach(r=>console.log(`   #${r.id} odchylka ${r.odchylka} mm  ${r.name}`));
console.log(`\nprvnich 8 nesedicich:`);
nesedi.slice(0,8).forEach(r=>console.log(`   #${r.id} DB=${r.ted} zmereno=${r.zmereno} (${r.odchylka} mm od stredu) ok=${r.ok}  ${r.name}`));
fs.writeFileSync(process.argv[3],JSON.stringify(v,null,1));
