// Rez ze ZIVEHO stavu sceny - nastupce 2026-08-20_section_cut.js.
//
// PROC: puvodni nastroj si dil orientoval ve VLASTNIM rigu a Robert pak
// schvaloval obrazek, ktery nemusel odpovidat tomu, co dela runWallAut ve
// scene (presne to se stalo u kolecka 3404 - schvaleny rez C9.5 ukazoval
// osu kolecka v rovine steny, ale zive byla ulozena osa kolmo ke stene).
// Tenhle nastroj NIC neorientuje - bere matrixWorld profilu i dilu
// exportovane primo z bezici sceny (headless Playwright), takze
// obrazek == realita je garantovane.
//
// Vstup: JSON {profMatrix, accMatrix, profAxisWorld, wallNormalWorld,
//              accCenter, profFile, accFile} (export z page.evaluate).
// Rez: rovina s normalou = osa profilu, prochazi stredem dilu.
// Kresli se v souradnicich u = normala steny (kladne VEN ze steny),
// v = osa_profilu x u.
// Vystup: JSON segmenty pro matplotlib (mm mrizka, kota zasunuti).
const THREE = require("/opt/konfigurator/node_modules/three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const fs = require("fs");

const [,, stateFile, outFile] = process.argv;
const st = JSON.parse(fs.readFileSync(stateFile, "utf8"));

function loadWithMatrix(file, matArr) {
  const clean = file.split("?")[0]; // katalogove cesty maji cache-buster ?v=...
  const p = clean.startsWith("/") ? clean : "/opt/konfigurator/webapp/" + clean.replace(/^\.\//, "");
  const obj = parseGlbMesh(p);
  const grp = new THREE.Group();
  grp.matrixAutoUpdate = false;
  grp.matrix.fromArray(matArr);
  grp.add(obj);
  grp.updateMatrixWorld(true);
  return grp;
}
const prof = loadWithMatrix(st.profFile, st.profMatrix);
const acc = loadWithMatrix(st.accFile, st.accMatrix);

const nrm = new THREE.Vector3().fromArray(st.profAxisWorld).normalize();   // normala roviny rezu
const origin = new THREE.Vector3().fromArray(st.accCenter);
// Smer "ven ze steny" NEodvozovat z konektoroveho indexu (bookkeeping muze
// ukazovat na jiny konektor) - geometricky: kolma slozka spojnice
// stred profilu -> stred dilu vuci ose profilu. Dil sedi na stene, takze
// tahle slozka miri od osy profilu skrz attach stenu ven.
const profBB = new THREE.Box3().setFromObject(prof);
const profCen = profBB.getCenter(new THREE.Vector3());
const radial = origin.clone().sub(profCen);
radial.addScaledVector(nrm, -radial.dot(nrm));
const uDir = radial.normalize();
const vDir = new THREE.Vector3().crossVectors(nrm, uDir).normalize();

function sectionSegments(obj, cutNormal, projFn) {
  const segs = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  obj.traverse(n => {
    if (!n.isMesh || !n.geometry || !n.geometry.attributes.position) return;
    const pos = n.geometry.attributes.position, index = n.geometry.index;
    const triCount = index ? index.count / 3 : pos.count / 3;
    for (let t = 0; t < triCount; t++) {
      const ia = index ? index.getX(t*3) : t*3, ib = index ? index.getX(t*3+1) : t*3+1, ic = index ? index.getX(t*3+2) : t*3+2;
      vA.fromBufferAttribute(pos, ia).applyMatrix4(n.matrixWorld);
      vB.fromBufferAttribute(pos, ib).applyMatrix4(n.matrixWorld);
      vC.fromBufferAttribute(pos, ic).applyMatrix4(n.matrixWorld);
      const pts = [];
      [[vA,vB],[vB,vC],[vC,vA]].forEach(([p1,p2]) => {
        const d1 = p1.clone().sub(origin).dot(cutNormal), d2 = p2.clone().sub(origin).dot(cutNormal);
        if ((d1 > 0) !== (d2 > 0)) {
          const s = d1 / (d1 - d2);
          pts.push(projFn(p1.clone().lerp(p2, s)));
        }
      });
      if (pts.length === 2) segs.push([pts[0][0], pts[0][1], pts[1][0], pts[1][1]]);
    }
  });
  return segs;
}

// stena v u-souradnici: nejvzdalenejsi bod profilu ve smeru uDir
let wallU = -Infinity;
const tmp = new THREE.Vector3();
prof.traverse(n => {
  if (!n.isMesh || !n.geometry || !n.geometry.attributes.position) return;
  const pos = n.geometry.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    tmp.fromBufferAttribute(pos, i).applyMatrix4(n.matrixWorld);
    const u = tmp.clone().sub(origin).dot(uDir);
    if (u > wallU) wallU = u;
  }
});

// Rez A: rovina kolmo na osu profilu (normala = nrm), kresli u=uDir, v=vDir
const projA = (p) => { const d = p.clone().sub(origin); return [d.dot(uDir), d.dot(vDir)]; };
const profSegs = sectionSegments(prof, nrm, projA);
const dilSegs = sectionSegments(acc, nrm, projA);
// Rez B: rovina kolmo na vDir (u vecsiny wall dilu = osa kolecka/svisla),
// kresli u=uDir (hloubka do steny), w=nrm (podel profilu) - ukaze kruh
// kolecka vuci drazce podel profilu.
const projB = (p) => { const d = p.clone().sub(origin); return [d.dot(uDir), d.dot(nrm)]; };
const profSegsB = sectionSegments(prof, vDir, projB);
const dilSegsB = sectionSegments(acc, vDir, projB);
// zasunuti = o kolik dil presahuje rovinu steny smerem DOVNITR (u < wallU
// je uvnitr? ne - uDir je ven, stena je max profilu; dovnitr = u < wallU;
// dil zasahuje do drazky kdyz jeho min-u je POD wallU a zaroven cast dilu
// je nad wallU. Hloubka zasunuti = wallU - min(u dilu) omezene na >=0.
let dilMinU = Infinity, dilMaxU = -Infinity;
dilSegs.forEach(([x1,,x2]) => { dilMinU = Math.min(dilMinU, x1, x2); dilMaxU = Math.max(dilMaxU, x1, x2); });
const zasunuti = Math.max(0, wallU - dilMinU);

fs.writeFileSync(outFile, JSON.stringify({
  profil: profSegs, dil: dilSegs, profilB: profSegsB, dilB: dilSegsB, wallU, zasunuti,
}));
console.log("profil segs:", profSegs.length, "| dil segs:", dilSegs.length,
            "| stena u =", wallU.toFixed(2), "| zasunuti =", zasunuti.toFixed(2), "mm");
