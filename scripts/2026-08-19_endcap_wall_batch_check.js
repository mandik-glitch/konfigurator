// Batch verification of ALL "endcap" and "wall" attach_mode parts against
// REAL .glb geometry - exact reproduction of production runZaslepkaAut /
// runWallAut candidate selection (incl. 2026-08-19 accessoryThinFaceIdx
// fix), per WORKFLOW.md bod 11 ("Place All pro kazdy naucteny rezim").
// Extends the same systematic Node.js harness method already used for
// corner_side (scratchpad/rozek/precompute_attach_pose.js) to the two
// remaining unverified families. See VLASTNOSTI_PROFILU.md "Pravidlo
// profilů - montážní plocha plochého příslušenství..." for the underlying
// fix this harness is checking end-to-end, across the WHOLE family, not
// just the 2 reference SKUs that were manually verified on 2026-08-19.
const fs = require("fs");
const path = require("path");
const THREE = require("three");
const { parseGlbMesh } = require("./2026-08-19_glb_real_geometry.js");
const shared = require("../webapp/js/scene-geometry-shared.js");
const { computeConnectorsLocal, worldConnectorsOf, isProfilePart } = shared;

const KATALOG = path.join(__dirname, "..", "webapp", "katalog");

// ---- partCompatMeta, ported 1:1 from webapp/scene.html (ln ~3349-3385) ----
const PROFILE_SIZE_NUMBERS = [10, 20, 25, 30, 35, 40, 45, 50, 60, 80, 90];
function partCompatMeta(p) {
  const sku = String(p.sku || "");
  const name = String(p.name || "");
  const seg = sku.split(".");
  let slot = null;
  const sizes = new Set();
  seg.forEach((x, i) => {
    if (i >= 3 && slot === null && (x === "06" || x === "08" || x === "10") && i < seg.length - 1) {
      slot = parseInt(x, 10);
    }
    if (x.length === 4 && /^\d+$/.test(x)) {
      const a = parseInt(x.slice(0, 2), 10), b = parseInt(x.slice(2), 10);
      if (PROFILE_SIZE_NUMBERS.includes(a) && PROFILE_SIZE_NUMBERS.includes(b)) { sizes.add(a); sizes.add(b); }
    }
  });
  const mSlot = name.match(/dr[áa]žk\w*\s*(\d{1,2})|\bS(\d{1,2})\b/i);
  if (slot === null && mSlot) slot = parseInt(mSlot[1] || mSlot[2], 10);
  const reSize = /(\d{2})\s*[xX×]\s*(\d{2,3})/g;
  let m;
  while ((m = reSize.exec(name)) !== null) {
    [m[1], m[2]].forEach(v => { const n = parseInt(v, 10); if (PROFILE_SIZE_NUMBERS.includes(n)) sizes.add(n); });
  }
  return { slot, sizes: Array.from(sizes) };
}

// ---- real-profile catalog: size -> glb file (only ones that actually
// exist as real GLBs, per cfg_dily; same-groove fallback for "system"
// sizes without their own real profile, same as precompute_attach_pose.js
// used for corner_side) ----
// bot8 2026-08-19: kompozitni rozmery (nerovnostranny prurez, napr. 30x60)
// MUSI mit prednost pred jednotlivym cislem - jinak test omylem substituuje
// mensi ctvercovy profil (30x30) za skutecny cil (30x60), coz falesne
// vyrobi "spatny dotyk" jen kvuli spatne zvolenemu TESTOVACIMU profilu, ne
// kvuli realne chybe algoritmu (presne tohle se stalo u product_3151).
const REAL_PROFILE_BY_COMPOUND_SIZE = { "30,60": "Object_1.glb", "40,80": "Object_14.glb" };
const REAL_PROFILE_BY_SIZE = {
  20: "profil_20x20.glb",      // also 20x40/20x80 exist but 20x20 is groove-6 rep
  30: "profil_30x30_uzavreny.glb",
  35: "profil_35x35.glb",
  40: "Object_11.glb",         // 40x40
  45: "Object_2.glb",          // 45x45
};
const GROOVE_FALLBACK = { 6: "profil_20x20.glb", 8: "profil_30x30_uzavreny.glb", 10: "Object_11.glb" };

