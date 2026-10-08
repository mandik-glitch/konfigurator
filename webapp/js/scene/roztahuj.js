// ==================== "Roztahuj" - zivé protazeni pricky + naslednych
// svislych noh (Robert, 2026-08-31, doslovne): "funkci protažení zadní
// nohy (členité nohy) dolů/nahoru a návazně s tím posun příčky a
// zkrácení/natažení spodní zadní nohy chci mít jako živou funkci v
// ručním režimu scény. pro všechny typy nohou profil 30x30, 40x40...
// aplikuj to na tlačítko Roztahuj (původní funkci toho tlačítka smaž)
// chytnu myší právě tu příčku, budu pohybovat nahoru dolu a s tím se
// budou ty profily nohy délkově přizpůsobovat."
//
// DULEZITE (transparentne, at to Robert vi): tlacitko "Roztahuj" s PUVODNI
// (jinou) funkci uz bylo jednou SMAZANO (viz komentar u RECT_FRAME_TOUCH_EPS,
// cca radek 11260: "puvodne vznikly pro tlacitko Roztahuj (smazano, Robert
// 2026-08-22 [remove-fn])") - v dobe tohoto zadani uz v kodu ZADNE tlacitko
// "Roztahuj" nebylo. Tohle je tedy NOVE tlacitko se stejnym jmenem a UPLNE
// JINOU funkci, ne navrat/oprava puvodniho.
//
// Obecny geometricky vzor (viz KOMPONENTY_EUROBOXY.md "Uzavreni vyrezove
// nohy" + PRAVIDLA_SPOJU.md "cela plocha cela"): vodorovna "pricka" (profil)
// dosedá jednou stranou/koncem na HORNI konec jedne svisle nohy (cap-styl)
// a druhym koncem se BOCNI plochou dotyka DALSI svisle nohy (T-styl) - vsechny
// 3 dily STEJNEHO prurezu (30x30 nebo 40x40, detekovano za behu z
// cross_section_mm, nikdy hardcoded). Tazenim pricky nahoru/dolu (jen
// svetova osa Y - X/Z zustavaji fixni) se OBE nohy delkove prizpusobi:
// kazda drzi svuj VZDALENY konec pevne na miste, BLIZKY konec ("sev" u
// pricky) sleduje novou vysku pricky.
//
// Detekce je GENERICKA, zadne hardcodovane nazvy/role dilu (na rozdil od
// scratch skriptu scripts/tmp_2026-08-30_build_depth_variants_both.js,
// jehoz "role" retezce - sloupek-pred-podbehem/pricka-uzavreni-vyrezu/
// zadni-svislice-nad-zarezem - jsou jen bookkeeping toho skriptu, appka je
// nikdy nevidi): pro kazdy jiny umisteny profil stejneho prurezu s
// KOLMOU (skoro presne svislou, dot s (0,1,0) > 0.9) delkovou osou se
// overi, jestli nektery jeho koncovy ("end") bod lezi (v ramci tolerance)
// na "sevu" pricky (spodni NEBO horni plocha pricky podle jeji tloustky T)
// A soucasne se s prickou fyzicky dotyka (profilesStillTouching, stejna
// funkce jako pouziva zbytek appky pro "jeste se dotyka?"). Takovy profil
// je "hnany" partner. Profil dotceny jen VPROSTRED sve delky (zadny konec
// u sevu - napr. plny sloupek, kolem ktereho pricka jen prochazi) timhle
// testem projde jako NE-partner automaticky, beze zvlastniho rozlisovani
// cap-styl / T-styl - matematika protazeni je pro oba styly STEJNA (viz
// roztahujComputeForY nize), rozdil je jen v tom, na ktere strane sevu
// (+-T/2) dany konec lezi, a to se meri primo z aktualni geometrie, ne
// z pevneho predpokladu.
const ROZTAHUJ_MIN_LEN_MM = 30, ROZTAHUJ_MAX_LEN_MM = 3000; // stejny rozsah jako bezne protazeni oranzovou sipkou (viz DRAG_MIN/MAX u dragState)
const ROZTAHUJ_SEAM_EPS_MM = 2; // tolerance "konec profilu lezi na sevu pricky" (o neco volnejsi nez RECT_FRAME_TOUCH_EPS - realna geometrie, viz KOMPONENTY_EUROBOXY.md)

let roztahujMode = false;
let roztahujDragState = null; // {crossbar, startY, axisState, initialAlong, verticals:[...], moved, downX, downY}
const btnRoztahuj = document.getElementById("btnRoztahuj");

function roztahujProfileEndIdxs(entry) {
  if (!entry || !entry.connectorsLocal) return null;
  const idxs = [];
  entry.connectorsLocal.forEach((c, i) => { if (c.kind === "end") idxs.push(i); });
  return idxs.length === 2 ? idxs : null;
}

