const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const KAT = "/opt/konfigurator/webapp/katalog/car_bodies/";
const base = "Fiat_Doblo_FI14_2010-2022";
function loadWall(suf) {
  const m = parseGlbMesh(KAT + base + suf + ".glb");
  m.material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  m.updateMatrixWorld(true);
  m.geometry.computeBoundsTree();
  return m;
}
const wallL = loadWall("_L");
const wallB = loadWall("_B");

const data = JSON.parse(fs.readFileSync("/opt/konfigurator/backups/2026-09-12_oblozeni_K075_SERAZENE.json", "utf8"));
const dil = data.dily.find(d => d.nazev === "bok-levy");

const raycaster = new THREE.Raycaster();
raycaster.firstHitOnly = true;

function nearestHit(origin, dir, mesh, far) {
  raycaster.set(origin, dir.clone().normalize());
  raycaster.far = far || 3000;
  const hits = raycaster.intersectObject(mesh, false);
  return hits.length ? hits[0] : null;
}

console.log("Bod (panel, X posunuty od stredu ke stene = +X smer) | realny hit na _L (vzdalenost od bodu) | realny hit na _B");
const pts = dil.body.filter(p => -1620 <= p[2] && p[2] <= -1520);
for (const [x, y, z] of pts) {
  const origin = new THREE.Vector3(0, y, z); // stred vozu na tehle Y/Z, X=0
  const dir = new THREE.Vector3(x, 0, 0); // smerem k bodu panelu (a dal)
  const hitL = nearestHit(origin, dir, wallL, 2000);
  // taky zkusit smer primo od bodu panelu kolmo (+-X) k nejblizsi realne stene
  const originAtPoint = new THREE.Vector3(x, y, z);
  const hitFromPointPosX = nearestHit(originAtPoint, new THREE.Vector3(1, 0, 0), wallL, 500);
  const hitFromPointNegX = nearestHit(originAtPoint, new THREE.Vector3(-1, 0, 0), wallL, 500);
  const distL = hitL ? hitL.distance : null;
  const panelDist = Math.abs(x);
  console.log(
    `x=${x.toFixed(1)} y=${y.toFixed(1)} z=${z.toFixed(1)} | panel|x|=${panelDist.toFixed(1)} | realL@tehleY,Z odstredu=${distL ? distL.toFixed(1) : "NENALEZENO"} | delta=${distL ? (panelDist-distL).toFixed(1) : "?"} | hit+X=${hitFromPointPosX?hitFromPointPosX.distance.toFixed(1):"-"} hit-X=${hitFromPointNegX?hitFromPointNegX.distance.toFixed(1):"-"}`
  );
}
