// Obecna, znovupouzitelna METODA "uhelniky na spoje nohou" (bot16, 2026-09-01).
//
// Puvod: uhelniky (rohove spojky, katalog attach_mode="corner_side",
// SKU-typovy suffix ".01") byly poprve aplikovany hromadne na 21 vnitrnich
// spoju nohou konkretni sestavy (Jumpy CI14 eurobox regal, product_assemblies
// id=47 - viz KOMPONENTY_EUROBOXY.md/PRISLUSENSTVI_PRIPOJENI.md, ta sestava uz
// v DB neexistuje, byla smazana pri bezne session-uklidu). Tenhle soubor je
// GENERALIZACE tehdejsiho jednorazoveho portu (scripts/tmp_2026-08-31_
// uhelniky_leg_joints.js) - misto pevnych indexu jedne konkretni sestavy a
// natvrdo zapsane 30x30 pozy bere JAKOUKOLI mnozinu profilu jedne nohy
// (libovolny prurez, libovolne rozlozeni spoju - "plain" i "vyrez" tvar) a
// katalog vsech dostupnych uhelnikovych dilu (natazeny z DB skriptem
// 2026-09-01_fetch_uhelnik_catalog.py), a vraci spravna umisteni pro VSECHNY
// nalezene vnitrni spoje.
//
// Vsechny geometricke funkce nize jsou PORTOVANY 1:1 (ne aproximovane) ze
// zive `webapp/scene.html` (aktualni verze k 2026-09-01: findAccessoryTo
// ProfileCandidates(AllSpins), uhelnikCornerFrameQuat, applyFaceToFaceCandidate,
// uhelnikAutAlignAxial, geoFaceSnapToCornerWalls, uhelnikLugAlignToSlots,
// uhelnikAutPoseCandidates, uhelnikAutPlaceOne, uhelnikAutPlaceForPair,
// profileLengthAxisWorld, profilesStillTouching, crossSectionKey,
// skuTypeSuffix+partCompatMeta.sizes, uhelnikAutPart) - viz cross-referencni
// komentare u kazde funkce. computeConnectorsLocal/worldConnectorsOf/
// isProfilePart/linkJointPeers pochazeji primo ze sdileneho
// webapp/js/scene-geometry-shared.js (stejny zdroj jako prohlizec pouziva).
//
// ***** KRITICKA PAST (zdokumentovana uz drive, PLATI STEJNE TADY) *****
// computeConnectorsLocal(obj) pocita Box3().setFromObject(obj), tedy SVETOVY
// bounding box AKTUALNI transformace objektu - NENI nezavisly na pozici/
// rotaci/skale, i kdyz nazev "Local" naznacuje opak. Zive scene.html VZDY
// vola computeConnectorsLocal na cerstve nactenem meshi PRED nastavenim
// position/quaternion/scale (viz makeProfileEntry/makeBracketTemplate nize).
// Kdyby se pocitalo AZ PO umisteni, worldConnectorsOf by transformaci
// aplikoval PODRUHE - vysledkem jsou falesne rovnobezne osy a 0 nalezenych
// spoju misto ocekavaneho poctu (presne takhle to poprve selhalo 2026-08-31).
//
// Pouziti (viz scripts/2026-09-01_uhelniky_leg_joints_verify.js pro plny
// priklad na 2 velikostech prurezu):
//   const lib = require("./2026-09-01_uhelniky_leg_joints_lib.js");
//   const legEntries = legParts.map((p, idx) => lib.makeProfileEntry(glbPath, p));
//   const catalog = JSON.parse(fs.readFileSync(".../2026-09-01_uhelnik_catalog.json"));
//   const { results, stats } = lib.applyUhelnikyToLeg(legEntries, catalog, KATALOG_DIR);

const THREE = require("three");
global.THREE = THREE;
const { parseGlbMesh } = require("./2026-08-19_glb_real_geometry.js");
const shared = require("/opt/konfigurator/webapp/js/scene-geometry-shared.js");
const { computeConnectorsLocal, worldConnectorsOf, isProfilePart, linkJointPeers } = shared;

