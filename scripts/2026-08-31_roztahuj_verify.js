// Overeni "Roztahuj" (bot16, 2026-08-31) - zivá funkce v webapp/scene.html:
// chyt myší vodorovnou pricku, tazenim nahoru/dolu se DVE navazujici svisle
// nohy delkove prizpusobi (viz komentar v scene.html u "==== Roztahuj ====").
//
// Tenhle skript NEOTESTOVAVA skutecne mysi udalosti (nejde je v tomhle
// prostredi simulovat - viz zadani) - misto toho:
//  1) postavi realnou geometrii (Object_7.glb, 30x30 profil) presne podle
//     buildVyrezAtDepth(326) ze scripts/tmp_2026-08-30_build_depth_variants_both.js
//     (bez pozadavku na ten skript primo, aby se predeslo jeho vedlejsim
//     efektum pri require - konstanty/vzorec zkopirovany 1:1),
//  2) reimplementuje (kopie 1:1 z scene.html) roztahujProfileEndIdxs/
//     roztahujFindPartners/roztahujComputeForY + male pomocne funkce
//     (crossSectionKey/profileLengthAxisWorld/profilesStillTouching), a
//  3) overi, ze detekce najde PRAVE 2 partnery (sloupek-pred-podbehem +
//     zadni-svislice-nad-zarezem, NE predni-svislice - ta je jen "bytostne"
//     dotcena vprostred sve delky), a ze matematika protazeni pro 2 ruzne
//     tazene Y pricky da spravne delky/pozice obou noh.
//
// Spusteni: `npm install` v ROOTU repa (ne ve scripts/), pak
//   node scripts/2026-08-31_roztahuj_verify.js

