// stul-konfigurator.js - "Generátor stolu" ve 3D scéně: PŘÍJEMCE konfigurace, bez vlastního ovládání (bot8, 2026-10-04; původně panel z 2026-10-02).
//
// Robert 2026-10-03: ovládání stolu se NEDUPLIKUJE (bylo 3× zvlášť: stránka stolu, tenhle panel, Volba komponent v mini-shopu) -> „jeden modul pro vše“. Konfiguraci se nastavuje
// na stránce Generátor stolu (webapp/stul-konfigurator.html = společný modul voleb product-configurator.js, stejný jako v mini-shopu) a tlačítkem „Vložit do Scény“ se pošle sem:
//   * BroadcastChannel „stul-konfigurace“: generátor pošle {type:"ping", req}, každá otevřená karta Scény odpoví {type:"pong", id, viditelna, aktivni}, generátor vybere JEDNU a pošle jí
//     {type:"vloz", query, req} na její soukromý kanál „stul-konfigurace-<id>“ → vložení/výměna stolu ve scéně, odpověď {type:"ack", req, ok, viditelna, vymena, zprava} (protokol v2, bot10 2026-10-08;
//     starý {type:"vloz", query} na veřejném kanálu se dál obsluhuje, viz „příjem z generátoru“ níže);
//   * nebo se Scéna otevře s ?stul=<query> (stránka ji otevře sama, když žádná neodpověděla): po načtení katalogu se stůl vloží a parametr se z adresy odstraní.
// `query` = parametry generátoru (sirka=…&hloubka=…&vzpery=1…), GET /api/stul/konfigurace?query vrací díly ve formátu custom_shapes.data.parts; vložené díly jsou normální entries
// (živá cena, kusovník, spoje, „Uložit jako sestavu“ fungují jako u každého tvaru). Každé další vložení vymění JEN vlastní díly (cizí obsah scény zůstane, poloha stolu se zachová).
//
// Načítá se AŽ PO #app-script (jako universal-import.js) - používá globály scény: placed, scene, insertCustomShape, applyAutoPlacementOffset, releaseBrokenProfileJoints,
// releaseAllJointsFor, rebuildOccupiedConnectors, refreshEndpointMarkers, refreshDimLabels, window.refreshSummary, selectedMoveEntries, axisMoveSelectedEntries, jointGroups,
// currentAssemblyMeta, SCENE_LAST_LOADED_KEY, sceneUndoRestoring, sceneGeneration, CATALOG, initFloatingShapesWindow. clearAll() se NEVOLÁ - odebírá jen vlastní díly.
(function () {
  "use strict";

  const API = "/api/stul/konfigurace";
  const CHANNEL = "stul-konfigurace";
  const GENERATOR_URL = "/stul-konfigurator.html";               // generator stolu 01 (system 30)
  const GENERATOR_URL_40 = "/stul-konfigurator-40.html";         // generator stolu 02 (system 40, profil 40x40; bot10 2026-10-04)
  const GENERATORY = { 30: { no: "01", url: GENERATOR_URL }, 35: { no: "03", url: "/stul-konfigurator-35.html" }, 40: { no: "02", url: GENERATOR_URL_40 },     // generator stolu 03 = system 35 (profil 35x35; bot10 2026-10-05)
    41: { no: "04", url: "/stul-konfigurator-41.html", profil: 40, bezSceny: true },                                                            // generator stolu 04 = system 41 (ergonomicky stul SSE, profil podelniku 40x40; nohy SSE ve Scene zatim nejsou; bot8 2026-10-05)
    45: { no: "05", url: "/stul-konfigurator-45.html", profil: 40 } };                                                                                          // generator stolu 05 = system 45 (hluboky stul az 2500 mm, profil 40x40 jako system 40; bot10 2026-10-07)
  const KATALOG_MAX_CEKANI_MS = 5000;

  const state = {
    data: null,            // poslední odpověď serveru
    query: null,           // poslední vložená konfigurace (query string generátoru)
    own: [],               // entries ve scéně, které patří generátoru
    rawMin: null,          // minimální roh obalky vloženého stolu v "vygenerovaných" souřadnicích (pro zachování posunu)
    inserted: false,       // stůl je ve scéně
    seq: 0,                // číslo požadavku (zahodit opožděné odpovědi)
    posledniStav: "",      // poslední text stavu (setStatus) - posílá se generátoru, když vložení selže (panel Generátor stolu bývá zavřený)
    ui: null,
  };

  // ---------------------------------------------------------------------------------------------------------------
  // čistá logika (testováno bez prohlížeče)
  // ---------------------------------------------------------------------------------------------------------------
  async function fetchConfig(query) {
    const r = await fetch(API + "?" + String(query || ""), { credentials: "same-origin" });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      const err = new Error(data.error || ("HTTP " + r.status));
      err.kod = data.kod;
      throw err;
    }
    return data;
  }

  function systemDat(data) { const s = data && data.parametry ? Number(data.parametry.system) : 30; return GENERATORY[s] ? s : 30; }

  // Navlek nohou (jekl 40x40x2) a jeho zaslepka (jen system 35; bot10 2026-10-05) NEJSOU v katalogu Sceny (tvar vyrabi jen server pro model e-shopu): insertCustomShape by pri neznamem dilu vlozeni
  // prerusil (alert + nedokoncena sestava), proto se do Sceny nevkladaji; indexy `lic_peers` a `attached_to.prof` ostatnich dilu se prepocitaji.
  const DILY_BEZ_SCENY = { jekl_40x40x2: true, jekl_zaslepka_40: true, sse_jekl_40: true, sse_profil_35: true, sse_plech_150: true, sse_patka_35: true };
  function dilyProScenu(dily) {
    const mapa = {}, vystup = [];
    dily.forEach((d, i) => { if (!DILY_BEZ_SCENY[d.part_id]) { mapa[i] = vystup.length; vystup.push(d); } });
    if (vystup.length === dily.length) return dily;
    return vystup.map(d => {
      const c = Object.assign({}, d);
      if (Array.isArray(d.lic_peers)) c.lic_peers = d.lic_peers.filter(j => j in mapa).map(j => mapa[j]);
      if (d.attached_to) {
        if (d.attached_to.prof in mapa) c.attached_to = Object.assign({}, d.attached_to, { prof: mapa[d.attached_to.prof] });
        else delete c.attached_to;
      }
      return c;
    });
  }

  function shapeFromData(data) {
    const sy = systemDat(data);
    return { name: "Generátor stolu " + GENERATORY[sy].no + " " + (sy === 41 ? "SSE" : "systém " + sy), parts: dilyProScenu(data.dily), join_groups: [], frame_groups: [], text_labels: [] };
  }

  function summaryText(data) {
    if (!data) return "";
    const p = data.parametry, r = data.rozmery;
    const sy = systemDat(data);
    const pr = GENERATORY[sy].profil || sy;                    // šířka profilu v mm (u stolu SSE 40, ne číslo systému 41)
    return (sy !== 30 ? (sy === 41 ? "SSE" : "Systém " + sy) + " (profil " + pr + "×" + pr + ") · " : "") + "Deska " + Math.round(p.sirka) + " × " + Math.round(p.hloubka) + " mm, výška desky " + Math.round(p.vyska) +
      " mm · celková výška " + Math.round(r.vyska_mm) + " mm · " + data.pocet_spoju + " spojů profilů · " + dilyProScenu(data.dily).length + " dílů" +
      (dilyProScenu(data.dily).length !== data.dily.length ? " (návlek nohou se do Scény nevkládá)" : "");
  }

  // ---------------------------------------------------------------------------------------------------------------
  // práce se scénou (jen vlastní díly)
  // ---------------------------------------------------------------------------------------------------------------
  function sceneRefresh() {
    if (typeof rebuildOccupiedConnectors === "function") rebuildOccupiedConnectors();
    if (typeof refreshEndpointMarkers === "function") refreshEndpointMarkers();
    if (typeof refreshDimLabels === "function") refreshDimLabels();
    if (typeof window.refreshSummary === "function") window.refreshSummary();
  }

  function removeOwnEntries() {
    const mine = state.own.filter(e => placed.includes(e));
    if (!mine.length) { state.own = []; return; }
    const gone = new Set(mine);
    mine.forEach(e => {
      if (typeof selectedMoveEntries !== "undefined") selectedMoveEntries.delete(e);
      if (typeof axisMoveSelectedEntries !== "undefined") axisMoveSelectedEntries.delete(e);
      if (typeof releaseAllJointsFor === "function") releaseAllJointsFor(e);
      scene.remove(e.object3d);
      const idx = placed.indexOf(e);
      if (idx !== -1) placed.splice(idx, 1);
    });
    if (typeof jointGroups !== "undefined" && jointGroups.length) {
      jointGroups = jointGroups.map(g => { gone.forEach(e => g.delete(e)); return g; }).filter(g => g.size > 1);
    }
    if (typeof refreshMoveSelectionLabel === "function") refreshMoveSelectionLabel();
    if (typeof refreshMoveAxisButtons === "function") refreshMoveAxisButtons();
    if (typeof syncCatalogSelectionHighlight === "function") syncCatalogSelectionHighlight();
    state.own = [];
  }

  function boxMin(entries) {
    if (!entries.length || typeof bboxOfEntries !== "function") return null;
    const b = bboxOfEntries(entries);
    return b.isEmpty() ? null : [b.min.x, b.min.y, b.min.z];
  }

  // Zachová polohu stolu ve scéně: rozdíl mezi aktuálním minimálním rohem obalky stolu a rohem v "vygenerovaných"
  // souřadnicích (ruční posun / první automatické umístění vedle jiného obsahu) se použije i pro novou konfiguraci.
  function currentOffset() {
    const mine = state.own.filter(e => placed.includes(e));
    const now = boxMin(mine);
    if (!now || !state.rawMin) return null;
    return [now[0] - state.rawMin[0], now[1] - state.rawMin[1], now[2] - state.rawMin[2]];
  }

  let opQueue = Promise.resolve();
  function queueOp(fn) {
    const run = opQueue.then(fn);
    opQueue = run.catch(() => {});
    return run;
  }

  function applyToScene(data) {
    return queueOp(async () => {
      const offset = state.inserted ? currentOffset() : null;
      removeOwnEntries();
      const hadOthers = placed.length > 0;
      const savedMeta = currentAssemblyMeta;
      let savedKey = null;
      try { savedKey = localStorage.getItem(SCENE_LAST_LOADED_KEY); } catch (e) { /* ignoruj */ }
      const gen = sceneGeneration, startIdx = placed.length;
      try {
        sceneUndoRestoring = true;           // vložení = jeden krok zpět, ne mezistavy
        await insertCustomShape(shapeFromData(data), { inPlace: true });
        if (sceneGeneration !== gen) return;
        const added = placed.slice(startIdx);
        state.own = added.slice();
        const ocekavano = dilyProScenu(data.dily).length;
        if (added.length !== ocekavano) {         // insertCustomShape se při chybě jednoho dílu zastaví (alert) - napůl vložený stůl by klamal (kusovník, cena, výkresy do nabídky)
          removeOwnEntries();
          state.inserted = false;
          state.rawMin = null;
          sceneRefresh();
          throw new Error("vložilo se jen " + added.length + " z " + ocekavano + " dílů stolu, stůl se do Scény nevkládá napůl");
        }
        const rawMin = boxMin(added);          // obalka v souřadnicích ze serveru (před posunem)
        if (offset) {
          added.forEach(e => e.object3d.position.set(e.object3d.position.x + offset[0], e.object3d.position.y + offset[1], e.object3d.position.z + offset[2]));
          added.forEach(e => { e.object3d.userData.basePos = e.object3d.position.clone(); });
        } else if (hadOthers && added.length) {
          applyAutoPlacementOffset(startIdx, []);
          added.forEach(e => { e.object3d.userData.basePos = e.object3d.position.clone(); });
          added.forEach(e => { if (typeof releaseBrokenProfileJoints === "function") releaseBrokenProfileJoints(e); });
        }
        state.rawMin = rawMin;
        state.inserted = true;
      } finally {
        sceneUndoRestoring = false;
        // konfigurátor nemění identitu otevřené sestavy ani klíč obnovy po F5
        currentAssemblyMeta = savedMeta;
        try {
          if (savedKey == null) localStorage.removeItem(SCENE_LAST_LOADED_KEY);
          else localStorage.setItem(SCENE_LAST_LOADED_KEY, savedKey);
        } catch (e) { /* ignoruj */ }
      }
      sceneRefresh();
    });
  }

  function removeFromScene() {
    return queueOp(async () => {
      removeOwnEntries();
      state.inserted = false;
      state.rawMin = null;
      sceneRefresh();
    });
  }

  // ---------------------------------------------------------------------------------------------------------------
  // panel (jen informace + odebrání) a příjem konfigurace
  // ---------------------------------------------------------------------------------------------------------------
  function $(id) { return document.getElementById(id); }

  function setStatus(text, isError) {
    state.posledniStav = text || "";
    const el = $("stulKonfStatus");
    if (!el) return;
    el.textContent = text || "";
    el.style.color = isError ? "#e08080" : "var(--text-muted)";
  }

  function renderProblems(data) {
    const el = $("stulKonfProblems");
    if (!el) return;
    el.textContent = "";
    if (!data) return;
    const probs = data.problemy || [];
    if (!probs.length) {
      el.style.color = "#7fc97f";
      el.textContent = "✔ Všechny díly i spoje jsou v pořádku (každý konec profilu dosedá, žádné zanoření).";
      return;
    }
    el.style.color = "#e08080";
    const head = document.createElement("div");
    head.textContent = "⚠ Konstrukce neplatí (" + probs.length + "): tuto kombinaci by zákazník nedostal.";
    el.appendChild(head);
    probs.slice(0, 8).forEach(pr => {
      const d = document.createElement("div");
      d.style.cssText = "font-size:11px;margin-left:8px;";
      d.textContent = "• " + pr.text;
      el.appendChild(d);
    });
    if (probs.length > 8) {
      const d = document.createElement("div");
      d.style.cssText = "font-size:11px;margin-left:8px;";
      d.textContent = "… a dalších " + (probs.length - 8);
      el.appendChild(d);
    }
  }

  // Vloží (nebo vymění) stůl podle konfigurace `query` (parametry generátoru). Vrací Promise; chyba serveru nic ve scéně nemění.
  async function vloz(query) {
    const mySeq = ++state.seq;
    setStatus("Počítám…", false);
    let data;
    try {
      data = await fetchConfig(query);
    } catch (err) {
      if (mySeq !== state.seq) return false;
      setStatus("Chyba: " + err.message, true);
      return false;
    }
    if (mySeq !== state.seq) return false;            // mezitím přišla novější konfigurace
    if (GENERATORY[systemDat(data)].bezSceny) {                  // stůl SSE: nohy SSE (jekly, plechy, vnitřní profily) nejsou ve Scéně → neúplný stůl by klamal, nevkládá se
      setStatus("Stůl SSE se do Scény zatím nevkládá (nohy SSE ve Scéně nejsou).", true);
      return false;
    }
    state.data = data;
    state.query = query;
    renderProblems(data);
    setStatus(summaryText(data), false);
    if (typeof CATALOG !== "undefined" && !CATALOG.length) { setStatus("Katalog dílů se ještě načítá, zkus za chvíli.", true); return false; }
    let nenalezene = [];
    try { nenalezene = await doplnChybejiciDily(dilyProScenu(data.dily)); } catch (err) { nenalezene = ["(" + err.message + ")"]; }
    if (mySeq !== state.seq) return false;            // mezitím přišla novější konfigurace
    if (nenalezene.length) { setStatus("Do Scény nejde vložit díl stolu, který katalog nezná: " + nenalezene.join(", ") + ". Stůl se nevkládá, aby nebyl napůl.", true); return false; }
    try { await applyToScene(data); } catch (err) { setStatus("Vložení do scény selhalo: " + err.message, true); return false; }
    return true;
  }

  // ---------------------------------------------------------------------------------------------------------------
  // díly stolu, které katalog Scény nezná (bot10, 2026-10-08)
  // ---------------------------------------------------------------------------------------------------------------
  // GET /api/katalog vrací produkty jen s visible_in_scene=1. Patka M8 (product_3251, systémy 30 a 35) ji má 0, takže ji insertCustomShape nenašel, na prvním takovém dílu vkládání PŘERUŠIL
  // ("neznámý díl product_3251 v katalogu") a stůl s patkami zůstal ve Scéně napůl (21 z 51 dílů) - i ve výkresech a 3D pohledech, které Scéna dělá do online nabídky z generátoru.
  // Chybějící produkt se proto před vložením doplní do CATALOG z veřejné karty (GET /api/shop/products/<id>: název, soubor modelu, barva, cena) jen pro tuto relaci, jako to dělá vandr-ref.js;
  // do výběru dílů ve Scéně se nedostane (visible_in_scene: false). Cena dílu je z karty bez koeficientu Scény (jen u takto doplněných dílů). Nelze-li díl doplnit, stůl se nevloží napůl.
  function radekKatalogu(id, p) {
    return {
      id: id, name: p.name || id, layer: "produkt", material_label: null, dims_mm: [null, null, null], length_mm: null, cross_section_mm: [null, null],
      weight_kg: p.weight_g != null ? Number(p.weight_g) / 1000 : null, price_czk: p.price_czk_placeholder != null ? Number(p.price_czk_placeholder) : null, price_per_cut_czk: null,
      file: "katalog/" + p.glb_file + "?v=" + (typeof CACHE_BUST !== "undefined" ? CACHE_BUST : Date.now()), visible_in_scene: false, source: "product",
      category_id: p.category_id != null ? p.category_id : null, shop_product_id: p.id, stock_qty: p.stock_qty != null ? p.stock_qty : null,
      accessory_conn_enabled: null, uhelnik_pose: null, sku: p.sku || null, color_hex: p.color_hex || null, attach_mode: null, attach_pose: null, attach_offset_mm: 0, geo_faces: null,
      is_board_material: !!p.is_board_material, unit: p.unit || null, price_basis: p.price_basis || null, thumbnail_file: null, dogus_image_schema_url: null, place_vertical: !!p.place_vertical,
    };
  }

  // Vrací seznam id dílů, které katalog nezná A nepodařilo se je doplnit (prázdný = vše je k dispozici).
  async function doplnChybejiciDily(parts) {
    const chybi = [];
    parts.forEach(d => { if (chybi.indexOf(d.part_id) < 0 && !katalogPartById(d.part_id)) chybi.push(d.part_id); });
    const nepodarilo = [];
    for (const id of chybi) {
      const m = /^product_(\d{1,9})$/.exec(String(id));
      if (!m) { nepodarilo.push(id); continue; }
      try {
        const r = await fetch("/api/shop/products/" + m[1], { credentials: "same-origin" });
        const j = await r.json().catch(() => ({}));
        const p = r.ok && j && j.product;
        if (!p || !p.glb_file || String(p.id) !== m[1]) { nepodarilo.push(id); continue; }
        if (!katalogPartById(id)) CATALOG.push(radekKatalogu(id, p));
      } catch (e) { nepodarilo.push(id); }
    }
    return nepodarilo;
  }

  function build(section) {
    section.textContent = "";
    const mk = (tag, attrs, text) => {
      const el = document.createElement(tag);
      if (attrs) Object.keys(attrs).forEach(k => { if (k === "style") el.style.cssText = attrs[k]; else el.setAttribute(k, attrs[k]); });
      if (text != null) el.textContent = text;
      return el;
    };
    const head = mk("div", { class: "hint", style: "display:flex;align-items:center;gap:6px;" });
    head.appendChild(mk("strong", null, "Generátor stolu (systém 30, 35, 40, 45 a SSE)"));
    section.appendChild(head);
    section.appendChild(mk("div", { id: "stulKonfInfo", style: "font-size:11px;color:var(--text-muted);margin:4px 0;" },
      "Konfiguraci stolu nastavíš na stránce Generátor stolu (01 = systém 30, 02 = systém 40, 03 = systém 35, 04 = stůl SSE – ten se do Scény zatím nevkládá, 05 = systém 45, hluboký stůl; stejné ovládání jako v mini-shopu) a tlačítkem „Vložit do Scény“ ji pošleš sem. Další vložení vymění jen vlastní díly stolu."));
    const btns = mk("div", { style: "display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;" });
    const open = mk("button", { type: "button", id: "stulKonfOpenBtn", style: "font-size:12px;" }, "Otevřít generátor stolu");
    const del = mk("button", { type: "button", id: "stulKonfRemoveBtn", style: "font-size:12px;" }, "Odebrat stůl ze scény");
    btns.appendChild(open); btns.appendChild(del);
    section.appendChild(btns);
    section.appendChild(mk("div", { id: "stulKonfStatus", style: "font-size:11px;margin-top:6px;color:var(--text-muted);" }));
    section.appendChild(mk("div", { id: "stulKonfProblems", style: "font-size:12px;margin-top:4px;" }));
    open.addEventListener("click", () => { window.open(GENERATORY[systemDat(state.data)].url, "_blank"); });
    del.addEventListener("click", () => { removeFromScene(); setStatus("Stůl odebrán ze scény.", false); });
    state.ui = section;
  }

  // ---------------------------------------------------------------------------------------------------------------
  // příjem z generátoru, protokol v2 (bot10, 2026-10-08; protějšek: webapp/js/stul-do-sceny.js)
  // ---------------------------------------------------------------------------------------------------------------
  // Robert: „klikl jsem na vložit do scény, nic se nevložilo“ - stůl se vložil do JINÉ (skryté) karty Scény a nikdo neřekl do které (karet bývá víc, každý odkaz „Scéna“ otevře novou, prázdnou).
  // Každá karta Scény má vlastní id: na „ping“ generátoru se hned ohlásí („pong“: viditelná?, kdy ji uživatel naposledy použil), generátor vybere JEDNU a pošle jí stůl na její soukromý kanál
  // „stul-konfigurace-<id>“; ostatní karty se nemění. Odpověď („ack“ s req) přijde až po vložení (smí trvat déle než 1,5 s - studená Scéna načítá modely) a nese viditelnost, zda šlo o výměnu
  // a při chybě text hlášení (panel „Generátor stolu“ bývá zavřený). Karta, do které se stůl vložil, když byla skrytá, dostane před název „● “ (zmizí, jakmile se ukáže). Starý protokol
  // (veřejný kanál, {type:"vloz", query} bez req) se dál obsluhuje pro generátory ze starší verze stránky.
  const SCENE_ID = Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
  let posledniAktivita = Date.now();
  let titulPuvodni = null;
  ["pointerdown", "keydown", "wheel", "touchstart"].forEach(ev => window.addEventListener(ev, () => { posledniAktivita = Date.now(); }, { passive: true, capture: true }));
  function zrusZnackuKarty() { try { if (titulPuvodni != null) { document.title = titulPuvodni; titulPuvodni = null; } } catch (e) { /* ignoruj */ } }
  function oznacKartu() { try { if (document.hidden && titulPuvodni == null) { titulPuvodni = document.title; document.title = "● " + titulPuvodni; } } catch (e) { /* ignoruj */ } }
  document.addEventListener("visibilitychange", () => { if (!document.hidden) { posledniAktivita = Date.now(); zrusZnackuKarty(); } });
  window.addEventListener("focus", () => { posledniAktivita = Date.now(); zrusZnackuKarty(); });

  function obsluzVlozeni(m, kanal) {                                                       // spolecne pro soukromy kanal a zalozni cestu generatoru v2 (verejny kanal s req)
    const vymena = !!state.inserted, seq0 = state.seq + 1;                                // vloz() zvysuje state.seq hned na zacatku: jine cislo po skonceni = prebil ho novejsi pozadavek
    return vloz(m.query).then(ok => {
      if (ok) oznacKartu();
      const zprava = ok ? "" : (state.seq !== seq0 ? "vložení přebil novější požadavek z generátoru" : String(state.posledniStav || "").slice(0, 240));
      try { kanal.postMessage({ type: "ack", req: m.req, ok: !!ok, viditelna: !document.hidden, vymena: vymena, zprava: zprava }); } catch (e) { /* ignoruj */ }
    });
  }

  function listen() {
    if (typeof BroadcastChannel === "undefined") return;
    try {
      const bc = new BroadcastChannel(CHANNEL);
      bc.onmessage = (ev) => {
        const m = ev && ev.data;
        if (!m) return;
        if (m.type === "ping" && typeof m.req === "string") {                              // generátor hledá Scénu: ohlásím se, nic nevkládám
          try { bc.postMessage({ type: "pong", req: m.req, id: SCENE_ID, viditelna: !document.hidden, aktivni: posledniAktivita }); } catch (e) { /* ignoruj */ }
          return;
        }
        if (m.type !== "vloz" || typeof m.query !== "string") return;
        if (typeof m.req === "string") { obsluzVlozeni(m, bc); return; }                  // záložní cesta generátoru v2: na ping jsem nestihla odpovědět (vytížená Scéna), odpovím ackem s req
        vloz(m.query).then(ok => { if (ok) oznacKartu(); try { bc.postMessage({ type: "ack", ok: !!ok }); } catch (e) { /* ignoruj */ } });   // starý protokol: do každé karty Scény
      };
      state.channel = bc;
      const pc = new BroadcastChannel(CHANNEL + "-" + SCENE_ID);                           // soukromý kanál této karty: generátor v2 posílá stůl jen jedné Scéně
      pc.onmessage = (ev) => {
        const m = ev && ev.data;
        if (!m || m.type !== "vloz" || typeof m.query !== "string" || typeof m.req !== "string") return;
        obsluzVlozeni(m, pc);
      };
      state.privateChannel = pc;
    } catch (e) { /* zadny kanal - zbyva ?stul= */ }
  }

  function fromUrl() {
    let q = null;
    try { q = new URLSearchParams(location.search).get("stul"); } catch (e) { q = null; }
    if (!q) return;
    window.__stulZAdresy = true;                             // (stul-nabidka-vykresy.js pozna, ze stul v adrese byl, i kdyz parametr hned mizi)
    try {                                                    // parametr z adresy pryc, at ho F5 nevlozi znovu
      const u = new URL(location.href); u.searchParams.delete("stul"); history.replaceState(null, "", u.pathname + (u.search || "") + u.hash);
    } catch (e) { /* ignoruj */ }
    const t0 = Date.now();
    const wait = () => {
      if ((typeof CATALOG !== "undefined" && CATALOG.length) || Date.now() - t0 > KATALOG_MAX_CEKANI_MS) {
        // po vlozeni se posle udalost (vykresy do nabidky z konfigurace stolu, stul-nabidka-vykresy.js, na ni cekaji); bez posluchace se nic nedeje
        vloz(q).then(ok => { try { window.dispatchEvent(new CustomEvent("stul-z-adresy-vlozen", { detail: { ok: !!ok } })); } catch (e) { /* stara scena bez CustomEvent */ } });
      } else setTimeout(wait, 100);
    };
    wait();
  }

  function init() {
    const section = $("stulKonfSection");
    if (!section) return;
    build(section);
    if (typeof initFloatingShapesWindow === "function") {
      initFloatingShapesWindow({
        sectionId: "stulKonfSection", title: "Generátor stolu (systém 30, 35, 40, 45 a SSE)", winId: "fwStulKonfWindow",
        tabId: "fwStulKonfTab", tabLabel: "▸ Generátor stolu", storageKey: "sceneStulKonfFloatingWindow",
        tabDefaultTop: 440, startClosedByDefault: true,
      });
    }
    listen();
    fromUrl();
  }

  // pro testy (bez prohlížeče)
  window.StulKonf = { state, shapeFromData, summaryText, vloz, applyToScene, removeFromScene, removeOwnEntries, currentOffset, renderProblems, fetchConfig, sceneId: SCENE_ID };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