// ---- profil-entry tovarna (dodrzuje povinne poradi: connectorsLocal PRED umistenim) ----
function makeProfileEntry(glbPath, placement) {
  const obj = parseGlbMesh(glbPath);
  const connectorsLocal = computeConnectorsLocal(obj, { wallSnap: false });
  obj.position.set(...placement.position);
  obj.quaternion.set(...placement.quaternion);
  obj.scale.set(...(placement.scale || [1, 1, 1]));
  obj.updateMatrixWorld(true);
  const part = {
    id: placement.id || glbPath,
    length_mm: placement.length_mm != null ? placement.length_mm : 1000,
    cross_section_mm: placement.cross_section_mm,
  };
  return { part, object3d: obj, connectorsLocal, role: placement.role, idx: placement.idx };
}

// ---- katalogovy dil (uhelnik) - sablona nactena jednou, klonovana pro kazdy roh ----
function makeBracketTemplate(katalogDir, bracketMeta) {
  const glbPath = katalogDir + bracketMeta.glb_file;
  const obj0 = parseGlbMesh(glbPath);
  const connectorsLocal = computeConnectorsLocal(obj0, { wallSnap: true, geoFaces: bracketMeta.geo_faces || undefined });
  const part = {
    id: bracketMeta.part_id,
    geo_faces: bracketMeta.geo_faces || null,
    attach_mode: bracketMeta.attach_mode,
    accessory_conn_enabled: bracketMeta.accessory_conn_enabled || null,
    length_mm: null,
    cross_section_mm: [null, null],
  };
  return { glbPath, connectorsLocal, part, uhelnik_pose: bracketMeta.uhelnik_pose, meta: bracketMeta };
}
function freshBracketObj(template) {
  return parseGlbMesh(template.glbPath); // stejna geometrie, novy nezavisly THREE objekt na kazdy roh
}

// ---- katalogovy vyber dilu podle prurezu - port uhelnikAutPart(sizeNum) ----
// (webapp/scene.html: filtr skuTypeSuffix()==="01" && attach_mode==="corner_side"
// uz je proveden PRI EXPORTU katalogu - viz 2026-09-01_fetch_uhelnik_catalog.py
// - tady zbyva jen krok "sizes.includes(sizeNum)", stejne jako v zive funkci.)
function resolveBracketForSize(sizeNum, catalogTemplates) {
  if (sizeNum == null) return catalogTemplates[0] || null;
  const sized = catalogTemplates.filter(t => t.meta.sizes.includes(sizeNum));
  if (!sized.length) return null; // presne tahle velikost v katalogu neni - radeji nic nez spatna velikost (viz Robert 2026-08-17)
  return sized[0];
}

// ---- crossSectionKey (webapp/scene.html ~13804) ----
function crossSectionKey(cross_section_mm) {
  if (!cross_section_mm || cross_section_mm[0] == null || cross_section_mm[1] == null) return null;
  return Math.round(cross_section_mm[0]) + "x" + Math.round(cross_section_mm[1]);
}

// ---- profileLengthAxisWorld (webapp/scene.html ~14849) ----
function profileLengthAxisWorld(entry) {
  const endIdxs = [];
  entry.connectorsLocal.forEach((c, i) => { if (c.kind === "end") endIdxs.push(i); });
  if (endIdxs.length !== 2) return null;
  const w = worldConnectorsOf(entry);
  return w[endIdxs[1]].point.clone().sub(w[endIdxs[0]].point).normalize();
}

// ---- profilesStillTouching (webapp/scene.html ~14991) ----
function profilesStillTouching(a, b, epsMm) {
  a.object3d.updateMatrixWorld(true);
  b.object3d.updateMatrixWorld(true);
  const boxA = new THREE.Box3().setFromObject(a.object3d);
  const boxB = new THREE.Box3().setFromObject(b.object3d);
  if (boxA.isEmpty() || boxB.isEmpty()) return false;
  boxA.expandByScalar(epsMm != null ? epsMm : 2);
  return boxA.intersectsBox(boxB);
}

