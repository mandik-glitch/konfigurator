// Automaticke vsazeni desky (bot4, 2026-08-09) - vyclenene z app-script
// (bot14, 2026-09-03, PLAN_ROZDELENI_FRONTENDU.md). 1:1 presun, beze
// zmeny chovani. Klasicky script (ne modul), sdili globalni scope s
// app-script - musi se nacist PRED nim (viz <script src> v scene.html,
// stejne umisteni jako scene-geometry-shared.js/three-mesh-bvh.js).
// ==================== Automaticke vsazeni desky (bot4, 2026-08-09) ====================
// Robert: "ve scene mame profily a do nich se da zasunout deska PR10,
// potřebuji vyřešit funkci k doplnění desky PR10 do sceny, mezi profily
// tvořící uzavřený rám, profily by se označili a funkce použila, PR10
// správného rozměru by naskočila do drážek profilů" - upřesněno v
// konverzaci: (1) funguje i jen mezi 2 rovnoběžnými profily, ne nutně
// uzavřený rám; (2) druhý režim "položení NA profily" (uzavřený/
// polouzavřený rám, deska -2mm od vnějšího rozměru, libovolný průřez -
// na rozdíl od režimu do drážky, který cílí na "drážka 10mm" rodinu);
// (3) hloubka zásunu do drážky = 10mm (potvrzeno Robertem).
//
// v1 omezení (transparentně, ne mlčky): jen pravoúhlé uspořádání
// zarovnané na 2 kolmé světové osy, a jen VODOROVNÉ vsazení (rovina
// profilů rovnoběžná se zemí, 3. osa = Y) - svislé panely (stěny)
// nepodporovány, viz chybová hláška níže.
const GROOVE_INSERT_DEPTH_MM = 10; // hrana desky zajede 10mm pod profil (drážka 10mm rodina, PR10 tloušťka 10mm)
const TOP_LAY_CLEARANCE_MM = 2; // celková vůle po obvodu při položení navrch (1mm na stranu)
const BOARD_INSERT_PART_ID = "product_3539"; // PR10 v CATALOG (viz fetch_katalog_parts, api/app.py)

const _AXIS_DEFS = [
  { name: "x", vec: new THREE.Vector3(1, 0, 0) },
  { name: "y", vec: new THREE.Vector3(0, 1, 0) },
  { name: "z", vec: new THREE.Vector3(0, 0, 1) },
];
const _AXIS_IDX = { x: 0, y: 1, z: 2 };
function _axisVecByName(name) { return _AXIS_DEFS.find(a => a.name === name).vec; }
// Vsechna geometrie v teto appce je stavena pravouhle (viz zbytek
// sceny) - smer profilu proto vzdy prislusi jedne ze 3 svetovych os
// (prah 0.9 = max ~25 stupnu odchylka), ne libovolnemu uhlu.
function _classifyWorldAxis(dir) {
  let best = null, bestDot = 0;
  for (const a of _AXIS_DEFS) {
    const d = Math.abs(dir.dot(a.vec));
    if (d > bestDot) { bestDot = d; best = a.name; }
  }
  return bestDot >= 0.9 ? best : null;
}

