// Vyfiltruje z navrhu uhelniku (2026-09-05_add_uhelniky_all_legs.js --out) ty,
// ktere by NOVE kolidovaly s jinym dilem sestavy nebo s jiz prijatym uhelnikem
// (bot22, 2026-09-05). Meri SPRAVNY GLB: part_id product_3045 renderuje
// product_2895.glb (shop_products.glb_file) - puvodni add skript merìl gap jen
// pres katalog geo_faces (flush na profily nohy OK), ale kolizi s okolim
// (box/patra/sousedni uhelnik) neoveril proti realne GLB geometrii.
// Greedy: uhelniky se prijimaji v poradi, kazdy proti dosud prijatemu stavu.
//
// === OPRAVA 2026-09-11 (bot16) - filtr byl slepy k vlastni noze ===
// Puvodne tu byl radek, ktery PRESKAKOVAL profily vlastni nohy:
//     if(o.p.part_id==="Object_7" && Math.abs(...-uz)<=60) continue;
// Duvod byl "na ty uhelnik dosedá flush". Jenze `emb()` nize uz SAMO je test
// PRUNIKU, ne dotyku - vyzaduje prekryv > EPS na VSECH TRECH osach, takze
// flush dosed (prekryv 0 na dotykove ose) jim neprojde ani bez toho radku.
// Preskok byl tedy zbytecny a soucasne delal filtr slepym k realnym prunikum
// do vlastni nohy. Zmereno 2026-09-11 nad celym katalogem: 44 uhelniku
// pronika do profilu vlastni nohy o 5-22 mm a filtr by PRESKOCIL 44 ze 44.
// Zaroven overeno, ze odstraneni preskoku nedela falesne poplachy: ze 5164
// uhelniku v DB ma prunik > 1mm prave tech 44, zbylych 5120 ma <= 1mm
// (spravne umistene uhelniky lezi v rohu MIMO bounding boxy obou profilu).
// Sweep scripts/2026-09-11_sweep_kolizni_uhelniky.cjs slouzi jako regresni
// test - po teto oprave uz nesmi vznikat nove kusy, ktere by nasel.
//
// === PROC SE TED VYPISUJE, KOLIK PARU SE POROVNALO ===
// Poučeni z teto kontroly (AGENTS_LOG.md 2026-09-11): DVAKRAT PO SOBE
// ohlasila "0 kolizi" z duvodu, ktery s cistotou nesouvisel - poprve protoze
// chybejici GLB vratil null a geometrie se TISE nemerila, podruhe protoze se
// partner zamerne preskakoval. Kontrola, ktera nema jak selhat hlasite, mlci
// i kdyz nemeri nic. Proto se ted vypisuje POCET POROVNANYCH PARU a pocet
// dilu, jejichz geometrii neslo zmerit - a kdyz se neco zmerit nepodarilo,
// skript skonci NENULOVYM exitem misto falesne uklidnujiciho "0 kolizi".
const fs=require("fs"); const THREE=require("/opt/konfigurator/node_modules/three");
const {parseGlbMesh}=require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT="/opt/konfigurator/webapp/katalog/";
const asm=process.argv[2], navrhPath=process.argv[3], outPath=process.argv[4];
const all=JSON.parse(fs.readFileSync(asm,"utf8"));
const navrh=JSON.parse(fs.readFileSync(navrhPath,"utf8"));
const rowById=new Map((all.rows||all).map(r=>[r.id,r]));
// part_id -> nazev GLB. NEHADA se z part_id (AGENTS_LOG.md 2026-09-05:
// "part_id NENI nazev GLB souboru"), cte se z mapy vygenerovane z
// shop_products.glb_file. Puvodne tu byl natvrdo jediny zaznam
// {"product_3045":"product_2895"} - jenze odlisny nazev GLB maji CTYRI
// produkty, takze `product_3939` (MDF deska), `product_3539` a
// `product_3671` se do kolizi TISE nezapocitavaly vubec (box() vracel null).
// Tretí vyskyt teze tridy chyby, viz hlavicka a AGENTS_LOG.md 2026-09-11.
const MAPA_PATH="/opt/konfigurator/scripts/2026-09-11_glb_mapping.json";
if(!fs.existsSync(MAPA_PATH)){
  console.error(`CHYBA: chybi mapa GLB ${MAPA_PATH}. Vygeneruj ji`
    + " (scripts/2026-09-11_dump_glb_mapping.py) - bez ni by se cast dilu"
    + " tise nemerila a kontrola by hlasila falesne cisto.");
  process.exit(1);
}
const GLBMAP=JSON.parse(fs.readFileSync(MAPA_PATH,"utf8")).mapa;
// Karoserie NENI katalogovy dil (vlastni tvar, GLB se nacita jinou cestou) a
// do kolizni kontroly uhelniku nepatri - navic podle WORKFLOW.md bodu 25 v
// sestave vubec nema byt. Vylouceno ZAMERNE, proto se nepocita jako "neslo
// zmerit".
const jeKaroserie=p=>String(p.part_id||"").startsWith("car_body_");
const cache={};
function box(p){ const g=GLBMAP[p.part_id]||p.part_id;
  if(!(g in cache)){const f=KAT+g+".glb"; cache[g]=fs.existsSync(f)?parseGlbMesh(f):null;}
  const m=cache[g]; if(!m) return null;
  m.position.set(...p.position); const q=p.quaternion||[0,0,0,1]; m.quaternion.set(q[0],q[1],q[2],q[3]);
  const s=p.scale||[1,1,1]; m.scale.set(s[0],s[1],s[2]); m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m); }
