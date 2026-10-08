// bot24 2026-09-02. VW31 B/C/D/E variants on top of the newly-extended base
// (id=126, rebuilt by 2026-09-02_bot24_caddy_podbeh_fix.js) - same convention
// as the earlier B/C/D/E work (bot16, 2026-09-01): legs/rails/X-Z footprint are
// FIXED (from the base build), only the eurobox GLB placed on each existing
// rail slot changes, subject to "new height <= slot's original height" (the
// slot's clearance to the rail/level above it was already verified for the
// ORIGINAL height, so a smaller box is automatically safe - no new floor/rail
// collision test needed for that reason alone). Eurobox-vs-walls collision is
// still verified fresh per variant (arch shape differs from the old, shorter
// base this batch replaces).
const THREE = require("three");
const fs = require("fs");
const { makeEnv, KAT } = require("/opt/konfigurator/scripts/2026-09-01_bot16_env_factory.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const EUROBOX_GLB = { 120: KAT + "product_3788.glb", 170: KAT + "product_3793.glb", 220: KAT + "product_3794.glb", 270: KAT + "product_3795.glb" };
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
const Q_ALONG_Z = [-0.707107, 0, 0, 0.707107];

const base = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/bot24_VW31_result.json", "utf8"));
const env = makeEnv("Volkswagen_Caddy_VW31_2021-");
const { collidesWithWalls } = env;
const D = base.D, T = base.T, offsetX = base.offsetX;

// Non-eurobox parts (legs+rails+spojnice+zaslepky) - identical across all
// variants including the base itself.
const structuralParts = base.allParts.filter(p => !p.part_id.startsWith("product_37"));
// Slot geometry per (col,level): derive railZFrom/railZTo/railYCenter/original H
// directly from the base build's own eurobox part positions+role (role encodes
// col/level: "eurobox-col{ci}-p{li}").
const baseBoxes = base.allParts.filter(p => p.part_id.startsWith("product_37"));
function roleKey(role) { const m = role.match(/eurobox-col(\d+)-p(\d+)/); return m ? `${m[1]}-${m[2]}` : role; }
const slotOriginal = {};
baseBoxes.forEach(p => {
  const key = roleKey(p.role);
  const origH = Object.keys(EUROBOX_PID).find(h => EUROBOX_PID[h] === p.part_id);
  slotOriginal[key] = { origH: Number(origH), samplePos: p.position, role: p.role };
});
console.log("slots:", JSON.stringify(slotOriginal, null, 1));

// Need railYCenter (world) + slot Z-range per slot to reposition a different
// height's box the same way the original builder did (bottom-anchored: box
// bottom sits at railYCenter+T/2, centered in its Z-slot).
const CONNECTOR_POS = { 1: [15, 415], 2: [15, 415, 816], 3: [15, 415, 816, 1217] };
function slotZRangeFor(ci, li) {
  const col = base.columnSummaries[ci];
  const legFromZ = col.legFromZ, legToZ = col.legToZ;
  const railZFrom = legFromZ + T;
  // N is always 1 for this vehicle's columns (verified: base.columnSummaries N)
  const positions = CONNECTOR_POS[col.N];
  return { zFrom: railZFrom + positions[0], zTo: railZFrom + positions[1] };
}
// railYCenter (world) for each slot = original box's rail center; recover it
// from the ORIGINAL box placement using the same inverse formula used by the
// builder: targetYbottom = railYCenter + T/2 = originalBoxBottomWorldY + 12
// (12mm eurobox foot, per builder code) => railYCenter = origBottomY + 12 - T/2.
function railYCenterFor(ci, li, origPart) {
  const m = parseGlbMesh(EUROBOX_GLB[slotOriginal[`${ci}-${li}`].origH]);
  m.position.set(...origPart.position); m.quaternion.set(...origPart.quaternion); m.scale.set(1,1,1); m.updateMatrixWorld(true);
  const b = new THREE.Box3().setFromObject(m);
  return (b.min.y + 12) - T / 2;
}

function buildVariant(heightsBySlot) {
  // heightsBySlot: { "0-0": 270, "0-1": 220, "0-2": 170, "1-0": 220 }
  const probeCache = {};
  function probeFor(h) {
    if (probeCache[h]) return probeCache[h];
    const m = parseGlbMesh(EUROBOX_GLB[h]); m.position.set(0,0,0); m.quaternion.set(...Q_ALONG_Z); m.scale.set(1,1,1); m.updateMatrixWorld(true);
    const b = new THREE.Box3().setFromObject(m);
    return (probeCache[h] = { box: b, center: [(b.min.x+b.max.x)/2,(b.min.y+b.max.y)/2,(b.min.z+b.max.z)/2] });
  }
  const targetXcenter = offsetX - D / 2;
  const newBoxes = [];
  for (const key of Object.keys(slotOriginal)) {
    const [ci, li] = key.split("-").map(Number);
    const origPart = baseBoxes.find(p => roleKey(p.role) === key);
    const railYCenter = railYCenterFor(ci, li, origPart);
    const { zFrom, zTo } = slotZRangeFor(ci, li);
    const H = heightsBySlot[key];
    if (H > slotOriginal[key].origH) throw new Error(`slot ${key}: requested height ${H} exceeds verified original ${slotOriginal[key].origH}`);
    const probe = probeFor(H);
    const targetZcenter = (zFrom + zTo) / 2;
    const targetYbottom = railYCenter + T / 2;
    newBoxes.push({
      part_id: EUROBOX_PID[H],
      position: [targetXcenter - probe.center[0], targetYbottom - probe.box.min.y - 12, targetZcenter - probe.center[2]],
      quaternion: [...Q_ALONG_Z], scale: [1,1,1], role: `eurobox-col${ci}-p${li}`,
    });
  }
  // verify: each box vs walls
  function meshOf(p) {
    const m = parseGlbMesh(EUROBOX_GLB[Object.keys(EUROBOX_PID).find(h => EUROBOX_PID[h] === p.part_id)]);
    m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale); m.updateMatrixWorld(true); return m;
  }
  for (const p of newBoxes) {
    const grp = new THREE.Group(); grp.add(meshOf(p)); grp.updateMatrixWorld(true);
    if (collidesWithWalls(grp)) return { ok: false, reason: "eurobox-collision:" + p.role };
  }
  // self-collision vs structural parts (nesting with Object_7/product_3071 expected via T-style side contact isn't relevant here; only box-vs-box overlap matters)
  const boxMeshes = newBoxes.map(meshOf);
  for (let i = 0; i < boxMeshes.length; i++) for (let j = i+1; j < boxMeshes.length; j++) {
    const A = new THREE.Box3().setFromObject(boxMeshes[i]), B = new THREE.Box3().setFromObject(boxMeshes[j]);
    const ox = Math.min(A.max.x,B.max.x)-Math.max(A.min.x,B.min.x), oy = Math.min(A.max.y,B.max.y)-Math.max(A.min.y,B.min.y), oz = Math.min(A.max.z,B.max.z)-Math.max(A.min.z,B.min.z);
    if (ox>0.5 && oy>0.5 && oz>0.5) return { ok: false, reason: `box-self-collision(${i},${j})` };
  }
  const allParts = [...structuralParts, ...newBoxes];
  return { ok: true, allParts, heightsBySlot, totalBoxes: newBoxes.length, distinctHeights: [...new Set(Object.values(heightsBySlot))] };
}

const VARIANTS = {
  B: { "0-0": 270, "0-1": 220, "0-2": 120, "1-0": 170 },
  C: { "0-0": 220, "0-1": 170, "0-2": 120, "1-0": 120 },
  D: { "0-0": 220, "0-1": 170, "0-2": 120, "1-0": 220 },
  E: { "0-0": 220, "0-1": 170, "0-2": 120, "1-0": 170 },
};

const results = {};
for (const [name, hm] of Object.entries(VARIANTS)) {
  const r = buildVariant(hm);
  results[name] = r.ok ? { ok: true, heightsBySlot: r.heightsBySlot, totalBoxes: r.totalBoxes, distinctHeights: r.distinctHeights } : r;
  if (r.ok) fs.writeFileSync(`/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/bot24_VW31_variant_${name}.json`, JSON.stringify(r, null, 1));
}
console.log(JSON.stringify(results, null, 1));
