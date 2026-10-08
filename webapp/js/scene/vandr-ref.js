// vandr-ref.js - VANDR MODEL (karta VD-...) jako REFERENCNI objekt v hlavni Scene, posazeny do karoserie z knihovny (bot8, 2026-10-07).
//
// Robert 2026-10-06: "VD-2c24d107-... tuto sestavu potrebuji vlozit do sceny a do karoserie MAN L3H3" (-> "Hlavni scena, cely model", bez ceny a kusovniku, jde s nim posouvat).
// Vandr karta je MONOLITICKY GLB (webapp/katalog/vandr/, chraneny: jen staff pres /api/vandr-glb-file/); do Sceny se vklada CELY, beze zmeny, jako "kontrolni pomucka"
// (role kontrolni-pomucka-vandr-<karta>, scene-geometry-shared.js isKontrolniPart): mimo kusovnik, cenu, spoje, kolizni kontrolu karoserie a mimo ULOZENI sestavy/tvaru
// (collectSelectedEntriesForSave ji vyrazuje) - presne jako "Obloženi karoserie (kontrola)". Jde s nim hybat beznymi nastroji sceny (Posun mysi, osy) i tlacitky panelu.
//
// Zarovnani Vandr souradnic -> karoserie z knihovny (overeno na K-227 MAN TGE L3H3 FWD, Node kolizni modul 2026-10-06: bez kolize, u steny pod 10 mm, od prepazky 271 mm jako ve Vandr):
//   - Vandr vuz ma prepazku na +z a levou stranu na +x (pravotociva soustava OTOCENA o 180 st. kolem Y proti knihovne, kde je prepazka na -z a leva strana na -x) -> otoceni o 180 st. kolem Y,
//   - podlaha: horni plocha plechu "podlaha" ve Vandr modelu (y_v) -> horni plocha podlahy karoserie (paprsek shora v ose vozu),
//   - prepazka: konec plechu "podlaha" na +z (z_v) -> lic prepazky v karoserii (vodorovny paprsek z zadku podel osy vozu): p' = R_y(180) p + (0, y_podlaha - y_v, z_prepazka + z_v).
// Plechy "podlaha", "dimension*", "fixarea", "legshoverbox", "logo", "text" se z referencniho modelu odeberou (pomocne uzly exportu, viz kontrola.html VD_VYNECHAT).
// Model BEZ plechu "podlaha" (napr. ponk na prepazku #4969, FBX mimo Vandr admin): nejnizsi bod modelu = podlaha, nejvyssi z (zada, tam je prepazka) = lic prepazky, x vystredeno v ose vozu.
//
// Vstup: panel "Vandr model v karoserii" (plovouci okno) NEBO adresa /scene.html?vandr=<id karty>[&karoserie=K-227] (nic se nemaze, scena nic neobnovuje z F5 - viz scene.html).
// Nacita se AZ PO stul-konfigurator.js; pouziva globaly sceny: placed, scene, camera, controls, loader, CATALOG, CUSTOM_SHAPES, insertCustomShape, isCarBodyPart, isKontrolniPart,
// applyPartMaterial, bboxOfEntries, sceneUndoRestoring, currentAssemblyMeta, SCENE_LAST_LOADED_KEY.
(function () {
  "use strict";

  const ID_PREFIX = "vandr_";
  const ROLE_PREFIX = "kontrolni-pomucka-vandr-";
  const POMOCNE_RE = /^(podlaha|karoserie|dimension|fixarea|legshoverbox|logo|text)/i;      // segmenty cesty uzlu = pomocne uzly Vandr exportu
  const KATALOG_MAX_CEKANI_MS = 30000;
  const state = { kartaId: null, karta: null, entry: null, tvarId: null, zarovnani: null, seq: 0, ui: null, shapes: [], prehled: null, fw: null, zUrl: false };

  const $ = id => document.getElementById(id);
  const qs = new URLSearchParams(location.search);

  // ---------------------------------------------------------------------------------------------------------------------------------
  // pomocne
  // ---------------------------------------------------------------------------------------------------------------------------------
  function setStatus(text, chyba) {
    const el = $("vandrRefStatus");
    if (el) { el.textContent = text || ""; el.style.color = chyba ? "#e08080" : "var(--text-muted)"; }
    const b = $("vandrRefBanner");
    if (b) { b.textContent = text || ""; b.style.background = chyba ? "#8a1f1f" : "#16324f"; b.hidden = !text; }
  }

  function vandrUrl(glbFile) {
    return String(glbFile).startsWith("vandr/") ? "/api/vandr-glb-file/" + String(glbFile).slice("vandr/".length) : "/katalog/" + glbFile;
  }

  function cestaUzlu(n) {
    const seg = [];
    for (let o = n; o; o = o.parent) if (o.name) seg.push(o.name);
    return seg.reverse();
  }
  const jePomocny = n => cestaUzlu(n).some(s => POMOCNE_RE.test(s));

  async function ctiKartu(id) {
    const r = await fetch("/api/kontrola-scena/vd/" + encodeURIComponent(id), { credentials: "same-origin" });
    const d = await r.json().catch(() => ({}));
    if (!r.ok || !d.product) throw new Error((d && d.error) || ("karta " + id + ": HTTP " + r.status));
    return d.product;
  }

  function nactiGlb(url) {
    return new Promise((resolve, reject) => loader.load(url, g => resolve(g.scene), undefined, reject));
  }

  // karoserie z knihovny = vlastni tvary "... [K-xxx] ... - karoserie (L+R_D+B)"
  function tvaryKaroserii() {
    return (typeof CUSTOM_SHAPES !== "undefined" ? CUSTOM_SHAPES : []).filter(s => /karoserie \(L\+R_D\+B\)\s*$/.test(s.name || ""));
  }
  function kodKaroserie(s) { const m = /\[(K-\d+[a-z]?)\]/i.exec(s.name || ""); return m ? m[1].toUpperCase() : null; }
  function najdiTvar(kod) {
    const k = String(kod || "").trim().toUpperCase();
    return tvaryKaroserii().find(s => kodKaroserie(s) === k) || null;
  }
  const maKaroserii = () => placed.some(e => isCarBodyPart(e));

  // ---------------------------------------------------------------------------------------------------------------------------------
  // zmereni karoserie (podlaha, prepazka) a Vandr modelu (plech podlaha)
  // ---------------------------------------------------------------------------------------------------------------------------------
  function zmerKaroserii() {
    const meshes = [];
    placed.forEach(e => { if (isCarBodyPart(e)) e.object3d.traverse(n => { if (n.isMesh) meshes.push(n); }); });
    if (!meshes.length) return null;
    scene.updateMatrixWorld(true);
    const box = new THREE.Box3();
    meshes.forEach(m => box.expandByObject(m));
    const rc = new THREE.Raycaster();
    const ys = [];
    for (const k of [0.3, 0.45, 0.6]) {                      // svisle paprsky shora v ose vozu mezi zadkem a prepazkou
      const z = box.max.z - (box.max.z - box.min.z) * k;
      rc.set(new THREE.Vector3(0, box.max.y + 500, z), new THREE.Vector3(0, -1, 0));
      rc.far = box.max.y - box.min.y + 1000;
      const h = rc.intersectObjects(meshes, false)[0];
      if (h) ys.push(h.point.y);
    }
    if (!ys.length) return null;
    ys.sort((a, b) => a - b);
    const yPodlaha = ys[Math.floor(ys.length / 2)];
    rc.set(new THREE.Vector3(0, yPodlaha + 700, box.max.z - 100), new THREE.Vector3(0, 0, -1));
    rc.far = box.max.z - box.min.z + 500;
    const hb = rc.intersectObjects(meshes, false)[0];
    if (!hb) return null;
    return { yPodlaha, zPrepazka: hb.point.z, box };
  }

  function zmerVandr(pre) {
    pre.updateMatrixWorld(true);
    const pod = new THREE.Box3(), vse = new THREE.Box3();
    let mamPod = false;
    pre.traverse(n => {
      if (!n.isMesh) return;
      if (cestaUzlu(n).some(s => /^podlaha/i.test(s))) { pod.expandByObject(n); mamPod = true; }
      else if (!jePomocny(n)) vse.expandByObject(n);
    });
    // bez plechu podlahy (model mimo Vandr export, napr. ponk na prepazku): nejnizsi bod = podlaha, nejvyssi z (zada modelu) = prepazka, vystredit v ose vozu
    return mamPod ? { yTop: pod.max.y, zKonec: pod.max.z, xStred: 0, podlaha: true }
                  : { yTop: vse.min.y, zKonec: vse.max.z, xStred: (vse.min.x + vse.max.x) / 2, podlaha: false };
  }

  // ---------------------------------------------------------------------------------------------------------------------------------
  // vlozeni
  // ---------------------------------------------------------------------------------------------------------------------------------
  let opQueue = Promise.resolve();
  function queueOp(fn) { const run = opQueue.then(fn); opQueue = run.catch(() => {}); return run; }

  function sceneRefresh() {
    if (typeof rebuildOccupiedConnectors === "function") rebuildOccupiedConnectors();
    if (typeof refreshEndpointMarkers === "function") refreshEndpointMarkers();
    if (typeof refreshDimLabels === "function") refreshDimLabels();
    if (typeof window.refreshSummary === "function") window.refreshSummary();
  }

  function odeberReferenci() {
    const e = state.entry;
    state.entry = null;
    if (!e || !placed.includes(e)) return;
    if (typeof selectedMoveEntries !== "undefined") selectedMoveEntries.delete(e);
    if (typeof axisMoveSelectedEntries !== "undefined") axisMoveSelectedEntries.delete(e);
    scene.remove(e.object3d);
    placed.splice(placed.indexOf(e), 1);
    if (typeof refreshMoveSelectionLabel === "function") refreshMoveSelectionLabel();
    if (typeof refreshMoveAxisButtons === "function") refreshMoveAxisButtons();
    if (typeof syncCatalogSelectionHighlight === "function") syncCatalogSelectionHighlight();
    sceneRefresh();
  }

  function zarameni() {
    if (typeof bboxOfEntries !== "function" || !camera || !camera.isPerspectiveCamera || typeof controls === "undefined") return;
    const box = bboxOfEntries(placed);
    if (box.isEmpty()) return;
    const c = box.getCenter(new THREE.Vector3()), s = box.getSize(new THREE.Vector3());
    const dist = Math.max(s.x, s.y, s.z) * 0.9 / Math.tan((camera.fov || 45) * Math.PI / 360);
    camera.position.copy(c).add(new THREE.Vector3(0.9, 0.55, 1.0).normalize().multiplyScalar(dist));
    controls.target.copy(c);
    camera.lookAt(c);
    controls.update();
  }

  async function vloz(kartaId, kodKarosErie) {
    const mySeq = ++state.seq;
    return queueOp(async () => {
      if (mySeq !== state.seq) return false;
      try {
        setStatus("Načítám kartu #" + kartaId + "…", false);
        if (typeof CATALOG === "undefined" || !CATALOG.length) throw new Error("Katalog dílů se ještě načítá, zkus za chvíli.");
        const karta = await ctiKartu(kartaId);
        const url = vandrUrl(karta.glb_file);
        // karoserie (jen kdyz ve scene zadna neni; jinak se pouzije ta, co tam je)
        if (!maKaroserii()) {
          const tvar = najdiTvar(kodKarosErie);
          if (!tvar) throw new Error(kodKarosErie ? ("Karoserie " + kodKarosErie + " není v knihovně.") : "Ve scéně není karoserie - vyber ji v panelu.");
          setStatus("Vkládám karoserii " + kodKarosErie + "…", false);
          const savedMeta = currentAssemblyMeta;
          let savedKey = null;
          try { savedKey = localStorage.getItem(SCENE_LAST_LOADED_KEY); } catch (e) { /* ignoruj */ }
          try {
            sceneUndoRestoring = true;
            await insertCustomShape(tvar, { inPlace: true });
          } finally {
            sceneUndoRestoring = false;
            currentAssemblyMeta = savedMeta;
            try { if (savedKey == null) localStorage.removeItem(SCENE_LAST_LOADED_KEY); else localStorage.setItem(SCENE_LAST_LOADED_KEY, savedKey); } catch (e) { /* ignoruj */ }
          }
          state.tvarId = tvar.id != null ? tvar.id : null;
        }
        const mer = zmerKaroserii();
        if (!mer) throw new Error("Z karoserie se nepodařilo změřit podlahu a přepážku.");
        setStatus("Načítám model z karty (2-3 MB)…", false);
        const pre = await nactiGlb(url);                       // jen ke zmereni plechu podlahy a barev materialu (puvodni materialy prepise material sceny)
        const vz = zmerVandr(pre);
        const barvy = [];
        pre.traverse(n => { if (n.isMesh) { const m = Array.isArray(n.material) ? n.material[0] : n.material; barvy.push({ pomocny: jePomocny(n), hex: m && m.color ? "#" + m.color.getHexString() : null }); } });

        odeberReferenci();
        const partId = ID_PREFIX + karta.id;
        for (let i = CATALOG.length - 1; i >= 0; i--) if (CATALOG[i].id === partId) CATALOG.splice(i, 1);
        CATALOG.push({
          id: partId, name: (karta.name || ("Karta " + karta.id)) + " (Vandr, referenční)", layer: "produkt", material_label: null, dims_mm: [null, null, null], length_mm: null,
          cross_section_mm: [null, null], weight_kg: null, price_czk: null, price_per_cut_czk: null, file: url, visible_in_scene: false, source: "product", category_id: null,
          shop_product_id: null, stock_qty: null, color_hex: null, is_board_material: false, sku: karta.sku || null,
        });
        const poz = [vz.xStred, mer.yPodlaha - vz.yTop, mer.zPrepazka + vz.zKonec];
        const shape = { name: "Vandr model (referenční): " + (karta.name || karta.id),
          parts: [{ part_id: partId, position: poz, quaternion: [0, 1, 0, 0], scale: [1, 1, 1], role: ROLE_PREFIX + karta.id }], join_groups: [], frame_groups: [], text_labels: [] };
        const savedMeta2 = currentAssemblyMeta;
        let savedKey2 = null;
        try { savedKey2 = localStorage.getItem(SCENE_LAST_LOADED_KEY); } catch (e) { /* ignoruj */ }
        const startIdx = placed.length;
        try {
          sceneUndoRestoring = true;
          await insertCustomShape(shape, { inPlace: true });
        } finally {
          sceneUndoRestoring = false;
          currentAssemblyMeta = savedMeta2;
          try { if (savedKey2 == null) localStorage.removeItem(SCENE_LAST_LOADED_KEY); else localStorage.setItem(SCENE_LAST_LOADED_KEY, savedKey2); } catch (e) { /* ignoruj */ }
        }
        const entry = placed.slice(startIdx).find(e => e.part && e.part.id === partId);
        if (!entry) throw new Error("Model se do scény nevložil.");
        // pomocne uzly pryc, ostatnim meshum unikatni jmeno + puvodni barva z GLB (jinak by sceneu vsechno splynulo do jedne barvy vrstvy)
        const pryc = [];
        const meshColors = {};
        let i = 0;
        entry.object3d.traverse(n => {
          if (!n.isMesh) return;
          const b = barvy[i++];
          if (!b || b.pomocny) { pryc.push(n); return; }
          n.name = "vr" + (i - 1);
          if (b.hex) meshColors[n.name] = b.hex;
        });
        pryc.forEach(n => { if (n.parent) n.parent.remove(n); });
        entry.object3d.userData.meshColors = meshColors;
        applyPartMaterial(entry.object3d, entry.part.layer, undefined);
        state.kartaId = karta.id; state.karta = karta; state.entry = entry; state.zarovnani = { poz: poz.slice(), mer, vz };
        sceneRefresh();
        zarameni();
        const b = new THREE.Box3().setFromObject(entry.object3d);
        const mezeraPrep = Math.round(b.min.z - mer.zPrepazka);
        setStatus("Hotovo: karta #" + karta.id + " v karoserii" + (kodKarosErie ? " " + kodKarosErie : "") + " - podlaha y " + Math.round(mer.yPodlaha) + ", přepážka z " + Math.round(mer.zPrepazka) +
          ", mezera regálu k přepážce " + mezeraPrep + " mm. Posouvej tlačítky níže nebo běžnými nástroji scény; model není v kusovníku, ceně ani v uložení.", false);
        if (state.zUrl && state.fw && state.fw.show) state.fw.show();                      // z odkazu: ukaz panel s posunem hned
        try { const u = new URL(location.href); u.searchParams.set("vandr", String(karta.id)); if (kodKarosErie) u.searchParams.set("karoserie", kodKarosErie); history.replaceState(null, "", u.pathname + u.search + u.hash); } catch (e) { /* ignoruj */ }
        return true;
      } catch (err) {
        setStatus("Vandr model se nepodařilo vložit: " + (err && err.message || err), true);
        return false;
      }
    });
  }

  // posun / otoceni referencniho modelu tlacitky panelu (mm, stupne kolem svisle osy modelu)
  function posun(dx, dy, dz) {
    const e = state.entry;
    if (!e || !placed.includes(e)) { setStatus("Žádný Vandr model ve scéně.", true); return; }
    e.object3d.position.x += dx; e.object3d.position.y += dy; e.object3d.position.z += dz;
    e.object3d.userData.basePos = e.object3d.position.clone();
    e.object3d.updateMatrixWorld(true);
  }
  function otoc(stupne) {
    const e = state.entry;
    if (!e || !placed.includes(e)) { setStatus("Žádný Vandr model ve scéně.", true); return; }
    const c = new THREE.Box3().setFromObject(e.object3d).getCenter(new THREE.Vector3());
    const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), stupne * Math.PI / 180);
    const p = e.object3d.position.clone().sub(c).applyQuaternion(q).add(c);          // otoceni kolem svisle osy stredu modelu
    e.object3d.position.copy(p);
    e.object3d.quaternion.premultiply(q);
    e.object3d.userData.basePos = e.object3d.position.clone();
    e.object3d.updateMatrixWorld(true);
  }
  function zarovnejZnovu() {
    const e = state.entry, z = state.zarovnani;
    if (!e || !z || !placed.includes(e)) { setStatus("Žádný Vandr model ve scéně.", true); return; }
    e.object3d.position.set(z.poz[0], z.poz[1], z.poz[2]);
    e.object3d.quaternion.set(0, 1, 0, 0);
    e.object3d.userData.basePos = e.object3d.position.clone();
    e.object3d.updateMatrixWorld(true);
    setStatus("Vandr model je zpět ve výchozím zarovnání.", false);
  }

  // ---------------------------------------------------------------------------------------------------------------------------------
  // panel
  // ---------------------------------------------------------------------------------------------------------------------------------
  function mk(tag, attrs, text) {
    const el = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(k => { if (k === "style") el.style.cssText = attrs[k]; else el.setAttribute(k, attrs[k]); });
    if (text != null) el.textContent = text;
    return el;
  }

  async function idZKarty(txt) {
    const t = String(txt || "").trim();
    if (/^\d{1,9}$/.test(t)) return parseInt(t, 10);
    if (!/^VD-[0-9a-f-]{36}$/i.test(t)) throw new Error("Zadej číslo karty (např. 4967) nebo SKU VD-…");
    if (!state.prehled) {
      const r = await fetch("/api/admin/vandr-vyroba/prehled", { credentials: "same-origin" });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error((d && d.error) || ("přehled karet: HTTP " + r.status));
      state.prehled = d.kartas || [];
    }
    const k = state.prehled.find(x => String(x.sku).toLowerCase() === t.toLowerCase());
    if (!k) throw new Error("Karta " + t + " nenalezena.");
    return k.shop_product_id;
  }

  function naplnSelect() {
    const sel = $("vandrRefKaroserie");
    if (!sel) return;
    const f = (($("vandrRefFiltr") || {}).value || "").trim().toLowerCase();
    const cur = sel.value;
    sel.textContent = "";
    tvaryKaroserii().filter(s => !f || (s.name || "").toLowerCase().includes(f)).slice(0, 300).forEach(s => {
      const k = kodKaroserie(s);
      if (!k) return;
      const o = mk("option", { value: k }, (s.name || "").replace(/\s*-\s*karoserie \(L\+R_D\+B\)\s*$/, ""));
      sel.appendChild(o);
    });
    if (cur && Array.from(sel.options).some(o => o.value === cur)) sel.value = cur;
  }

  function build(section) {
    section.textContent = "";
    section.appendChild(mk("div", { class: "hint", style: "display:flex;align-items:center;gap:6px;" })).appendChild(mk("strong", null, "Vandr model v karoserii (referenční)"));
    section.appendChild(mk("div", { style: "font-size:11px;color:var(--text-muted);margin:4px 0;" },
      "Vloží celý Vandr regál (karta VD-…) beze změny do karoserie z knihovny. Je to pomůcka: není v kusovníku, ceně ani v uložení."));
    const r1 = mk("div", { style: "display:flex;gap:6px;margin-top:6px;" });
    r1.appendChild(mk("input", { type: "text", id: "vandrRefKarta", placeholder: "karta: číslo (4967) nebo SKU VD-…", style: "flex:1;font-size:12px;" }));
    section.appendChild(r1);
    const r2 = mk("div", { style: "display:flex;gap:6px;margin-top:6px;" });
    r2.appendChild(mk("input", { type: "text", id: "vandrRefFiltr", placeholder: "hledat karoserii (např. MAN L3H3)", style: "flex:1;font-size:12px;" }));
    section.appendChild(r2);
    section.appendChild(mk("select", { id: "vandrRefKaroserie", style: "width:100%;margin-top:6px;font-size:12px;" }));
    const btns = mk("div", { style: "display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;" });
    const bVloz = mk("button", { type: "button", id: "vandrRefVloz", style: "font-size:12px;" }, "Vložit do scény a karoserie");
    const bZpet = mk("button", { type: "button", id: "vandrRefZpet", style: "font-size:12px;" }, "Výchozí zarovnání");
    const bOdeber = mk("button", { type: "button", id: "vandrRefOdeber", style: "font-size:12px;" }, "Odebrat model");
    btns.appendChild(bVloz); btns.appendChild(bZpet); btns.appendChild(bOdeber);
    section.appendChild(btns);
    // posun / otoceni
    const nudge = mk("div", { style: "margin-top:8px;font-size:11px;color:var(--text-muted);" }, "Posun (mm) a otočení modelu:");
    section.appendChild(nudge);
    const mkRada = (popis, osa) => {
      const row = mk("div", { style: "display:flex;gap:3px;align-items:center;margin-top:3px;" });
      row.appendChild(mk("span", { style: "width:78px;font-size:11px;" }, popis));
      [-50, -10, -1, 1, 10, 50].forEach(v => {
        const b = mk("button", { type: "button", class: "vandr-ref-nudge", "data-osa": osa, "data-v": String(v), style: "font-size:11px;padding:2px 5px;" }, (v > 0 ? "+" : "") + v);
        b.addEventListener("click", () => posun(osa === "x" ? v : 0, osa === "y" ? v : 0, osa === "z" ? v : 0));
        row.appendChild(b);
      });
      section.appendChild(row);
    };
    mkRada("X (bok)", "x"); mkRada("Y (výška)", "y"); mkRada("Z (délka)", "z");
    const rot = mk("div", { style: "display:flex;gap:3px;align-items:center;margin-top:3px;" });
    rot.appendChild(mk("span", { style: "width:78px;font-size:11px;" }, "Otočit"));
    [-90, 90, 180].forEach(v => { const b = mk("button", { type: "button", class: "vandr-ref-rot", "data-v": String(v), style: "font-size:11px;padding:2px 5px;" }, (v > 0 ? "+" : "") + v + "°"); b.addEventListener("click", () => otoc(v)); rot.appendChild(b); });
    section.appendChild(rot);
    section.appendChild(mk("div", { id: "vandrRefStatus", style: "font-size:11px;margin-top:6px;color:var(--text-muted);" }));
    $("vandrRefFiltr").addEventListener("input", naplnSelect);
    bVloz.addEventListener("click", async () => {
      try {
        const id = await idZKarty($("vandrRefKarta").value);
        const kod = ($("vandrRefKaroserie") || {}).value || null;
        await vloz(id, kod);
      } catch (e) { setStatus(e.message, true); }
    });
    bZpet.addEventListener("click", zarovnejZnovu);
    bOdeber.addEventListener("click", () => { odeberReferenci(); setStatus("Vandr model odebrán ze scény.", false); });
    state.ui = section;
  }

  function banner() {
    if ($("vandrRefBanner")) return;
    const b = mk("div", { id: "vandrRefBanner", style: "position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:100000;max-width:min(92vw,720px);padding:10px 16px;border-radius:10px;" +
      "background:#16324f;color:#fff;font:13px/1.4 system-ui,sans-serif;box-shadow:0 6px 24px rgba(0,0,0,.35);text-align:center;" });
    b.hidden = true;
    (document.body || document.documentElement).appendChild(b);
  }

  function fromUrl() {
    const id = qs.get("vandr");
    if (!/^\d{1,9}$/.test(id || "")) return;
    const kod = (qs.get("karoserie") || "").trim() || null;
    state.zUrl = true;
    banner();
    setStatus("Čekám na načtení katalogu a karoserií…", false);
    const t0 = Date.now();
    const wait = () => {
      const ready = typeof CATALOG !== "undefined" && CATALOG.length && typeof CUSTOM_SHAPES !== "undefined" && CUSTOM_SHAPES.length;
      if (ready) { naplnSelect(); if ($("vandrRefKarta")) $("vandrRefKarta").value = id; if (kod && $("vandrRefKaroserie") && Array.from($("vandrRefKaroserie").options).some(o => o.value === kod)) $("vandrRefKaroserie").value = kod; vloz(parseInt(id, 10), kod).then(() => { state.zUrl = false; }); }
      else if (Date.now() - t0 > KATALOG_MAX_CEKANI_MS) setStatus("Katalog nebo knihovna karoserií se nenačetly - zkus znovu načíst stránku.", true);
      else setTimeout(wait, 150);
    };
    wait();
  }

  function init() {
    const section = $("vandrRefSection");
    if (!section) return;
    build(section);
    if (typeof initFloatingShapesWindow === "function") {
      state.fw = initFloatingShapesWindow({
        sectionId: "vandrRefSection", title: "Vandr model v karoserii", winId: "fwVandrRefWindow",
        tabId: "fwVandrRefTab", tabLabel: "▸ Vandr model", storageKey: "sceneVandrRefFloatingWindow",
        tabDefaultTop: 480, startClosedByDefault: true,
      });
    }
    // seznam karoserii se plni, az jsou nactene vlastni tvary
    const t0 = Date.now();
    const poll = () => { if (typeof CUSTOM_SHAPES !== "undefined" && CUSTOM_SHAPES.length) naplnSelect(); else if (Date.now() - t0 < KATALOG_MAX_CEKANI_MS) setTimeout(poll, 300); };
    poll();
    fromUrl();
  }

  window.VandrRef = { vloz, posun, otoc, zarovnejZnovu, odeberReferenci, state, najdiTvar, zmerKaroserii, zmerVandr, tvaryKaroserii };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
