// Kolizni modul pro karoserii Opel/Vauxhall/Renault/Citroen Vivaro OP18
// 2019- (car_bodies id=642 L / 643 R_D / 644 B). Kopie produkcni kolizni
// logiky z tmp_2026-08-31_place_ci25.js, presmerovano na Vivaro GLB.
// DULEZITE ROZDIL OD CI25/CI24/MOVANO: Vivaro GLB soubory byly TETO session
// (bot16, 2026-08-31) FYZICKY OTOCENY o 180 stupnu kolem Y (viz audit
// scripts/2026-08-31_car_body_orientation_audit_results.jsonl - Vivaro OP18
// vysel B_midZ=+2643 = NEEDS_FLIP, presne jako CI14 pred svym flipem).
// Po flipu: stena L je na ZAPORNE strane X (X in [-807,0]), prepazka B je
// na VELKE ZAPORNE strane Z (Z in [-2912,-2375]), otevreny konec je na
// MALE KLADNE Z (~+147) - stejny vzor jako opravena CI14.
const THREE = require("three");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = MeshBVHLib.disposeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const CARB = KAT + "car_bodies/";

const wallL = parseGlbMesh(CARB + "Opel_Vivaro_OP18_2019-_L.glb");
const wallR = parseGlbMesh(CARB + "Opel_Vivaro_OP18_2019-_R_D.glb");
const wallB = parseGlbMesh(CARB + "Opel_Vivaro_OP18_2019-_B.glb");
const wallMeshes = [wallL, wallR, wallB];
wallMeshes.forEach(m => m.updateMatrixWorld(true));

const boxL0 = new THREE.Box3().setFromObject(wallL);
const boxR0 = new THREE.Box3().setFromObject(wallR);
const boxB0 = new THREE.Box3().setFromObject(wallB);

wallMeshes.forEach(m => m.geometry.computeBoundsTree());

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
const raycaster = new THREE.Raycaster();
raycaster.firstHitOnly = true;
function collidesWithWalls(object3d) {
  object3d.updateMatrixWorld(true);
  let hit = false;
  object3d.traverse(n => {
    if (hit || !n.isMesh) return;
    const edges = meshWorldEdgeSample(n, COLLISION_MAX_EDGES_PER_PART);
    for (const [p0, p1] of edges) {
      const dir = p1.clone().sub(p0);
      const dist = dir.length();
      if (dist < 1e-6) continue;
      dir.normalize();
      raycaster.set(p0, dir);
      raycaster.far = dist;
      if (raycaster.intersectObjects(wallMeshes, false).length) { hit = true; break; }
    }
  });
  return hit;
}

const OBJECT11_PATH = KAT + "Object_11.glb";
const OBJECT7_PATH = KAT + "Object_7.glb";
function partGlbPath(partId) {
  if (partId === "Object_7") return OBJECT7_PATH;
  return OBJECT11_PATH;
}
function buildLegObject(customShapeParts) {
  const group = new THREE.Group();
  for (const p of customShapeParts) {
    const mesh = parseGlbMesh(partGlbPath(p.part_id));
    mesh.position.set(p.position[0], p.position[1], p.position[2]);
    mesh.quaternion.set(p.quaternion[0], p.quaternion[1], p.quaternion[2], p.quaternion[3]);
    mesh.scale.set(p.scale[0], p.scale[1], p.scale[2]);
    group.add(mesh);
  }
  group.updateMatrixWorld(true);
  return group;
}

function boxOf(obj) { obj.updateMatrixWorld(true); return new THREE.Box3().setFromObject(obj); }

module.exports = {
  wallL, wallR, wallB, wallMeshes, collidesWithWalls, meshWorldEdgeSample,
  buildLegObject, boxOf, parseGlbMesh, KAT,
  boxL0, boxR0, boxB0,
};

if (require.main === module) {
  console.log("L", boxL0.min, boxL0.max);
  console.log("R_D", boxR0.min, boxR0.max);
  console.log("B", boxB0.min, boxB0.max);
}