// ---- findAccessoryToProfileCandidates(AllSpins) (webapp/scene.html ~14117/14199) ----
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
      if (isProfilePart(profEntry.part)) {
        const n = pc.normal.clone().normalize();
        let aw = null;
        if (pc.kind === "face") {
          const a = profileLengthAxisWorld(profEntry);
          if (a) aw = a.clone().addScaledVector(n, -a.dot(n));
        } else {
          const firstFace = profWorld.find(w => w.kind === "face");
          if (firstFace) { const fn = firstFace.normal.clone(); aw = fn.addScaledVector(n, -fn.dot(n)); }
        }
        if (aw && aw.lengthSq() > 1e-6) {
          aw.normalize();
          let r = Math.abs(localDir.x) < 0.9 ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 1, 0);
          r = r.addScaledVector(localDir, -r.dot(localDir)).normalize();
          const rw = r.clone().applyQuaternion(quat);
          rw.addScaledVector(n, -rw.dot(n));
          if (rw.lengthSq() > 1e-6) {
            rw.normalize();
            const ang = Math.atan2(n.dot(new THREE.Vector3().crossVectors(rw, aw)), Math.max(-1, Math.min(1, rw.dot(aw))));
            quat.premultiply(new THREE.Quaternion().setFromAxisAngle(n, ang));
          }
        }
      }
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

// ---- uhelnikCornerFrameQuat (webapp/scene.html ~15364) ----
function uhelnikCornerFrameQuat(axisDir, side, dWall) {
  const u = axisDir.clone().multiplyScalar(side).normalize();
  const w = new THREE.Vector3().crossVectors(u, dWall).normalize();
  const n2 = new THREE.Vector3().crossVectors(w, u).normalize();
  const m = new THREE.Matrix4().makeBasis(u, n2, w);
  return new THREE.Quaternion().setFromRotationMatrix(m);
}

// ---- uhelnikAutPoseCandidates (webapp/scene.html ~15408) ----
function uhelnikAutPoseCandidates(accEntry, P, dWall) {
  return findAccessoryToProfileCandidatesAllSpins(accEntry, P).filter(c => {
    const pc = worldConnectorsOf(P)[c.forcedParentConnIdx];
    return pc && pc.kind === "face" && pc.normal.dot(dWall) > 0.7;
  });
}

// ---- applyFaceToFaceCandidate (webapp/scene.html ~19733, bez UI-only opts) ----
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
  linkJointPeers(childEntry, parentEntry);
  return true;
}

// ---- uhelnikAutAlignAxial (webapp/scene.html ~15417) ----
function uhelnikAutAlignAxial(accEntry, axisA, axisDir, L, t, side) {
  accEntry.object3d.updateMatrixWorld(true);
  const bb = new THREE.Box3().setFromObject(accEntry.object3d);
  if (bb.isEmpty()) return false;
  let m0 = Infinity, m1 = -Infinity;
  for (let xi = 0; xi < 2; xi++) for (let yi = 0; yi < 2; yi++) for (let zi = 0; zi < 2; zi++) {
    const corner = new THREE.Vector3(xi ? bb.max.x : bb.min.x, yi ? bb.max.y : bb.min.y, zi ? bb.max.z : bb.min.z);
    const tt = corner.sub(axisA).dot(axisDir);
    if (tt < m0) m0 = tt;
    if (tt > m1) m1 = tt;
  }
  const w = m1 - m0;
  let target0;
  if (side > 0) { if (t + w > L + 1) return false; target0 = t; }
  else { if (t - w < -1) return false; target0 = t - w; }
  accEntry.object3d.position.addScaledVector(axisDir, target0 - m0);
  accEntry.object3d.updateMatrixWorld(true);
  return true;
}

