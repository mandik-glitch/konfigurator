// Sdilena overovaci knihovna pro sirokou davku (shape_geometry_methods.id=11,
// krok 6/7), pouzita napric vsemi 14 modely / 44 sestavami zadanymi bot8
// 2026-09-12. a) SAT (hranovy raycasting) VSECH netransparentnich dilu proti
// REALNE GLB karoserii (_L/_R_D/_B) - ocekava se 0 kolizi. b) presna mezera
// (0.000mm) na kazdem zmenenem svaru (sloupek-pred-podbehem top vs
// zadni-svislice-nad-zarezem bottom) + kontrola "nevisi ve vzduchu" u
// nejnizsiho patra kazdeho dotceneho sloupce. c) self-kolize (Box3, vsechny
// pary ruzne role, preskoc zname vnorovaci prekryvy) - PROTI BASELINE
// (puvodni netransformovana data), aby se odlisily NOVE kolize od uz
// existujicich (nevznikly touhle upravou) prekryvu.
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");

const KAT = "/opt/konfigurator/webapp/katalog/";

function loadWalls(base) {
  function loadWall(suf) {
    const m = parseGlbMesh(KAT + "car_bodies/" + base + suf + ".glb");
    m.material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
    m.updateMatrixWorld(true);
    m.geometry.computeBoundsTree();
    return m;
  }
  return [loadWall("_L"), loadWall("_R_D"), loadWall("_B")];
}

function meshWorldEdgeSample(mesh, maxEdges) {
  const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
  const edges = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (let t = 0; t < triCount; t += step) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); } else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    edges.push([vA.clone(), vB.clone()], [vB.clone(), vC.clone()], [vC.clone(), vA.clone()]);
  }
  return edges;
}

