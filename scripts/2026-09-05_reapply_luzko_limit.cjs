// Znovu aplikuje pravidlo limit_maximalni_vysky_patra (KOMPONENTY_EUROBOXY.md,
// shape_geometry_methods.id=3): LŮŽKO (rail = nosník+spojnice patra) musí mít
// railYCenter <= TOP_Y - T/2, kde TOP_Y = horní okraj profilu nohy. BOX smí
// přesahovat (podepřen jen zdola), LŮŽKO ne (bot22, 2026-09-05).
//
// Robert: "kde se zkrátily nohy, musí se znovu aplikovat pravidla." Po zkrácení
// noh (id=8 dveře / id=6 podběh) zůstala u některých sestav lůžka nad novým
// (nižším) TOP_Y - tady se ta lůžka + jejich boxy odstraní.
//
// ODSTRANÍ díl, když:
//   - je to rail/lůžko (nosnik-* nebo spojnice-sloupecN/colN) a jeho Y-střed > limit
//   - je to eurobox a jeho SPODEK (Box3.min.y) > limit  (= box stojí na odstraněném lůžku;
//     box posledního VALIDNÍHO lůžka má spodek <= limit a zůstává, i když vrškem přesahuje)
// Nohy (svislice/cap/sloupek), úhelníky a záslepky noh zůstávají beze změny.
//
// READ-ONLY, vysledek do --out JSON.  node ... <all.json> [--out navrh.json]
const fs=require("fs"); const THREE=require("/opt/konfigurator/node_modules/three");
const {parseGlbMesh}=require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT="/opt/konfigurator/webapp/katalog/";
const asm=process.argv[2]; const outIdx=process.argv.indexOf("--out"); const outPath=outIdx>0?process.argv[outIdx+1]:null;
const all=JSON.parse(fs.readFileSync(asm,"utf8"));
const GLBMAP={"product_3045":"product_2895"}; const cache={};
function box(p){ const g=GLBMAP[p.part_id]||p.part_id;
  if(!(g in cache)){const f=KAT+g+".glb"; cache[g]=fs.existsSync(f)?parseGlbMesh(f):null;}
  const m=cache[g]; if(!m) return null;
  m.position.set(...p.position); const q=p.quaternion||[0,0,0,1]; m.quaternion.set(q[0],q[1],q[2],q[3]);
  const s=p.scale||[1,1,1]; m.scale.set(s[0],s[1],s[2]); m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m); }
const T=30;
const isRail=r=>/^nosnik/.test(r)||/^spojnice-(sloupec|col)\d/.test(r);
const isBox=r=>/^eurobox/.test(r);
const patched={}; let totRemoved=0, sestDot=0;
for(const row of (all.rows||all)){
  let topY=-1e9;
  for(const p of row.parts){ if(!p.position) continue; const r=p.role||"";
    if(p.part_id==="Object_7" && /svislice|^cap$/.test(r)){ const b=box(p); if(b) topY=Math.max(topY,b.max.y); } }
  if(topY<-1e8) continue;
  const limit=topY - T/2;
  const keep=[]; const removed=[];
  for(const p of row.parts){
    const r=p.role||""; let drop=false;
    if(p.position && (isRail(r)||isBox(r))){
      const b=box(p);
      if(b){
        if(isRail(r) && (b.min.y+b.max.y)/2 > limit+1) drop=true;
        if(isBox(r) && b.min.y > limit+1) drop=true;
      }
    }
    if(drop) removed.push(r); else keep.push(p);
  }
  if(removed.length){ patched[row.id]={id:row.id,name:row.name,keep,removedCount:removed.length};
    totRemoved+=removed.length; sestDot++;
    console.log("id="+String(row.id).padEnd(4)+row.name.slice(0,40).padEnd(41)+" odstranit "+removed.length+" dilu (luzka+boxy nad TOP_Y)"); }
}
console.log("\ndotcenych sestav: "+sestDot+" | dilu k odstraneni: "+totRemoved);
if(outPath){ const o={}; for(const id in patched) o[id]={id:patched[id].id,name:patched[id].name,parts:patched[id].keep};
  fs.writeFileSync(outPath, JSON.stringify(o)); console.log("navrh (nova parts) -> "+outPath+" (NIC DO DB)"); }