// ---- geoFaceSnapToCornerWalls (webapp/scene.html ~15449) ----
function geoFaceSnapToCornerWalls(accEntry, P, pairTag, dWall, axisDir, side) {
  const gf = accEntry.part && Array.isArray(accEntry.part.geo_faces) ? accEntry.part.geo_faces : null;
  if (!gf || gf.length < 2) return;
  const C = pairTag && (pairTag.a === P ? pairTag.b : pairTag.a);
  if (!C || !C.object3d) return;
  const obj = accEntry.object3d;
  obj.updateMatrixWorld(true);
  const n1w = dWall.clone().normalize();
  const n2w = axisDir.clone().multiplyScalar(side).normalize();
  const wallPlane = (entry, n) => {
    const b = new THREE.Box3().setFromObject(entry.object3d);
    let m = -Infinity;
    for (let xi = 0; xi < 2; xi++) for (let yi = 0; yi < 2; yi++) for (let zi = 0; zi < 2; zi++) {
      const v = new THREE.Vector3(xi ? b.max.x : b.min.x, yi ? b.max.y : b.min.y, zi ? b.max.z : b.min.z).dot(n);
      if (v > m) m = v;
    }
    return m;
  };
  const w1 = wallPlane(P, n1w), w2 = wallPlane(C, n2w);
  const faces = gf.slice(0, 2).map(f => ({ p: new THREE.Vector3(f.x, f.y, f.z), n: new THREE.Vector3(f.nx, f.ny, f.nz).normalize() }));
  if (Math.abs(faces[0].n.dot(faces[1].n)) > 0.3) return;
  const qOrig = obj.quaternion.clone(), pOrig = obj.position.clone();
  const solve = (fA, fB) => {
    const s1 = fA.n.clone();
    const s2 = fB.n.clone().addScaledVector(s1, -s1.dot(fB.n)).normalize();
    const s3 = new THREE.Vector3().crossVectors(s1, s2);
    const t1 = n1w.clone().negate();
    const t2 = n2w.clone().negate().addScaledVector(t1, -t1.dot(n2w.clone().negate())).normalize();
    const t3 = new THREE.Vector3().crossVectors(t1, t2);
    const MS = new THREE.Matrix4().makeBasis(s1, s2, s3);
    const MT = new THREE.Matrix4().makeBasis(t1, t2, t3);
    const q = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().multiplyMatrices(MT, MS.invert()));
    obj.quaternion.copy(q); obj.position.copy(pOrig); obj.updateMatrixWorld(true);
    const RpA = fA.p.clone().applyQuaternion(q).add(obj.position);
    const RpB = fB.p.clone().applyQuaternion(q).add(obj.position);
    obj.position.addScaledVector(n1w, w1 - RpA.dot(n1w));
    obj.position.addScaledVector(n2w, w2 - RpB.dot(n2w));
    obj.updateMatrixWorld(true);
    const cen = new THREE.Box3().setFromObject(obj).getCenter(new THREE.Vector3());
    const inside = cen.dot(n1w) > w1 - 0.5 && cen.dot(n2w) > w2 - 0.5;
    return { q: q.clone(), pos: obj.position.clone(), inside, ang: q.angleTo(qOrig) };
  };
  const sols = [solve(faces[0], faces[1]), solve(faces[1], faces[0])];
  const inside = sols.filter(s => s.inside);
  let sol = null;
  if (inside.length) sol = inside.reduce((a, b) => (a.ang <= b.ang ? a : b));
  if (!sol) { obj.quaternion.copy(qOrig); obj.position.copy(pOrig); obj.updateMatrixWorld(true); return; }
  obj.quaternion.copy(sol.q); obj.position.copy(sol.pos); obj.updateMatrixWorld(true);
}

