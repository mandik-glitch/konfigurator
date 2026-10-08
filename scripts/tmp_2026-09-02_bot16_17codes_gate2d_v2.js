const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";

const rows = JSON.parse(fs.readFileSync(`${SCRATCH}/rows_full_postupdate.json`, "utf8"));
const H_TARGET_BY_CODE = { OP18: 1190, TO22: 1190, TO23: 1190, VW13: 1104, VW14: 1104, VW21: 1092, VW22: 1092, VW31: 1092, VW32: 1092 };
const REPRESENTATIVES = { OP18: 57, TO22: 64, TO23: 65, VW13: 122, VW14: 123, VW21: 124, VW22: 125, VW31: 126, VW32: 127 };
const WALL_ROLES = new Set(["cap", "zadni-svislice-dolni", "zadni-svislice-nad-zarezem", "zadni-svislice"]);
const LEG_TOPISH = new Set(["predni-svislice", ...WALL_ROLES]);

function box3ForPart(p) {
  const m = parseGlbMesh(KAT + p.part_id + ".glb");
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}
const rowsById = new Map(rows.map(r => [r.id, r]));
let allOk = true;
for (const [code, id] of Object.entries(REPRESENTATIVES)) {
  const row = rowsById.get(id);
  const Htgt = H_TARGET_BY_CODE[code];
  const parts = row.data.parts.filter(p => LEG_TOPISH.has(p.role));
  const zGroups = new Map();
  for (const p of parts) {
    const key = p.position[2].toFixed(3);
    if (!zGroups.has(key)) zGroups.set(key, []);
    zGroups.get(key).push(p);
  }
  let legOk = true;
  const legTops = [];
  for (const [z, items] of zGroups.entries()) {
    let top = -Infinity;
    for (const p of items) {
      const b = box3ForPart(p);
      if (b.max.y > top) top = b.max.y;
    }
    legTops.push({ z, top });
    if (Math.abs(top - Htgt) > 1) legOk = false;
  }
  console.log(code, "rowId=", id, "H_target=", Htgt, "legTops=", JSON.stringify(legTops.map(l=>l.top.toFixed(2))), "OK=", legOk);
  if (!legOk) allOk = false;
}
console.log("ALL OK:", allOk);
