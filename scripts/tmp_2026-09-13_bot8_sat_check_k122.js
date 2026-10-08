const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const KAT = "/opt/konfigurator/webapp/katalog/car_bodies/";
function loadWall(base, suf) {
  const m = parseGlbMesh(KAT + base + suf + ".glb");
  m.material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  m.updateMatrixWorld(true);
  m.geometry.computeBoundsTree();
  return m;
}
const raycaster = new THREE.Raycaster();
raycaster.firstHitOnly = true;
function meshWorldEdgeSample(mesh, maxEdges) {
  const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
  const edges = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (let t = 0; t < triCount; t += step) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t*3); ib = idx.getX(t*3+1); ic = idx.getX(t*3+2); } else { ia=t*3; ib=t*3+1; ic=t*3+2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    edges.push([vA.clone(),vB.clone()],[vB.clone(),vC.clone()],[vC.clone(),vA.clone()]);
  }
  return edges;
}
function collidesWithWallsReal(mesh, walls) {
  const edges = meshWorldEdgeSample(mesh, 200);
  for (const [p0,p1] of edges) {
    const dir = p1.clone().sub(p0), dist = dir.length();
    if (dist < 1e-6) continue;
    dir.normalize();
    raycaster.set(p0, dir); raycaster.far = dist;
    if (raycaster.intersectObjects(walls, false).length) return true;
  }
  return false;
}
function partMesh(p) {
  const gp = R.glbPath(p.part_id);
  if (!gp) return null;
  const m = parseGlbMesh(gp);
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

const BASE = "Citroën_Jumpy_CI14_2016-"; // K-118/K-122 - over presne v datech pred pouzitim naostro
const walls = [loadWall(BASE,"_L"), loadWall(BASE,"_R_D"), loadWall(BASE,"_B")];

const IDS = process.argv.slice(2).map(Number);
for (const aid of IDS) {
  const data = JSON.parse(fs.readFileSync(`/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/rebuilt_${aid}.json`, "utf8"));
  const uhelniky = data.parts.filter(p => String(p.role||"").startsWith("uhelnik-"));
  let coll = 0;
  for (const p of uhelniky) {
    const m = partMesh(p);
    if (m && collidesWithWallsReal(m, walls)) coll++;
  }
  console.log(`id=${aid}: ${coll}/${uhelniky.length} novych uhelniku koliduje s realnou karoserii`);
}