// ---- uhelnikLugAlignToSlots (webapp/scene.html ~15524-ish, viz uhelnikAutPlaceOne blok) ----
function uhelnikLugAlignToSlots(accEntry, P, pairTag, dWall, axisDir, side) {
  const C = pairTag && (pairTag.a === P ? pairTag.b : pairTag.a);
  if (!C || !C.object3d) return;
  const free = new THREE.Vector3().crossVectors(dWall, axisDir);
  if (free.lengthSq() < 0.5) return;
  free.normalize();
  const obj = accEntry.object3d;
  obj.updateMatrixWorld(true);
  const planeOf = (entry, n) => {
    const b = new THREE.Box3().setFromObject(entry.object3d);
    let m = -Infinity;
    for (let xi = 0; xi < 2; xi++) for (let yi = 0; yi < 2; yi++) for (let zi = 0; zi < 2; zi++) {
      const v = new THREE.Vector3(xi ? b.max.x : b.min.x, yi ? b.max.y : b.min.y, zi ? b.max.z : b.min.z).dot(n);
      if (v > m) m = v;
    }
    return m;
  };
  const n1 = dWall.clone().normalize(), n2 = axisDir.clone().multiplyScalar(side).normalize();
  const w1 = planeOf(P, n1), w2 = planeOf(C, n2);
  let sum = 0, cnt = 0;
  const tmp = new THREE.Vector3();
  obj.traverse(nd => {
    if (!nd.isMesh || !nd.geometry || !nd.geometry.attributes.position) return;
    const pos = nd.geometry.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      tmp.fromBufferAttribute(pos, i).applyMatrix4(nd.matrixWorld);
      if (tmp.dot(n1) < w1 - 0.05 || tmp.dot(n2) < w2 - 0.05) { sum += tmp.dot(free); cnt++; }
    }
  });
  if (!cnt) return;
  const target = new THREE.Box3().setFromObject(P.object3d).getCenter(new THREE.Vector3()).dot(free);
  const shift = target - sum / cnt;
  if (Math.abs(shift) < 0.02 || Math.abs(shift) > 6) return;
  obj.position.addScaledVector(free, shift);
  obj.updateMatrixWorld(true);
}

// ---- uhelnikAutPlaceOne (webapp/scene.html ~15524, "pose" ted PARAMETR misto global) ----
function uhelnikAutPlaceOne(accEntry, P, dWall, axisA, axisDir, L, t, side, pairTag, pose) {
  let cands = uhelnikAutPoseCandidates(accEntry, P, dWall);
  if (!cands.length) return false;
  const geoCandsUAP = cands.filter(c => accEntry.connectorsLocal[c.childFaceConnIdx].isGeoFace);
  if (geoCandsUAP.length) cands = geoCandsUAP;
  let cand = cands[0];
  if (pose && Array.isArray(pose.q) && pose.q.length === 4) {
    const F = uhelnikCornerFrameQuat(axisDir, side, dWall);
    const qRel = new THREE.Quaternion(pose.q[0], pose.q[1], pose.q[2], pose.q[3]);
    const target = F.clone().multiply(qRel);
    let pool = cands.filter(c => c.childFaceConnIdx === pose.face);
    if (!pool.length) pool = cands;
    const localToC = new THREE.Vector3(-1, 0, 0).applyQuaternion(qRel.clone().invert());
    const toC = axisDir.clone().multiplyScalar(-side);
    let bestDot = -Infinity, bestAng = Infinity;
    pool.forEach(c => {
      const d = localToC.clone().applyQuaternion(c.option.quat).dot(toC);
      const ang = c.option.quat.angleTo(target);
      if (d > bestDot + 1e-4 || (Math.abs(d - bestDot) <= 1e-4 && ang < bestAng)) { bestDot = d; bestAng = ang; cand = c; }
    });
  }
  applyFaceToFaceCandidate(cand, accEntry, P);
  if (!uhelnikAutAlignAxial(accEntry, axisA, axisDir, L, t, side)) return false;
  geoFaceSnapToCornerWalls(accEntry, P, pairTag, dWall, axisDir, side);
  uhelnikLugAlignToSlots(accEntry, P, pairTag, dWall, axisDir, side);
  return { cand };
}

