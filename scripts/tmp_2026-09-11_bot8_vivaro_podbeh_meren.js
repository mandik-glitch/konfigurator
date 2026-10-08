// Overeni Vivaro (7 sestav, 2 unikatni karoserie) - koliduje "sloupek-pred-
// podbehem" (WALL_CLEARANCE_ARCH=124mm) skutecne se skutecnym podbehem?
// Zadani bot3 2026-09-11: ZMERIT, ne opravit. Kolizni krokovani (stejna
// metoda jako runOne()/batch_pipeline.js - hranovy raycasting proti REALNE
// GLB geometrii karoserie), ne Box3 - hloubka se zjisti postupnym
// posouvanim pryc od steny, dokud kolize nezmizi.
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const KAT = "/opt/konfigurator/webapp/katalog/";
const COLLISION_MAX_EDGES = 600; // vic nez obvykle (300) - tenky 30x30 profil, chceme jistotu

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
function collides(mesh, wallMeshes) {
  const edges = meshWorldEdgeSample(mesh, COLLISION_MAX_EDGES);
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

const wallCache = {};
function wallsFor(base) {
  if (wallCache[base]) return wallCache[base];
  const wallL = parseGlbMesh(KAT + base + "_L.glb");
  const wallR = parseGlbMesh(KAT + base + "_R_D.glb");
  const wallB = parseGlbMesh(KAT + base + "_B.glb");
  const meshes = [wallL, wallR, wallB];
  meshes.forEach(m => { m.updateMatrixWorld(true); m.geometry.computeBoundsTree(); });
  return (wallCache[base] = meshes);
}

function sloupekMesh(p, xOverride) {
  const m = parseGlbMesh(KAT + "Object_7.glb");
  const pos = xOverride != null ? [xOverride, p.position[1], p.position[2]] : p.position;
  m.position.set(...pos);
  m.quaternion.set(...p.quaternion);
  m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

const cases = [
  { base: "car_bodies/Opel_Vivaro_OP18_2019-", assemblies: [57, 259, 329],
    sloupky: [
      { position: [-612, 108.5, -1096], quaternion: [0, 0, 0, 1], scale: [1, 0.213, 1] },
      { position: [-612, 71.5, -234], quaternion: [0, 0, 0, 1], scale: [1, 0.139, 1] },
    ] },
  { base: "car_bodies/Opel_Vivaro_OP31_2020-", assemblies: [136, 157, 158, 179],
    sloupky: [
      { position: [-611, 158.492431640625, -395.98352813720703], quaternion: [0, 0, 0, 1], scale: [1, 0.313, 1] },
    ] },
];

// past c.7 (skill 3d-scena-spoje): hranovy raycast NEVIDI dil CELY vnoreny
// do vetsiho bez protnuti povrchu hranou. Staticky test v puvodni pozici by
// tomuhle mohl podlehnout (presne "falesne uklidneni", pred kterym bot3
// varoval). Reseni: NEtestovat jen v klidove pozici, ale ZAMEST od bezpecne
// (jiste volne) pozice X=-50 (stred vozu) SMEREM KE STENE - behem prejezdu
// MUSI hrana sondy protnout povrch pri prechodu zvenku dovnitr, i kdyby
// staticky test v koncove pozici byl slepy. Prvni X, kde se objevi kolize,
// je skutecna hranice povrchu karoserie na tehle Y/Z pozici.
function sweepFindFirstCollisionX(p, walls, xStart, xTarget) {
  const dir = xTarget > xStart ? 1 : -1;
  let x = xStart;
  let steps = 0;
  const maxSteps = Math.abs(xTarget - xStart) + 50;
  while (steps < maxSteps) {
    if (collides(sloupekMesh(p, x), walls)) return x;
    x += dir; steps++;
  }
  return null; // zadna kolize nalezena po cele draze
}

for (const c of cases) {
  console.log(`\n=== ${c.base} (sestavy ${c.assemblies.join(",")}) ===`);
  const walls = wallsFor(c.base);
  c.sloupky.forEach((p, i) => {
    const xBuilt = p.position[0];
    const hitStatic = collides(sloupekMesh(p), walls);
    const firstHitX = sweepFindFirstCollisionX(p, walls, -50, xBuilt - 30);
    console.log(`  sloupek[${i}] Z=${p.position[2]} X_postaveno=${xBuilt} (124mm od steny):`);
    console.log(`    staticky test v klidove pozici: koliduje=${hitStatic}`);
    if (firstHitX === null) {
      console.log(`    zamet od X=-50 smerem ke stene: ZADNA kolize nalezena az do X=${xBuilt - 30} - podbeh tam neni / sonda ho nezachytila ani zametem`);
    } else {
      const hloubka = firstHitX - xBuilt; // kladne = postavena pozice je JESTE PRED prvni kolizi (bezpecne), zaporne = postavena pozice je ZA prvni kolizi (uvnitr)
      console.log(`    zamet od X=-50: prvni kolize pri X=${firstHitX} (t.j. ${Math.abs(xBuilt - firstHitX).toFixed(0)}mm od postavene pozice ${xBuilt > firstHitX ? "DAL od steny (bezpecne)" : "BLIZ ke stene/UVNITR (kolize)"})`);
      if (xBuilt <= firstHitX) {
        console.log(`    !!! POSTAVENA POZICE JE V KOLIZI (nebo presne na hranici) - hloubka zanoreni cca ${(firstHitX - xBuilt).toFixed(0)}mm`);
      } else {
        console.log(`    OK - postavena pozice je ${(xBuilt - firstHitX).toFixed(0)}mm PRED prvni kolizi, bezpecna rezerva`);
      }
    }
  });
}