const THREE = require("three");
const { parseGlbMesh } = require("./2026-08-19_glb_real_geometry.js");
const { computeConnectorsLocal, worldConnectorsOf, isProfilePart, applyLengthScale, roztahujComputeForY } =
  require("../webapp/js/scene-geometry-shared.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const OBJ7 = KAT + "Object_7.glb";

// ---- 1) geometrie 1:1 podle buildVyrezAtDepth(326) ----
const T = 30, H = 1180, CAP_H = 260, CUTOUT_H = 395;
const CAP_OFFSET_FROM_WALL = 70;
const WALL_CLEARANCE_ARCH = 349 - 225; // 124mm
const D = 326;

function part(xCenter, yCenter, lengthY, vertical, zCenter, role) {
  return {
    position: [xCenter, yCenter, zCenter],
    quaternion: vertical ? [0, 0, 0, 1] : [0, 0, -0.707107, 0.707107],
    scale: [1, lengthY / 1000, 1],
    role,
  };
}

const zCenter = T / 2;
const colRight = D - WALL_CLEARANCE_ARCH, colLeft = colRight - T;
const partSloupek = part((colLeft + colRight) / 2, CUTOUT_H / 2, CUTOUT_H, true, zCenter, "sloupek-pred-podbehem");
const closeLeft = T, closeRight = D - T, closeLen = closeRight - closeLeft;
const partPricka = part((closeLeft + closeRight) / 2, CUTOUT_H + T / 2, closeLen, false, zCenter, "pricka-uzavreni-vyrezu");
const upperH = (H - CAP_H) - CUTOUT_H;
const partZadni = part(D - T / 2, CUTOUT_H + upperH / 2, upperH, true, zCenter, "zadni-svislice-nad-zarezem");
const partPredni = part(T / 2, H / 2, H, true, zCenter, "predni-svislice");

// ---- Node "entry" builder - stejna konvence jako zbytek projektu
// (connectorsLocal se pocita PRED nastavenim finalni pozice/rotace/skaly,
// viz KOMPONENTY_EUROBOXY.md a komentar u loadCustomShapePartEntry). ----
function mkEntry(p, lengthMm) {
  const obj = parseGlbMesh(OBJ7);
  const connectorsLocal = computeConnectorsLocal(obj, {});
  obj.position.set(...p.position);
  obj.quaternion.set(...p.quaternion);
  obj.scale.set(...p.scale);
  obj.updateMatrixWorld(true);
  return { part: { cross_section_mm: [30, 30], length_mm: lengthMm }, object3d: obj, connectorsLocal, role: p.role };
}

const crossbarEntry = mkEntry(partPricka, closeLen);
const sloupekEntry = mkEntry(partSloupek, CUTOUT_H);
const zadniEntry = mkEntry(partZadni, upperH);
const predniEntry = mkEntry(partPredni, H);
const placed = [crossbarEntry, sloupekEntry, zadniEntry, predniEntry];

// ---- 2) kopie pomocnych funkci ze scene.html (1:1 logika) ----
function crossSectionKey(cross_section_mm) {
  if (!cross_section_mm || cross_section_mm[0] == null || cross_section_mm[1] == null) return null;
  return Math.round(cross_section_mm[0]) + "x" + Math.round(cross_section_mm[1]);
}
function profileLengthAxisWorld(entry) {
  const endIdxs = [];
  entry.connectorsLocal.forEach((c, i) => { if (c.kind === "end") endIdxs.push(i); });
  if (endIdxs.length !== 2) return null;
  const w = worldConnectorsOf(entry);
  return w[endIdxs[1]].point.clone().sub(w[endIdxs[0]].point).normalize();
}
function profilesStillTouching(a, b, epsMm) {
  a.object3d.updateMatrixWorld(true);
  b.object3d.updateMatrixWorld(true);
  const boxA = new THREE.Box3().setFromObject(a.object3d);
  const boxB = new THREE.Box3().setFromObject(b.object3d);
  if (boxA.isEmpty() || boxB.isEmpty()) return false;
  boxA.expandByScalar(epsMm != null ? epsMm : 2);
  return boxA.intersectsBox(boxB);
}
const RECT_FRAME_TOUCH_EPS = 0.75;

function roztahujProfileEndIdxs(entry) {
  if (!entry || !entry.connectorsLocal) return null;
  const idxs = [];
  entry.connectorsLocal.forEach((c, i) => { if (c.kind === "end") idxs.push(i); });
  return idxs.length === 2 ? idxs : null;
}

const ROZTAHUJ_SEAM_EPS_MM = 2;

function roztahujFindPartners(crossbarEntry) {
  const crossEndIdxs = roztahujProfileEndIdxs(crossbarEntry);
  if (!crossEndIdxs) return { error: "no 2 ends" };
  const upVec = new THREE.Vector3(0, 1, 0);
  const crossAxis = profileLengthAxisWorld(crossbarEntry);
  if (!crossAxis) return { error: "no axis" };
  if (Math.abs(crossAxis.dot(upVec)) > 0.5) return { error: "crossbar is vertical" };
  const crossKey = crossSectionKey(crossbarEntry.part && crossbarEntry.part.cross_section_mm);
  if (!crossKey) return { error: "no cross section" };
  const Tloc = Math.max(...(crossbarEntry.part.cross_section_mm || []).filter(v => v != null));
  if (!Tloc) return { error: "no thickness" };
  crossbarEntry.object3d.updateMatrixWorld(true);
  const crossY = crossbarEntry.object3d.position.y;
  const seamYs = [crossY - Tloc / 2, crossY + Tloc / 2];

  const found = [];
  placed.forEach(cand => {
    if (cand === crossbarEntry) return;
    if (!cand.part || !isProfilePart(cand.part)) return;
    if (crossSectionKey(cand.part.cross_section_mm) !== crossKey) return;
    const candAxis = profileLengthAxisWorld(cand);
    if (!candAxis || Math.abs(candAxis.dot(upVec)) < 0.9) return;
    if (!profilesStillTouching(crossbarEntry, cand, RECT_FRAME_TOUCH_EPS + 1)) return;
    const endIdxs = roztahujProfileEndIdxs(cand);
    if (!endIdxs) return;
    const w = worldConnectorsOf(cand);
    const wPts = endIdxs.map(i => w[i]);
    let bestDiff = Infinity, bestLocalIdx = -1;
    wPts.forEach((wp, i) => {
      seamYs.forEach(seamY => {
        const diff = Math.abs(wp.point.y - seamY);
        if (diff < bestDiff) { bestDiff = diff; bestLocalIdx = endIdxs[i]; }
      });
    });
    if (bestDiff > ROZTAHUJ_SEAM_EPS_MM) return;
    const nearIdx = bestLocalIdx;
    const farIdx = endIdxs.find(i => i !== nearIdx);
    const nearY = w[nearIdx].point.y;
    const farY = w[farIdx].point.y;
    found.push({
      entry: cand, role: cand.role,
      endIdxA: endIdxs[0], endIdxB: endIdxs[1],
      farIdx, farY,
      delta: nearY - crossY,
      sign: farY - nearY >= 0 ? 1 : -1,
      localLen: cand.connectorsLocal[endIdxs[0]].point.distanceTo(cand.connectorsLocal[endIdxs[1]].point),
    });
  });

  if (found.length !== 2) return { error: `found ${found.length} partners, expected 2`, found };
  return { ok: true, verticals: found, T: Tloc };
}

// roztahujComputeForY (cisty numericky vypocet) NENI kopirovan sem - je
// JEDINA implementace v webapp/js/scene-geometry-shared.js (require nahore),
// pouzita beze zmeny zivou scenou i timhle overovacim skriptem.

// ---- 3) TESTY ----
let failures = 0;
function check(label, cond, detail) {
  if (cond) { console.log(`  OK   ${label}`); }
  else { console.log(`  FAIL ${label}${detail ? " -- " + detail : ""}`); failures++; }
}

console.log(`=== Roztahuj verify - buildVyrezAtDepth(${D}) ===`);
console.log("crossbar (pricka) Y stred =", crossbarEntry.object3d.position.y, "X range ~", closeLeft, "-", closeRight);

const res = roztahujFindPartners(crossbarEntry);
console.log("\n--- Detekce partneru ---");
if (!res.ok) {
  console.log("  DETEKCE SELHALA:", res.error);
  failures++;
} else {
  const roles = res.verticals.map(v => v.role).sort();
  check("nalezeny presne 2 partneri", res.verticals.length === 2, JSON.stringify(roles));
  check("partneri jsou sloupek-pred-podbehem + zadni-svislice-nad-zarezem (NE predni-svislice)",
    roles.join(",") === "sloupek-pred-podbehem,zadni-svislice-nad-zarezem", JSON.stringify(roles));
  check("predni-svislice NENI mezi partnery (bytostny dotyk vprostred delky)",
    !res.verticals.some(v => v.role === "predni-svislice"));
  check("T (tloustka prurezu) = 30", res.T === 30, res.T);

  console.log("\n--- Pocatecni stav kazdeho partnera ---");
  res.verticals.forEach(v => {
    console.log(`  ${v.role}: farY=${v.farY.toFixed(2)} delta=${v.delta.toFixed(2)} sign=${v.sign} localLen=${v.localLen.toFixed(2)}`);
  });
  const sloupek = res.verticals.find(v => v.role === "sloupek-pred-podbehem");
  const zadni = res.verticals.find(v => v.role === "zadni-svislice-nad-zarezem");
  check("sloupek delta ~ -15 (crossbar sedi NA jeho top koncem, T/2 pod stredem pricky)",
    Math.abs(sloupek.delta - (-T / 2)) < 0.6, sloupek.delta);
  check("zadni-svislice delta ~ -15 (jeji bottom konec u sevu, stejny sev jako sloupek)",
    Math.abs(zadni.delta - (-T / 2)) < 0.6, zadni.delta);
  check("sloupek farY = 0 (jeho SPODNI konec, u podlahy, zustava fixni)", Math.abs(sloupek.farY - 0) < 0.05, sloupek.farY);
  check("zadni-svislice farY = 920 (jeji HORNI konec zustava fixni)", Math.abs(zadni.farY - 920) < 0.05, zadni.farY);

  console.log("\n--- Matematika protazeni (2 ruzne tazene Y) ---");
  // Test A: posun pricky o +50mm nahoru (crossY 410 -> 460)
  {
    const r = roztahujComputeForY(460, res.verticals, 30, 3000);
    console.log("  crossY pozadovano=460 -> aplikovano=", r.crossY.toFixed(2));
    check("crossY neomezeno (v rozsahu) = presne 460", Math.abs(r.crossY - 460) < 1e-6, r.crossY);
    const legSloupek = r.legs[res.verticals.indexOf(sloupek)];
    const legZadni = r.legs[res.verticals.indexOf(zadni)];
    // sloupek: nearY=crossY+delta=460-15=445, far=0 => delka=445
    check("sloupek nova delka = 445 (460 - 15 - 0)", Math.abs(legSloupek.length - 445) < 0.05, legSloupek.length);
    // zadni: nearY=460-15=445, far=920 => delka=920-445=475
    check("zadni-svislice nova delka = 475 (920 - 445)", Math.abs(legZadni.length - 475) < 0.05, legZadni.length);

    // aplikuj skutecne (applyLengthScale) a over VYSLEDNOU SVETOVOU geometrii
    const scaleSloupek = legSloupek.length / sloupek.localLen;
    applyLengthScale(sloupek.entry, scaleSloupek, sloupek.farIdx, sloupek.endIdxA, sloupek.endIdxB);
    const wSloupek = worldConnectorsOf(sloupek.entry);
    const farPt = wSloupek[sloupek.farIdx].point, nearPt = wSloupek[endOther(sloupek)].point;
    check("sloupek far konec zustal na Y=0 po applyLengthScale", Math.abs(farPt.y - 0) < 0.05, farPt.y);
    check("sloupek near konec je na Y=445 po applyLengthScale", Math.abs(nearPt.y - 445) < 0.05, nearPt.y);
    check("sloupek X/Z se nezmenily (jen delka/Y)", Math.abs(farPt.x - nearPt.x) < 0.05 && Math.abs(farPt.z - nearPt.z) < 0.05);

    const scaleZadni = legZadni.length / zadni.localLen;
    applyLengthScale(zadni.entry, scaleZadni, zadni.farIdx, zadni.endIdxA, zadni.endIdxB);
    const wZadni = worldConnectorsOf(zadni.entry);
    const farPtZ = wZadni[zadni.farIdx].point, nearPtZ = wZadni[endOther(zadni)].point;
    check("zadni-svislice far konec zustal na Y=920", Math.abs(farPtZ.y - 920) < 0.05, farPtZ.y);
    check("zadni-svislice near konec je na Y=445", Math.abs(nearPtZ.y - 445) < 0.05, nearPtZ.y);
  }

  // Test B: posun pricky o -80mm dolu (crossY 410 -> 330), pocitano od PUVODNIHO stavu
  // (novy vypocet nad puvodnimi farY/delta - drag start hodnoty se nemeni behem tazeni).
  {
    const r = roztahujComputeForY(330, res.verticals, 30, 3000);
    console.log("\n  crossY pozadovano=330 -> aplikovano=", r.crossY.toFixed(2));
    check("crossY = 330 (v rozsahu)", Math.abs(r.crossY - 330) < 1e-6, r.crossY);
    const legSloupek = r.legs[res.verticals.indexOf(sloupek)];
    const legZadni = r.legs[res.verticals.indexOf(zadni)];
    // sloupek: nearY=330-15=315, far=0 => delka=315
    check("sloupek nova delka = 315 (330 - 15 - 0)", Math.abs(legSloupek.length - 315) < 0.05, legSloupek.length);
    // zadni: nearY=315, far=920 => delka=605
    check("zadni-svislice nova delka = 605 (920 - 315)", Math.abs(legZadni.length - 605) < 0.05, legZadni.length);
  }

  // Test C: klamp - tazeni pricky tak daleko dolu, ze by sloupek vysel <30mm
  {
    // sloupek delka 30 => nearY = 0 + 30 = 30 => crossY = nearY - delta = 30 - (-15) = 45
    const r = roztahujComputeForY(-500, res.verticals, 30, 3000); // extremni pozadavek daleko pod povolene minimum
    console.log("\n  crossY pozadovano=-500 (extremni) -> clamped=", r.crossY.toFixed(2));
    check("crossY je CLAMPNUTO (ne -500)", r.crossY > -500, r.crossY);
    const legSloupek = r.legs[res.verticals.indexOf(sloupek)];
    check("sloupek delka clampnuta na minimum 30mm (nikdy zaporna/nulova)", Math.abs(legSloupek.length - 30) < 0.05, legSloupek.length);
    check("crossY po klampu = 45 (30 - (-15))", Math.abs(r.crossY - 45) < 0.05, r.crossY);
  }
}

function endOther(v) { return v.endIdxA === v.farIdx ? v.endIdxB : v.endIdxA; }

console.log(`\n=== VYSLEDEK: ${failures === 0 ? "VSECHNY TESTY PROSLY" : failures + " TESTU SELHALO"} ===`);
process.exit(failures === 0 ? 0 : 1);