function partMesh(p) {
  const glbPath = R.glbPath(p.part_id);
  if (!glbPath) throw new Error("CHYBI GLB pro part_id=" + p.part_id + " role=" + p.role);
  const m = parseGlbMesh(glbPath);
  m.position.set(...p.position);
  m.quaternion.set(...p.quaternion);
  m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

function isKnownNesting(a, b) {
  const ra = a.role || "", rb = b.role || "";
  const rules = [
    [/^eurobox-/, /^(nosnik|spojnice)-/],
    [/^zaslepka/, /^(predni-svislice|zadni-svislice|cap|sloupek-pred-podbehem)/],
    [/^uhelnik-/, /^(nosnik|spojnice|predni-svislice|zadni-svislice|sloupek-pred-podbehem|cap)/],
    [/^logo-ochrana-/, /^(nosnik|spojnice|predni-svislice|zadni-svislice|cap|sloupek-pred-podbehem)/],
  ];
  for (const [ra_, rb_] of rules) {
    if ((ra_.test(ra) && rb_.test(rb)) || (ra_.test(rb) && rb_.test(ra))) return true;
  }
  return false;
}

function selfCollide(parts) {
  const testableL = parts.filter(p => !R.jeKaroserie(p.part_id) && !(p.role || "").startsWith("kontrolni-pomucka"));
  const cache = testableL.map(p => ({ p, box: new THREE.Box3().setFromObject(partMesh(p)) }));
  const list = [];
  for (let i = 0; i < cache.length; i++) {
    for (let j = i + 1; j < cache.length; j++) {
      const a = cache[i], b = cache[j];
      if (a.p.role === b.p.role) continue;
      if (isKnownNesting(a.p, b.p)) continue;
      if (!a.box.intersectsBox(b.box)) continue;
      const ix = Math.min(a.box.max.x, b.box.max.x) - Math.max(a.box.min.x, b.box.min.x);
      const iy = Math.min(a.box.max.y, b.box.max.y) - Math.max(a.box.min.y, b.box.min.y);
      const iz = Math.min(a.box.max.z, b.box.max.z) - Math.max(a.box.min.z, b.box.min.z);
      const vol = Math.max(0, ix) * Math.max(0, iy) * Math.max(0, iz);
      if (vol > 2000) {
        list.push({ a: a.p.role, aX: +a.p.position[0].toFixed(2), aZ: +a.p.position[2].toFixed(2), b: b.p.role, bX: +b.p.position[0].toFixed(2), bZ: +b.p.position[2].toFixed(2), vol: +vol.toFixed(0), overlap_mm: [ix, iy, iz].map(v => +v.toFixed(1)) });
      }
    }
  }
  return { susp: list.length, list };
}

// notchChecks: [{ z, oldYnew, deltaY }] - jeden zaznam na kazdou vyrezovou
// nohu, ktera se v teto sestave menila.
function verifyAssembly({ partsNew, partsOrig, carBodyBase, notchChecks, label }) {
  const walls = loadWalls(carBodyBase);
  function collidesWithWallsReal(mesh) {
    const edges = meshWorldEdgeSample(mesh, 300);
    const raycaster = new THREE.Raycaster();
    for (const [p0, p1] of edges) {
      const dir = p1.clone().sub(p0), dist = dir.length();
      if (dist < 1e-6) continue;
      dir.normalize();
      raycaster.set(p0, dir); raycaster.far = dist;
      if (raycaster.intersectObjects(walls, false).length) return true;
    }
    return false;
  }

  // a) SAT
  const testable = partsNew.filter(p => !R.jeKaroserie(p.part_id) && !(p.role || "").startsWith("kontrolni-pomucka"));
  let collisions = 0;
  const collidingList = [];
  for (const p of testable) {
    const mesh = partMesh(p);
    if (collidesWithWallsReal(mesh)) { collisions++; collidingList.push({ role: p.role, part_id: p.part_id, position: p.position }); }
  }

  // b) presna mezera na kazdem zmenenem svaru + "nevisi ve vzduchu"
  const seamChecks = [];
  let allSeamsOk = true;
  for (const nc of (notchChecks || [])) {
    const sloupek = testable.find(p => p.role === "sloupek-pred-podbehem" && Math.abs(p.position[2] - nc.z) < 2);
    const svislice = testable.find(p => p.role === "zadni-svislice-nad-zarezem" && Math.abs(p.position[2] - nc.z) < 2);
    let gap = null, gapOk = null;
    if (sloupek && svislice) {
      const bSloupek = new THREE.Box3().setFromObject(partMesh(sloupek));
      const bSvislice = new THREE.Box3().setFromObject(partMesh(svislice));
      gap = bSvislice.min.y - bSloupek.max.y;
      gapOk = Math.abs(gap) < 1e-3;
    } else if (svislice) {
      // K-281-styl noha bez sloupku (viz AGENTS_LOG zapis) - jen over,
      // ze zadni-svislice-nad-zarezem sama sedi presne na newYnew.
      const bSvislice = new THREE.Box3().setFromObject(partMesh(svislice));
      gap = bSvislice.min.y - (nc.oldYnew + nc.deltaY);
      gapOk = Math.abs(gap) < 1e-3;
    }
    allSeamsOk = allSeamsOk && (gapOk === true);
    seamChecks.push({ z: nc.z, oldYnew: nc.oldYnew, newYnew: nc.oldYnew + nc.deltaY, hasSloupek: !!sloupek, hasSvislice: !!svislice, gap, gapOk });
  }

  // c) self-kolize baseline vs nova
  const baseline = selfCollide(partsOrig);
  const after = selfCollide(partsNew);
  const newProblems = after.list.filter(x => !baseline.list.some(b => b.a === x.a && b.b === x.b && b.aX === x.aX && b.bX === x.bX));

  const report = {
    label, testedParts: testable.length, collisions, collidingList,
    seamChecks, allSeamsOk,
    baselineSelfSusp: baseline.susp, afterSelfSusp: after.susp, newProblems,
    OK: collisions === 0 && allSeamsOk && newProblems.length === 0,
  };
  return report;
}

module.exports = { verifyAssembly, loadWalls, partMesh, selfCollide };