// Najde presne 2 "hnane" svisle partnery pricky (crossbarEntry) - viz
// komentar k celemu bloku vyse pro definici. Cisty geometricky test nad
// AKTUALNIM stavem sceny (`placed`), zadne postranni efekty. Vraci
// {ok:true, verticals:[{entry,endIdxA,endIdxB,farIdx,farY,delta,sign,localLen}], T}
// nebo {error}.
function roztahujFindPartners(crossbarEntry) {
  const crossEndIdxs = roztahujProfileEndIdxs(crossbarEntry);
  if (!crossEndIdxs) return { error: "Roztahuj: vyber jednoduchý profil (2 konce), ne příslušenství." };
  const upVec = new THREE.Vector3(0, 1, 0);
  const crossAxis = profileLengthAxisWorld(crossbarEntry);
  if (!crossAxis) return { error: "Roztahuj: nepodařilo se určit délkovou osu vybraného profilu." };
  if (Math.abs(crossAxis.dot(upVec)) > 0.5) {
    return { error: "Roztahuj: vybraný profil je svislý - chyť vodorovnou příčku, ne nohu." };
  }
  const crossKey = crossSectionKey(crossbarEntry.part && crossbarEntry.part.cross_section_mm);
  if (!crossKey) return { error: "Roztahuj: vybraný profil nemá platný průřez." };
  const T = Math.max(...(crossbarEntry.part.cross_section_mm || []).filter(v => v != null));
  if (!T) return { error: "Roztahuj: vybraný profil nemá platnou tloušťku průřezu." };
  crossbarEntry.object3d.updateMatrixWorld(true);
  const crossY = crossbarEntry.object3d.position.y;
  const seamYs = [crossY - T / 2, crossY + T / 2]; // spodni / horni plocha pricky

  const found = [];
  placed.forEach(cand => {
    if (cand === crossbarEntry) return;
    if (!cand.part || !isProfilePart(cand.part)) return;
    if (crossSectionKey(cand.part.cross_section_mm) !== crossKey) return; // jen STEJNY prurez (30x30/40x40...)
    const candAxis = profileLengthAxisWorld(cand);
    if (!candAxis || Math.abs(candAxis.dot(upVec)) < 0.9) return; // jen skoro presne svisle profily
    if (!profilesStillTouching(crossbarEntry, cand, RECT_FRAME_TOUCH_EPS + 1)) return;
    const endIdxs = roztahujProfileEndIdxs(cand);
    if (!endIdxs) return;
    const w = worldConnectorsOf(cand);
    const wPts = endIdxs.map(i => w[i]);
    // ktery ze 2 koncu (pokud vubec nejaky) lezi na sevu pricky?
    let bestDiff = Infinity, bestLocalIdx = -1;
    wPts.forEach((wp, i) => {
      seamYs.forEach(seamY => {
        const diff = Math.abs(wp.point.y - seamY);
        if (diff < bestDiff) { bestDiff = diff; bestLocalIdx = endIdxs[i]; }
      });
    });
    if (bestDiff > ROZTAHUJ_SEAM_EPS_MM) return; // zadny konec u sevu = "bytostny" dotyk vprostred delky, mimo rozsah teto funkce
    const nearIdx = bestLocalIdx;
    const farIdx = endIdxs.find(i => i !== nearIdx);
    const nearY = w[nearIdx].point.y;
    const farY = w[farIdx].point.y;
    found.push({
      entry: cand,
      endIdxA: endIdxs[0], endIdxB: endIdxs[1],
      farIdx,
      farY,
      delta: nearY - crossY,                 // konstantni odsazeni ("sev" - crossY), typicky +-T/2
      sign: farY - nearY >= 0 ? 1 : -1,       // smer, kterym od sevu lezi VZDALENY konec
      localLen: cand.connectorsLocal[endIdxs[0]].point.distanceTo(cand.connectorsLocal[endIdxs[1]].point),
    });
  });

  if (found.length !== 2) {
    return { error: `Roztahuj: u vybrané příčky nalezeno ${found.length} sousedních svislých profilů stejného průřezu u jejího švu (potřeba přesně 2).` };
  }
  return { ok: true, verticals: found, T };
}

// POZOR: cisty numericky vypocet ("dana Y pricky -> nova delka/pozice
// obou noh, s clampem") NENI definovan tady - viz `roztahujComputeForY`
// v `webapp/js/scene-geometry-shared.js` (nactena jako global pres
// <script src="js/scene-geometry-shared.js"> uz PRED timhle blokem - viz
// hlavicka souboru NASTROJE_SCENY.md "pravidlo pro budouci funkce": zadne
// THREE/DOM zavislosti, takze ROVNOU do sdileneho souboru, aby ji beze
// zmeny mohl pouzit i Node.js overovaci skript
// (scripts/2026-08-31_roztahuj_verify.js) - presne stejny princip jako
// applyLengthScale.

