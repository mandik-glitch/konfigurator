// Diagnostika: skutecna mezera (SAT, mesh-presna) mezi konkretni nohou a realnou
// karoserii, krokovana v Z, aby se overilo KTERA noha je "u prepazky" tam, kde
// vertex-vzorkovani steny (localWallZRange) dava podezrele velkou hodnotu.
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");

const [, , dataPath, carBodyBase, legZstr] = process.argv;
const legZ = Number(legZstr);
const raw = JSON.parse(fs.readFileSync(dataPath, "utf8"));
const parts = raw.parts.filter(p => !String(p.part_id || "").startsWith("car_body_") && !String(p.role || "").startsWith("kontrolni-pomucka"));
const legParts = parts.filter(p => Math.abs(p.position[2] - legZ) < 5);
console.log("dilu na teto noze:", legParts.length, legParts.map(p => p.role));

const KAT = "/opt/konfigurator/webapp/katalog/";
function loadWall(suf) {
  const m = parseGlbMesh(KAT + "car_bodies/" + carBodyBase + suf + ".glb");
  m.material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  m.updateMatrixWorld(true);
  m.geometry.computeBoundsTree();
  return m;
}
const walls = [loadWall("_L"), loadWall("_R_D"), loadWall("_B")];
const raycaster = new THREE.Raycaster();
function edges(mesh, maxEdges) {
  const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
  const out = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (let t = 0; t < triCount; t += step) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); } else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    out.push([vA.clone(), vB.clone()], [vB.clone(), vC.clone()], [vC.clone(), vA.clone()]);
  }
  return out;
}
function collides(mesh) {
  for (const [p0, p1] of edges(mesh, 400)) {
    const dir = p1.clone().sub(p0), dist = dir.length();
    if (dist < 1e-6) continue;
    dir.normalize();
    raycaster.set(p0, dir); raycaster.far = dist;
    if (raycaster.intersectObjects(walls, false).length) return true;
  }
  return false;
}

function buildMeshes(shiftZ) {
  return legParts.map(p => {
    const glbPath = R.glbPath(p.part_id);
    if (!glbPath) return null;
    const m = parseGlbMesh(glbPath);
    m.position.set(p.position[0], p.position[1], p.position[2] + shiftZ);
    m.quaternion.set(...p.quaternion);
    m.scale.set(...p.scale);
    m.updateMatrixWorld(true);
    return { p, m };
  }).filter(Boolean);
}

const SHIFTS = process.argv[6] ? process.argv[6].split(",").map(Number) : [0, -2, -5, -10, -20, -30, -50, -80, -120, -160, -200, -210, -220];
for (const shift of SHIFTS) {
  const meshes = buildMeshes(shift);
  const hit = meshes.some(({ m }) => collides(m));
  console.log(`shift=${shift}mm  koliduje=${hit}`);
}
