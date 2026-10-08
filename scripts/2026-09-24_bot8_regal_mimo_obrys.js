const THREE=require("three"); const fs=require("fs");
const {partMesh}=require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");
const {parseGlbMesh}=require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R=require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const KAT="/opt/konfigurator/webapp/katalog/car_bodies/";
const asms=JSON.parse(fs.readFileSync(process.argv[2],"utf8"));
for(const id of process.argv[3].split(",").map(Number)){
  const a=asms.find(x=>x.id===id); if(!a||!a.carBodyBase){console.log(`#${id} bez karoserie`);continue;}
  const bb={};
  for(const suf of ["_L","_R_D"]){
    try{const m=parseGlbMesh(KAT+a.carBodyBase+suf+".glb");m.updateMatrixWorld(true);
      const b=new THREE.Box3().setFromObject(m);bb[suf]=[b.min.x,b.max.x];}catch(e){bb[suf]=null;}
  }
  const xs=[];
  for(const p of a.parts.filter(p=>!R.jeKaroserie(p.part_id))){
    let m=null;try{m=partMesh(p);}catch(e){} if(!m)continue;
    const b=new THREE.Box3().setFromObject(m);xs.push(b.min.x,b.max.x);}
  const rmin=Math.min(...xs),rmax=Math.max(...xs);
  const vnitroMin=Math.min(bb._L[1],bb._R_D[1]), vnitroMax=Math.max(bb._L[0],bb._R_D[0]);
  console.log(`\n#${id} ok=${a.ok} DB=${a.umisteni_kod}  ${(a.name||"").replace(/[🟠\s]+/g," ").slice(0,36)}`);
  console.log(`   stena L  X=[${bb._L[0].toFixed(0)} .. ${bb._L[1].toFixed(0)}]`);
  console.log(`   stena R  X=[${bb._R_D[0].toFixed(0)} .. ${bb._R_D[1].toFixed(0)}]`);
  console.log(`   REGAL    X=[${rmin.toFixed(0)} .. ${rmax.toFixed(0)}]`);
  const venku = rmax > Math.max(bb._R_D[1],bb._L[1]) || rmin < Math.min(bb._R_D[0],bb._L[0]);
  console.log(`   -> ${venku?"CAST REGALU JE MIMO OBRYS KAROSERIE":"uvnitr obrysu"}`);
}