// ---- cornerGeometry - spolecny vypocet geometrie rohu dvou dotykajicich se
// kolmych profilu (P="pruchozi"/stenovy, C="kolmy", axisA/axisDir/L = osa a
// delka P, mn/mx = rozsah C podel teto osy, dWall = smer od osy P ke stredu
// C). Vytazeno z uhelnikAutPlaceForPair, aby ho mohly pouzit i verifikacni/
// diagnosticke skripty (napr. mereni gap/overlap) beze zdvojeni vypoctu. ----
function cornerGeometry(profA, profB) {
  profA.object3d.updateMatrixWorld(true); profB.object3d.updateMatrixWorld(true);
  const boxA = new THREE.Box3().setFromObject(profA.object3d), boxB = new THREE.Box3().setFromObject(profB.object3d);
  let dEndA = Infinity, dEndB = Infinity;
  worldConnectorsOf(profA).forEach(cw => { if (cw.kind === "end") dEndA = Math.min(dEndA, boxB.distanceToPoint(cw.point)); });
  worldConnectorsOf(profB).forEach(cw => { if (cw.kind === "end") dEndB = Math.min(dEndB, boxA.distanceToPoint(cw.point)); });
  const P = dEndA <= dEndB ? profB : profA;
  const C = P === profA ? profB : profA;
  const endIdxs = [];
  P.connectorsLocal.forEach((cn, i) => { if (cn.kind === "end") endIdxs.push(i); });
  if (endIdxs.length !== 2) return null;
  const wP = worldConnectorsOf(P);
  const axisA = wP[endIdxs[0]].point.clone();
  const axisVecFull = wP[endIdxs[1]].point.clone().sub(axisA);
  const L = axisVecFull.length();
  if (L < 1e-6) return null;
  const axisDir = axisVecFull.clone().normalize();
  const cBox = new THREE.Box3().setFromObject(C.object3d);
  let mn = Infinity, mx = -Infinity;
  for (let xi = 0; xi < 2; xi++) for (let yi = 0; yi < 2; yi++) for (let zi = 0; zi < 2; zi++) {
    const corner = new THREE.Vector3(xi ? cBox.max.x : cBox.min.x, yi ? cBox.max.y : cBox.min.y, zi ? cBox.max.z : cBox.min.z);
    const tt = corner.sub(axisA).dot(axisDir);
    if (tt < mn) mn = tt;
    if (tt > mx) mx = tt;
  }
  const cCenter = cBox.getCenter(new THREE.Vector3());
  const tC = cCenter.clone().sub(axisA).dot(axisDir);
  const foot = axisA.clone().addScaledVector(axisDir, tC);
  const dWall = cCenter.clone().sub(foot);
  if (dWall.length() < 1e-6) return null;
  dWall.normalize();
  return { P, C, axisA, axisDir, L, mn, mx, dWall };
}

// ---- uhelnikAutPlaceForPair (webapp/scene.html ~15628, katalog-driven vyber dilu) ----
// Vraci pole vysledku (0, 1 nebo 2 umistene uhelniky - podle toho, kam se u
// koncu profilu C podel osy P vejdou, presne jako runUhelnikAut/Place All).
function uhelnikAutPlaceForPair(profA, profB, catalogTemplates) {
  if (crossSectionKey(profA.part.cross_section_mm) !== crossSectionKey(profB.part.cross_section_mm)) return [];
  const aAxis = profileLengthAxisWorld(profA), bAxis = profileLengthAxisWorld(profB);
  if (!aAxis || !bAxis) return [];
  if (Math.abs(aAxis.dot(bAxis)) > 0.1) return [];
  if (!profilesStillTouching(profA, profB, 2)) return [];
  const geo = cornerGeometry(profA, profB);
  if (!geo) return [];
  const { P, C, axisA, axisDir, L, mn, mx, dWall } = geo;
  // velikost SKUTECNEHO profilu P (uhelnikAutPart sizeNum = max(cross_section_mm))
  const sizeNum = Math.max(...(P.part.cross_section_mm || []).filter(v => v != null)) || null;
  const template = resolveBracketForSize(sizeNum, catalogTemplates);
  if (!template) return []; // presne tahle velikost v katalogu neni - preskocit par (ne spatna velikost)
  const pairTag = { a: profA, b: profB };
  const placed = [];
  [{ side: 1, t: mx }, { side: -1, t: mn }].forEach(corner => {
    const obj = freshBracketObj(template);
    const accEntry = { part: template.part, object3d: obj, connectorsLocal: template.connectorsLocal };
    const outcome = uhelnikAutPlaceOne(accEntry, P, dWall, axisA, axisDir, L, corner.t, corner.side, pairTag, template.uhelnik_pose);
    if (outcome) {
      obj.updateMatrixWorld(true);
      placed.push({
        part_id: template.meta.part_id,
        sku: template.meta.sku,
        name: template.meta.name,
        size_mm: sizeNum,
        joint: { P_role: P.role, P_idx: P.idx, C_role: C.role, C_idx: C.idx, side: corner.side },
        position: [obj.position.x, obj.position.y, obj.position.z],
        quaternion: [obj.quaternion.x, obj.quaternion.y, obj.quaternion.z, obj.quaternion.w],
        scale: [1, 1, 1],
        object3d: obj,
      });
    }
  });
  return placed;
}