// Spocita cilove rozmery/pozici desky pro vybrane profily. mode:
// "groove" (do drazky, funguje i jen pro 2 rovnobezne) | "top" (na
// profily shora, potrebuje ram ve 2 smerech). Vraci
// {ok:true, axisU,axisV,thirdAxis, lengthU,lengthV, centerU,centerV,
// thirdCenter, warnings} nebo {ok:false, error}.
function detectBoardTargetBounds(entries, mode) {
  if (entries.length < 2) return { ok: false, error: "Vyber aspoň 2 profily." };
  for (const e of entries) {
    if (e.part && e.part.is_board_material) return { ok: false, error: "Ve výběru je deska - vyber jen profily." };
    // Robert (screenshot): "nefunguje, vybral jsem 2 profily" - realny
    // profil ma DNES vzdy vic nez 2 konektory (2×"end" + 1×"mid" +
    // 4×"face", viz computeConnectorsLocal) - puvodni kontrola delky pole
    // na presne 2 byla zastarala (kopie ze starsi verze pred pridanim
    // "mid"/"face" konektoru, stejny typ bugu jako drive u smazaneho
    // "Roztahuj") a odmitala UPLNE VSECHNY profily. Spravna kontrola: presne 2
    // konektory typu "end", zbytek (mid/face) je normalni soucast kazdeho
    // profilu a nema se testovat.
    if (!e.connectorsLocal || e.connectorsLocal.filter(c => c.kind === "end").length !== 2) {
      return { ok: false, error: "Vyber jen jednoduché profily (2 konce), ne příslušenství." };
    }
  }

  const info = entries.map(e => {
    const pts = entryEndWorldPoints(e);
    const dir = pts[1].clone().sub(pts[0]).normalize();
    return { entry: e, pts, axis: _classifyWorldAxis(dir) };
  });
  if (info.some(i => !i.axis)) {
    return { ok: false, error: "Vybrané profily nejsou zarovnané na světové osy (šikmé) - nepodporováno." };
  }

  const axesUsed = Array.from(new Set(info.map(i => i.axis)));
  if (axesUsed.length > 2) {
    return { ok: false, error: "Vybrané profily leží ve 3 různých směrech - deska může ležet jen v jedné rovině." };
  }

  // ---- Jen 1 smer pritomny: 2+ rovnobeznych profilu, deska mezi ne ----
  if (axesUsed.length === 1) {
    if (mode === "top") {
      return { ok: false, error: "Režim „Na profily“ potřebuje profily ve 2 směrech (rám), ne jen rovnoběžné." };
    }
    const runAxis = axesUsed[0];
    const runIdx = _AXIS_IDX[runAxis];
    const otherAxes = _AXIS_DEFS.map(a => a.name).filter(n => n !== runAxis);
    const centers = info.map(i => i.pts[0].clone().add(i.pts[1]).multiplyScalar(0.5));
    const spread = (name) => {
      const idx = _AXIS_IDX[name];
      const vals = centers.map(c => c.getComponent(idx));
      return Math.max(...vals) - Math.min(...vals);
    };
    // "mezerova" osa = ta ze zbylych 2 svetovych os, na ktere maji stredy
    // vybranych profilu vetsi rozptyl (tzn. skutecne rozestoupene, ne
    // shodou souradnic na te druhe ose).
    const gapAxis = spread(otherAxes[0]) >= spread(otherAxes[1]) ? otherAxes[0] : otherAxes[1];
    const thirdAxis = otherAxes.find(n => n !== gapAxis);
    if (thirdAxis !== "y") {
      return { ok: false, error: "Tahle verze podporuje jen vodorovné vsazení (deska rovnoběžná se zemí) - svislé panely zatím ne." };
    }
    const gapIdx = _AXIS_IDX[gapAxis];

    const sorted = info.slice().sort((a, b) => a.pts[0].getComponent(gapIdx) - b.pts[0].getComponent(gapIdx));
    const left = sorted[0], right = sorted[sorted.length - 1];
    const leftHalf = crossAxisHalfWidthTowardDirection(left.entry.connectorsLocal, left.entry.object3d.quaternion, _axisVecByName(gapAxis));
    const rightHalf = crossAxisHalfWidthTowardDirection(right.entry.connectorsLocal, right.entry.object3d.quaternion, _axisVecByName(gapAxis));
    const leftPos = left.pts[0].getComponent(gapIdx);
    const rightPos = right.pts[0].getComponent(gapIdx);
    const gap = (rightPos - rightHalf) - (leftPos + leftHalf);
    if (gap <= 0) return { ok: false, error: "Vybrané profily se překrývají nebo se dotýkají - není kam desku vložit." };

    // delka podel run osy = prunik (overlap) rozsahu VSECH vybranych
    // profilu - deska nikdy nepresahne fyzicky konec zadneho z nich.
    let runMin = -Infinity, runMax = Infinity;
    for (const i of info) {
      const a = i.pts[0].getComponent(runIdx), b = i.pts[1].getComponent(runIdx);
      runMin = Math.max(runMin, Math.min(a, b));
      runMax = Math.min(runMax, Math.max(a, b));
    }
    if (runMax <= runMin) return { ok: false, error: "Vybrané profily se podél délky nepřekrývají." };

    const thirdVals = info.map(i => i.pts[0].getComponent(_AXIS_IDX[thirdAxis]));
    return {
      ok: true,
      axisU: runAxis, axisV: gapAxis, thirdAxis,
      lengthU: runMax - runMin,
      lengthV: gap + 2 * GROOVE_INSERT_DEPTH_MM,
      centerU: (runMin + runMax) / 2,
      centerV: (leftPos + leftHalf + rightPos - rightHalf) / 2,
      thirdCenter: (Math.min(...thirdVals) + Math.max(...thirdVals)) / 2,
      warnings: [],
    };
  }

  // ---- Oba smery pritomne: ram (uzavreny, otevreny nebo polouzavreny) ----
  const [axisU, axisV] = axesUsed;
  const idxU = _AXIS_IDX[axisU], idxV = _AXIS_IDX[axisV];
  const thirdAxis = _AXIS_DEFS.map(a => a.name).find(n => n !== axisU && n !== axisV);
  if (thirdAxis !== "y") {
    return { ok: false, error: "Tahle verze podporuje jen vodorovné rámy (rovina rámu rovnoběžná se zemí) - svislé panely zatím ne." };
  }
  const thirdIdx = _AXIS_IDX[thirdAxis];

  // Vnejsi obalka (min/max) v obou osach - kazda hranice je urcena
  // KOLMYMI kusy (ty, co bezi podel druhe osy), jejich vlastnim
  // pulsirkovym prurezem v teto ose (viz crossAxisHalfWidthTowardDirection).
  // Vnitrni vyztuhy/T-podpery se do min/max prirozene nepromitnou (nejsou
  // na kraji), i kdyz jsou soucasti vyberu.
  let minU = Infinity, maxU = -Infinity, minUHalf = 0, maxUHalf = 0;
  let minV = Infinity, maxV = -Infinity, minVHalf = 0, maxVHalf = 0;
  const thirdVals = [];
  for (const i of info) {
    thirdVals.push(i.pts[0].getComponent(thirdIdx));
    if (i.axis === axisU) {
      const u0 = i.pts[0].getComponent(idxU), u1 = i.pts[1].getComponent(idxU);
      minU = Math.min(minU, u0, u1); maxU = Math.max(maxU, u0, u1);
      const half = crossAxisHalfWidthTowardDirection(i.entry.connectorsLocal, i.entry.object3d.quaternion, _axisVecByName(axisV));
      const vCenter = i.pts[0].getComponent(idxV);
      if (vCenter - half < minV) { minV = vCenter - half; minVHalf = half; }
      if (vCenter + half > maxV) { maxV = vCenter + half; maxVHalf = half; }
    } else {
      const v0 = i.pts[0].getComponent(idxV), v1 = i.pts[1].getComponent(idxV);
      minV = Math.min(minV, v0, v1); maxV = Math.max(maxV, v0, v1);
      const half = crossAxisHalfWidthTowardDirection(i.entry.connectorsLocal, i.entry.object3d.quaternion, _axisVecByName(axisU));
      const uCenter = i.pts[0].getComponent(idxU);
      if (uCenter - half < minU) { minU = uCenter - half; minUHalf = half; }
      if (uCenter + half > maxU) { maxU = uCenter + half; maxUHalf = half; }
    }
  }

  // Lehka (jen informativni, nikdy neblokujici - Robert potvrdil, ze i
  // neuplny/otevreny ram je platny vstup) validace uzavrenosti: konec
  // profilu, ktery se nedotyka zadneho jineho vybraneho profilu.
  const warnings = [];
  for (let i = 0; i < info.length; i++) {
    for (const end of [0, 1]) {
      const p = info[i].pts[end];
      const touches = info.some((j, ji) => ji !== i &&
        (j.pts[0].distanceTo(p) < RECT_FRAME_TOUCH_EPS || j.pts[1].distanceTo(p) < RECT_FRAME_TOUCH_EPS));
      if (!touches) {
        warnings.push("Profil „" + ((info[i].entry.part && info[i].entry.part.name) || "?") + "“ má volný konec - strana rámu může být otevřená.");
      }
    }
  }

  let lengthU, lengthV;
  if (mode === "top") {
    lengthU = (maxU - minU) - TOP_LAY_CLEARANCE_MM;
    lengthV = (maxV - minV) - TOP_LAY_CLEARANCE_MM;
  } else {
    const innerMinU = minU + 2 * minUHalf, innerMaxU = maxU - 2 * maxUHalf;
    const innerMinV = minV + 2 * minVHalf, innerMaxV = maxV - 2 * maxVHalf;
    lengthU = (innerMaxU - innerMinU) + 2 * GROOVE_INSERT_DEPTH_MM;
    lengthV = (innerMaxV - innerMinV) + 2 * GROOVE_INSERT_DEPTH_MM;
  }
  if (lengthU <= 0 || lengthV <= 0) {
    return { ok: false, error: "Vypočtený rozměr desky vyšel nulový nebo záporný - zkontroluj výběr." };
  }

  return {
    ok: true, axisU, axisV, thirdAxis,
    lengthU, lengthV,
    centerU: (minU + maxU) / 2, centerV: (minV + maxV) / 2,
    thirdCenter: (Math.min(...thirdVals) + Math.max(...thirdVals)) / 2,
    warnings,
  };
}

