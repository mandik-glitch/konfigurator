// Rez JEDNIM souborem (_L nebo _R_D) - zadny cross-file sev, takze
// walkLoop (skutecna, ne konvexni smycka) by mel fungovat a ukazat
// konkavni zarez podbehu, pokud na dane vysce existuje.
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/car_bodies/";

function sectionSegments(obj, origin, cutNormal, projFn) {
  const segs = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  const pos = obj.geometry.attributes.position, index = obj.geometry.index;
  const triCount = index ? index.count / 3 : pos.count / 3;
  for (let t = 0; t < triCount; t++) {
    const ia = index ? index.getX(t*3) : t*3, ib = index ? index.getX(t*3+1) : t*3+1, ic = index ? index.getX(t*3+2) : t*3+2;
    vA.fromBufferAttribute(pos, ia).applyMatrix4(obj.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(obj.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(obj.matrixWorld);
    const pts = [];
    [[vA,vB],[vB,vC],[vC,vA]].forEach(([p1,p2]) => {
      const d1 = p1.clone().sub(origin).dot(cutNormal), d2 = p2.clone().sub(origin).dot(cutNormal);
      if ((d1>0)!==(d2>0)) { const s = d1/(d1-d2); pts.push(projFn(p1.clone().lerp(p2,s))); }
    });
    if (pts.length === 2) segs.push([pts[0][0],pts[0][1],pts[1][0],pts[1][1]]);
  }
  return segs;
}
function keyOf(x,z){ return `${x.toFixed(1)},${z.toFixed(1)}`; }
function connectedComponents(segs) {
  const uf = {};
  function ufind(a){ if(!(a in uf)) uf[a]=a; while(uf[a]!==a){uf[a]=uf[uf[a]];a=uf[a];} return a; }
  function uunion(a,b){ const ra=ufind(a),rb=ufind(b); if(ra!==rb) uf[ra]=rb; }
  for (const [x1,z1,x2,z2] of segs) uunion(keyOf(x1,z1),keyOf(x2,z2));
  const groups = {};
  for (const s of segs) { const r=ufind(keyOf(s[0],s[1])); (groups[r]=groups[r]||[]).push(s); }
  return Object.values(groups);
}
function walkLoop(segList) {
  const adj = new Map(), pointOf = new Map();
  for (const [x1,z1,x2,z2] of segList) {
    const k1=keyOf(x1,z1), k2=keyOf(x2,z2);
    pointOf.set(k1,[x1,z1]); pointOf.set(k2,[x2,z2]);
    if(!adj.has(k1)) adj.set(k1,[]); if(!adj.has(k2)) adj.set(k2,[]);
    adj.get(k1).push(k2); adj.get(k2).push(k1);
  }
  const start = keyOf(segList[0][0], segList[0][1]);
  const loop = [start]; const visited = new Set(); let cur = start;
  for (let i=0;i<segList.length+2;i++) {
    const neighbors = adj.get(cur)||[];
    const next = neighbors.find(n => !visited.has(cur+"|"+n));
    if (next==null) break;
    visited.add(cur+"|"+next); visited.add(next+"|"+cur);
    loop.push(next); cur = next;
    if (cur===start) break;
  }
  return { points: loop.map(k=>pointOf.get(k)), degrees: [...adj.values()].map(v=>v.length) };
}

const base = "Fiat_Doblo_FI14_2010-2022";
const m = parseGlbMesh(KAT + base + "_L.glb");
m.updateMatrixWorld(true);

for (const y of [80, 120, 160, 200, 250, 300, 350]) {
  const segs = sectionSegments(m, new THREE.Vector3(0,y,0), new THREE.Vector3(0,1,0), p => [p.x, p.z]);
  const comps = connectedComponents(segs).sort((a,b)=>b.length-a.length);
  if (!comps.length) { console.log(`Y=${y}: zadny rez`); continue; }
  const main = comps[0];
  const maxDeg = Math.max(...(walkLoop(main).degrees));
  const loop = walkLoop(main);
  const closed = loop.points.length > 2 && keyOf(...loop.points[0]) === keyOf(...loop.points[loop.points.length-1]);
  const xs = main.flatMap(s=>[s[0],s[2]]), zs = main.flatMap(s=>[s[1],s[3]]);
  console.log(`Y=${y}: hlavni komponenta ${main.length} usecek, smycka ${loop.points.length} bodu, uzavrena=${closed}, maxStupen=${maxDeg}, X[${Math.min(...xs).toFixed(0)},${Math.max(...xs).toFixed(0)}] Z[${Math.min(...zs).toFixed(0)},${Math.max(...zs).toFixed(0)}], pocet komponent=${comps.length}`);
}