function pickProfileFile(meta) {
  const sorted = [...meta.sizes].sort((a, b) => a - b);
  if (sorted.length >= 2) {
    const key = sorted.slice(0, 2).join(",");
    if (REAL_PROFILE_BY_COMPOUND_SIZE[key]) return REAL_PROFILE_BY_COMPOUND_SIZE[key];
  }
  for (const s of meta.sizes) if (REAL_PROFILE_BY_SIZE[s]) return REAL_PROFILE_BY_SIZE[s];
  if (meta.slot && GROOVE_FALLBACK[meta.slot]) return GROOVE_FALLBACK[meta.slot];
  return "profil_30x30_uzavreny.glb"; // last-resort default (most common family)
}

// ---- production functions, faithfully copied from webapp/scene.html ----
function findAccessoryToProfileCandidates(accEntry, profEntry) {
  const candidates = [];
  const enabledList = Array.isArray(accEntry.part.accessory_conn_enabled) ? accEntry.part.accessory_conn_enabled : null;
  const profWorld = worldConnectorsOf(profEntry);
  profWorld.forEach((pc, pIdx) => {
    if (pc.kind !== "face" && pc.kind !== "end") return;
    accEntry.connectorsLocal.forEach((cc, cIdx) => {
      if (cc.kind !== "face" && cc.kind !== "end") return;
      if (enabledList && !cc.isGeoFace && !enabledList.includes(cIdx)) return;
      const targetDir = pc.normal.clone().negate();
      const localDir = cc.normal.clone().normalize();
      const quat = new THREE.Quaternion().setFromUnitVectors(localDir, targetDir.normalize());
      candidates.push({ type: "accessory-face", forcedParentConnIdx: pIdx, childFaceConnIdx: cIdx, option: { quat } });
    });
  });
  return candidates;
}
function findAccessoryToProfileCandidatesAllSpins(accEntry, profEntry) {
  const base = findAccessoryToProfileCandidates(accEntry, profEntry);
  const out = [];
  base.forEach(c => {
    const localDir = accEntry.connectorsLocal[c.childFaceConnIdx].normal.clone().normalize();
    for (let spin = 0; spin < 4; spin++) {
      const spinQuat = new THREE.Quaternion().setFromAxisAngle(localDir, spin * Math.PI / 2);
      const quat = c.option.quat.clone().multiply(spinQuat);
      out.push({ ...c, spinIndex: spin, option: { quat } });
    }
  });
  return out;
}
function applyFaceToFaceCandidate(candidate, childEntry, parentEntry) {
  const quat = candidate.option.quat;
  childEntry.object3d.quaternion.copy(quat);
  childEntry.object3d.position.set(0, 0, 0);
  childEntry.object3d.updateMatrixWorld(true);
  const parentFaceWorld = worldConnectorsOf(parentEntry)[candidate.forcedParentConnIdx];
  const childFaceLocal = childEntry.connectorsLocal[candidate.childFaceConnIdx];
  const rotatedLocalPoint = childFaceLocal.point.clone().applyQuaternion(quat);
  const pos = parentFaceWorld.point.clone().sub(rotatedLocalPoint);
  childEntry.object3d.position.copy(pos);
  childEntry.object3d.updateMatrixWorld(true);
}
function applyAttachTeachOffset(accEntry, connIdx, offMm) {
  if (!offMm) return;
  accEntry.object3d.updateMatrixWorld(true);
  const n = worldConnectorsOf(accEntry)[connIdx].normal.clone().normalize();
  accEntry.object3d.position.addScaledVector(n, offMm);
  accEntry.object3d.updateMatrixWorld(true);
}
// scene.html ~14702 (2026-08-19 fix)
function accessoryThinFaceIdx(accEntry, obj) {
  const accFaceIdxs = [];
  accEntry.connectorsLocal.forEach((c, i) => { if (c.kind === "face") accFaceIdxs.push(i); });
  if (!accFaceIdxs.length) return null;
  obj.updateMatrixWorld(true);
  const accWorld = worldConnectorsOf(accEntry);
  const accCenter = new THREE.Box3().setFromObject(obj).getCenter(new THREE.Vector3());
  let thinFaceIdx = null, thinDist = Infinity;
  accFaceIdxs.forEach(i => {
    const dist = accWorld[i].point.distanceTo(accCenter);
    if (dist < thinDist) { thinDist = dist; thinFaceIdx = i; }
  });
  return thinFaceIdx;
}
function partConnectorOpts(p) {
  return { wallSnap: !isProfilePart(p), geoFaces: (p && Array.isArray(p.geo_faces)) ? p.geo_faces : undefined };
}