function insertBoardIntoSelection(mode) {
  expandSelectionToGroups();
  const entries = Array.from(currentJoinSelectionUnion());
  const bounds = detectBoardTargetBounds(entries, mode);
  if (!bounds.ok) { showJoinToast(bounds.error); return; }
  const p = CATALOG.find(x => x.id === BOARD_INSERT_PART_ID);
  if (!p) { showJoinToast("Deska PR10 není v katalogu k dispozici."); return; }
  loader.load(p.file, (gltf) => {
    const obj = gltf.scene;
    applyPartMaterial(obj, p.layer, p.color_hex);
    // connectorsLocal se pocita PRED nastavenim quaternionu (stejne
    // poradi jako placeAtOrigin) - jsou tedy v surovem/nenatocenem
    // lokalnim prostoru GLB.
    const connectorsLocal = computeBoardEdgeConnectors(obj);
    obj.position.set(0, 0, 0);
    obj.quaternion.copy(baseQuaternion(0, "horizontal"));
    obj.updateMatrixWorld(true);
    const entry = { part: p, object3d: obj, connectorsLocal, customColor: p.color_hex || undefined };

    const rawWidth = connectorsLocal[0].point.distanceTo(connectorsLocal[1].point);
    const rawHeight = connectorsLocal[2].point.distanceTo(connectorsLocal[3].point);
    // Zjisti, ktery ze 2 hranovych paru (sirka [0,1] / vyska [2,3]) po
    // aplikaci quaternionu lezi podel axisU, aby se spravny cilovy
    // rozmer priradil spravne ose.
    const widthWorldDir = connectorsLocal[0].point.clone().sub(connectorsLocal[1].point).normalize()
      .applyQuaternion(obj.quaternion).normalize();
    const widthAlongU = Math.abs(widthWorldDir.dot(_axisVecByName(bounds.axisU))) > 0.5;
    const targetWidth = widthAlongU ? bounds.lengthU : bounds.lengthV;
    const targetHeight = widthAlongU ? bounds.lengthV : bounds.lengthU;

    applyLengthScale(entry, targetWidth / rawWidth, 0, 0, 1);
    applyLengthScale(entry, targetHeight / rawHeight, 2, 2, 3);

    // applyLengthScale kotvi kazde skalovani na jinem pevnem bode (fixConnIdx)
    // - misto slozite pivot-algebry presunout az na konci CELY objekt tak,
    // aby jeho aktualni (uz spravne zeskalovany) svetovy stred bboxu sedel
    // presne na spocitany cilovy stred.
    const box = new THREE.Box3().setFromObject(obj);
    const curCenter = new THREE.Vector3(); box.getCenter(curCenter);
    const targetCenter = new THREE.Vector3();
    targetCenter.setComponent(_AXIS_IDX[bounds.axisU], bounds.centerU);
    targetCenter.setComponent(_AXIS_IDX[bounds.axisV], bounds.centerV);
    targetCenter.setComponent(_AXIS_IDX[bounds.thirdAxis], bounds.thirdCenter);
    obj.position.add(targetCenter.clone().sub(curCenter));
    obj.updateMatrixWorld(true);
    obj.userData.basePos = obj.position.clone();

    scene.add(obj);
    placed.push(entry);
    rebuildOccupiedConnectors();
    refreshEndpointMarkers(); refreshDimLabels();
    refreshSummary();
    const baseMsg = mode === "top" ? "Deska položena na profily." : "Deska vsazena do drážek.";
    showJoinToast(bounds.warnings.length ? baseMsg + " " + bounds.warnings[0] : baseMsg);
  }, undefined, (err) => { console.error("GLB load failed for board insert", err); alert("Nepodařilo se načíst desku."); });
}

document.getElementById("btnInsertBoardGroove").addEventListener("click", () => insertBoardIntoSelection("groove"));
document.getElementById("btnInsertBoardTop").addEventListener("click", () => insertBoardIntoSelection("top"));
