const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const KAT = "/opt/konfigurator/webapp/katalog/";
function loadWall(suf) {
  const m = parseGlbMesh(KAT + "car_bodies/Fiat_Doblo_FI14_2010-2022" + suf + ".glb");
  m.material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  m.updateMatrixWorld(true);
  m.geometry.computeBoundsTree();
  return m;
}
const wallL = loadWall("_L");

const panel = parseGlbMesh(KAT + "kontrolni_pomucky/K075_oblozeni_bok-levy.glb");
const geo = panel.geometry;
const pos = geo.attributes.position;
const n = pos.count;
const step = Math.max(1, Math.floor(n / 60));
const raycaster = new THREE.Raycaster();
raycaster.firstHitOnly = true;

let distances = [];
for (let i = 0; i < n; i += step) {
  const p = new THREE.Vector3(pos.getX(i), pos.getY(i), pos.getZ(i));
  let best = null;
  for (const dir of [new THREE.Vector3(1,0,0), new THREE.Vector3(-1,0,0)]) {
    raycaster.set(p, dir);
    raycaster.far = 50;
    const hits = raycaster.intersectObject(wallL, false);
    if (hits.length && (best === null || hits[0].distance < best)) best = hits[0].distance;
  }
  if (best !== null) distances.push(best);
}
distances.sort((a,b)=>a-b);
console.log("vzorku:", distances.length);
console.log("min:", distances[0]?.toFixed(2), "max:", distances[distances.length-1]?.toFixed(2), "median:", distances[Math.floor(distances.length/2)]?.toFixed(2));
console.log("prvnich 10:", distances.slice(0,10).map(d=>d.toFixed(2)));
console.log("poslednich 10:", distances.slice(-10).map(d=>d.toFixed(2)));