const EPS=1.0;
const emb=(a,b)=>Math.min(a.max.x,b.max.x)-Math.max(a.min.x,b.min.x)>EPS
  && Math.min(a.max.y,b.max.y)-Math.max(a.min.y,b.min.y)>EPS
  && Math.min(a.max.z,b.max.z)-Math.max(a.min.z,b.min.z)>EPS;
// hloubka pruniku = nejmensi z prekryvu pres 3 osy (0 a min = zadny prunik)
const hloubka=(a,b)=>Math.min(
  Math.min(a.max.x,b.max.x)-Math.max(a.min.x,b.min.x),
  Math.min(a.max.y,b.max.y)-Math.max(a.min.y,b.min.y),
  Math.min(a.max.z,b.max.z)-Math.max(a.min.z,b.min.z));

const clean={}; let tot=0,kept=0,drop=0;
let porovnanoParu=0, nezmereno=0;           // viz hlavicka: "0 z 0" != "0 z 2000"
const nezmereneDily=new Set(), detail=[];
for(const id in navrh){
  const row=rowById.get(Number(id)); if(!row) continue;
  const sGeometrii=row.parts.filter(p=>p.position&&!jeKaroserie(p)).map(p=>({p,b:box(p)}));
  for(const e of sGeometrii) if(!e.b){ nezmereno++; nezmereneDily.add(e.p.part_id); }
  const others=sGeometrii.filter(e=>e.b);
  const accepted=[];  // {p,b}
  const keep=[];
  for(const u of navrh[id].add){
    tot++;
    const bu=box(u);
    if(!bu){ nezmereno++; nezmereneDily.add(u.part_id); drop++; continue; }
    let hit=false, nejhlubsi=0, sKym=null;
    // vs VSECHNY ostatni dily VCETNE profilu vlastni nohy. Flush dosed jimi
    // neprojde sam od sebe (emb vyzaduje prekryv > EPS na vsech 3 osach),
    // takze uhelnik, ktery na nohu jen doseda, se nezahazuje.
    for(const o of others){
      porovnanoParu++;
      if(emb(bu,o.b)){ const h=hloubka(bu,o.b);
        if(h>nejhlubsi){ nejhlubsi=h; sKym=o.p.role||o.p.part_id; } hit=true; }
    }
    // vs jiz prijate uhelniky
    for(const a of accepted){
      porovnanoParu++;
      if(emb(bu,a.b)){ const h=hloubka(bu,a.b);
        if(h>nejhlubsi){ nejhlubsi=h; sKym=(a.p.role||a.p.part_id)+" (uhelnik)"; } hit=true; }
    }
    if(hit){ drop++;
      detail.push({asm:Number(id), role:u.role||"?", poz:u.position.map(v=>Math.round(v*10)/10),
                   prunik:Math.round(nejhlubsi*10)/10, sKym});
      continue; }
    accepted.push({p:u,b:bu}); keep.push(u); kept++;
  }
  if(keep.length) clean[id]={id:Number(id),name:navrh[id].name,add:keep};
}
fs.writeFileSync(outPath, JSON.stringify(clean));
console.log("uhelniku v navrhu:", tot, "| prijato:", kept, "| vyrazeno (kolize):", drop);
console.log("POROVNANO PARU:", porovnanoParu, "- 0 kolizi z 0 porovnanych je CHYBA, ne vysledek");
console.log("dotcenych sestav po filtru:", Object.keys(clean).length);
if(detail.length){
  console.log("\nvyrazene kusy (prunik mm, s cim):");
  for(const d of detail) console.log(`  #${d.asm} ${d.role} poz=[${d.poz}] prunik ${d.prunik}mm do ${d.sKym}`);
}
console.log("\nclean navrh ->", outPath);
if(nezmereno){
  // Tohle je presne ta chyba z 2026-09-05: chybejici GLB -> null -> kolize se
  // TISE nemerily -> falesnych "0 kolizi". Radsi hlasite selhat.
  console.error(`\nCHYBA: u ${nezmereno} dilu neslo zmerit geometrii (chybejici GLB?): `
    + [...nezmereneDily].join(", ")
    + "\nVysledek NENI duveryhodny - cast dilu se do kolizi vubec nezapocitala.");
  process.exit(1);
}
if(porovnanoParu===0){
  console.error("\nCHYBA: neporovnal se ani jeden par - kontrola fakticky nebezela.");
  process.exit(1);
}
