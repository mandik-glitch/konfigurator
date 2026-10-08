// Generic collision module factory - same technique as
// scripts/tmp_2026-08-31_place_vivaro.js, parameterized by car body base path
// so it can be reused across many vehicle models without copy-pasting.
const THREE = require("three");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = MeshBVHLib.disposeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const OBJECT11_PATH = KAT + "Object_11.glb";
const OBJECT7_PATH = KAT + "Object_7.glb";
// OPRAVA 2026-09-04 (bot22): puvodni verze vracela pro VSECHNO krome
// "Object_7" soubor Object_11.glb (profil 40x40x1000 mm). Pro sestavy
// slozene jen z techhle dvou profilu to sedelo, ale eurobox regaly obsahuji
// i prislusenstvi - a zaslepka "product_3071" je deska 30x30x9 mm. Ta se do
// kolizniho testu nacetla jako METROVA TYC 40x40, takze "kolidovala" se
// stropem prakticky vsude. Zmereno na OP18/VW21/FO36/MB47: VSECHNY hlasene
// kolize hornich dilu nohy byly timhle zpusobene a se spravnou geometrii
// mizi. Nove se pouzije skutecny GLB dilu, kdyz existuje; Object_11 zustava
// jen jako fallback pro legacy custom_shapes dily bez vlastniho souboru
// (zpetne kompatibilni - Object_7 i Object_11 se resolvuji stejne jako driv).
const fs_ = require("fs");
const _glbPathCache = {};
function partGlbPath(partId) {
  if (partId === "Object_7") return OBJECT7_PATH;
  if (partId === "Object_11") return OBJECT11_PATH;
  if (!(partId in _glbPathCache)) {
    const own = KAT + partId + ".glb";
    _glbPathCache[partId] = fs_.existsSync(own) ? own : OBJECT11_PATH;
  }
  return _glbPathCache[partId];
}

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

function makeCollisionModule(basePath) {
  // basePath e.g. "/opt/.../car_bodies/Peugeot_Expert_PE12_2007-2015"
  const wallL = parseGlbMesh(basePath + "_L.glb");
  const wallR = parseGlbMesh(basePath + "_R_D.glb");
  const wallB = parseGlbMesh(basePath + "_B.glb");
  const wallMeshes = [wallL, wallR, wallB];
  wallMeshes.forEach(m => m.updateMatrixWorld(true));

  const boxL0 = new THREE.Box3().setFromObject(wallL);
  const boxR0 = new THREE.Box3().setFromObject(wallR);
  const boxB0 = new THREE.Box3().setFromObject(wallB);

  wallMeshes.forEach(m => m.geometry.computeBoundsTree());

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

  return { wallL, wallR, wallB, wallMeshes, collidesWithWalls, buildLegObject, boxOf, boxL0, boxR0, boxB0 };
}

module.exports = { makeCollisionModule, partGlbPath, KAT };