function touchReport(A, B) {
  const axes = ["x", "y", "z"];
  const report = {};
  axes.forEach(ax => {
    const gap = Math.max(A.min[ax] - B.max[ax], B.min[ax] - A.max[ax]);
    const overlap = Math.min(A.max[ax], B.max[ax]) - Math.max(A.min[ax], B.min[ax]);
    report[ax] = { gap: +gap.toFixed(4), overlap: +overlap.toFixed(4) };
  });
  return report;
}
function classifyReport(report) {
  let touchAxes = 0, fullOverlapAxes = 0;
  ["x", "y", "z"].forEach(ax => {
    const r = report[ax];
    if (Math.abs(r.overlap) <= 0.05 && r.gap <= 0.05) touchAxes++;
    else if (r.overlap > 0.05) fullOverlapAxes++;
  });
  return { touchAxes, fullOverlapAxes, flush: touchAxes === 1 && fullOverlapAxes === 2 };
}

// ---- run over all parts ----
const parts = JSON.parse(fs.readFileSync(
  "/tmp/claude-0/-opt-konfigurator/b336267e-a1f5-4ea8-b332-89232804d6ac/scratchpad/endcap_wall_parts.json", "utf8"));

const results = [];
for (const p of parts) {
  const glbPath = path.join(KATALOG, p.glb_file);
  if (!fs.existsSync(glbPath)) { results.push({ ...p, error: "glb soubor chybi na disku" }); continue; }
  const meta = partCompatMeta(p);
  const profFile = pickProfileFile(meta);
  const profPath = path.join(KATALOG, profFile);
  let accObj, profObj, accEntry, profEntry;
  try {
    profObj = parseGlbMesh(profPath);
    profObj.position.set(0, 0, 0); profObj.quaternion.identity(); profObj.updateMatrixWorld(true);
    const profPart = { length_mm: 1000, cross_section_mm: [30, 30] }; // marks it as profile (isProfilePart checks cross_section_mm presence via part shape upstream; here just for wallSnap flag it's irrelevant, profiles never wallSnap)
    profEntry = { part: profPart, object3d: profObj, connectorsLocal: computeConnectorsLocal(profObj, { wallSnap: false }) };

    accObj = parseGlbMesh(glbPath);
    accObj.position.set(0, 0, 0); accObj.quaternion.identity(); accObj.updateMatrixWorld(true);
    const accPart = {
      id: p.id, name: p.name, attach_mode: p.attach_mode,
      accessory_conn_enabled: p.accessory_conn_enabled ? JSON.parse(p.accessory_conn_enabled) : null,
      geo_faces: p.geo_faces_json ? JSON.parse(p.geo_faces_json) : undefined,
    };
    accEntry = { part: accPart, object3d: accObj, connectorsLocal: computeConnectorsLocal(accObj, partConnectorOpts(accPart)) };
  } catch (e) {
    results.push({ ...p, error: "parse selhal: " + e.message });
    continue;
  }

  // exact production candidate filter per mode
  let cands = findAccessoryToProfileCandidatesAllSpins(accEntry, profEntry);
  if (p.attach_mode === "endcap") cands = cands.filter(c => profEntry.connectorsLocal[c.forcedParentConnIdx].kind === "end");
  else cands = cands.filter(c => profEntry.connectorsLocal[c.forcedParentConnIdx].kind === "face");

  if (!cands.length) { results.push({ ...p, profFile, error: "0 kandidatu (nekompatibilni profil/orientace)" }); continue; }

  const geoCands = cands.filter(c => accEntry.connectorsLocal[c.childFaceConnIdx].isGeoFace);
  // bot8 2026-08-19: presna kopie nove produkcni logiky (bestFlushAccessoryCandidateIdx
  // v webapp/scene.html) - zmer-a-oveř misto odhadu, s puvodni heuristikou
  // jako zalozni sit.
  function bestFlushIdx(cands2) {
    const profBoxRef = new THREE.Box3().setFromObject(profEntry.object3d);
    for (let i = 0; i < cands2.length; i++) {
      applyFaceToFaceCandidate(cands2[i], accEntry, profEntry);
      accObj.updateMatrixWorld(true);
      const accBox = new THREE.Box3().setFromObject(accObj);
      let touchAxes = 0, fullOverlapAxes = 0;
      ["x", "y", "z"].forEach(ax => {
        const gap = Math.max(profBoxRef.min[ax] - accBox.max[ax], accBox.min[ax] - profBoxRef.max[ax]);
        const overlap = Math.min(profBoxRef.max[ax], accBox.max[ax]) - Math.max(profBoxRef.min[ax], accBox.min[ax]);
        if (Math.abs(overlap) <= 0.05 && gap <= 0.05) touchAxes++;
        else if (overlap > 0.05) fullOverlapAxes++;
      });
      if (touchAxes === 1 && fullOverlapAxes === 2) return i;
    }
    return null;
  }
  const flushIdx = geoCands.length ? null : bestFlushIdx(cands);
  const thinFaceIdx = (geoCands.length || flushIdx != null) ? null : accessoryThinFaceIdx(accEntry, accObj);
  const thinCands = thinFaceIdx != null ? cands.filter(c => c.childFaceConnIdx === thinFaceIdx) : [];
  const cand = geoCands.length ? geoCands[0] : (flushIdx != null ? cands[flushIdx] : (thinCands.length ? thinCands[0] : cands[0]));

  applyFaceToFaceCandidate(cand, accEntry, profEntry);
  applyAttachTeachOffset(accEntry, cand.childFaceConnIdx, Number(p.attach_offset_mm) || 0);
  profObj.updateMatrixWorld(true); accObj.updateMatrixWorld(true);

  const profBox = new THREE.Box3().setFromObject(profObj);
  const accBox = new THREE.Box3().setFromObject(accObj);
  const report = touchReport(profBox, accBox);
  const cls = classifyReport(report);

  results.push({
    id: p.id, sku: p.sku, name: p.name, attach_mode: p.attach_mode,
    profFile, candSource: geoCands.length ? "geoFace" : (flushIdx != null ? "flushMeasured" : (thinCands.length ? "thinFace" : "first")),
    report, flush: cls.flush, touchAxes: cls.touchAxes, fullOverlapAxes: cls.fullOverlapAxes,
  });
}

const ok = results.filter(r => r.flush);
const bad = results.filter(r => !r.flush);
console.log(`\n=== VYSLEDEK: ${ok.length}/${results.length} FLUSH (0 kandidatu / parse chyby / spatny dotyk = ${bad.length}) ===\n`);
bad.forEach(r => {
  console.log(`FAIL [${r.attach_mode}] id=${r.id} sku=${r.sku} "${r.name}"`);
  if (r.error) console.log(`  chyba: ${r.error}`);
  else console.log(`  profFile=${r.profFile} candSource=${r.candSource} report=${JSON.stringify(r.report)}`);
});
fs.writeFileSync(
  "/tmp/claude-0/-opt-konfigurator/b336267e-a1f5-4ea8-b332-89232804d6ac/scratchpad/endcap_wall_batch_results.json",
  JSON.stringify(results, null, 2));
console.log("\nplny vysledek: scratchpad/endcap_wall_batch_results.json");
