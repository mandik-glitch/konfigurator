// ===== Interaktivni umistovani vlozeneho tvaru na rastr (Robert
// 2026-08-04) ===== Lehky poloprusvitny grid na podlaze (hustota z
// inputu "Rastr vkladani (mm)", pamatuje se v localStorage), cely tvar
// jede za mysi prichytavany na uzly rastru (kotva = roh XZ-obalky tvaru,
// spodek tvaru se polozi na podlahu y=0), LEVY klik = vlozit presne tam,
// Escape = cele vlozeni zrusit (dily se odstrani). Prave/stredni tlacitko
// (orbit/pan kamery) zustava funkcni.
let shapePlacementState = null;

function shapeInsertGridStepMm() {
  const inp = document.getElementById("shapeInsertGridMm");
  let v = inp ? parseFloat((inp.value || "").replace(",", ".")) : NaN;
  if (!isFinite(v) || v <= 0) v = 50;
  v = Math.max(1, Math.min(1000, v));
  return v;
}
try {
  const inpInit = document.getElementById("shapeInsertGridMm");
  if (inpInit) {
    const saved = localStorage.getItem("shapeInsertGridMm");
    // Robert 2026-08-08 ("velikost oka je stanovena stejným číslem
    // které nastavuje vstupní grid tvaru"): hlavni podlahova mrizka
    // (viz rebuildMainGrid vyse) ma stejny krok jako tenhle input -
    // pokud uz je v localStorage ulozena jina hodnota nez vychozich 50
    // (HTML atribut value), je potreba mrizku hned prekreslit (samotne
    // prepsani .value totiz zadny "change" event nevyvola).
    if (saved) { inpInit.value = saved; if (typeof rebuildMainGrid === "function") rebuildMainGrid(); }
    inpInit.addEventListener("change", () => {
      try { localStorage.setItem("shapeInsertGridMm", String(shapeInsertGridStepMm())); } catch (e) { /* ignoruj */ }
      if (typeof rebuildMainGrid === "function") rebuildMainGrid();
    });
  }
} catch (e) { /* ignoruj */ }

