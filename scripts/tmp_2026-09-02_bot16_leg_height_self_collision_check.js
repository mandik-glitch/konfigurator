// bot16 2026-09-02 - self-collision sanity check for the 51 rows just updated
// by the id=8 leg-height fix: does the NEW (post-update, fresh from DB) front-
// svislice / wall-top piece box now volumetrically overlap any OTHER non-car-body
// part in the same row? Shrink boxes by 2mm before testing to avoid false
// positives from intentional flush joints (e.g. the zaslepka end-cap sitting
// right at the profile's end plane).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";

const APPLIED_IDS = [58,59,60,61,62,63,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,105,106,128,129,130,131,132,133,134,135,136,145,146,149,150,151,152,157,158,167,168,171,172,173,174,179,180];

const rows = JSON.parse(fs.readFileSync(`${SCRATCH}/rows_full.json`, "utf8")); // fresh post-update export
const plan = JSON.parse(fs.readFileSync(`${SCRATCH}/plan.json`, "utf8")); // stale plan (pre-recompute would be needed for idx) - instead re-derive from role directly

const meshCache = {};
function getMesh(id) { if (!meshCache[id]) meshCache[id] = parseGlbMesh(KAT + id + ".glb"); return meshCache[id]; }
function box3For(p) {
  const m = getMesh(p.part_id);
  m.position.set(p.position[0], p.position[1], p.position[2]);
  m.quaternion.set(p.quaternion[0], p.quaternion[1], p.quaternion[2], p.quaternion[3]);
  m.scale.set(p.scale[0], p.scale[1], p.scale[2]);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}
function shrink(b, eps) {
  return new THREE.Box3(b.min.clone().addScalar(eps), b.max.clone().addScalar(-eps));
}

const WALL_ROLES = new Set(["cap", "zadni-svislice-dolni", "zadni-svislice-nad-zarezem", "zadni-svislice"]);
const rowsById = new Map(rows.map(r => [r.id, r]));

let totalChecked = 0, totalOverlaps = 0;
const findings = [];

for (const id of APPLIED_IDS) {
  const row = rowsById.get(id);
  const parts = row.data.parts;
  // identify all leg-changed pieces (front-svislice + wall-top per leg cluster by Z)
  const changed = [];
  const zGroups = new Map();
  parts.forEach((p, idx) => {
    if (p.role === "predni-svislice" || WALL_ROLES.has(p.role)) {
      const key = p.position[2].toFixed(3);
      if (!zGroups.has(key)) zGroups.set(key, []);
      zGroups.get(key).push({ p, idx });
    }
  });
  for (const [, items] of zGroups.entries()) {
    const front = items.find(it => it.p.role === "predni-svislice");
    const capItem = items.find(it => it.p.role === "cap");
    let wall = capItem;
    if (!wall) {
      // geometric argmax top among wall candidates
      let best = null, bestTop = -Infinity;
      for (const it of items) {
        if (!WALL_ROLES.has(it.p.role)) continue;
        const b = box3For(it.p);
        if (b.max.y > bestTop) { bestTop = b.max.y; best = it; }
      }
      wall = best;
    }
    if (front) changed.push(front);
    if (wall) changed.push(wall);
  }

  const others = parts.filter(p => !p.part_id.startsWith("car_body"));
  for (const c of changed) {
    totalChecked++;
    const bC = shrink(box3For(c.p), 2);
    for (let i = 0; i < others.length; i++) {
      if (others[i] === c.p) continue;
      const o = others[i];
      // skip the piece's own matched zaslepka (flush by design, already excluded via shrink+role heuristic below not needed since product_3071 is tiny 9mm - shrink 2mm each side leaves 5mm, real overlaps would still show if genuinely embedded)
      const bO = shrink(box3For(o), 2);
      if (bC.intersectsBox(bO)) {
        totalOverlaps++;
        findings.push({ id, role: c.p.role, otherRole: o.role, otherPartId: o.part_id });
      }
    }
  }
}
console.log(JSON.stringify({ totalChecked, totalOverlaps, findings: findings.slice(0, 50) }, null, 1));
