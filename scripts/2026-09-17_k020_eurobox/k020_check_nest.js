const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const parts = require(process.argv[2] || "./k020_parts.json").parts.filter(p => !p.part_id.startsWith("car_body_") && !String(p.role||"").startsWith("uhelnik-")); // karoserie se tu nekontroluje (kolize se stenami resi k020_build.js)
const m = p => { const x = parseGlbMesh(KAT + p.part_id + ".glb"); x.position.set(...p.position); x.quaternion.set(...p.quaternion); x.scale.set(...p.scale); x.updateMatrixWorld(true); return new THREE.Box3().setFromObject(x); };
const B = parts.map(m);
const ov = (a, b) => [0,1,2].map(k => Math.min(a.max.getComponent(k), b.max.getComponent(k)) - Math.max(a.min.getComponent(k), b.min.getComponent(k)));
const problems = []; let pairs = 0;
parts.forEach((p, i) => {
  if (p.part_id === "Object_7") return;
  parts.forEach((q, j) => {
    if (i === j) return;
    if (q.part_id !== "Object_7" && j < i) return;
    pairs++;
    const o = ov(B[i], B[j]);
    if (!(o[0] > 0.5 && o[1] > 0.5 && o[2] > 0.5)) return;
    const isBox = p.part_id.startsWith("product_37"), isCap = p.part_id === "product_3071";
    let ok = false, why = "";
    if (isBox && q.part_id === "Object_7" && /^(nosnik|spojnice)-sloupec/.test(q.role) && o[1] <= 12.6 && B[i].min.y < B[j].max.y) { ok = true; why = "nozka boxu v luzku"; }
    if (isCap && q.part_id === "Object_7" && p.role === "zaslepka-" + q.role) { ok = true; why = "cep zaslepky ve vlastnim profilu"; }
    if (!ok) problems.push({ a: p.role, b: q.role, overlap: o.map(v => +v.toFixed(2)) });
  });
});
console.log("rozsah: dvojic box/zaslepka x cokoli =", pairs, "| boxu", parts.filter(p=>p.part_id.startsWith("product_37")).length, "zaslepek", parts.filter(p=>p.part_id==="product_3071").length);
console.log("NEOCEKAVANE prekryvy:", problems.length); problems.forEach(x => console.log("  ", JSON.stringify(x)));