function startShapePlacementMode(entries, extraObjects) {
  if (shapePlacementState) {
    showJoinToast("Nejdřív umísti (klikem) nebo zruš (Escape) předchozí vkládaný tvar.");
    return false;
  }
  if (!entries || !entries.length) return false;
  const step = shapeInsertGridStepMm();
  // vychozi obalka + startovni pozice dilu
  const box = new THREE.Box3();
  const startPositions = new Map();
  entries.forEach(e => {
    e.object3d.updateMatrixWorld(true);
    box.union(new THREE.Box3().setFromObject(e.object3d));
    startPositions.set(e, e.object3d.position.clone());
  });
  if (box.isEmpty()) return false;
  // bot8, 2026-08-17: text_labels (sceneTextLabels) nejsou "entries" (zadny
  // katalogovy dil), ale musi se posouvat SPOLU s tvarem behem interaktivniho
  // umistovani - vlastni (mensi) mapa start-pozic, stejny `off` vektor nize.
  extraObjects = extraObjects || [];
  const extraStartPositions = new Map();
  extraObjects.forEach(o => extraStartPositions.set(o, o.position.clone()));
  // slaby grid na podlaze - velikost v celych nasobcich kroku, pocet car
  // omezeny na max ~800 na smer (jemny rastr 1mm by jinak polozil scenu)
  const gridDivs = Math.min(800, Math.max(10, Math.round(20000 / step)));
  const gridSize = gridDivs * step;
  const grid = new THREE.GridHelper(gridSize, gridDivs, 0x7f8ea3, 0x55606e);
  grid.material.transparent = true;
  grid.material.opacity = 0.22;
  grid.material.depthWrite = false;
  grid.position.set(0, 0.5, 0); // tesne nad podlahou, at neproblika se zemi
  scene.add(grid);
  const st = {
    entries, startPositions,
    extraObjects, extraStartPositions,
    bboxMin: box.min.clone(),
    grid, step,
    // Robert 2026-08-06: "pri vkladani objektu do sceny kolečkem myši
    // ovlivňujeme umístění objektu v ose Z" (mysleno svisle - CAD
    // konvence Z=vyska; ve three.js je to osa Y). Kolecko nahoru =
    // zvednout o krok rastru, dolu = spustit, minimum je podlaha.
    // wheelAccum: jemna kolecka/touchpady posilaji DESITKY wheel
    // udalosti na jedno fyzicke cvaknuti (deltaMode=0, pixely) - bez
    // akumulace se za kazdou udalost pricetl cely krok rastru a "na
    // dve otoceni se posunul o 5 m" (Robertovo hlaseni). Krok se ted
    // provede az po nasbirani ~100 pixelu deltaY = 1 cvaknuti.
    liftY: 0, lastSx: null, lastSz: null, wheelAccum: 0,
    onMove: null, onDown: null, onKey: null, onWheel: null,
  };
  shapePlacementState = st;
  const planeY0 = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  // Sdilene prepocitani pozice ze zapamatovaneho uzlu rastru + zdvihu -
  // vola ho pohyb mysi (po novem raycastu) i kolecko (bez pohybu mysi).
  const applyOffset = () => {
    if (st.lastSx == null) return;
    const off = new THREE.Vector3(st.lastSx - st.bboxMin.x, -st.bboxMin.y + st.liftY, st.lastSz - st.bboxMin.z);
    st.entries.forEach(e => {
      const sp = st.startPositions.get(e);
      e.object3d.position.copy(sp.clone().add(off));
      e.object3d.updateMatrixWorld(true);
    });
    st.extraObjects.forEach(o => {
      const sp = st.extraStartPositions.get(o);
      o.position.copy(sp.clone().add(off));
      o.updateMatrixWorld(true);
    });
    if (typeof refreshEndpointMarkers === "function") refreshEndpointMarkers();
    if (typeof refreshDimLabels === "function") refreshDimLabels();
  };
  const moveTo = (ev) => {
    const rect = renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((ev.clientX - rect.left) / rect.width) * 2 - 1,
      -((ev.clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    const hit = new THREE.Vector3();
    if (!raycaster.ray.intersectPlane(planeY0, hit)) return;
    // kotva: XZ-roh obalky tvaru na uzel rastru, spodek na podlahu (+ zdvih)
    st.lastSx = Math.round(hit.x / st.step) * st.step;
    st.lastSz = Math.round(hit.z / st.step) * st.step;
    applyOffset();
  };
  st.onMove = (ev) => { try { moveTo(ev); } catch (e) { /* nerozbit vkladani */ } };
  st.onDown = (ev) => {
    if (ev.button !== 0) return; // jen levy klik vklada; orbit/pan nechat byt
    ev.preventDefault();
    ev.stopImmediatePropagation(); // nesmi probehnout oznacovani/tazeni dilu
    finishShapePlacement();
  };
  st.onKey = (ev) => {
    if (ev.key !== "Escape") return;
    ev.preventDefault();
    ev.stopImmediatePropagation();
    cancelShapePlacement();
  };
  st.onWheel = (ev) => {
    // Robert 2026-08-06 ("pohyb objektu koleckem prebije zoomovani"):
    // se Shift/Ctrl kolecko NEzachytavame - propadne do OrbitControls
    // a normalne zoomuje i behem vkladani. Samotne kolecko = zdvih.
    if (ev.shiftKey || ev.ctrlKey) return;
    // capture + stopImmediatePropagation: behem vkladani kolecko NESMI
    // zoomovat scenu (OrbitControls posloucha na stejnem elementu).
    ev.preventDefault();
    ev.stopImmediatePropagation();
    // Normalizace deltaY na pixely (deltaMode 1 = radky, 2 = stranky)
    // a akumulace - krok az po nasbirani celeho cvaknuti (~100 px).
    const dy = ev.deltaMode === 1 ? ev.deltaY * 33 : ev.deltaMode === 2 ? ev.deltaY * 100 : ev.deltaY;
    st.wheelAccum += dy;
    const NOTCH = 100;
    let changed = false;
    while (st.wheelAccum <= -NOTCH) { st.liftY += st.step; st.wheelAccum += NOTCH; changed = true; }
    while (st.wheelAccum >= NOTCH) {
      const next = Math.max(0, st.liftY - st.step);
      if (next === st.liftY) { st.wheelAccum = 0; break; } // uz na podlaze - nekumulovat dal
      st.liftY = next; st.wheelAccum -= NOTCH; changed = true;
    }
    if (changed) { try { applyOffset(); } catch (e) { /* nerozbit vkladani */ } }
  };
  renderer.domElement.addEventListener("pointermove", st.onMove);
  renderer.domElement.addEventListener("pointerdown", st.onDown, { capture: true });
  window.addEventListener("keydown", st.onKey, { capture: true });
  renderer.domElement.addEventListener("wheel", st.onWheel, { capture: true, passive: false });
  showJoinToast("Umísti tvar: pohybuj myší po rastru (" + st.step + " mm), kolečko = zvednout/spustit, Shift+kolečko = zoom, klik = vložit. Escape = zrušit.");
  return true;
}

function endShapePlacementCleanup() {
  const st = shapePlacementState;
  if (!st) return;
  renderer.domElement.removeEventListener("pointermove", st.onMove);
  renderer.domElement.removeEventListener("pointerdown", st.onDown, { capture: true });
  window.removeEventListener("keydown", st.onKey, { capture: true });
  renderer.domElement.removeEventListener("wheel", st.onWheel, { capture: true });
  scene.remove(st.grid);
  if (st.grid.geometry) st.grid.geometry.dispose();
  if (st.grid.material) st.grid.material.dispose();
  shapePlacementState = null;
}

function finishShapePlacement() {
  const st = shapePlacementState;
  if (!st) return;
  st.entries.forEach(e => {
    e.object3d.updateMatrixWorld(true);
    e.object3d.userData.basePos = e.object3d.position.clone();
  });
  endShapePlacementCleanup();
  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
  showJoinToast("Tvar vložen.");
}

function cancelShapePlacement() {
  const st = shapePlacementState;
  if (!st) return;
  st.entries.forEach(e => {
    scene.remove(e.object3d);
    const idx = placed.indexOf(e);
    if (idx >= 0) placed.splice(idx, 1);
    if (typeof selectedMoveEntries !== "undefined") selectedMoveEntries.delete(e);
    if (typeof axisMoveSelectedEntries !== "undefined") axisMoveSelectedEntries.delete(e);
  });
  st.extraObjects.forEach(o => {
    scene.remove(o);
    const idx = sceneTextLabels.indexOf(o);
    if (idx >= 0) sceneTextLabels.splice(idx, 1);
    if (o.material) { if (o.material.map) o.material.map.dispose(); o.material.dispose(); }
  });
  endShapePlacementCleanup();
  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
  showJoinToast("Vkládání tvaru zrušeno.");
}
