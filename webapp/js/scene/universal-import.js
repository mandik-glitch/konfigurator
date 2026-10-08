// universal-import.js - panel "Import objektu (FBX)" ve 3D scene - bot8,
// 2026-09-29. Robert: "postav univerzalni funkci, ktera importuje libovolny
// objekt: rozpojene dily (jako SSE.vzor.01), rucni mapovani na katalog,
// nove dily jako karty s novym SKU, funkcni cena/spoje/nabidka". UI ma
// byt PRIMO ve scene (Robertova volba), aby byl videt dil, ktery se
// zrovna mapuje.
//
// Nacita se AZ PO #app-script (stejne jako roztahuj.js) - pouziva globalni
// funkce/promenne sceny: initFloatingShapesWindow, insertCustomShape,
// applyAutoPlacementOffset, releaseBrokenProfileJoints, releaseAllJointsFor,
// CATALOG (catalog-panels.js), katalogPartById, placed, selectedMoveEntries,
// axisMoveSelectedEntries, jointGroups, currentAssemblyMeta,
// sceneUndoRestoring, sceneGeneration, SCENE_LAST_LOADED_KEY, scene, camera,
// controls, bboxOfEntries, csReloadCategoriesAndShapes,
// CUSTOM_SHAPES, CUSTOM_SHAPE_CATEGORIES, buildCatalogList,
// renderCatalogImagePanel, rebuildOccupiedConnectors, refreshEndpointMarkers,
// refreshDimLabels, window.refreshSummary, refreshMoveSelectionLabel,
// refreshMoveAxisButtons, refreshAxisMoveLabel, syncCatalogSelectionHighlight,
// paintHoverEntry/paintHoverMesh, dragState, axisMoveDragState, rotateActive.
// clearAll() se NEVOLA - import nikdy nesmaze scenu.
//
// Tok: [1] FBX -> POST /api/admin/universal-import/analyze -> seznam dilu
// + nahledove GLB (staff-only URL). Nahled ve scene BEZ noveho
// renderovaciho kodu: docasne radky "tmpimport_<i>" v CATALOG (file =
// nahledova URL) + insertCustomShape() s identitou - dily jsou normalni
// klikaci entries. [2] tabulka: SKUPINY stejnych dilu (stejne rozmery +
// pocet vrcholu/trojuhelniku = tentyz dil, napr. 4 kolecka = 1 radek "x4"
// s jednim mapovanim; Robert 2026-09-30 "tady je milion dilu"), sekce
// "Rozpoznane profily" (prirazene automaticky, sbalene), "Ostatni dily",
// "Sum". Mapovani: existujici dil (hledani nad CATALOG) / novy dil (SKU
// <kod>.DIL-NNN, stejne SKU pro celou skupinu = jedna karta) / preskocit.
// Klik na radek = zvyrazneni dilu ve scene, vyber ve scene = radek.
// [3] POST build -> docasny nahled pryc, nove katalogove radky do CATALOG,
// reload stromu tvaru, novy tvar se prida VEDLE stavajiciho obsahu sceny.
//
// Import NIKDY nemaze scenu (Robert 2026-09-30 "kdyz importuju novy fbx, nesmi
// se nic ve scene smazat"): nahled i vysledek jdou pres insertCustomShape(...,
// {inPlace:true}) + applyAutoPlacementOffset (+X, mezera 300 mm); prerenderovani
// nahledu odebere jen entries "tmpimport_*". Nahled je mimo cenu/kusovnik/undo/
// ulozeni/online nabidku (scene.html isImportPreviewEntry); operace jdou frontou.
//
// Backend: api/universal_import.py (tam je i zduvodneni, proc se dily
// "nevzdali" - vlastni GLB s puvodnimi vrcholy, jako SSE.vzor.01).
(function () {
  "use strict";

  const TMP_PREFIX = "tmpimport_";
  const state = { token: null, parts: [], decisions: {}, sourceName: "", shapeCode: "", building: false,
                  collapsed: { profily: true, ostatni: false, drobne: true, sum: true } };

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function $(id) { return document.getElementById(id); }

  // --- docasne katalogove radky pro nahled ---------------------------------
  function removeTmpCatalogRows() {
    if (typeof CATALOG === "undefined") return;
    for (let i = CATALOG.length - 1; i >= 0; i--) {
      if (String(CATALOG[i].id).startsWith(TMP_PREFIX)) CATALOG.splice(i, 1);
    }
  }

  function addTmpCatalogRows(parts) {
    removeTmpCatalogRows();
    parts.forEach(p => {
      CATALOG.push({
        id: TMP_PREFIX + p.i, name: "náhled: " + p.name, layer: "produkt",
        material_label: null, dims_mm: p.dims_mm, length_mm: null, cross_section_mm: [null, null],
        weight_kg: null, price_czk: null, price_per_cut_czk: null,
        file: p.preview_url, visible_in_scene: false, source: "product", category_id: null,
        shop_product_id: null, stock_qty: null, color_hex: null, is_board_material: false,
      });
    });
  }

  function tmpPartsShape(parts) {
    return {
      name: "náhled importu: " + state.sourceName,
      parts: parts.map(p => ({ part_id: TMP_PREFIX + p.i, position: [0, 0, 0], quaternion: [0, 0, 0, 1], scale: [1, 1, 1] })),
      join_groups: [], frame_groups: [], text_labels: [],
    };
  }

  function entryForPart(i) {
    if (typeof placed === "undefined") return null;
    return placed.find(e => e && e.part && e.part.id === TMP_PREFIX + i) || null;
  }

  // --- nahled ve scene: import NIKDY nemaze stavajici obsah ---------------------
  function isTmpEntry(e) { return !!(e && e.part && String(e.part.id).startsWith(TMP_PREFIX)); }

  function sceneRefresh() {
    rebuildOccupiedConnectors(); refreshEndpointMarkers(); refreshDimLabels();
    window.refreshSummary(); // lokalni refreshSummary() je tabulka importu, ne scena
  }

  function selectionSets() {
    const sets = [];
    if (typeof selectedMoveEntries !== "undefined") sets.push(selectedMoveEntries);
    if (typeof axisMoveSelectedEntries !== "undefined") sets.push(axisMoveSelectedEntries);
    return sets;
  }

  let previewMeta = null; // identita otevrene sestavy, kterou nastavil nahled v PRAZDNE scene

  // Odebere JEN dily nahledu; cisteni navaznych stavu jako deleteSelectedEntries().
  function removeTmpEntries() {
    const tmp = placed.filter(isTmpEntry);
    if (tmp.length) {
      const gone = new Set(tmp);
      let selChanged = false, axisChanged = false;
      tmp.forEach(e => {
        if (typeof selectedMoveEntries !== "undefined" && selectedMoveEntries.delete(e)) selChanged = true;
        if (typeof axisMoveSelectedEntries !== "undefined" && axisMoveSelectedEntries.delete(e)) axisChanged = true;
        if (typeof releaseAllJointsFor === "function") releaseAllJointsFor(e);
        scene.remove(e.object3d);
        const idx = placed.indexOf(e);
        if (idx !== -1) placed.splice(idx, 1);
      });
      if (typeof selectedMoveEntries !== "undefined" && (selChanged || selectedMoveEntries.size)) {
        refreshMoveSelectionLabel();
        refreshMoveAxisButtons();
      }
      if (axisChanged && typeof refreshAxisMoveLabel === "function") refreshAxisMoveLabel();
      if (typeof jointGroups !== "undefined" && jointGroups.length) {
        jointGroups = jointGroups.map(g => { gone.forEach(e => g.delete(e)); return g; }).filter(g => g.size > 1);
      }
      if (typeof paintHoverEntry !== "undefined" && gone.has(paintHoverEntry)) { paintHoverEntry = null; paintHoverMesh = null; }
      if (typeof syncCatalogSelectionHighlight === "function") syncCatalogSelectionHighlight();
    }
    if (previewMeta && currentAssemblyMeta === previewMeta) currentAssemblyMeta = null;
    previewMeta = null;
    sceneRefresh();
  }

  // Vlozi tvar VEDLE stavajiciho obsahu (prazdna scena = puvodni souradnice).
  // Vraci true, kdyz ve scene uz neco bylo. Identita otevrene sestavy a klic
  // pro obnovu po F5 se pri vkladani vedle cizího obsahu nemeni.
  async function addShapeToScene(shape, isPreview) {
    const hadOthers = placed.some(e => !isTmpEntry(e));
    const savedMeta = currentAssemblyMeta;
    let savedKey = null;
    try { savedKey = localStorage.getItem(SCENE_LAST_LOADED_KEY); } catch (e) { /* ignoruj */ }
    const gen = sceneGeneration, startIdx = placed.length;
    try {
      sceneUndoRestoring = true; // vlozeni = jeden krok zpet, ne mezistavy
      await insertCustomShape(shape, { inPlace: true });
      if (sceneGeneration !== gen) return false;
      const added = placed.slice(startIdx);
      if (hadOthers && added.length) {
        applyAutoPlacementOffset(startIdx, []);
        added.forEach(e => { e.object3d.userData.basePos = e.object3d.position.clone(); }); // rozlozeny pohled
        added.forEach(e => { if (typeof releaseBrokenProfileJoints === "function") releaseBrokenProfileJoints(e); });
      }
      if (!hadOthers && isPreview) previewMeta = currentAssemblyMeta;
    } finally {
      sceneUndoRestoring = false;
      if (hadOthers && sceneGeneration === gen) {
        currentAssemblyMeta = savedMeta;
        try {
          if (savedKey == null) localStorage.removeItem(SCENE_LAST_LOADED_KEY);
          else localStorage.setItem(SCENE_LAST_LOADED_KEY, savedKey);
        } catch (e) { /* ignoruj */ }
      }
    }
    sceneRefresh();
    return hadOthers;
  }

  // Bez clearAll() se uz nezvysuje sceneGeneration, takze se prekryvajici
  // prerenderovani nahledu musi radit za sebe (jinak by se dily zdvojily).
  let sceneOpQueue = Promise.resolve();
  function queueSceneOp(fn) {
    const run = sceneOpQueue.then(fn);
    sceneOpQueue = run.catch(() => {});
    return run;
  }

  function panCameraTo(entries) {
    if (!entries.length || typeof bboxOfEntries !== "function" || typeof camera === "undefined" || typeof controls === "undefined") return;
    const box = bboxOfEntries(entries);
    if (box.isEmpty()) return;
    const delta = box.getCenter(new THREE.Vector3()).sub(controls.target);
    camera.position.add(delta);
    controls.target.add(delta);
    controls.update();
  }

  function showPreview(opts) {
    const pan = !!(opts && opts.pan);
    return queueSceneOp(async () => {
      removeTmpEntries();
      addTmpCatalogRows(state.parts);
      if (!state.parts.length) return;
      const beside = await addShapeToScene(tmpPartsShape(state.parts), true);
      if (beside && pan) panCameraTo(placed.filter(isTmpEntry));
    });
  }

  function hidePreview() {
    return queueSceneOp(async () => { removeTmpEntries(); removeTmpCatalogRows(); });
  }

  function addFinalShape(shape) {
    return queueSceneOp(() => addShapeToScene(shape, false));
  }

  function sceneSelectionKinds() {
    let real = false, tmp = false;
    selectionSets().forEach(s => s.forEach(e => { if (isTmpEntry(e)) tmp = true; else if (e) real = true; }));
    return { real, tmp };
  }

  // Pisici kontext = textove pole; zaskrtavatko/tlacitko/slider klavesam fokus neberou.
  function isTypingField(el, isJ) {
    if (!el || !el.tagName) return false;
    if (el.isContentEditable) return true;
    const tag = el.tagName;
    if (tag === "TEXTAREA") return true;
    if (tag === "SELECT") return isJ;
    if (tag !== "INPUT") return false;
    const t = (el.type || "text").toLowerCase();
    return !["checkbox", "radio", "button", "submit", "reset", "range", "color", "file", "image"].includes(t);
  }

  // --- sum = ploche utrzky bez objemu (58x2x0) nebo drobky (< 10 mm) ---------
  function isFragment(p) {
    if (p.fragment) return true;
    const s = (p.dims_mm || []).slice().sort((a, b) => a - b);
    return s.length === 3 && (s[0] < 0.5 || s[2] < 10);
  }

  function partById(i) { return state.parts.find(x => x.i === i); }

  // --- skupiny stejnych dilu ---------------------------------------------------
  // Stejny dil = stejne rozmery bboxu (do 1 mm). Pocet vrcholu se ZAMERNE
  // neporovnava - Rhino tesseluje kazdou instanci trochu jinak (4 kolecka
  // 45x73x109 mela 12550/12569/12839/12610 vrcholu). Zrcadlove dvojice
  // (leva/prava bocnice) maji stejny bbox a seskupi se taky - backend pri
  // buildu pozna, ze se geometrie neshoduje zadnou rotaci, a zalozi pro
  // ne samostatnou kartu (viz universal_import.py build, warnings).
  function groupKey(p) {
    const s = (p.dims_mm || []).slice().sort((a, b) => a - b);
    return s.map(v => Math.round(v)).join("x");
  }

  function sameDims(a, b) {
    const sa = (a.dims_mm || []).slice().sort((x, y) => x - y);
    const sb = (b.dims_mm || []).slice().sort((x, y) => x - y);
    return sa.length === 3 && sb.length === 3 && sa.every((v, k) => Math.abs(v - sb[k]) <= 1.0);
  }

  // Drobne dily (Robert 2026-09-30: "u SSE importu jsem neresil
  // mikrodily") - nerozpoznane a bez rozhodnuti, max rozmer <= hranice
  // (vychozi 60 mm, pole "drobne do"). Po rozboru se automaticky prilepi
  // k sousednimu dilu (merge-small); co zbyde, je v sekci "Drobne dily".
  function smallLimit() {
    const v = parseFloat(($("uimpSmallMm") || {}).value);
    return Number.isFinite(v) && v > 0 ? v : 60;
  }

  function isSmall(p) {
    if (isFragment(p)) return false;
    const d = decisionOf(p.i);
    if (d && d.action !== "skip") return false;
    if (p.suggest_kind === "profil" || p.suggest_kind === "exact") return false;
    return Math.max(...(p.dims_mm || [0])) <= smallLimit();
  }

  function smallIds() { return state.parts.filter(isSmall).map(p => p.i); }

  function sectionOf(p) {
    if (isFragment(p)) return "sum";
    const d = decisionOf(p.i);
    if (p.suggest_kind === "profil" || (d && d.action === "existing" && isProfileId(d.part_id))) return "profily";
    if (isSmall(p)) return "drobne";
    return "ostatni";
  }

  function isProfileId(id) {
    const kp = typeof katalogPartById === "function" ? katalogPartById(id) : null;
    return !!(kp && kp.length_mm && kp.cross_section_mm && kp.cross_section_mm[0] != null);
  }

  let groups = [];
  function buildGroups() {
    // shlukovani s toleranci 1 mm (ne jen presny klic - 85x40 vs 85x41 je
    // tentyz dil s jinym zaokrouhlenim)
    const list = [];
    state.parts.forEach(p => {
      let g = list.find(x => sameDims(x.rep, p) && isFragment(x.rep) === isFragment(p));
      if (!g) { g = { key: groupKey(p) + "#" + p.i, members: [], rep: p }; list.push(g); }
      g.members.push(p.i);
    });
    groups = list;
    groups.forEach(g => { g.section = sectionOf(g.rep); g.maxDim = Math.max(...g.rep.dims_mm); });
    const order = { profily: 0, ostatni: 1, drobne: 2, sum: 3 };
    groups.sort((a, b) => (order[a.section] - order[b.section]) || (b.maxDim - a.maxDim) || (a.rep.i - b.rep.i));
    return groups;
  }

  // --- skupina = "jedno mapovani pro vsechny" (badge ×N) -----------------------
  // Clen skupiny bez vlastniho rozhodnuti prevezme rozhodnuti skupiny. Bez toho
  // autoApplySuggestions (po dilech, jen "exact"/"profil") priradil jen cast
  // skupiny, radek ukazoval prirazeni reprezentanta a build zbytek tise poslal
  // jako skip (Robertuv stul 2026-09-30: druhy perfopanel #30 v tvaru chybel).
  function syncGroupDecisions() {
    let changed = false;
    groups.forEach(g => {
      const src = [g.rep.i].concat(g.members).map(i => state.decisions[i]).find(d => d && d.action !== "skip");
      if (!src) return;
      g.members.forEach(i => { if (!state.decisions[i]) { state.decisions[i] = Object.assign({}, src); changed = true; } });
    });
    if (changed) scheduleDraftSave();
    return changed;
  }

  // ruzna rozhodnuti uvnitr jedne skupiny (napr. po smazani reprezentanta se
  // skupiny preskupi) - radek ukazuje jen reprezentanta, build by poslal vic
  // karet; panel to musi rict (pocet ruznych rozhodnuti, 0 = jednotne)
  function decisionKey(d) { return d && d.action !== "skip" ? [d.action, d.part_id || "", d.sku || ""].join("|") : "skip"; }
  function groupDecisionsMixed(g) {
    const keys = new Set(g.members.map(i => decisionKey(state.decisions[i])));
    return keys.size > 1 ? keys.size : 0;
  }

  function groupOfPart(i) { return groups.find(g => g.members.includes(i)); }
  function decisionOf(i) { return state.decisions[i]; }

  function setGroupDecision(g, dec) {
    g.members.forEach(i => { state.decisions[i] = dec ? Object.assign({}, dec) : undefined; if (!dec) delete state.decisions[i]; });
    refreshSummary();
    scheduleDraftSave();
  }

  // --- zvyrazneni radek <-> scena -------------------------------------------
  // Robert 2026-09-30: "kdyz na radek kliknu, musi se ten dil poradne
  // zvyraznit, napr. zcervenat" - cela skupina cervene (vlastni klon
  // materialu per mesh, aby se neobarvily dily sdilejici material), zpet
  // puvodni material pri zvyrazneni jine skupiny.
  const RED = 0xff2a2a;
  function paintEntry(entry, on) {
    if (!entry || !entry.object3d) return;
    entry.object3d.traverse(n => {
      if (!n.isMesh || !n.material) return;
      if (on) {
        if (!n.userData.uimpOrigMat) {
          n.userData.uimpOrigMat = n.material;
          const m = n.material.clone();
          if (m.color) m.color.setHex(RED);
          if (m.emissive) m.emissive.setHex(0x7a0000);
          n.material = m;
        }
      } else if (n.userData.uimpOrigMat) {
        const tmp = n.material;
        n.material = n.userData.uimpOrigMat;
        delete n.userData.uimpOrigMat;
        if (tmp && tmp.dispose) tmp.dispose();
      }
    });
  }

  function unpaintAll() {
    if (typeof placed === "undefined") return;
    placed.forEach(e => { if (isTmpEntry(e)) paintEntry(e, false); });
  }

  let highlightedKey = null;
  function highlightGroup(g) {
    unpaintAll();
    g.members.forEach(i => { const e = entryForPart(i); if (e) paintEntry(e, true); });
    highlightedKey = g.key;
    document.querySelectorAll("#uimpRows tr.uimp-active").forEach(tr => tr.classList.remove("uimp-active"));
    const tr = document.querySelector(`#uimpRows tr[data-key="${CSS.escape(g.key)}"]`);
    if (tr) tr.classList.add("uimp-active");
  }

  let lastSelSig = "";
  setInterval(() => {
    if (!state.token || typeof selectedMoveEntries === "undefined") return;
    const sel = [...selectedMoveEntries].filter(e => e && e.part && String(e.part.id).startsWith(TMP_PREFIX));
    const sig = sel.map(e => e.part.id).join(",");
    if (sig === lastSelSig) return;
    lastSelSig = sig;
    if (!sel.length) return;
    const i = parseInt(String(sel[sel.length - 1].part.id).slice(TMP_PREFIX.length), 10);
    const g = groupOfPart(i);
    if (!g) return;
    if (state.collapsed[g.section]) { state.collapsed[g.section] = false; renderTable(); }
    document.querySelectorAll("#uimpRows tr.uimp-active").forEach(x => x.classList.remove("uimp-active"));
    const tr = document.querySelector(`#uimpRows tr[data-key="${CSS.escape(g.key)}"]`);
    if (tr) { tr.classList.add("uimp-active"); tr.scrollIntoView({ block: "nearest" }); }
  }, 400);

  // --- hledani v katalogu (profily i produkty, nad CATALOG) -------------------
  function catalogCandidates(q) {
    q = q.trim().toLowerCase();
    if (!q) return [];
    // bez 3D modelu (_PENDING_ = ceka na prevod) kartu nenabizet - sestaveni by ji
    // odmitlo (ulozeny tvar by scena nenacetla)
    return CATALOG.filter(p => !String(p.id).startsWith(TMP_PREFIX) && !String(p.id).startsWith("car_body_"))
      .filter(p => p.file && !/(^|\/)_PENDING_/.test(p.file))
      .filter(p => (p.name || "").toLowerCase().includes(q) || String(p.id).toLowerCase().includes(q))
      .slice(0, 12);
  }

  function wireSearch(tr, g) {
    const input = tr.querySelector(".uimp-search");
    const box = tr.querySelector(".uimp-suggest");
    const render = () => {
      const list = catalogCandidates(input.value);
      if (!input.value.trim()) { box.style.display = "none"; box.innerHTML = ""; return; }
      box.innerHTML = list.length
        ? list.map(p => `<div class="uimp-row" data-id="${esc(p.id)}">${esc(p.name)} <span style="color:#8b93a1">(${esc(p.id)})</span></div>`).join("")
        : '<div class="uimp-row" style="color:#8b93a1">nic nenalezeno</div>';
      box.style.display = "block";
      box.querySelectorAll(".uimp-row[data-id]").forEach(row => {
        row.onmousedown = (ev) => {
          ev.preventDefault();
          setGroupDecision(g, { action: "existing", part_id: row.dataset.id });
          input.value = "";
          box.style.display = "none";
          renderTable();
        };
      });
    };
    input.addEventListener("input", render);
    input.addEventListener("focus", render);
    input.addEventListener("blur", () => setTimeout(() => { box.style.display = "none"; }, 150));
  }

  // --- rozhodnuti per skupina ---------------------------------------------------
  function defaultSku(i) {
    const code = (state.shapeCode || "IMPORT").trim();
    return `${code}.DIL-${String(i).padStart(3, "0")}`;
  }

  function newDecisionFor(g) {
    return { action: "new", name: `${state.shapeCode || "import"} - ${g.rep.name}`, sku: defaultSku(g.rep.i) };
  }

  function renderDecisionCell(tr, g) {
    const p = g.rep;
    const dec = decisionOf(p.i) || { action: "skip" };
    const cell = tr.querySelector(".uimp-decision");
    let html = "";
    if (dec.action === "existing") {
      const kp = katalogPartById(dec.part_id);
      html = `<span style="color:#7ee081">→ ${esc(kp ? kp.name : dec.part_id)}</span> <span style="color:#8b93a1">(${esc(dec.part_id)})</span>
        <button type="button" class="linklike uimp-change">změnit</button>`;
    } else if (dec.action === "new") {
      html = `<span style="color:#f0c674">nový díl${g.members.length > 1 ? " (1 karta ×" + g.members.length + ")" : ""}</span>
        <input class="uimp-new-name" value="${esc(dec.name)}" placeholder="název dílu" style="width:150px;">
        <input class="uimp-new-sku" value="${esc(dec.sku)}" placeholder="SKU" style="width:130px;">
        <button type="button" class="linklike uimp-change">změnit</button>`;
    } else {
      let sugg = "";
      if (p.suggested_part_id) {
        const kp = katalogPartById(p.suggested_part_id);
        const kind = p.suggest_kind === "exact" ? "stejný díl" : p.suggest_kind === "profil" ? "profil" : "podobný rozměr";
        const col = p.suggest_kind === "rozmer" ? "#c9a86a" : "#7ee081";
        sugg = `<div style="color:${col};">rozpoznáno (${kind}): ${esc(kp ? kp.name : p.suggested_part_id)}
          <button type="button" class="linklike uimp-usesugg" style="font-size:10px;">použít</button></div>`;
      }
      html = `<span style="color:#8b93a1">přeskočit</span>
        <div class="uimp-pick" style="position:relative; display:inline-block;">
          <input class="uimp-search" placeholder="hledat v katalogu…" style="width:150px;">
          <div class="uimp-suggest"></div>
        </div>
        <button type="button" class="linklike uimp-mknew">nový díl</button>${sugg}`;
    }
    const mixed = groupDecisionsMixed(g);
    if (mixed) html = `<div style="color:#e5a35a;">⚠ ve skupině jsou ${mixed} různá přiřazení - vyber znovu, ať platí pro všechny</div>` + html;
    cell.innerHTML = html;
    const us = cell.querySelector(".uimp-usesugg");
    if (us) us.onclick = () => { setGroupDecision(g, { action: "existing", part_id: p.suggested_part_id }); renderTable(); };
    const chg = cell.querySelector(".uimp-change");
    if (chg) chg.onclick = () => { setGroupDecision(g, { action: "skip" }); renderTable(); };
    const mk = cell.querySelector(".uimp-mknew");
    if (mk) mk.onclick = () => { setGroupDecision(g, newDecisionFor(g)); renderTable(); };
    const nn = cell.querySelector(".uimp-new-name");
    if (nn) nn.oninput = () => { g.members.forEach(i => { if (state.decisions[i]) state.decisions[i].name = nn.value; }); scheduleDraftSave(); };
    const ns = cell.querySelector(".uimp-new-sku");
    if (ns) ns.oninput = () => { g.members.forEach(i => { if (state.decisions[i]) state.decisions[i].sku = ns.value; }); scheduleDraftSave(); };
    if (cell.querySelector(".uimp-search")) wireSearch(tr, g);
  }

  function fragmentIds() {
    return state.parts.filter(p => isFragment(p) && !(state.decisions[p.i] && state.decisions[p.i].action !== "skip")).map(p => p.i);
  }

  function refreshSummary() {
    const n = state.parts.length;
    let ex = 0, nw = 0;
    Object.values(state.decisions).forEach(d => { if (!d) return; if (d.action === "existing") ex++; else if (d.action === "new") nw++; });
    const nf = fragmentIds().length;
    const newSkus = new Set(Object.values(state.decisions).filter(d => d && d.action === "new").map(d => d.sku));
    $("uimpSummary").textContent = `${n} dílů v ${groups.length} skupinách: ${ex} na existující, ${nw} nových (${newSkus.size} karet), ${n - ex - nw} přeskočit` + (nf ? ` (z toho ${nf} šum)` : "");
    $("uimpBuildBtn").disabled = state.building || (ex + nw === 0);
    const fb = $("uimpFragBtn");
    if (fb) { fb.textContent = `smazat šum (${nf})`; fb.style.display = nf ? "" : "none"; }
  }

  const SECTION_LABEL = { profily: "Rozpoznané profily", ostatni: "Ostatní díly", drobne: "Drobné díly (nerozpoznané, do hranice)", sum: "Šum (ploché útržky, drobky)" };

  function renderTable() {
    const rows = $("uimpRows");
    rows.innerHTML = "";
    buildGroups();
    syncGroupDecisions();
    const bySection = { profily: [], ostatni: [], drobne: [], sum: [] };
    groups.forEach(g => bySection[g.section].push(g));
    ["profily", "ostatni", "drobne", "sum"].forEach(sec => {
      const list = bySection[sec];
      if (!list.length) return;
      const nParts = list.reduce((s, g) => s + g.members.length, 0);
      const hdr = document.createElement("tr");
      hdr.className = "uimp-section";
      hdr.innerHTML = `<td colspan="4" style="cursor:pointer; color:#d0d4da; background:#20252c; font-weight:600;">${state.collapsed[sec] ? "▸" : "▾"} ${SECTION_LABEL[sec]} — ${nParts} dílů, ${list.length} ${list.length === 1 ? "skupina" : list.length < 5 ? "skupiny" : "skupin"}</td>`;
      hdr.onclick = () => { state.collapsed[sec] = !state.collapsed[sec]; renderTable(); };
      rows.appendChild(hdr);
      if (state.collapsed[sec]) return;
      list.forEach(g => {
        const p = g.rep;
        const tr = document.createElement("tr");
        tr.dataset.key = g.key;
        const mult = g.members.length > 1 ? ` <span style="color:#8fb8e0; font-weight:600;" title="${g.members.length} stejných dílů - jedno mapování pro všechny">×${g.members.length}</span>` : "";
        const ops = (p.n_merged_ops ? ` <span style="color:#8b93a1">+${p.n_merged_ops} op.</span>` : "")
          + (isFragment(p) ? ` <span style="color:#8b93a1; border:1px solid #3a4048; border-radius:3px; padding:0 3px;" title="plochý útržek bez objemu nebo drobek < 10 mm">šum</span>` : "");
        const joined = (p.joined && g.members.length === 1) ? ` <span style="color:#8fb8e0" title="vzniklo spojením (J)">⛓${p.n_members}</span> <button type="button" class="linklike uimp-split" style="font-size:10px;">rozpojit</button>` : "";
        tr.innerHTML = `<td style="width:18px;"><input type="checkbox" class="uimp-check" title="označit skupinu (J = spojit, Delete = smazat)"></td>
          <td style="cursor:pointer;" class="uimp-name" title="${esc(p.node || p.name)}">${esc(p.name)}${mult}${ops}${joined} <button type="button" class="linklike uimp-remove" style="font-size:10px; color:#e08080;" title="smazat z importu (celou skupinu)">✕</button></td>
          <td style="white-space:nowrap; color:#8b93a1;">${p.dims_mm.map(v => Math.round(v)).join("×")}</td>
          <td class="uimp-decision"></td>`;
        tr.querySelector(".uimp-name").onclick = (ev) => { if (ev.target.closest(".uimp-split, .uimp-remove")) return; highlightGroup(g); };
        const sp = tr.querySelector(".uimp-split");
        if (sp) sp.onclick = () => splitPart(p.i);
        tr.querySelector(".uimp-remove").onclick = () => removeParts(g.members.slice());
        rows.appendChild(tr);
        renderDecisionCell(tr, g);
      });
    });
    refreshSummary();
  }

  // --- J: spojit oznacene dily do jednoho -------------------------------------
  function getJoinSelection() {
    const ids = new Set();
    document.querySelectorAll("#uimpRows tr[data-key]").forEach(tr => {
      const cb = tr.querySelector(".uimp-check");
      if (cb && cb.checked) { const g = groups.find(x => x.key === tr.dataset.key); if (g) g.members.forEach(i => ids.add(i)); }
    });
    selectionSets().forEach(set => set.forEach(e => {
      if (isTmpEntry(e)) ids.add(parseInt(String(e.part.id).slice(TMP_PREFIX.length), 10));
    }));
    return [...ids].filter(Number.isFinite).sort((a, b) => a - b);
  }

  async function applyPartsUpdate(data, statusText) {
    const alive = new Set(data.parts.map(p => p.i));
    Object.keys(state.decisions).forEach(k => { if (!alive.has(parseInt(k, 10))) delete state.decisions[k]; });
    state.parts = data.parts;
    await showPreview();
    autoApplySuggestions(false);
    renderTable();
    $("uimpStatus").textContent = statusText;
  }

  async function joinSelected() {
    const status = $("uimpStatus");
    if (!state.token) return;
    const ids = getJoinSelection();
    if (ids.length < 2) { status.textContent = "Označ aspoň 2 díly (zaškrtnutím v tabulce nebo výběrem ve scéně) a stiskni J."; return; }
    status.textContent = `spojuji ${ids.length} dílů…`;
    try {
      const r = await fetch(`/api/admin/universal-import/${state.token}/join`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ parts: ids }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
      delete state.decisions[data.joined_i];
      await applyPartsUpdate(data, `✓ ${ids.length} dílů spojeno do jednoho (#${data.joined_i}) - teď ${data.n_parts} dílů`);
      const g = groupOfPart(data.joined_i);
      if (g) { state.collapsed[g.section] = false; renderTable(); highlightGroup(g); }
    } catch (e) {
      status.textContent = "Chyba spojení: " + e.message;
    }
  }

  async function splitPart(i) {
    const status = $("uimpStatus");
    if (!state.token) return;
    try {
      const r = await fetch(`/api/admin/universal-import/${state.token}/split`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ i }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
      delete state.decisions[i];
      await applyPartsUpdate(data, `✓ díl #${i} rozpojen zpět - teď ${data.n_parts} dílů`);
    } catch (e) {
      status.textContent = "Chyba rozpojení: " + e.message;
    }
  }

  // --- smazat dil(y) z importu / zrusit cely import ------------------------------
  async function removeParts(ids) {
    const status = $("uimpStatus");
    if (!state.token || !ids.length) return;
    try {
      const r = await fetch(`/api/admin/universal-import/${state.token}/remove`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ parts: ids }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
      await applyPartsUpdate(data, `✓ smazáno ${ids.length} dílů - teď ${data.n_parts} dílů`);
    } catch (e) {
      status.textContent = "Chyba mazání: " + e.message;
    }
  }

  // drobne nerozpoznane dily -> prilepit k nejblizsimu vetsimu dilu (server
  // spoji geometrii, jako CAD operace pri rozboru). quiet=true = bez
  // prekresleni sceny (vola se pred prvnim vlozenim nahledu).
  async function mergeSmall(quiet) {
    if (!state.token) return 0;
    // nejdriv rozsirit rozhodnuti skupin: clen skupiny s prirazenou kartou neni
    // "drobny nerozpoznany" a nesmi se prilepit k sousedovi (driv analyze()
    // lepil krytky/patky stejne skupiny drive, nez je prevzaly rozhodnuti)
    buildGroups();
    syncGroupDecisions();
    const ids = smallIds();
    if (!ids.length) { if (!quiet) $("uimpStatus").textContent = "žádné drobné nerozpoznané díly k přilepení"; return 0; }
    // k dilum mapovanym na EXISTUJICI katalogovy dil (profily, stejne dily,
    // rucni prirazeni) se nic neprilepuje - ve tvaru je nahradi katalogove
    // GLB, prilepena geometrie by zmizela
    const excludeHosts = state.parts.filter(p => {
      const d = decisionOf(p.i);
      return (d && d.action === "existing") || p.suggest_kind === "profil" || p.suggest_kind === "exact";
    }).map(p => p.i);
    try {
      const r = await fetch(`/api/admin/universal-import/${state.token}/merge-small`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, max_mm: smallLimit(), exclude_hosts: excludeHosts }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
      if (quiet) {
        const alive = new Set(data.parts.map(p => p.i));
        Object.keys(state.decisions).forEach(k => { if (!alive.has(parseInt(k, 10))) delete state.decisions[k]; });
        state.parts = data.parts;
      } else {
        await applyPartsUpdate(data, `✓ ${data.n_merged} drobných dílů přilepeno k sousedům` + (data.n_left ? `, ${data.n_left} bez souseda zůstalo` : ""));
      }
      return data.n_merged || 0;
    } catch (e) {
      $("uimpStatus").textContent = "Chyba přilepení drobných dílů: " + e.message;
      return 0;
    }
  }

  function removeSelected() {
    const ids = getJoinSelection();
    if (!ids.length) { $("uimpStatus").textContent = "Označ díly ke smazání (zaškrtnutím nebo výběrem ve scéně) a stiskni Delete."; return; }
    removeParts(ids);
  }

  async function cancelImport() {
    if (state.token) {
      try { await fetch(`/api/admin/universal-import/${state.token}`, { method: "DELETE" }); } catch (e) { /* ignoruj */ }
    }
    state.token = null; state.parts = []; state.decisions = {};
    await hidePreview();
    $("uimpStep2").style.display = "none";
    $("uimpFile").value = "";
    $("uimpStatus").textContent = "import zrušen";
    loadDrafts();
  }

  // J/Delete patri importu jen pri oznacenych DILECH IMPORTU; skutecny dil ve
  // scene (mimo panel importu) klavesa nikdy nesmaze ani nespoji.
  document.addEventListener("keydown", (ev) => {
    if (!state.token || state.building) return;
    const isJ = ev.key === "j" || ev.key === "J";
    const isDel = ev.key === "Delete";
    if (!isJ && !isDel) return;
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
    if (isTypingField(ev.target, isJ)) return;
    if ((typeof dragState !== "undefined" && dragState) || (typeof axisMoveDragState !== "undefined" && axisMoveDragState)
        || (typeof rotateActive !== "undefined" && rotateActive)) return;
    if (!getJoinSelection().length) return;
    const inPanel = !!(ev.target && ev.target.closest && ev.target.closest("#universalImportSection, #fwUimpWindow"));
    const sel = sceneSelectionKinds();
    if (sel.real && !sel.tmp && !inPanel) return;
    ev.preventDefault();
    ev.stopPropagation();
    if (isJ) joinSelected(); else removeSelected();
  });

  // rozpoznane profily a "stejny dil" se prirazuji AUTOMATICKY (jako u
  // "Rozklad FBX na profily" v adminu) - "podobny rozmer" je jen napoveda.
  function autoApplySuggestions(force) {
    let n = 0;
    state.parts.forEach(p => {
      if (p.suggested_part_id && (p.suggest_kind === "exact" || p.suggest_kind === "profil")
          && (force || !state.decisions[p.i] || state.decisions[p.i].action === "skip")) {
        state.decisions[p.i] = { action: "existing", part_id: p.suggested_part_id };
        n++;
      }
    });
    if (n) scheduleDraftSave();
    return n;
  }

  function applyAllSuggestions() {
    autoApplySuggestions(false);
    renderTable();
  }

  async function recognizeAgain() {
    const status = $("uimpStatus");
    if (!state.token) return;
    status.textContent = "rozpoznávám díly proti katalogu…";
    try {
      const r = await fetch(`/api/admin/universal-import/${state.token}/recognize`, { method: "POST" });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
      const byI = new Map(data.parts.map(p => [p.i, p]));
      state.parts.forEach(p => { const q = byI.get(p.i); if (q) { p.suggested_part_id = q.suggested_part_id; p.suggest_kind = q.suggest_kind; } });
      const n = autoApplySuggestions(false);
      renderTable();
      status.textContent = `rozpoznáno: ${data.n_exact} stejných dílů, ${data.n_suggested_profiles - data.n_exact} dalších návrhů (${n} nově přiřazeno)`;
    } catch (e) {
      status.textContent = "Chyba rozpoznání: " + e.message;
    }
  }

  // --- rozpracovane importy: autosave + pokracovani -------------------------------
  let draftTimer = null;
  function scheduleDraftSave() {
    if (!state.token) return;
    clearTimeout(draftTimer);
    draftTimer = setTimeout(saveDraft, 1200);
  }

  async function saveDraft() {
    if (!state.token) return;
    const catSel = $("uimpCategory");
    try {
      const r = await fetch(`/api/admin/universal-import/${state.token}/draft`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shape_name: $("uimpShapeName").value, shape_code: $("uimpShapeCode").value,
          category_id: catSel && catSel.value ? parseInt(catSel.value, 10) : null,
          decisions: state.decisions,
        }),
      });
      const data = await r.json();
      const el = $("uimpSaved");
      if (el) el.textContent = r.ok ? `uloženo ${(data.saved_at || "").slice(11, 16)}` : "uložení selhalo";
    } catch (e) {
      const el = $("uimpSaved");
      if (el) el.textContent = "uložení selhalo";
    }
  }

  async function loadDrafts() {
    const wrap = $("uimpDraftsWrap");
    if (!wrap) return;
    try {
      const r = await fetch("/api/admin/universal-import/drafts");
      const data = await r.json();
      const drafts = (data.drafts || []).filter(d => d.token !== state.token);
      if (!drafts.length) { wrap.style.display = "none"; return; }
      const sel = $("uimpDrafts");
      // cas a pocet dilu PRVNI - vic rozboru tehoz souboru ma stejny nazev
      sel.innerHTML = drafts.map(d => {
        const t = (d.saved_at || d.modified || "").slice(5, 16).replace("T", " ");
        const txt = `${t} · ${d.n_decided}/${d.n_parts} dílů · ${d.shape_name || d.source_name || d.token.slice(0, 8)}`;
        return `<option value="${esc(d.token)}" title="${esc(txt)}">${esc(txt)}</option>`;
      }).join("");
      $("uimpDraftsLabel").textContent = `Rozpracované importy (${drafts.length}):`;
      wrap.style.display = "";
    } catch (e) { wrap.style.display = "none"; }
  }

  async function resumeDraft(token) {
    const status = $("uimpStatus");
    if (!token) return;
    status.textContent = "načítám rozpracovaný import…";
    try {
      const r = await fetch(`/api/admin/universal-import/${token}`);
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
      state.token = token;
      state.parts = data.parts;
      state.sourceName = data.source_name || "";
      const dr = data.draft || {};
      state.decisions = dr.decisions || {};
      $("uimpShapeName").value = dr.shape_name || "";
      $("uimpShapeCode").value = dr.shape_code || "";
      state.shapeCode = $("uimpShapeCode").value.trim();
      fillCategories();
      if (dr.category_id != null) $("uimpCategory").value = String(dr.category_id);
      await showPreview({ pan: true });
      $("uimpStep2").style.display = "";
      if (!Object.keys(state.decisions).length) autoApplySuggestions(false);
      renderTable();
      status.textContent = `pokračuji: ${state.sourceName} – ${data.n_parts} dílů (uloženo ${dr.saved_at || "?"})`;
      loadDrafts();
    } catch (e) {
      status.textContent = "Chyba načtení: " + e.message;
    }
  }

  async function discardDraft(token) {
    if (!token) return;
    try { await fetch(`/api/admin/universal-import/${token}`, { method: "DELETE" }); } catch (e) { /* ignoruj */ }
    await loadDrafts();
    const n = $("uimpDrafts") && $("uimpDraftsWrap").style.display !== "none" ? $("uimpDrafts").options.length : 0;
    $("uimpStatus").textContent = n ? `zahozeno - zbývá ${n} rozpracovaných importů` : "zahozeno - žádný rozpracovaný import";
  }

  async function discardAllDrafts() {
    const sel = $("uimpDrafts");
    const tokens = sel ? [...sel.options].map(o => o.value) : [];
    if (!tokens.length) return;
    if (!confirm(`Zahodit všech ${tokens.length} rozpracovaných importů? (nic z nich nebylo založeno)`)) return;
    for (const t of tokens) {
      try { await fetch(`/api/admin/universal-import/${t}`, { method: "DELETE" }); } catch (e) { /* ignoruj */ }
    }
    await loadDrafts();
    $("uimpStatus").textContent = `zahozeno ${tokens.length} rozpracovaných importů`;
  }

  function allRemainingNew() {
    buildGroups();
    groups.forEach(g => {
      if (g.section === "sum") return;
      const d = decisionOf(g.rep.i);
      if (!d || d.action === "skip") setGroupDecision(g, newDecisionFor(g));
    });
    renderTable();
  }

  // --- [1] analyze ------------------------------------------------------------
  async function analyze() {
    const file = $("uimpFile").files[0];
    const status = $("uimpStatus");
    if (!file) { status.textContent = "Vyber FBX soubor."; return; }
    status.textContent = "nahrávám a rozebírám na díly…";
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("merge_ops", $("uimpMergeOps").checked ? "1" : "0");
      const r = await fetch("/api/admin/universal-import/analyze", { method: "POST", body: fd });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
      state.token = data.token;
      state.parts = data.parts;
      state.sourceName = data.source_name;
      state.decisions = {};
      state.collapsed = { profily: true, ostatni: false, drobne: true, sum: true };
      if (!$("uimpShapeCode").value.trim()) $("uimpShapeCode").value = data.shape_code_suggestion || "";
      if (!$("uimpShapeName").value.trim()) $("uimpShapeName").value = file.name.replace(/\.fbx$/i, "");
      state.shapeCode = $("uimpShapeCode").value.trim();
      loadDrafts();
      const n = autoApplySuggestions(false);
      // drobne nerozpoznane dily rovnou prilepit k sousedum (jako u SSE)
      const merged = await mergeSmall(true);
      await showPreview({ pan: true });
      $("uimpStep2").style.display = "";
      renderTable();
      status.textContent = `${data.total_meshes} meshů → ${state.parts.length} dílů v ${groups.length} skupinách; ${n} dílů přiřazeno automaticky (profily/stejné díly), ${data.n_merged_ops + merged} drobných částí přilepeno k dílům`;
    } catch (e) {
      status.textContent = "Chyba: " + e.message;
    }
  }

  // --- [3] build --------------------------------------------------------------
  async function build() {
    const status = $("uimpStatus");
    const shapeName = $("uimpShapeName").value.trim();
    if (!shapeName) { status.textContent = "Vyplň název tvaru."; return; }
    buildGroups();
    syncGroupDecisions();
    const decisions = state.parts.map(p => Object.assign({ i: p.i }, state.decisions[p.i] || { action: "skip" }));
    for (const d of decisions) {
      if (d.action === "new" && !(d.sku || "").trim()) { status.textContent = `Díl #${d.i}: chybí SKU nového dílu.`; return; }
    }
    const catSel = $("uimpCategory");
    const body = {
      token: state.token, shape_name: shapeName, shape_code: $("uimpShapeCode").value.trim(),
      category_id: catSel && catSel.value ? parseInt(catSel.value, 10) : null,
      decisions,
    };
    state.building = true; refreshSummary();
    status.textContent = "sestavuji tvar (zakládám nové karty, GLB, spoje)…";
    try {
      const r = await fetch("/api/admin/universal-import/build", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
      await hidePreview();
      (data.katalog_rows || []).forEach(p => {
        CATALOG.push({
          id: p.id, name: p.name, layer: p.layer, material_label: p.material_label, dims_mm: p.dims_mm,
          length_mm: p.length_mm, cross_section_mm: p.cross_section_mm, weight_kg: p.weight_kg_approx,
          price_czk: p.price_czk_approx_PLACEHOLDER, price_per_cut_czk: p.price_per_cut_czk,
          file: "katalog/" + p.file + "?v=" + Date.now(), visible_in_scene: !!p.visible_in_scene,
          source: p.source || "product", category_id: p.category_id != null ? p.category_id : null,
          shop_product_id: p.shop_product_id != null ? p.shop_product_id : null,
          stock_qty: p.stock_qty != null ? p.stock_qty : null, color_hex: p.color_hex || null,
          is_board_material: !!p.is_board_material,
        });
      });
      if (typeof buildCatalogList === "function") buildCatalogList();
      if (typeof renderCatalogImagePanel === "function") renderCatalogImagePanel();
      await csReloadCategoriesAndShapes();
      const shape = (CUSTOM_SHAPES || []).find(s => s.id === data.custom_shape_id);
      let besides = false;
      if (shape) besides = await addFinalShape(shape);
      const warn = (data.warnings || []).length ? ` ⚠ ${data.warnings.join("; ")}` : "";
      status.textContent = `✓ tvar „${data.name}“ (#${data.custom_shape_id}): ${data.n_parts} dílů, ${data.new_products.length} nových karet, ${data.joints_found} spojů. Nové karty jsou neaktivní (active=0) - cenu/kategorii doplň v adminu → Sklad.${besides ? " Vložen vedle stávajícího obsahu scény - nic se nesmazalo." : ""}${warn}`;
      state.token = null; state.parts = []; state.decisions = {};
      $("uimpStep2").style.display = "none";
      $("uimpFile").value = "";
      loadDrafts();
    } catch (e) {
      status.textContent = "Chyba: " + e.message;
    } finally {
      state.building = false; refreshSummary();
    }
  }

  function fillCategories() {
    const sel = $("uimpCategory");
    if (!sel || typeof CUSTOM_SHAPE_CATEGORIES === "undefined") return;
    const flat = [];
    (function walk(nodes, depth) {
      (nodes || []).forEach(n => { flat.push({ id: n.id, name: "  ".repeat(depth) + n.name }); walk(n.children, depth + 1); });
    })(CUSTOM_SHAPE_CATEGORIES, 0);
    sel.innerHTML = '<option value="">(bez kategorie)</option>' + flat.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  }

  function injectStyle() {
    const st = document.createElement("style");
    st.textContent = `
      #uimpTable td, #uimpTable th { padding:2px 4px; border-bottom:1px solid #2c3138; vertical-align:top; }
      #uimpRows tr.uimp-active td { background:#2a3a2a; }
      #uimpRows tr[data-key]:hover td { background:#262b33; }
      #uimpRows tr.uimp-section td { padding-top:6px; }
      .uimp-suggest { display:none; position:absolute; left:0; top:100%; z-index:50; min-width:240px; max-height:200px; overflow:auto;
        background:#1e2228; border:1px solid #3a4048; border-radius:4px; box-shadow:0 4px 12px rgba(0,0,0,.5); }
      .uimp-row { padding:3px 6px; cursor:pointer; font-size:11px; }
      .uimp-row:hover { background:#2e3540; }
      .uimp-decision input { font-size:11px; }`;
    document.head.appendChild(st);
  }

  function init() {
    if (!$("universalImportSection")) return;
    injectStyle();
    $("uimpAnalyzeBtn").onclick = analyze;
    $("uimpBuildBtn").onclick = build;
    $("uimpApplySuggestBtn").onclick = applyAllSuggestions;
    $("uimpAllNewBtn").onclick = allRemainingNew;
    const joinBtn = document.createElement("button");
    joinBtn.type = "button"; joinBtn.id = "uimpJoinBtn"; joinBtn.className = "linklike"; joinBtn.style.fontSize = "11px";
    joinBtn.textContent = "spojit označené (J)";
    joinBtn.title = "Označ díly zaškrtnutím v tabulce nebo výběrem ve scéně (Posun myší) a stiskni J - slijí se do jednoho dílu s jedním mapováním. Jde vrátit tlačítkem „rozpojit“.";
    joinBtn.onclick = joinSelected;
    $("uimpAllNewBtn").parentNode.appendChild(joinBtn);
    const delBtn = document.createElement("button");
    delBtn.type = "button"; delBtn.id = "uimpRemoveBtn"; delBtn.className = "linklike"; delBtn.style.fontSize = "11px"; delBtn.style.color = "#e08080";
    delBtn.textContent = "smazat označené (Del)";
    delBtn.title = "Označené díly z importu úplně odstranit (nebudou ve tvaru ani v katalogu).";
    delBtn.onclick = removeSelected;
    $("uimpAllNewBtn").parentNode.appendChild(delBtn);
    const smallWrap = document.createElement("span");
    smallWrap.style.fontSize = "11px"; smallWrap.style.whiteSpace = "nowrap";
    smallWrap.innerHTML = `<label style="color:var(--text-muted);">drobné do <input id="uimpSmallMm" type="number" value="60" min="1" max="500" step="5" style="width:52px; font-size:11px;"> mm</label>
      <button type="button" id="uimpMergeSmallBtn" class="linklike" style="font-size:11px;" title="Nerozpoznané drobné díly (max rozměr do hranice) přilepí k nejbližšímu většímu dílu - jako CAD operace při rozboru. Rozpoznané (profily, stejné díly) a už přiřazené se nesahají.">přilepit drobné k sousedům</button>`;
    $("uimpAllNewBtn").parentNode.appendChild(smallWrap);
    $("uimpMergeSmallBtn").onclick = () => mergeSmall(false);
    $("uimpSmallMm").addEventListener("change", renderTable);
    const fragBtn = document.createElement("button");
    fragBtn.type = "button"; fragBtn.id = "uimpFragBtn"; fragBtn.className = "linklike"; fragBtn.style.fontSize = "11px"; fragBtn.style.color = "#e08080"; fragBtn.style.display = "none";
    fragBtn.textContent = "smazat šum (0)";
    fragBtn.title = "Smaže všechny dosud nepřiřazené ploché útržky (nulová tloušťka) a drobky pod 10 mm. Pokud některý patří k dílu, radši ho k němu nejdřív spoj přes J.";
    fragBtn.onclick = () => { const ids = fragmentIds(); if (ids.length && confirm(`Smazat ${ids.length} útržků/drobků z importu?`)) removeParts(ids); };
    $("uimpAllNewBtn").parentNode.appendChild(fragBtn);
    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button"; cancelBtn.id = "uimpCancelBtn"; cancelBtn.className = "linklike"; cancelBtn.style.fontSize = "11px";
    cancelBtn.textContent = "zrušit import";
    cancelBtn.title = "Zahodit rozpracovaný import (nic se nezaložilo) a začít znovu.";
    cancelBtn.onclick = cancelImport;
    $("uimpAnalyzeBtn").parentNode.appendChild(cancelBtn);
    $("uimpApplySuggestBtn").textContent = "použít rozpoznané";
    $("uimpApplySuggestBtn").title = "Rozpoznané profily a stejné díly se přiřazují automaticky hned po rozboru; tohle doplní přiřazení u dílů, které jsi mezitím přepnul na „přeskočit“. „Podobný rozměr“ je jen nápověda - u řádku klikni „použít“.";
    const recBtn = document.createElement("button");
    recBtn.type = "button"; recBtn.id = "uimpRecognizeBtn"; recBtn.className = "linklike"; recBtn.style.fontSize = "11px";
    recBtn.textContent = "rozpoznat znovu";
    recBtn.title = "Znovu porovnat všechny díly s aktuálním katalogem (po spojení dílů nebo když mezitím přibyly karty).";
    recBtn.onclick = recognizeAgain;
    $("uimpAllNewBtn").parentNode.insertBefore(recBtn, $("uimpAllNewBtn"));
    const saveBtn = document.createElement("button");
    saveBtn.type = "button"; saveBtn.id = "uimpSaveBtn"; saveBtn.className = "linklike"; saveBtn.style.fontSize = "11px";
    saveBtn.textContent = "uložit rozpracované";
    saveBtn.title = "Rozpracované mapování se ukládá automaticky po každé změně; tohle uloží hned. Pokračovat jde přes „Rozpracované importy“ i po obnovení stránky.";
    saveBtn.onclick = saveDraft;
    const savedSpan = document.createElement("span");
    savedSpan.id = "uimpSaved"; savedSpan.style.fontSize = "11px"; savedSpan.style.color = "var(--text-muted)";
    $("uimpBuildBtn").parentNode.insertBefore(saveBtn, $("uimpBuildBtn"));
    $("uimpBuildBtn").parentNode.insertBefore(savedSpan, $("uimpBuildBtn"));
    const draftsWrap = document.createElement("div");
    draftsWrap.id = "uimpDraftsWrap"; draftsWrap.style.display = "none"; draftsWrap.style.marginTop = "4px";
    draftsWrap.style.fontSize = "11px";
    draftsWrap.innerHTML = `<span id="uimpDraftsLabel" style="color:var(--text-muted);">Rozpracované importy:</span>
      <select id="uimpDrafts" style="max-width:260px; font-size:11px;"></select>
      <button type="button" id="uimpResumeBtn" class="linklike" style="font-size:11px;">pokračovat</button>
      <button type="button" id="uimpDiscardBtn" class="linklike" style="font-size:11px; color:#e08080;">zahodit</button>
      <button type="button" id="uimpDiscardAllBtn" class="linklike" style="font-size:11px; color:#e08080;">zahodit vše</button>`;
    $("uimpStatus").parentNode.insertBefore(draftsWrap, $("uimpStatus"));
    $("uimpResumeBtn").onclick = () => resumeDraft($("uimpDrafts").value);
    $("uimpDiscardBtn").onclick = () => { if (confirm("Zahodit tento rozpracovaný import?")) discardDraft($("uimpDrafts").value); };
    $("uimpDiscardAllBtn").onclick = discardAllDrafts;
    ["uimpShapeName", "uimpShapeCode", "uimpCategory"].forEach(id => $(id).addEventListener("change", scheduleDraftSave));
    $("uimpShapeName").addEventListener("input", scheduleDraftSave);
    loadDrafts();
    $("uimpShapeCode").oninput = () => { state.shapeCode = $("uimpShapeCode").value.trim(); };
    $("uimpCategory").onfocus = fillCategories;
    fillCategories();
    if (typeof initFloatingShapesWindow === "function") {
      initFloatingShapesWindow({
        sectionId: "universalImportSection", title: "Import objektu (FBX)", winId: "fwUimpWindow",
        tabId: "fwUimpTab", tabLabel: "▸ Import objektu", storageKey: "sceneUniversalImportFloatingWindow",
        tabDefaultTop: 408, startClosedByDefault: true,
      });
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
