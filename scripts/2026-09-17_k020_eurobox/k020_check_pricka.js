// Dosed "pricka-uzavreni-vyrezu" a "sloupek-pred-podbehem" (vc. paty na podlaze) na 3 osach.
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const parts = require(process.argv[2] || "./k020_parts.json").parts.filter(p => p.part_id === "Object_7");
const B = parts.map(p => { const m = parseGlbMesh(KAT + "Object_7.glb"); m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale); m.updateMatrixWorld(true); return new THREE.Box3().setFromObject(m); });
const ov = (a, b) => [0,1,2].map(k => Math.min(a.max.getComponent(k), b.max.getComponent(k)) - Math.max(a.min.getComponent(k), b.min.getComponent(k)));
const sz = b => [0,1,2].map(k => b.max.getComponent(k) - b.min.getComponent(k));
let chyb = 0;
parts.forEach((p, i) => {
  if (!/^(pricka-uzavreni-vyrezu|sloupek-pred-podbehem)/.test(p.role)) return;
  const t = [];
  parts.forEach((q, j) => {
    if (i === j) return;
    const o = ov(B[i], B[j]);
    const k = o.map((v, a) => Math.abs(v) <= 0.05 ? a : -1).filter(a => a >= 0);
    if (k.length !== 1) return;
    const others = [0,1,2].filter(a => a !== k[0]);
    if (!others.every(a => o[a] > 0.5)) return;
    const full = others.every(a => o[a] >= Math.min(sz(B[i])[a], sz(B[j])[a]) - 0.05);
    if (!full) chyb++;
    t.push(`${q.role}:${"xyz"[k[0]]}:${full ? "plna" : "NEPLNA"}`);
  });
  console.log(p.role, "Y", B[i].min.y.toFixed(1), "-", B[i].max.y.toFixed(1), "->", t.join(", "));
});
console.log("neplnych dosedu:", chyb);
