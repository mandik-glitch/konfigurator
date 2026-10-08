// Class 4 audit: front leg (or any leg) standing inside the real sliding-door
// opening of the _R_D wall mesh. Detection method established 2026-09-02
// (car_body_placement_methods.id=1, key vylouceni_bocniho_dvernich_otvoru):
// gap >150mm between Z-sorted vertices in Y in [200,900] band of the _R_D.glb
// = a real hole in the wall (door opening), not just free space.
//
// For every is_public=1 row: load its car body's _R_D wall, find door gap(s),
// then check whether ANY leg part (Object_7 parts NOT tagged with a
// sloupecN/colN column role - i.e. predni-svislice/zadni-svislice*/cap/
// sloupek-pred-podbehem/pricka-uzavreni-vyrezu) has a Z-extent overlapping
// the gap.
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";
const KAT = "/opt/konfigurator/webapp/katalog/";

const rowsList = fs.readFileSync(`${SCRATCH}/all_public_rows.tsv`, "utf8").trim().split("\n")
  .map(l => { const [id, ...rest] = l.split("\t"); return { id: Number(id), name: rest.join("\t") }; });
const carBodies = {};
fs.readFileSync(`${SCRATCH}/car_bodies.tsv`, "utf8").trim().split("\n").forEach(l => {
  const [id, name, glb] = l.split("\t");
  carBodies[Number(id)] = { name, glb };
});
function baseForCarBodyId(id) {
  const rec = carBodies[id];
  if (!rec) return null;
  let f = rec.glb.replace(/^car_bodies\//, "");
  return f.replace(/_B_wall\.glb$/, "").replace(/_B\.glb$/, "").replace(/_R_D\.glb$/, "").replace(/_L\.glb$/, "");
}

function detectDoorGaps(wallMesh) {
  const pos = wallMesh.geometry.attributes.position.array;
  const zs = [];
  for (let i = 0; i < pos.length; i += 3) {
    const y = pos[i + 1], z = pos[i + 2];
    if (y >= 200 && y <= 900) zs.push(z);
  }
  zs.sort((a, b) => a - b);
  const zMinAll = zs[0], zMaxAll = zs[zs.length - 1];
  const gaps = [];
  for (let i = 1; i < zs.length; i++) {
    const g = zs[i] - zs[i - 1];
    if (g > 150) gaps.push({ near: zs[i - 1], far: zs[i], gap: g });
  }
  // Reject gaps that are actually just the EDGE of the modeled mesh (open
  // cargo end / unmodeled cab area) rather than a real door cut FRAMED by
  // wall material on both sides - require at least 300mm of further
  // material beyond each side of the gap within the same Y band.
  const MARGIN = 300;
  return gaps.filter(g => (g.near - zMinAll) >= MARGIN && (zMaxAll - g.far) >= MARGIN);
}

function colTagOf(role) { return /sloupec\d+|col\d+/.test(role || ""); }
const LEG_ROLE_PREFIXES = ["predni-svislice", "zadni-svislice", "cap", "sloupek-pred-podbehem", "pricka-uzavreni-vyrezu"];
function isLegRole(role) {
  if (!role) return false;
  if (colTagOf(role)) return false; // column/rung/box parts, not legs
  return LEG_ROLE_PREFIXES.some(p => role.startsWith(p)) || role === "cap";
}

let object7Mesh = null;
function loadObject7() {
  if (!object7Mesh) object7Mesh = parseGlbMesh(KAT + "Object_7.glb");
  return object7Mesh;
}
const wallCache = {};
function getWallR(base) {
  if (wallCache[base] !== undefined) return wallCache[base];
  try {
    const m = parseGlbMesh(KAT + "car_bodies/" + base + "_R_D.glb");
    m.updateMatrixWorld(true);
    wallCache[base] = m;
  } catch (e) { wallCache[base] = null; }
  return wallCache[base];
}
const gapCache = {};
function getGaps(base) {
  if (gapCache[base]) return gapCache[base];
  const wall = getWallR(base);
  const gaps = wall ? detectDoorGaps(wall) : [];
  gapCache[base] = gaps;
  return gaps;
}

const report = [];
for (const row of rowsList) {
  let data;
  try { data = JSON.parse(fs.readFileSync(`${SCRATCH}/rows/${row.id}.json`, "utf8")); } catch (e) { report.push({ id: row.id, name: row.name, error: "no data" }); continue; }
  const parts = data.parts || [];
  const carBodyIds = [...new Set(parts.filter(p => p.part_id.startsWith("car_body_")).map(p => Number(p.part_id.slice("car_body_".length))))];
  if (!carBodyIds.length) { report.push({ id: row.id, name: row.name, error: "no car body" }); continue; }
  const base = baseForCarBodyId(carBodyIds[0]);
  const gaps = getGaps(base);
  if (!gaps.length) { report.push({ id: row.id, name: row.name, base, gaps: 0 }); continue; }

  const legParts = parts.filter(p => p.part_id === "Object_7" && isLegRole(p.role));
  const hits = [];
  for (const lp of legParts) {
    // REAL Z-extent via actual GLB geometry (position/quaternion/scale
    // applied), not an approximation - a vertical piece (identity
    // quaternion) has Z-extent = the 30mm profile cross-section regardless
    // of its scale.y (length), while a piece rotated to run along Z (cap,
    // pricka-uzavreni-vyrezu) has Z-extent = its real scaled length.
    const src = loadObject7();
    const mesh = src.clone(); mesh.geometry = src.geometry;
    mesh.position.set(lp.position[0], lp.position[1], lp.position[2]);
    mesh.quaternion.set(lp.quaternion[0], lp.quaternion[1], lp.quaternion[2], lp.quaternion[3]);
    mesh.scale.set(lp.scale[0], lp.scale[1], lp.scale[2]);
    mesh.updateMatrixWorld(true);
    const b3 = new THREE.Box3().setFromObject(mesh);
    for (const g of gaps) {
      if (b3.max.z > g.near && b3.min.z < g.far) { hits.push({ role: lp.role, zRange: [Math.round(b3.min.z), Math.round(b3.max.z)], gap: g }); break; }
    }
  }
  report.push({ id: row.id, name: row.name, base, gaps: gaps.length, gapDetail: gaps, hits });
  process.stderr.write(`done id=${row.id}\n`);
}
console.log(JSON.stringify(report, null, 1));
