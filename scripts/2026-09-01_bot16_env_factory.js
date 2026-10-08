// Generalizovana kolizni "prostredi" tovarna - parametrizovano prefixem
// karoserie (L/R_D/B .glb), pro Caddy/Ford Connect/Doblo batch (bot16 2026-09-01).
// Vzor: tmp_2026-08-31_place_movano.js / tmp_2026-08-31_place_vivaro.js.
const THREE = require("three");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = MeshBVHLib.disposeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const CARB = KAT + "car_bodies/";
const OBJECT7_PATH = KAT + "Object_7.glb";

function makeEnv(bodyPrefix) {
  const wallL = parseGlbMesh(CARB + bodyPrefix + "_L.glb");
  const wallR = parseGlbMesh(CARB + bodyPrefix + "_R_D.glb");
  const wallB = parseGlbMesh(CARB + bodyPrefix + "_B.glb");
  const wallMeshes = [wallL, wallR, wallB];
  wallMeshes.forEach(m => m.updateMatrixWorld(true));
  const boxL0 = new THREE.Box3().setFromObject(wallL);
  const boxR0 = new THREE.Box3().setFromObject(wallR);
  const boxB0 = new THREE.Box3().setFromObject(wallB);
  wallMeshes.forEach(m => m.geometry.computeBoundsTree());

  const MAX_EDGES = 300;
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
      const edges = meshWorldEdgeSample(n, MAX_EDGES);
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
  function buildLegObject(customShapeParts) {
    const group = new THREE.Group();
    for (const p of customShapeParts) {
      const mesh = parseGlbMesh(OBJECT7_PATH);
      mesh.position.set(p.position[0], p.position[1], p.position[2]);
      mesh.quaternion.set(p.quaternion[0], p.quaternion[1], p.quaternion[2], p.quaternion[3]);
      mesh.scale.set(p.scale[0], p.scale[1], p.scale[2]);
      group.add(mesh);
    }
    group.updateMatrixWorld(true);
    return group;
  }
  return { wallL, wallR, wallB, wallMeshes, collidesWithWalls, buildLegObject, boxL0, boxR0, boxB0 };
}

module.exports = { makeEnv, KAT, CARB, OBJECT7_PATH };