// ---- findLegInternalJoints - obecna detekce vsech platnych spoju v NOZE ----
// (port hlavni smycky runUhelnikAut(), omezene na jednu "nohu" = libovolny
// seznam profilovych entries; kazdy pár se testuje presne stejnou trojici
// podminek jako zive tlacitko "⟂ Automat -> Uhelnik": kolmost os, stejny
// prurez, fyzicky dotyk).
function findLegInternalJoints(legEntries) {
  const pairs = [];
  for (let i = 0; i < legEntries.length; i++) {
    for (let j = i + 1; j < legEntries.length; j++) {
      const a = legEntries[i], b = legEntries[j];
      const aAxis = profileLengthAxisWorld(a), bAxis = profileLengthAxisWorld(b);
      if (!aAxis || !bAxis) continue;
      if (Math.abs(aAxis.dot(bAxis)) > 0.1) continue;
      if (crossSectionKey(a.part.cross_section_mm) !== crossSectionKey(b.part.cross_section_mm)) continue;
      if (!profilesStillTouching(a, b, 2)) continue;
      pairs.push([a, b]);
    }
  }
  return pairs;
}

// ---- hlavni verejne API: aplikuje uhelniky na VSECHNY vnitrni spoje jedne nohy ----
function applyUhelnikyToLeg(legEntries, bracketCatalogMeta, katalogDir) {
  const catalogTemplates = bracketCatalogMeta.map(m => makeBracketTemplate(katalogDir, m));
  const pairs = findLegInternalJoints(legEntries);
  const results = [];
  const perPair = [];
  pairs.forEach(([a, b]) => {
    const placedForPair = uhelnikAutPlaceForPair(a, b, catalogTemplates);
    perPair.push({ a: a.role, b: b.role, count: placedForPair.length });
    results.push(...placedForPair);
  });
  return {
    results,
    stats: {
      pairsChecked: legEntries.length * (legEntries.length - 1) / 2,
      pairsMatched: pairs.length,
      totalBracketsPlaced: results.length,
      perPair,
    },
  };
}

module.exports = {
  makeProfileEntry,
  makeBracketTemplate,
  freshBracketObj,
  resolveBracketForSize,
  crossSectionKey,
  profileLengthAxisWorld,
  profilesStillTouching,
  findAccessoryToProfileCandidates,
  findAccessoryToProfileCandidatesAllSpins,
  uhelnikCornerFrameQuat,
  uhelnikAutPoseCandidates,
  applyFaceToFaceCandidate,
  uhelnikAutAlignAxial,
  geoFaceSnapToCornerWalls,
  uhelnikLugAlignToSlots,
  uhelnikAutPlaceOne,
  cornerGeometry,
  uhelnikAutPlaceForPair,
  findLegInternalJoints,
  applyUhelnikyToLeg,
};
