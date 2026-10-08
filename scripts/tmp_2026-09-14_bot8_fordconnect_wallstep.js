// Ford Connect K-237 (FO12) / K-239 (FO13) - regal je daleko od steny,
// chybi kolizni krokovani ke stene (car_body_placement_methods.id=1
// "kolizni-krokovani", krok 4). Zjisti, na ktere strane (L/R_D) regal
// skutecne stoji, zmer realnou vzdalenost ke skutecne GLB stene
// raycastingem, krokuj 1mm/2mm-zpet, spocitej JEDNOTNY X-posun pro
// CELOU sestavu (viz "prohnuti_steny_nemeni_relativni_pozici_noh" -
// nejprisnejsi/nejkratsi limit pro celou skupinu noh, ne kazda zvlast).
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const D = JSON.parse(fs.readFileSync(`${SCRATCH}/fordconnect_reps.json`, "utf8"));
const KAT = "/opt/konfigurator/webapp/katalog/";

const CARS = {
  128: "Ford_Connect_FO12_2014-",
  129: "Ford_Connect_FO13_2014-",
};

function loadWall(base, side) {
  const mesh = parseGlbMesh(`${KAT}car_bodies/${base}_${side}.glb`);
  mesh.updateMatrixWorld(true);
  mesh.traverse(n => { if (n.isMesh && n.geometry && !n.geometry.boundsTree) n.geometry.computeBoundsTree(); });
  return mesh;
}
function worldBox(p) {
  const glb = R.glbPath(p.part_id); if (!glb) return null;
  const mesh = parseGlbMesh(glb);
  mesh.position.set(...p.position); mesh.quaternion.set(...p.quaternion); mesh.scale.set(...p.scale);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}

for (const [idStr, info] of Object.entries(D)) {
  const id = Number(idStr);
  const base = CARS[id];
  const parts = info.parts.filter(p => !R.jeKaroserie(p.part_id));
  const rackBox = parts.reduce((acc, p) => acc ? acc.union(worldBox(p)) : worldBox(p), null);
  console.log(`\n=== id=${id} ${info.name.slice(0,40)} (${base}) ===`);
  console.log("rack X range:", rackBox.min.x.toFixed(1), rackBox.max.x.toFixed(1));

  const wallL = loadWall(base, "L");
  const wallR = loadWall(base, "R_D");
  const boxL = new THREE.Box3().setFromObject(wallL);
  const boxR = new THREE.Box3().setFromObject(wallR);
  console.log("wallL X range:", boxL.min.x.toFixed(1), boxL.max.x.toFixed(1));
  console.log("wallR X range:", boxR.min.x.toFixed(1), boxR.max.x.toFixed(1));

  // OPRAVA: L a R_D sdileji stejnou blizsi hranu (X=0, osa vozu) - "ktera
  // hranice je bliz" je nerozhodne (obe stejne blizko) a driv to spatne
  // vybralo R_D i pro rack lezici cely v zaporne polovine. Spravne
  // kriterium: na ktere STRANE OSY (znamenko X) rack skutecne lezi - to
  // URCUJE, ktera stena je ta jeho vlastni (L=zaporna cast, R_D=kladna).
  const rackCx = (rackBox.min.x + rackBox.max.x) / 2;
  const naZaporne = rackCx < 0;
  const wall = naZaporne ? wallL : wallR;
  const wallSide = naZaporne ? "L" : "R_D";
  const wallBox = naZaporne ? boxL : boxR;
  console.log("regal stoji proti stene:", wallSide, " (rack stred X=", rackCx.toFixed(1), ")");

  // smer ke stene: kladny, pokud stena je na X > rack, zaporny jinak
  const dirSign = (wallBox.min.x + wallBox.max.x) / 2 > rackCx ? 1 : -1;
  console.log("smer krokovani (dirSign):", dirSign);

  // Kolizni test: pro KAZDOU noh-hranu (predni-svislice/cap/zadni-svislice*)
  // krokuj 1mm smerem dirSign, dokud jeji REALNY box3 nezacne prekryvat
  // stenu (raycast presnejsi, ale pro rychlost pouzijeme Box3 vs Box3 s
  // BVH raycast potvrzenim na finalni hodnote).
  const raycaster = new THREE.Raycaster();
  raycaster.firstHitOnly = true;
  raycaster.far = 2000;
  function hitsWall(x0, y, z, dir) {
    raycaster.set(new THREE.Vector3(x0, y, z), new THREE.Vector3(dir, 0, 0));
    raycaster.far = 2000;
    const hits = raycaster.intersectObject(wall, true);
    return hits.length ? hits[0].distance : Infinity;
  }

  const legs = info.parts.filter(p => ["predni-svislice", "cap", "zadni-svislice-dolni", "zadni-svislice-nad-zarezem"].includes(p.role));
  let minDist = Infinity, limitingLeg = null;
  for (const leg of legs) {
    const d = hitsWall(leg.position[0], leg.position[1], leg.position[2], dirSign);
    if (d < minDist) { minDist = d; limitingLeg = leg; }
  }
  console.log("nejkratsi realna vzdalenost k realne stene (raycast od stredu nohy):", minDist.toFixed(2), "mm  (noha:", limitingLeg.role, "Z=", limitingLeg.position[2], ")");

  // Bezpecny posun = (vzdalenost - 2mm rezerva), ale odecist i polovinu
  // sirky profilu (30mm/2=15mm), protoze raycast je od STREDU nohy, ne od
  // jejiho vnejsiho povrchu smerem ke stene.
  const T2 = 15; // polovina 30mm profilu
  const shift = minDist - T2 - 2;
  console.log("POSUN CELEHO REGALU (smer", dirSign, "):", (dirSign*shift).toFixed(2), "mm v X");

  info._wallSide = wallSide;
  info._shiftX = dirSign * shift;
}

fs.writeFileSync(`${SCRATCH}/fordconnect_wallstep_result.json`, JSON.stringify(D));