// Promitne SVETOVY smer `dirWorld` (delky `refLenMm`, od bodu `originWorld`)
// na obrazovku - stejny princip jako computeScreenDragAxis u protazeni
// oranzovou sipkou (dragWorldToScreen/alongScreenAxis jsou uz obecne, bez
// zavislosti na `dragState`), jen misto osy dilu pouzivame PEVNOU svetovou
// osu Y (Roztahuj tahne vzdy jen svisle, X/Z pricky se nemeni).
function computeScreenAxisForWorldDir(originWorld, dirWorld, refLenMm) {
  const s0 = dragWorldToScreen(originWorld);
  const s1 = dragWorldToScreen(originWorld.clone().addScaledVector(dirWorld, refLenMm));
  const vx = s1.x - s0.x, vy = s1.y - s0.y;
  const len = Math.hypot(vx, vy);
  return {
    screenFixed: s0,
    screenAxisDir: len > 1e-6 ? { x: vx / len, y: vy / len } : { x: 0, y: -1 },
    screenAxisLen: len,
    refLenMm,
  };
}

function roztahujCancelDrag() {
  if (!roztahujDragState) return;
  const wasMoved = roztahujDragState.moved;
  roztahujDragState = null;
  controls.enabled = true;
  if (wasMoved) { rebuildOccupiedConnectors(); refreshEndpointMarkers(); refreshDimLabels(); refreshSummary(); }
}

btnRoztahuj.addEventListener("click", () => {
  roztahujMode = !roztahujMode;
  btnRoztahuj.classList.toggle("active", roztahujMode);
  if (!roztahujMode) {
    roztahujCancelDrag();
    return;
  }
  // stejna vzajemna vyluka jako u ostatnich rezimu klikani/tazeni po scene
  // (Obarvit dil / Mikroposuv / Posun mysi) - jen jeden takovy rezim aktivni.
  if (paintMode) {
    paintMode = false;
    btnPaintMode.classList.remove("active");
    if (paintHoverEntry) { setHoverHighlight(paintHoverEntry, false); paintHoverEntry = null; paintHoverMesh = null; }
  }
  if (moveMode) {
    moveMode = false;
    btnMoveMode.classList.remove("active");
    renderer.domElement.style.cursor = "";
    clearMoveSelection();
  }
  if (typeof setAxisMoveMode === "function" && axisMoveMode) setAxisMoveMode(false);
});

function roztahujExitMode(msg) {
  if (msg) showJoinToast(msg);
  roztahujMode = false;
  btnRoztahuj.classList.remove("active");
}

renderer.domElement.addEventListener("pointerdown", (ev) => {
  if (!roztahujMode || dragState || roztahujDragState) return;
  if (ev.button === 2) { roztahujExitMode(); return; } // prave tlacitko = konec rezimu, stejna konvence jako "Obarvit dil"
  const entry = entryAtEvent(ev);
  if (!entry || !entry.part || !isProfilePart(entry.part) || !placed.includes(entry)) {
    roztahujExitMode(); // klik na cokoli neplatneho = konec rezimu (spec Roberta)
    return;
  }
  const res = roztahujFindPartners(entry);
  if (!res.ok) { roztahujExitMode(res.error); return; }

  entry.object3d.updateMatrixWorld(true);
  const startY = entry.object3d.position.y;
  const axisState = computeScreenAxisForWorldDir(entry.object3d.position.clone(), new THREE.Vector3(0, 1, 0), 200);
  roztahujDragState = {
    crossbar: entry,
    startY,
    axisState,
    initialAlong: alongScreenAxis(ev.clientX, ev.clientY, axisState),
    verticals: res.verticals,
    moved: false,
    downX: ev.clientX, downY: ev.clientY,
  };
  controls.enabled = false;
  ev.preventDefault();
});

renderer.domElement.addEventListener("pointermove", (ev) => {
  if (!roztahujDragState) return;
  const st = roztahujDragState;
  if (!st.moved && (Math.abs(ev.clientX - st.downX) > 3 || Math.abs(ev.clientY - st.downY) > 3)) st.moved = true;
  if (!st.moved) return;
  let desiredY = st.startY;
  if (st.axisState.screenAxisLen > DRAG_MIN_SCREEN_AXIS_PX) {
    const curAlong = alongScreenAxis(ev.clientX, ev.clientY, st.axisState);
    const pixelDelta = curAlong - st.initialAlong;
    desiredY = st.startY + (pixelDelta / st.axisState.screenAxisLen) * st.axisState.refLenMm;
  }
  const result = roztahujComputeForY(desiredY, st.verticals, ROZTAHUJ_MIN_LEN_MM, ROZTAHUJ_MAX_LEN_MM);
  st.crossbar.object3d.position.y = result.crossY;
  st.crossbar.object3d.updateMatrixWorld(true);
  st.verticals.forEach((v, i) => {
    const scaleFactor = result.legs[i].length / v.localLen;
    applyLengthScale(v.entry, scaleFactor, v.farIdx, v.endIdxA, v.endIdxB);
  });
  refreshDimLabels();
});

window.addEventListener("pointerup", () => {
  if (!roztahujDragState) return;
  const st = roztahujDragState;
  roztahujDragState = null;
  controls.enabled = true;
  if (st.moved) {
    rebuildOccupiedConnectors();
    refreshEndpointMarkers(); refreshDimLabels();
    refreshSummary();
    showJoinToast("Roztahuj: příčka přesunuta, obě navazující nohy upraveny.");
  }
});
