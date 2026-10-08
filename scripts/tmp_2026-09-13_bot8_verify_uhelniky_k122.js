const fs = require("fs");
const THREE = require("three");
global.THREE = THREE;
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const MK = require("/opt/konfigurator/scripts/2026-09-11_mesh_kolize_lib.js");

const IDS = process.argv.slice(2).map(Number);
for (const aid of IDS) {
  const data = JSON.parse(fs.readFileSync(`/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/rebuilt_${aid}.json`, "utf8"));
  const parts = data.parts.filter(p => !String(p.part_id||"").startsWith("car_body_") && !String(p.role||"").startsWith("kontrolni-pomucka"));
  const prepared = parts.map(p => {
    const gp = R.glbPath(p.part_id);
    if (!gp) return null;
    return { p, D: MK.dilVeSvete(gp, p, parseGlbMesh) };
  }).filter(Boolean);

  let realCollisions = 0;
  const found = [];
  for (let i = 0; i < prepared.length; i++) {
    for (let j = i + 1; j < prepared.length; j++) {
      const A = prepared[i], B = prepared[j];
      // jen zajimave dvojice: aspon jedna je uhelnik (fokus overeni) A boxy se prekryvaji
      if (!String(A.p.role).startsWith("uhelnik-") && !String(B.p.role).startsWith("uhelnik-")) continue;
      if (!MK.prekryvBoxu(A.D.box, B.D.box)) continue;
      const verdict = MK.kolize(A.D, B.D, MK.TOL_MM, false);
      if (verdict && verdict.koliduje) {
        realCollisions++;
        found.push({ a: A.p.role, b: B.p.role, posA: A.p.position, posB: B.p.position });
      }
    }
  }
  console.log(`id=${aid}: dilu overeno=${prepared.length}, skutecnych kolizi (mesh-presne, focus na uhelniky)=${realCollisions}`);
  if (found.length) console.log(JSON.stringify(found, null, 1));
}
