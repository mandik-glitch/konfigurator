// Nezavisle overeni "zanoreni" u fronty Proace/e-Expert (bot3 zadal,
// bot9ovo hlaseni je jen podnet, ne diagnoza - mereno tu od nuly).
const THREE = require("three");
const path = require("path");
const fs = require("fs");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = MeshBVHLib.disposeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const COLLISION_MAX_EDGES_PER_PART = 300;

function meshWorldEdgeSample(mesh, maxEdges) {
  const geo = mesh.geometry;
  const pos = geo && geo.attributes && geo.attributes.position;
  if (!pos) return [];
  const idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
  const edges = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (let t = 0; t < triCount; t += step) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); }
    else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    edges.push([vA.clone(), vB.clone()], [vB.clone(), vC.clone()], [vC.clone(), vA.clone()]);
  }
  return edges;
}

const wallCache = {};
function wallsFor(basePath) {
  if (wallCache[basePath]) return wallCache[basePath];
  const wallL = parseGlbMesh(KAT + basePath + "_L.glb");
  const wallR = parseGlbMesh(KAT + basePath + "_R_D.glb");
  const wallB = parseGlbMesh(KAT + basePath + "_B.glb");
  const wallMeshes = [wallL, wallR, wallB];
  wallMeshes.forEach(m => m.updateMatrixWorld(true));
  wallMeshes.forEach(m => m.geometry.computeBoundsTree());
  wallCache[basePath] = wallMeshes;
  return wallMeshes;
}

function partMesh(p) {
  const mesh = parseGlbMesh(KAT + p.glb);
  mesh.position.set(p.position[0], p.position[1], p.position[2]);
  mesh.quaternion.set(p.quaternion[0], p.quaternion[1], p.quaternion[2], p.quaternion[3]);
  mesh.scale.set(p.scale[0], p.scale[1], p.scale[2]);
  mesh.updateMatrixWorld(true);
  return mesh;
}

const raycaster = new THREE.Raycaster();
raycaster.firstHitOnly = true;
function collidesWithWalls(mesh, wallMeshes) {
  const edges = meshWorldEdgeSample(mesh, COLLISION_MAX_EDGES_PER_PART);
  for (const [p0, p1] of edges) {
    const dir = p1.clone().sub(p0);
    const dist = dir.length();
    if (dist < 1e-6) continue;
    dir.normalize();
    raycaster.set(p0, dir);
    raycaster.far = dist;
    if (raycaster.intersectObjects(wallMeshes, false).length) return true;
  }
  return false;
}

const data = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const results = [];
for (const a of data) {
  if (!a.car_body_base) {
    results.push({ id: a.id, name: a.name, chyba: "vice/zadna karoserie" });
    continue;
  }
  let walls;
  try {
    walls = wallsFor(a.car_body_base);
  } catch (e) {
    results.push({ id: a.id, name: a.name, chyba: `sablona karoserie ${a.car_body_base}: ${e.message}` });
    continue;
  }
  // past c.7 (skill 3d-scena-spoje): hranovy raycast NEVIDI dil CELY
  // vnoreny do vetsiho obstacle, aniz by jeho hrana protla povrch -
  // karoserie je velka obalka, takze tohle riziko je tu realne. Doplnkova
  // Box3 kontrola (vsechny 3 osy, ne jen dotyk) jako druhy, nezavisly
  // signal - muze mit vlastni false positivy (pootoceny dil, past c.8
  // stohovaci geometrie), je to tedy DUVOD K BLIZSIMU OHLEDANI, ne
  // finalni verdikt.
  const wallBox = new THREE.Box3();
  for (const w of walls) wallBox.union(new THREE.Box3().setFromObject(w));

  const koliduje = [];
  const box3flag = [];
  for (const p of a.parts) {
    const mesh = partMesh(p);
    if (collidesWithWalls(mesh, walls)) {
      koliduje.push({ role: p.role, part_id: p.part_id, position: p.position });
    }
    const pb = new THREE.Box3().setFromObject(mesh);
    const ox = Math.min(pb.max.x, wallBox.max.x) - Math.max(pb.min.x, wallBox.min.x);
    const oy = Math.min(pb.max.y, wallBox.max.y) - Math.max(pb.min.y, wallBox.min.y);
    const oz = Math.min(pb.max.z, wallBox.max.z) - Math.max(pb.min.z, wallBox.min.z);
    const TOL = 3; // mm - nad dosed/touch pasmo
    if (ox > TOL && oy > TOL && oz > TOL) {
      box3flag.push({ role: p.role, part_id: p.part_id, position: p.position, overlap_mm: [Math.round(ox), Math.round(oy), Math.round(oz)] });
    }
  }
  results.push({ id: a.id, name: a.name, car_body_base: a.car_body_base, pocet_dilu: a.parts.length, koliduje_pocet: koliduje.length, koliduje });
}

const shrnuti = results.filter(r => r.koliduje_pocet > 0);
console.log(`Zkontrolovano ${results.length} sestav, ${shrnuti.length} ma alespon jeden kolidujici dil (hranovy raycast).`);
for (const r of shrnuti) {
  console.log(`#${r.id} ${r.name} [${r.car_body_base}]: ${r.koliduje_pocet}/${r.pocet_dilu} dilu koliduje`);
  const roleCounts = {};
  for (const k of r.koliduje) roleCounts[k.role] = (roleCounts[k.role] || 0) + 1;
  for (const [role, n] of Object.entries(roleCounts)) console.log(`    role=${role} x${n}`);
}
fs.writeFileSync("/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/kolize_vysledky.json",
  JSON.stringify(results, null, 1));
console.log("Plny vysledek: scratchpad/kolize_vysledky.json");
