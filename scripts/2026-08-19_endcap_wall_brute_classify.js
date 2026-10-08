// For each part that FAILED the exact-production-logic batch check
// (2026-08-19_endcap_wall_batch_check.js), brute-force search ALL
// connector indices x 4 spins to see whether a genuinely flush candidate
// exists anywhere (proving accessoryThinFaceIdx()'s "closest point to
// bbox center among face-kind connectors" heuristic just picked the WRONG
// one for an irregularly-shaped part), or whether NO candidate is flush
// at all (real physical mismatch - wrong attach_mode / needs curation).
const fs = require("fs");
const path = require("path");
const THREE = require("three");
const { parseGlbMesh } = require("./2026-08-19_glb_real_geometry.js");
const shared = require("../webapp/js/scene-geometry-shared.js");
const { computeConnectorsLocal, worldConnectorsOf } = shared;
const KATALOG = path.join(__dirname, "..", "webapp", "katalog");

const results = JSON.parse(fs.readFileSync(
  "/tmp/claude-0/-opt-konfigurator/b336267e-a1f5-4ea8-b332-89232804d6ac/scratchpad/endcap_wall_batch_results.json", "utf8"));
const parts = JSON.parse(fs.readFileSync(
  "/tmp/claude-0/-opt-konfigurator/b336267e-a1f5-4ea8-b332-89232804d6ac/scratchpad/endcap_wall_parts.json", "utf8"));
const partById = Object.fromEntries(parts.map(p => [p.id, p]));

function touchReport(A, B) {
  const axes = ["x", "y", "z"]; const r = {};
  axes.forEach(ax => {
    const gap = Math.max(A.min[ax] - B.max[ax], B.min[ax] - A.max[ax]);
    const overlap = Math.min(A.max[ax], B.max[ax]) - Math.max(A.min[ax], B.min[ax]);
    r[ax] = { gap: +gap.toFixed(4), overlap: +overlap.toFixed(4) };
  });
  return r;
}
function classify(r) {
  let touchAxes = 0, fullOverlapAxes = 0;
  ["x", "y", "z"].forEach(ax => {
    if (Math.abs(r[ax].overlap) <= 0.05 && r[ax].gap <= 0.05) touchAxes++;
    else if (r[ax].overlap > 0.05) fullOverlapAxes++;
  });
  return touchAxes === 1 && fullOverlapAxes === 2;
}
function applyFaceToFaceCandidate(quat, childEntry, parentEntry, forcedParentConnIdx, childFaceConnIdx) {
  childEntry.object3d.quaternion.copy(quat);
  childEntry.object3d.position.set(0, 0, 0);
  childEntry.object3d.updateMatrixWorld(true);
  const parentFaceWorld = worldConnectorsOf(parentEntry)[forcedParentConnIdx];
  const childFaceLocal = childEntry.connectorsLocal[childFaceConnIdx];
  const rotatedLocalPoint = childFaceLocal.point.clone().applyQuaternion(quat);
  const pos = parentFaceWorld.point.clone().sub(rotatedLocalPoint);
  childEntry.object3d.position.copy(pos);
  childEntry.object3d.updateMatrixWorld(true);
}

const failed = results.filter(r => !r.flush);
const out = [];
for (const r of failed) {
  const p = partById[r.id];
  if (!p || r.error) { out.push({ ...r, brute: "skip-error" }); continue; }
  const profPath = path.join(KATALOG, r.profFile);
  const glbPath = path.join(KATALOG, p.glb_file);
  const profObj = parseGlbMesh(profPath);
  profObj.position.set(0, 0, 0); profObj.quaternion.identity(); profObj.updateMatrixWorld(true);
  const profEntry = { part: {}, object3d: profObj, connectorsLocal: computeConnectorsLocal(profObj, { wallSnap: false }) };
  const wantKind = p.attach_mode === "endcap" ? "end" : "face";
  const profIdxs = profEntry.connectorsLocal.map((c, i) => c.kind === wantKind ? i : -1).filter(i => i >= 0);

  const accObj = parseGlbMesh(glbPath);
  accObj.position.set(0, 0, 0); accObj.quaternion.identity(); accObj.updateMatrixWorld(true);
  const accEntry = { part: {}, object3d: accObj, connectorsLocal: computeConnectorsLocal(accObj, { wallSnap: true }) };

  let found = null;
  outer:
  for (const pIdx of profIdxs) {
    for (let cIdx = 0; cIdx < accEntry.connectorsLocal.length; cIdx++) {
      const cc = accEntry.connectorsLocal[cIdx];
      if (cc.kind !== "face" && cc.kind !== "end") continue;
      for (let spin = 0; spin < 4; spin++) {
        const pc = worldConnectorsOf(profEntry)[pIdx];
        const targetDir = pc.normal.clone().negate();
        const localDir = cc.normal.clone().normalize();
        let quat = new THREE.Quaternion().setFromUnitVectors(localDir, targetDir.normalize());
        const spinQuat = new THREE.Quaternion().setFromAxisAngle(localDir, spin * Math.PI / 2);
        quat = quat.clone().multiply(spinQuat);
        applyFaceToFaceCandidate(quat, accEntry, profEntry, pIdx, cIdx);
        profObj.updateMatrixWorld(true); accObj.updateMatrixWorld(true);
        const profBox = new THREE.Box3().setFromObject(profObj);
        const accBox = new THREE.Box3().setFromObject(accObj);
        const rep = touchReport(profBox, accBox);
        if (classify(rep)) { found = { pIdx, cIdx, cKind: cc.kind, spin, rep }; break outer; }
      }
    }
  }
  out.push({ id: r.id, sku: r.sku, name: r.name, attach_mode: r.attach_mode, brute: found ? "FIXABLE" : "NO_FLUSH_ANYWHERE", found });
}

const fixable = out.filter(o => o.brute === "FIXABLE");
const noFlush = out.filter(o => o.brute === "NO_FLUSH_ANYWHERE");
console.log(`\nFIXABLE (flush candidate existuje, jen ho soucasna heuristika nenajde): ${fixable.length}`);
fixable.forEach(o => console.log(`  id=${o.id} sku=${o.sku} "${o.name}" -> cIdx=${o.found.cIdx}(${o.found.cKind}) spin=${o.found.spin}`));
console.log(`\nNO_FLUSH_ANYWHERE (zadny kandidat neni flush - jiny fyzicky problem/attach_mode): ${noFlush.length}`);
noFlush.forEach(o => console.log(`  id=${o.id} sku=${o.sku} "${o.name}"`));

fs.writeFileSync(
  "/tmp/claude-0/-opt-konfigurator/b336267e-a1f5-4ea8-b332-89232804d6ac/scratchpad/endcap_wall_brute_results.json",
  JSON.stringify(out, null, 2));
