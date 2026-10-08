/*
 * stul-host.js - STRANKA STOLU PRO ZAMESTNANCE nad SPOLECNYM modulem voleb (webapp/js/product-configurator.js, bot16) - bot8, 2026-10-04.
 *
 * Robert 2026-10-03: ovladani stolu se NEDUPLIKUJE (bylo 3x zvlast: stranka stolu, Panel stolu ve Scene, Volba komponent v mini-shopu) - "jeden modul pro vse".
 * Tahle stranka UZ NEMA vlastni jezdce, meze, zablokovane volby ani texty: vse dela modul podle schematu ze serveru (verejne trasy /api/shop/*, produkt 4934).
 * ROZLOZENI je STEJNE jako stranka produktu mini-shopu (baliace-stoly): mrizka oken (js/pdc-layout.js + miniweb/miniweb.css) - 3D vlevo, vpravo cena a vyroba, pod tim okna
 * Rozmery / Konstrukce / Prislusenstvi (skupiny voleb z modulu pres groupHost), Kusovnik, Vyrezy a loziska, Shrnuti.
 * Tady zustava jen to, co je specificke pro ZAMESTNANCE: okna cena/vyroba/kusovnik, hash v URL (odkaz na konfiguraci), kusovnik s cenami + technicke problemy + odkazy na vyrobni list
 * (z resp.staff, server ho da jen prihlasenemu zamestnanci na `staff: true`).
 *
 * Hash: verejne nazvy slotu (#w=1840&braces=1&bracelen=300); starsi odkazy s nazvy generatoru (#sirka=1840&vzpery=1) se prevedou (STARE_NA_SLOT).
 *
 * PET GENERATORU (Robert 2026-10-04 az 2026-10-07, bot10 + bot8): stejna stranka slouzi generatoru stolu 01 (system 30, profil 30x30, /stul-konfigurator.html), 02 (system 40, profil 40x40,
 * /stul-konfigurator-40.html), 03 (system 35, profil 35x35, /stul-konfigurator-35.html), 04 (system 41 = ergonomicky stul SSE, podelniky 40x40 + nohy SSE, /stul-konfigurator-41.html) i 05 (system 45 =
 * hluboky stul az 2500 mm, profil 40x40 jako system 40, od 1500 mm hloubky stredni rada noh, /stul-konfigurator-45.html);
 * system urcuje atribut data-system na <html>. Kazdy system ma vlastni produktovou kartu
 * (app_settings.configurator_products); karty se najdou ve schema.systems (api/stul_shop.py), takze stranka nema pevne ID karty 35 ani 40. Odkazy "Prepnout na system ..." v zahlavi
 * (po jednom pro kazdy dalsi system s kartou) nesou TENTYZ hash = tatáž konfigurace (vcetne sikmych vzper: ve 40 je nese spojka 3220, v 30 a 35 spojka 3254).
 */
(function () {
  "use strict";
  var GEN = { 30: { no: "01", page: "/stul-konfigurator.html" }, 35: { no: "03", page: "/stul-konfigurator-35.html" }, 40: { no: "02", page: "/stul-konfigurator-40.html" },
    41: { no: "04", page: "/stul-konfigurator-41.html" },                     // 41 = ergonomicky stul SSE (bot8, 2026-10-05)
    45: { no: "05", page: "/stul-konfigurator-45.html" } };                   // 45 = hluboky stul az 2500 mm, profil 40x40 jako system 40 (bot10, 2026-10-07)
  var SYSTEM = (function () { var n = parseInt(document.documentElement.getAttribute("data-system"), 10); return GEN[n] ? n : 30; })();      // system profilu stranky = sirka profilu v mm: 30 (generator 01) | 35 (03) | 40 (02); 41 = stul SSE (04, profil 40)
  function sysNazev(n) { return Number(n) === 41 ? "SSE" : "systém " + n; }          // SSE se viditelne nejmenuje „systém 41“ (Robert 2026-10-08); 41 je jen vnitrni klic (selection.system, hash, SKU)
  var PRODUCT_ID_30 = 4934;                                 // karta systemu 30 (app_settings.configurator_products); karty systemu 35 a 40 se najdou ve schema.systems
  var PRODUCT_ID = PRODUCT_ID_30;                           // produkt stranky; pro systemy 35 a 40 se po nacteni schema.systems nastavi S.productId
  var STARE_NA_SLOT = { sirka: "w", hloubka: "d", vyska: "h", presah: "ov", led_rameno: "arm", stojky: "posts", kolecka: "wheels", patky: "feet", panely: "panels", led: "led",
    suplik: "drawers", elektrozlab: "socket", drzak_pet: "pet", police: "shelf", suplik_posun: "boxpos", suplik_vlevo: "drawleft", pet_noha: "petleg", pet_strana: "petface", led_svetlo: "ledlight", pet_posun: "petpos", police_h1: "sh1", police_h2: "sh2", police_h3: "sh3", police_h4: "sh4", police_h5: "sh5", police_h6: "sh6", police_h7: "sh7", police_h8: "sh8", police_h9: "sh9", police_h10: "sh10", loz: "bearings", loz_rozteca: "bearpitch", loz_okraj: "bearedge",
    vzpery: "braces", vzpera_delka: "bracelen", navlek: "sleeve", navlek_delka: "sleevelen" };
  for (var n = 1; n <= 3; n++) {
    STARE_NA_SLOT["vyrez" + n] = "cut" + n; STARE_NA_SLOT["vyrez" + n + "_police"] = "cut" + n + "shelf";
    ["w", "d", "x", "z"].forEach(function (s) { STARE_NA_SLOT["vyrez" + n + "_" + s] = "cut" + n + s; });
  }
  var LABELS = {
    title: "Vaše konfigurace", reset: "Výchozí hodnoty", price: "Cena", noVat: "bez DPH", withVat: "s DPH", pending: "Počítám…", code: "Kód konfigurace", summary: "Souhrn",
    unavailable: "Tohle teď nejde zapnout.", errLoad: "Konfigurátor se nepodařilo načíst. Zkus to prosím znovu.", errNet: "Spojení selhalo. Zkus to prosím znovu.", retry: "Zkusit znovu",
    rateLimit: "Moc změn najednou, chvilku počkej…", rulesChanged: "Pravidla se změnila, načítám nové volby.", modelPrep: "Připravuji model…", modelErr: "Model se nepodařilo načíst, cena platí.",
    noWebgl: "Tenhle prohlížeč nepodporuje 3D náhled, volby a cena fungují.", viewerErr: "3D náhled se nepodařilo načíst, volby a cena fungují.", invalid: "Vyber platnou konfiguraci.",
    yes: "ano", no: "ne", auto: "automaticky", lock: "Klepnutím ovládáš 3D pohled", allowed: "Povoleno od {min} do {max} {unit}", handleTitle: "Tahem do strany posuneš střední nohu", handleCap: "{mm} mm od levé nohy", handleAria: "Poloha střední nohy"
  };
  var TILE_JS = "/js/pripni-cokoli-tile.js?v=6ed7fc6c7c", V3D_CSS = "/css/v3d.css?v=c76cbe7292";          // ukazka Pripni cokoli (PdcLayout.attachWindow); ?v= verzuje scripts/stul_verze.py
  var DOPLNKY = { profile: "Hlavní profil", attach: "Připni cokoli", profileText: "Profil {mm}×{mm} mm, drážka {g} mm." };          // stejne texty jako miniweb/i18n/cs.json (win.profile, win.attach, win.profile_text)
  var S = { ctl: null, staff: null, bomRows: [], bomOpen: {}, sel: null, L: null, admin: false, envPanel: false, productId: PRODUCT_ID, systems: [] };
  if (/[?&]debug=1/.test(location.search)) window.__pdcDebug = true;               // testy: modul vystavi window.__pdcState (S.ov, S.viewer...)

  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (text != null) e.textContent = text;
    return e;
  }
  function money(v) { return Number(v).toLocaleString("cs-CZ", { maximumFractionDigits: 0 }) + " Kč"; }
  function qtyText(x) { return x == null ? "" : String(Math.round(x * 100) / 100).replace(".", ","); }

  // ---------------------------------------------------------------- hash <-> vyber
  function parseHash(h) {
    var out = {}, raw = String(h || "").replace(/^#/, "");
    if (!raw) return out;
    raw.split("&").forEach(function (kv) {
      var i = kv.indexOf("="); if (i < 1) return;
      var k = decodeURIComponent(kv.slice(0, i)), v = decodeURIComponent(kv.slice(i + 1));
      var slot = Object.prototype.hasOwnProperty.call(STARE_NA_SLOT, k) ? STARE_NA_SLOT[k] : k;
      var val = v === "true" ? true : v === "false" ? false : v;
      if (k === "stredni_noha") { out.__mid_mm = Number(v); return; }
      if (typeof val === "string" && val !== "" && isFinite(Number(val))) val = Number(val);
      out[slot] = val;
    });
    if (out.__mid_mm != null) {                                      // stary odkaz: stredni noha v mm od leve nohy -> verejny slot `mid` v % mezi nohami
      var span = (Number(out.w) || 1200) - (SYSTEM === 41 ? 390 : SYSTEM === 45 ? 40 : SYSTEM);   // sirka profilu = cislo systemu (30 | 35 | 40; system 45 ma profil 40); stul SSE: osy krajnich noh jsou 195 mm od konce desky
      if (isFinite(out.__mid_mm) && span > 0) out.mid = Math.round(out.__mid_mm / span * 100);
      delete out.__mid_mm;
    }
    return out;
  }
  var HASH_SSE = { w: 1, d: 1, h: 1, mid: 1, shelf: 1, drawers: 1, drawercount: 1, boxpos: 1, drawleft: 1 };      // stul SSE (system 41) nema ostatni volby: odkaz nese jen jeho sloty (rozmery se prenesou i do jinych systemu)
  function zapisHash(sel) {
    var q = [];
    Object.keys(sel || {}).sort().forEach(function (k) {
      var v = sel[k]; if (v == null || typeof v === "object") return;
      if (SYSTEM === 41 && !HASH_SSE[k]) return;
      q.push(encodeURIComponent(k) + "=" + encodeURIComponent(typeof v === "boolean" ? (v ? 1 : 0) : v));
    });
    try { history.replaceState(null, "", "#" + q.join("&")); } catch (e) { /* ignoruj */ }
    updateSwitch();
  }

  // ---------------------------------------------------------------- tri generatory (system 30 / 35 / 40): karty ze schema.systems a prepinace s prenosem konfigurace
  function dalsiSystemy() { return [30, 35, 40, 41, 45].filter(function (s) { return s !== SYSTEM; }); }
  function produktSystemu(systems, sys) {
    for (var i = 0; i < systems.length; i++) if (systems[i].system === sys) return systems[i].card_id;
    return sys === 30 ? PRODUCT_ID_30 : null;
  }
  function nactiSystemy() {                                  // schema karty systemu 30 nese `systems` (starsi server bez pole = jen system 30)
    return fetch("/api/shop/products/" + PRODUCT_ID_30 + "/configurator?lang=cs", { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; })
      .then(function (sc) { return Array.isArray(sc && sc.systems) ? sc.systems : []; });
  }
  function updateSwitch() {                                  // odkazy nesou aktualni hash = tatez konfigurace v druhem systemu
    var box = $("sysSwitch");
    if (!box || box.hidden) return;
    Array.prototype.forEach.call(box.querySelectorAll("a[data-system]"), function (a) { a.setAttribute("href", GEN[a.getAttribute("data-system")].page + (location.hash || "")); });
  }
  function zobrazPrepinac() {                                // jeden odkaz pro kazdy dalsi system, ktery ma kartu (schema.systems)
    var box = $("sysSwitch");
    if (!box) return;
    box.textContent = "";
    dalsiSystemy().forEach(function (s) {
      if (!produktSystemu(S.systems, s)) return;
      box.appendChild(el("a", { "data-system": String(s), href: GEN[s].page }, s === 41 ? "Přepnout na ergonomický stůl SSE (nohy SSE; přenesou se rozměry)" : s === 45 ? "Přepnout na Robustní systém 45 (hluboký stůl, hloubka až 2500 mm; stejná konfigurace)" : "Přepnout na systém " + s + " (stejná konfigurace)"));
    });
    box.hidden = !box.firstChild;
    updateSwitch();
  }

  // ---------------------------------------------------------------- zamestnanecky blok (z resp.staff)
  function renderBom(k) {
    var body = $("bomBody");
    S.bomRows = [];
    body.textContent = "";
    if (!k) { body.appendChild(el("div", { "class": "note" }, "Kusovník se nepodařilo spočítat.")); return; }
    var tbl = el("table"), head = el("tr");
    ["Položka", "Rozměr", "Ks", "Cena/ks", "Celkem"].forEach(function (h) { head.appendChild(el("th", null, h)); });
    tbl.appendChild(el("thead")).appendChild(head);
    var tb = el("tbody");
    function sec(text) { var tr = el("tr", { "class": "sec" }); var td = el("td", null, text); td.colSpan = 5; tr.appendChild(td); tb.appendChild(tr); S.bomRows.push([text]); }
    function row(cells, cls) {
      var tr = el("tr", cls ? { "class": cls } : null);
      cells.forEach(function (c, i) { var td = el("td", null, c); if (i === 0 && cells.length < 5) td.colSpan = 4; tr.appendChild(td); });
      tb.appendChild(tr);
    }
    function line(x, cls, hid) {
      var cells = [x.nazev, x.rozmer || "", qtyText(x.mnozstvi), x.cena_ks == null ? "" : money(x.cena_ks), money(x.celkem)];
      row(cells, cls); S.bomRows.push(cells);
      if (hid) tb.lastChild.hidden = true;
    }
    // hlinikove profily (Robert 2026-10-04: "alu profily je dobre rozbalovat, aby zabrali 1 radek, kdyz jsou zabalene"): kazdy druh profilu je JEDEN radek (soucet kusu a ceny),
    // rozbalenim se ukazou delky; radky jednotlivych delek zustavaji v tabulce (kopirovani do tabulky je bere vsechny, soucet radku == celkem se nemeni)
    function jeProfil(x) { return /^Profil /.test(x.nazev || "") && /\bmm$/.test(x.rozmer || ""); }
    function skupinaProfilu(nazev, dily) {
      var ks = 0, celkem = 0;
      dily.forEach(function (d) { ks += d.mnozstvi || 0; celkem += d.celkem || 0; });
      var open = !!S.bomOpen[nazev], tr = el("tr", { "class": "grp" });
      var btn = el("button", { type: "button", "class": "bom-tog", "aria-expanded": open ? "true" : "false", title: "Rozbalit / sbalit délky" });
      btn.appendChild(el("span", { "class": "bom-chev", "aria-hidden": "true" }, open ? "▾" : "▸")); btn.appendChild(document.createTextNode(nazev));
      var td0 = el("td"); td0.appendChild(btn); tr.appendChild(td0);
      [dily.length + (dily.length === 1 ? " délka" : dily.length < 5 ? " délky" : " délek"), qtyText(ks), "", money(celkem)].forEach(function (c) { tr.appendChild(el("td", null, c)); });
      tb.appendChild(tr);
      var det = dily.slice().sort(function (a, b) { return (parseFloat(String(b.rozmer).replace(",", ".")) || 0) - (parseFloat(String(a.rozmer).replace(",", ".")) || 0); });
      var radky = det.map(function (d) { line(d, "det", !open); return tb.lastChild; });
      btn.addEventListener("click", function () {
        open = !open; S.bomOpen[nazev] = open; btn.setAttribute("aria-expanded", open ? "true" : "false"); btn.firstChild.textContent = open ? "▾" : "▸";
        radky.forEach(function (r) { r.hidden = !open; });
      });
    }
    sec("Materiál a díly");
    var skupiny = {}, poradi = [];
    (k.radky || []).forEach(function (x) {
      if (!jeProfil(x)) { poradi.push({ x: x }); return; }
      if (!skupiny[x.nazev]) { skupiny[x.nazev] = []; poradi.push({ grp: x.nazev }); }
      skupiny[x.nazev].push(x);
    });
    poradi.forEach(function (p) { if (p.grp) skupinaProfilu(p.grp, skupiny[p.grp]); else line(p.x); });
    sec("Práce, spoje a balné"); (k.prace || []).forEach(function (x) { line(x); });                   // POZOR: ne forEach(line) - forEach by predal index a pole jako `cls`/`hid` a radky by se skryly
    var c = k.celkem || {};
    [["Celkem bez DPH", c.bez_dph, "sum"], ["DPH " + c.sazba_dph + " %", c.dph, ""], ["Celkem s DPH", c.s_dph, "sum"]].forEach(function (x) {
      row([x[0], money(x[1])], x[2]); S.bomRows.push([x[0], "", "", "", money(x[1])]);
    });
    tbl.appendChild(tb); body.appendChild(tbl);
    var m = k.montaz || {};
    body.appendChild(el("div", { "class": "note" }, "Hmotnost " + String(k.hmotnost_kg).replace(".", ",") + " kg · Montáž (" + m.poznamka + "): " + money(m.czk) + " (" + m.pct + " %) · ceny bez DPH v Kč"));
    (k.varovani || []).forEach(function (w) { body.appendChild(el("div", { "class": "note" }, "⚠ " + w)); });
  }

  function renderStaff(r) {
    var st = r && r.staff;
    S.staff = st || null;
    var W = S.L.wins;
    ["price", "info", "bom"].forEach(function (k) { W[k].box.hidden = !st; });
    if (!st) return;
    if (st.cena) { $("priceNet").textContent = money(st.cena.bez_dph); $("priceGross").textContent = money(st.cena.s_dph) + " s DPH (" + st.cena.sazba_dph + " %)"; }
    $("titleCode").textContent = st.kod || "";
    renderBom(st.kusovnik);
    var pr = $("staffProblems");
    pr.textContent = "";
    (st.problemy || []).slice(0, 8).forEach(function (x) { pr.appendChild(el("div", null, "• " + (x.text || x.kod))); });
    var lk = $("staffLinks");
    lk.textContent = "";
    [["Výrobní list", st.vyrobni_list_url], ["Výrobní sestava (JSON)", st.vyrobni_sestava_url]].forEach(function (x) {
      if (!x[1]) return;
      var a = el("a", { href: x[1], target: "_blank", rel: "noopener" }, x[0]); lk.appendChild(a);
    });
    $("staffCode").textContent = "Kód konfigurace: " + (st.kod || "") + " · " + (st.pocet_spoju != null ? st.pocet_spoju + " spojů profilů" : "");
  }

  // ---------------------------------------------------------------- rozlozeni: mrizka oken jako stranka produktu mini-shopu
  function div(cls, id) { var d = el("div", cls ? { "class": cls } : null); if (id) d.id = id; return d; }
  function buildLayout() {
    var narrow = !!(window.matchMedia && window.matchMedia("(max-width: 899px)").matches);
    var L = window.PdcLayout.create({ narrow: narrow }), W = L.wins;
    S.L = L;
    var media = div("mw-pd-media", "stage"), panel = div(null, "host");
    var wStage = L.win("stage", "3D náhled"), wPrice = L.win("price", "Cena a scéna", { hidden: true }), wInfo = L.win("info", "Výroba a odkazy", { hidden: true });
    var wDim = L.win("dim", "", { fold: true, mobileOpen: true, hidden: true }), wFrame = L.win("frame", "", { fold: true, hidden: true }), wExtras = L.win("extras", "", { fold: true, hidden: true });
    var wBom = L.win("bom", "Kusovník s cenami (interní)", { fold: true, mobileOpen: true, hidden: true }), wAdv = L.win("adv", "Výřezy a ložiska", { fold: true, closed: true, hidden: true });
    var wSum = L.win("sum", "Shrnutí", { fold: true, hidden: true });
    var wRules = L.win("rules", "Pravidla stolu", { fold: true, closed: true, hidden: true });            // jen pro uzivatele s pravem (nastaveni) - viz start()
    var wDef = L.win("defcfg", "Výchozí konfigurace", { fold: true, mobileOpen: true, hidden: true });          // jen pro admina: "Uložit jako výchozí" (Robert 2026-10-05); ve 3. sloupci, ne vedle 3D (v pravém sloupci 1. řádku by prodloužilo 3D okno)
    // Hlavni profil a Pripni cokoli: STEJNE prvky jako v mini-shopu a ve vlozenem generatoru (Robert 2026-10-05, "prvky napric generatory na vsech mistech"); sdileny kod js/pdc-layout.js, plni se po nacteni modulu
    var wProfile = L.win("profile", DOPLNKY.profile, { hidden: true }), wAttach = L.win("attach", DOPLNKY.attach, { fold: true, hidden: true }), gate = window.PdcLayout.modelGate();
    var wVzhled = L.win("vzhled", "Vzhled online nabídek (barvy, lesk, AO, HDRI – pro všechny nabídky)", { fold: true, closed: true, hidden: true });          // jen pro admina: okno s kontrolní scénou nad modelem generátoru (bot10, 2026-10-07)
    var wEnv = L.win("env", "Prostředí (HDRI)", { fold: true, closed: true, hidden: true });          // jen pro admina: výběr HDRI ve 3D náhledu, "uložit pro všechny" (bot10 + bot8, 2026-10-04)

    var msg = div(null, "stageMsg"); msg.textContent = "Načítám 3D model…";
    wStage.body.appendChild(media); wStage.body.appendChild(msg);

    var priceBox = div("sh-price", "staffPrice");
    priceBox.appendChild(div("small")).textContent = "Cena bez DPH";
    var big = div("big", "priceNet"); big.textContent = "–"; priceBox.appendChild(big);
    var gross = div("small", "priceGross"); priceBox.appendChild(gross);
    wPrice.body.appendChild(priceBox);
    var b1 = el("button", { type: "button", id: "sceneBtn" }, "Vložit do Scény");
    var sc = div(null, "sceneStatus");
    if (SYSTEM === 41) { b1.disabled = true; b1.setAttribute("title", "Stůl SSE se do Scény zatím nevkládá"); sc.textContent = "Stůl SSE se do Scény zatím nevkládá (nohy SSE ve Scéně nejsou)."; }
    wPrice.body.appendChild(b1); wPrice.body.appendChild(sc);
    // "Do online nabidky" (Robert 2026-10-06, kontrakt bot5 docs/KONTRAKT_NABIDKA_Z_KONFIGURACE.md): STEJNE tlacitko a dialog u KAZDEHO generatoru (system 30 / 35 / 40 / 41), jeden sdileny modul
    // (js/stul-nabidka.js); ukaze se az po uspesne sonde backendu (GET /api/admin/konfigurace/nabidka: 200 jen se pravem nabidky.vytvorit, 401/403/404 = bez tlacitka)
    if (window.StulNabidka) S.nabidka = window.StulNabidka.mount(wPrice.body, {
      getPayload: function () { var pl = S.ctl && S.ctl.cartPayload(); return pl ? { product_id: S.productId, selection: pl.configuration.selection, rules_version: pl.configuration.rules_version, hash: pl.configuration.hash, kod: pl.kod, system: SYSTEM, sceneQuery: (window.StulDoSceny && window.StulDoSceny.dotaz && window.StulDoSceny.dotaz()) || null } : null; },
      onRulesChanged: function () { if (S.ctl) S.ctl.refresh(); }
    });
    // "Vytvorit kartu" (Robert 2026-10-07: "pridat do generatoru: tlacitko ktere z aktualni sestavy vytvori aktivni kartu"): STEJNY modul u KAZDEHO generatoru (js/stul-karta.js); ukaze se az po sonde backendu
    // (GET /api/admin/konfigurace/karta: 200 jen s pravem sklad_karty/vytvorit, 401/403/404 = bez tlacitka); kontrakt docs/KONTRAKT_KARTA_Z_KONFIGURACE.md
    if (window.StulKarta) S.karta = window.StulKarta.mount(wPrice.body, {
      getPayload: function () { var pl = S.ctl && S.ctl.cartPayload(); return pl ? { product_id: S.productId, selection: pl.configuration.selection, rules_version: pl.configuration.rules_version, hash: pl.configuration.hash, kod: pl.kod, system: SYSTEM } : null; },
      onRulesChanged: function () { if (S.ctl) S.ctl.refresh(); }
    });
    if (window.StulMontazStaff) window.StulMontazStaff.mount(wPrice.body);                            // % montaze primo v generatoru (modul bot16, pole se ukaze jen kdyz server odpovi; GET/PUT /api/stul/montaz, bot5)

    wInfo.body.appendChild(div(null, "staffProblems"));
    wInfo.body.appendChild(div(null, "staffLinks"));
    var b2 = el("button", { type: "button", id: "copyBtn", "class": "sh-ghost" }, "Zkopírovat odkaz na tuto konfiguraci");
    var row = div("sh-btns"); row.appendChild(b2); wInfo.body.appendChild(row);
    wInfo.body.appendChild(div(null, "staffCode"));

    wBom.body.appendChild(div(null, "bomBody"));
    var b3 = el("button", { type: "button", id: "bomCopy", "class": "sh-ghost" }, "Zkopírovat tabulku");
    var row3 = div("sh-btns"); row3.appendChild(b3); wBom.body.appendChild(row3);

    var side = div("mw-col mw-col-side"), col3 = div("mw-col mw-col-3");
    side.appendChild(wPrice.box); side.appendChild(wEnv.box); side.appendChild(wInfo.box);        // okno Prostředí (HDRI) hned pod oknem s cenou (Robert 2026-10-04)
    col3.appendChild(wAdv.box); col3.appendChild(wSum.box); col3.appendChild(wProfile.box); col3.appendChild(wAttach.box); col3.appendChild(wDef.box); col3.appendChild(wRules.box);          // Hlavni profil a Pripni cokoli ve 3. sloupci: v pravem sloupci 1. radku by prodlouzily 3D okno
    // pravidla stolu (Robert 2026-10-04): hloubka, od které přibývají svislé profily bočnic, kratší deska police a podpěry pod policí i pod deskou - nastavitelná, platí pro celý web
    var lab = el("label", { "for": "pravHloubka" }, "Hloubka stolu (mm), nad kterou přibývají podpěry a svislé profily bočnic");
    var inp = el("input", { type: "text", inputmode: "numeric", id: "pravHloubka", autocomplete: "off", "aria-describedby": "pravStav" });
    var lab2 = el("label", { "for": "pravVzpery" }, "Délka ramene LED od stojek (mm), od které se samy přidají šikmé vzpěry");
    var inp2 = el("input", { type: "text", inputmode: "numeric", id: "pravVzpery", autocomplete: "off", "aria-describedby": "pravStav" });
    var lab4 = el("label", { "for": "pravStredni" }, "Šířka stolu (mm), nad kterou vznikne střední noha");
    var inp4 = el("input", { type: "text", inputmode: "numeric", id: "pravStredni", autocomplete: "off", "aria-describedby": "pravStav" });
    var lab9 = el("label", { "for": "pravOdstupSt" }, "Nejmenší vzdálenost osy střední nohy od osy krajní nohy (mm; limit polohy střední nohy)");
    var inp9 = el("input", { type: "text", inputmode: "numeric", id: "pravOdstupSt", autocomplete: "off", "aria-describedby": "pravStav" });
    var lab10 = el("label", { "for": "pravStredniRada" }, "Hloubka stolu (mm), nad kterou přibude střední řada noh (jen systém 45; platí nejvýš od hloubky, nad kterou přibývají svislé profily bočnic)");
    var inp10 = el("input", { type: "text", inputmode: "numeric", id: "pravStredniRada", autocomplete: "off", "aria-describedby": "pravStav" });
    var lab11 = el("label", { "for": "pravRozpon" }, "Největší nepodepřený úsek desky (mm; podle něj se počítá počet podpěr pod deskou a policemi)");
    var inp11 = el("input", { type: "text", inputmode: "numeric", id: "pravRozpon", autocomplete: "off", "aria-describedby": "pravStav" });
    var lab3 = el("label", { "for": "pravVyrez" }, "Cena za jeden výřez v pracovní desce (Kč bez DPH, 0 = výřez cenu nemění)");
    var inp3 = el("input", { type: "text", inputmode: "numeric", id: "pravVyrez", autocomplete: "off", "aria-describedby": "pravStav" });
    var lab5 = el("label", { "for": "pravNavlek200" }, "Cena návleku nohy (jekl 40×40×2 se záslepkou) o délce 200 mm (Kč bez DPH za 1 ks, systém 35)");
    var inp5 = el("input", { type: "text", inputmode: "numeric", id: "pravNavlek200", autocomplete: "off", "aria-describedby": "pravStav" });
    var lab6 = el("label", { "for": "pravNavlek400" }, "Cena návleku nohy o délce 400 mm (mezi 200 a 400 mm se cena počítá lineárně)");
    var inp6 = el("input", { type: "text", inputmode: "numeric", id: "pravNavlek400", autocomplete: "off", "aria-describedby": "pravStav" });
    var lab7 = el("label", { "for": "pravNoha400" }, "Cena nohy SSE (2 jekly 40×40, spojnice, plechy, vnitřní profily, záslepky) při délce spojnice 400 mm (Kč bez DPH za 1 nohu, systém SSE; 0 = nezadáno)");
    var inp7 = el("input", { type: "text", inputmode: "numeric", id: "pravNoha400", autocomplete: "off", "aria-describedby": "pravStav" });
    var lab8 = el("label", { "for": "pravNoha1100" }, "Cena nohy SSE při délce spojnice 1100 mm (mezi 400 a 1100 mm se cena počítá lineárně)");
    var inp8 = el("input", { type: "text", inputmode: "numeric", id: "pravNoha1100", autocomplete: "off", "aria-describedby": "pravStav" });
    // pravidla se zadavaji PO SYSTEMECH (Robert 2026-10-05: "konkretni hodnoty chci mit nastavitelne pro jednotlive systemy zvlast, 30/35/40, kazdemu zadam individualne"): prepinac systemu nad poli
    var sysRow = div("sh-btns"); sysRow.setAttribute("role", "group"); sysRow.setAttribute("aria-label", "Systém profilu, jehož pravidla se upravují");
    sysRow.appendChild(el("span", { "class": "small", id: "pravSysCap" }, "Systém profilu:"));
    [30, 35, 40, 41, 45].forEach(function (n) { sysRow.appendChild(el("button", { type: "button", "class": "sh-ghost", id: "pravSys" + n, "data-sys": String(n), "aria-pressed": "false", title: n === 41 ? "Ergonomický stůl SSE (nohy SSE, podélníky 40×40)" : n === 45 ? "Systém 45 – hluboký stůl (profil 40×40, hloubka až 2500 mm)" : "Systém profilu " + n }, n === 41 ? "SSE" : String(n))); });
    var rb = div("sh-btns"); rb.appendChild(el("button", { type: "button", id: "pravUloz" }, "Uložit")); rb.appendChild(el("button", { type: "button", id: "pravVychozi", "class": "sh-ghost" }, "Výchozí"));
    var rs = div(null, "pravStav"); rs.setAttribute("role", "status");
    var rn = div("small"); rn.textContent = "Platí pro stoly zvoleného systému na celém webu (i mini-shop); každý systém (30 / 35 / 40 / 45 / SSE) má vlastní hodnoty, vidí je a mění jen admin. Hloubka 400–1600 mm (1500 a víc = podpěry se nikdy nepřidají; v systému 45, kde je stůl hluboký až 2500 mm, se podpěry přidají vždy nad zadanou hloubkou a nad hloubkou „střední řada noh“ (výchozí 1500 mm) přibude navíc střední řada noh); rameno LED 200–1500 mm (vzpěry se přidají jen když se vejdou, zákazník je může vypnout). Cena návleku nohy platí jen v systému 35, ceny nohy SSE jen v systému SSE (u SSE neplatí hloubka podpěr, vzpěry ani cena výřezu).";
    [sysRow, lab, inp, lab4, inp4, lab9, inp9, lab10, inp10, lab11, inp11, lab2, inp2, lab3, inp3, lab5, inp5, lab6, inp6, lab7, inp7, lab8, inp8, rb, rs, rn].forEach(function (n) { wRules.body.appendChild(n); });
    // vychozi konfigurace (Robert 2026-10-05: "postav mi admin tlacitko v generatoru, kterym ulozim konfiguraci jako vychozi"): jen admin, viz initVychozi()
    var dn = div("small"); dn.textContent = "Uloží aktuální konfiguraci jako výchozí stav tohoto generátoru pro všechny návštěvníky (stránka produktu, mini-shop, vložený generátor). Odkazy, které nesou jen odchylky od výchozí, se pak otevřou s novou výchozí.";
    var dbt = div("sh-btns"); dbt.appendChild(el("button", { type: "button", id: "defSave" }, "Uložit jako výchozí")); dbt.appendChild(el("button", { type: "button", id: "defReset", "class": "sh-ghost", hidden: "" }, "Vrátit původní výchozí"));
    var dst = div(null, "defStatus"); dst.setAttribute("role", "status");
    [dn, dbt, dst].forEach(function (n) { wDef.body.appendChild(n); });
    // vychozi UHEL POHLEDU 3D (Robert 2026-10-08: "chci nastavit vychozi uhel pohledu 3D v generatorech"): jen admin, platí pro VSECHNY generatory stolu (jedno nastaveni); viz initVychozi()
    var pbl = div(null, "pohledBlok"); pbl.hidden = true; pbl.style.marginTop = "14px";
    var pdn = div("small"); pdn.textContent = "Výchozí pohled 3D: otoč model tak, jak se má generátor otevírat, a ulož. Platí pro všechny generátory stolů (i stránka produktu, mini-shop, vložený generátor); tlačítko „3D“ ve 3D okně se pak vrací na tenhle pohled. Vzdálenost se dopočte sama, aby byl vidět celý stůl.";
    var pak = div("small"); pak.setAttribute("id", "pohledAktualni"); pak.setAttribute("aria-live", "off"); pak.style.cssText = "margin:8px 0;font-weight:600;min-height:1.2em";
    var pbt = div("sh-btns"); pbt.appendChild(el("button", { type: "button", id: "pohledSave" }, "Uložit aktuální pohled jako výchozí")); pbt.appendChild(el("button", { type: "button", id: "pohledReset", "class": "sh-ghost", hidden: "" }, "Vrátit původní pohled"));
    var pst = div(null, "pohledStatus"); pst.setAttribute("role", "status"); pst.style.marginTop = "8px";
    [pdn, pak, pbt, pst].forEach(function (n) { pbl.appendChild(n); });
    wDef.body.appendChild(pbl);
    var cfgBar = div("mw-cfgbar"); cfgBar.appendChild(panel);
    wVzhled.box.style.gridColumn = "1 / -1";          // okno Vzhled: dalsi (implicitni) radek mrizky pres celou sirku (iframe potrebuje misto); UVNITR mrizky, aby lista ceny na mobilu zustala dole (test C23); stranky generatoru maji vlastni grid-template-areas bez oblasti desc
    [wStage.box, side, cfgBar, wDim.box, wFrame.box, wExtras.box, wBom.box, col3, wVzhled.box].forEach(function (n) { L.grid.appendChild(n); });
    $("shGrid").appendChild(L.grid);

    var groupHost = L.groupHosts({ map: { g_size: wDim, g_frame: wFrame, g_extras: wExtras, g_cuts: wAdv, g_bearings: wAdv }, adv: wAdv, before: wBom.box });
    var sumHost = L.summaryHost(wSum, { all: function (n) { return "Celá konfigurace (" + n + ")"; }, less: "Méně" });
    return { media: media, panel: panel, groupHost: groupHost, sumHost: sumHost, reveal: L.reveal, profile: wProfile, attach: wAttach, gate: gate };
  }

  // ---------------------------------------------------------------- prostredi (HDRI) pro admina: nahled ve 3D + "ulozit pro vsechny" (PUT /api/shop/products/<id>/configurator/env)
  function envUrl() { return "/api/shop/products/" + S.productId + "/configurator"; }
  function loadScript(src) {
    return new Promise(function (ok, ko) { var s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = ko; document.head.appendChild(s); });
  }
  function initEnv(viewer) {
    if (S.envPanel || !viewer || !S.admin || !S.L) return;
    S.envPanel = true;
    var w = S.L.wins.env;
    (window.V3D && window.V3D.envPicker ? Promise.resolve() : loadScript("/js/v3d/env-picker.js?v=0f830cf1eb")).then(function () {
      return fetch(envUrl(), { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; });
    }).then(function (sc) {
      w.box.hidden = false;
      S.envPanel = window.V3D.envPicker(viewer, w.body, {
        saved: sc && sc.env ? sc.env : null,
        onSave: function (cfg) {                                       // cfg === null = vratit vychozi (smazat ulozene)
          return fetch(envUrl() + "/env", { method: "PUT", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cfg) })
            .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });
        }
      });
    }).catch(function () { S.envPanel = false; w.box.hidden = true; });
  }

  // ---------------------------------------------------------------- Vzhled online nabidek (jen admin; Robert 2026-10-07: "to nema byt jen v jedne karte, ale automaticky v kazde", "at se to negeneruje
  // porad dokola, muze to byt propojene do generatoru stolu a tam to muze sidlit"). Okno v generatoru = kontrolni scena (kontrola.html) v rezimu embed nad modelem TOHOTO generatoru (adresa GLB
  // z resolve, `mu:`; nic se nestavi na serveru): barvy materialu, lesk, AO, hlinik a HDRI platne pro VSECHNY online nabidky (ukladaji se samy, PUT /api/admin/v3d-vzhled). Iframe se nacte az pri
  // prvnim rozbaleni okna; odkaz ?vzhled=1 (z karty produktu) okno rozbali a ukaze. Model se pri zmene konfigurace nemeni sam (rozdelane upravy by se ztratily): tlacitko "Načíst aktuální model".
  function initVzhled() {
    var w = S.L && S.L.wins && S.L.wins.vzhled;
    if (!w || S.vzhledInit) return;
    S.vzhledInit = true;
    w.box.hidden = false;
    var head = w.box.querySelector(".mw-win-h");
    var info = div("small"); info.textContent = "Úpravy platí pro všechny online nabídky (stejné nastavení jako v kontrolní scéně): barvy materiálů, lesk, AO, hliník a HDRI; ukládají se samy. Okno ukazuje model právě otevřené konfigurace.";
    var bar = div("sh-btns"), holder = div(null, "vzhledHolder");
    var reload = el("button", { type: "button", id: "vzhledReload", "class": "sh-ghost" }, "Načíst aktuální model");
    var novy = el("a", { id: "vzhledNovy", href: "#", target: "_blank", rel: "noopener" }, "Otevřít ve zvláštním panelu");
    var frame = null, nacteno = null;
    function adresa(url) { return "/kontrola.html?items=mu:" + encodeURIComponent(url) + "&rezim=nabidka&embed=1&vzhled=1"; }
    function otevreno() { return !w.box.classList.contains("is-closed"); }
    function nacti(vynutit) {
      if (!S.modelUrl) { holder.textContent = "Čekám na 3D model konfigurace…"; return; }
      if (frame && nacteno === S.modelUrl && !vynutit) return;
      holder.textContent = ""; nacteno = S.modelUrl;
      frame = el("iframe", { id: "vzhledFrame", title: "Vzhled online nabídek", src: adresa(S.modelUrl) });
      frame.style.cssText = "width:100%;height:min(78vh,820px);min-height:520px;border:1px solid var(--line);background:#fff;display:block";
      holder.appendChild(frame);
      frame.addEventListener("load", function () { if (S.vzhledScroll) { S.vzhledScroll = false; try { w.box.scrollIntoView({ block: "start" }); } catch (e) { /* stary prohlizec */ } } });          // odkaz z karty: az po nacteni (mrizka oken se dokresluje pozdeji)
      novy.setAttribute("href", adresa(S.modelUrl));
    }
    reload.addEventListener("click", function () { nacti(true); });
    bar.appendChild(reload); bar.appendChild(novy);
    [info, bar, holder].forEach(function (n) { w.body.appendChild(n); });
    if (head) head.addEventListener("click", function () { if (otevreno()) nacti(false); });          // sklopne okno prepne tridu sam (pdc-layout); iframe az pri prvnim rozbaleni
    S.vzhledModel = function () { if (otevreno() && !frame) nacti(false); };                           // model dorazil az po rozbaleni
    if (/[?&]vzhled=1(?:&|$)/.test(location.search)) {                                                  // odkaz z karty produktu: okno rozbalit a ukazat
      S.vzhledScroll = true;
      w.box.classList.remove("is-closed"); if (head) head.setAttribute("aria-expanded", "true");
      nacti(false);
    }
  }

  // ---------------------------------------------------------------- pravidla stolu (nastavitelne prahy a ceny; PO SYSTEMECH 30 / 35 / 40, vidi jen admin)
  function initPravidla() {
    // pole pravidel: zobrazi se JEN to, co server (GET /api/stul/pravidla) zna, a PUT posila jen tyto klice - statika jde zive driv nez nasazene API (bot16: "neznamy klic pravidla")
    var POLE = [
      { key: "hloubka_stredni_profil", id: "pravHloubka", re: /^\d{3,4}(\.\d+)?$/, msg: "Zadej hloubku v mm jako číslo (např. 900)." },
      { key: "vzpery_od_ramene", id: "pravVzpery", re: /^\d{3,4}(\.\d+)?$/, msg: "Zadej délku ramene v mm jako číslo (např. 500)." },
      { key: "cena_vyrez", id: "pravVyrez", re: /^\d{1,6}(\.\d+)?$/, msg: "Zadej cenu výřezu v Kč jako číslo (0 = bez příplatku)." },
      { key: "sirka_stredni_noha", id: "pravStredni", re: /^\d{3,4}(\.\d+)?$/, msg: "Zadej šířku stolu v mm jako číslo (např. 1500)." },
      { key: "min_odstup_stredni_noha", id: "pravOdstupSt", re: /^\d{2,4}(\.\d+)?$/, msg: "Zadej vzdálenost v mm jako číslo (např. 150)." },
      { key: "hloubka_stredni_noha", id: "pravStredniRada", re: /^\d{3,4}(\.\d+)?$/, msg: "Zadej hloubku stolu v mm jako číslo (např. 1500)." },
      { key: "podpera_max_rozpon", id: "pravRozpon", re: /^\d{3,4}(\.\d+)?$/, msg: "Zadej délku úseku v mm jako číslo (např. 800)." },
      { key: "cena_navlek_200", id: "pravNavlek200", re: /^\d{1,6}(\.\d+)?$/, msg: "Zadej cenu návleku 200 mm v Kč jako číslo (např. 370)." },
      { key: "cena_navlek_400", id: "pravNavlek400", re: /^\d{1,6}(\.\d+)?$/, msg: "Zadej cenu návleku 400 mm v Kč jako číslo (např. 550)." },
      { key: "cena_noha_sse_400", id: "pravNoha400", re: /^\d{1,6}(\.\d+)?$/, msg: "Zadej cenu nohy SSE (spojnice 400 mm) v Kč jako číslo (0 = nezadáno)." },
      { key: "cena_noha_sse_1100", id: "pravNoha1100", re: /^\d{1,6}(\.\d+)?$/, msg: "Zadej cenu nohy SSE (spojnice 1100 mm) v Kč jako číslo (0 = nezadáno)." }
    ];
    var NAVLEK_KLICE = { cena_navlek_200: 1, cena_navlek_400: 1 };
    var HLUBOKE_KLICE = { hloubka_stredni_noha: 1 };                                         // jen u hlubokeho stolu (system 45; server: hluboke_systemy)
    var SSE_KLICE = { cena_noha_sse_400: 1, cena_noha_sse_1100: 1 };                         // jen u systemu SSE (server: sse_systemy)
    var SSE_NEPLATI = { hloubka_stredni_profil: 1, vzpery_od_ramene: 1, cena_vyrez: 1, podpera_max_rozpon: 1 };    // u systemu SSE nic nedelaji (nema podpery, vzpery ani vyrezy)
    var VYCHOZI_PORADI = ["hloubka_stredni_profil", "sirka_stredni_noha", "min_odstup_stredni_noha", "hloubka_stredni_noha", "podpera_max_rozpon", "vzpery_od_ramene", "cena_vyrez", "cena_navlek_200", "cena_navlek_400", "cena_noha_sse_400", "cena_noha_sse_1100"];
    var st = $("pravStav"), znama = {}, data = null, sys = SYSTEM, nacteno = {};        // data = odpoved serveru; sys = system, jehoz pravidla se prave upravuji; nacteno = hodnoty ze serveru pro sys (na hlidani neulozenych zmen)
    function stav(t, chyba) { st.textContent = t; st.style.color = chyba ? "var(--error)" : "var(--muted)"; }
    function zobraz(pole, ano) {
      var inp = $(pole.id), lab = inp.previousElementSibling;
      inp.style.display = ano ? "" : "none"; if (lab && lab.tagName === "LABEL") lab.style.display = ano ? "" : "none";
    }
    POLE.forEach(function (f) { zobraz(f, false); });
    function poSystemech() { return !!(data && data.systemy); }                    // starsi API (jedna sada pro vsechny systemy): jeden formular jako dosud
    function pravidlaSystemu(n) { return poSystemech() ? (data.systemy[String(n)] || {}) : ((data && data.pravidla) || {}); }
    function maNavlek(n) { return !poSystemech() || (data.navlek_systemy || []).indexOf(n) >= 0; }
    function jeSse(n) { return poSystemech() && (data.sse_systemy || []).indexOf(n) >= 0; }
    function jeHluboky(n) { return poSystemech() && (data.hluboke_systemy || []).indexOf(n) >= 0; }
    function plati(klic, n) { return NAVLEK_KLICE[klic] ? maNavlek(n) : HLUBOKE_KLICE[klic] ? jeHluboky(n) : SSE_KLICE[klic] ? jeSse(n) : SSE_NEPLATI[klic] ? !jeSse(n) : true; }          // ktera pole se u systemu zadavaji
    function vypisHodnoty() {
      var pr = pravidlaSystemu(sys); nacteno = {};
      POLE.forEach(function (f) {
        var jde = pr[f.key] != null && plati(f.key, sys);                              // ceny navleku jen u systemu s navlekem (35), ceny nohy SSE jen u SSE; u SSE neplati podpery / vzpery / vyrez
        znama[f.key] = jde;
        if (jde) { $(f.id).value = String(Math.round(pr[f.key])); nacteno[f.key] = $(f.id).value; }
        zobraz(f, jde);
      });
      [30, 35, 40, 41, 45].forEach(function (n) {
        var b = $("pravSys" + n); b.setAttribute("aria-pressed", n === sys ? "true" : "false"); b.style.borderColor = n === sys ? "var(--accent)" : ""; b.style.color = n === sys ? "var(--accent)" : "";
        b.style.display = ((n === 41 || n === 45) && poSystemech() && !data.systemy[String(n)]) ? "none" : "";                // starsi API bez systemu SSE / 45: tlacitko se neukazuje
      });
      $("pravSysCap").parentNode.style.display = poSystemech() ? "" : "none";          // bez po-systemoveho API se prepinac neukazuje
      var vychozi = (data && data.vychozi_systemu && data.vychozi_systemu[String(sys)]) || (data && data.vychozi) || {};          // vychozi hodnoty SYSTEMU (SSE: stredni noha od 2000 mm)
      $("pravVychozi").textContent = "Výchozí pro " + sysNazev(sys) + " (" + VYCHOZI_PORADI.filter(function (k) { return znama[k]; }).map(function (k) { return Math.round(vychozi[k] != null ? vychozi[k] : 0); }).join(", ") + ")";
    }
    function zmeneno() { return POLE.some(function (f) { return znama[f.key] && String($(f.id).value || "").replace(/\s+/g, "") !== nacteno[f.key]; }); }
    function nactiHodnoty(d) { data = d; vypisHodnoty(); }
    [30, 35, 40, 41, 45].forEach(function (n) {
      $("pravSys" + n).addEventListener("click", function () {
        if (n === sys) return;
        if (zmeneno()) { stav("Máš neuložené změny systému " + sys + " – ulož je (nebo obnov stránku), než přepneš.", true); return; }
        sys = n; stav("", false); vypisHodnoty();
      });
    });
    fetch("/api/stul/pravidla", { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) { if (d && (d.pravidla || d.systemy)) nactiHodnoty(d); })
      .catch(function () { /* nepřihlášený / bez práva: pole zůstanou skrytá */ });
    function uloz(pravidla) {
      stav("Ukládám…", false);
      var body = poSystemech() ? { system: sys, pravidla: pravidla } : pravidla;                  // po systemech: jen pravidla zvoleneho systemu; starsi API: plochy slovnik
      fetch("/api/stul/pravidla", { method: "PUT", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok, status: r.status, d: d }; }); })
        .then(function (x) {
          if (!x.ok) { stav(x.status === 403 ? "Na změnu pravidel nemáš oprávnění (jen admin)." : (x.d.error || "Uložení se nepovedlo."), true); return; }
          nactiHodnoty(x.d);
          stav("Uloženo (" + sysNazev(sys) + "), přepočítávám stůl…", false);
          setTimeout(function () { location.reload(); }, 600);
        }).catch(function () { stav("Spojení selhalo.", true); });
    }
    $("pravUloz").addEventListener("click", function () {
      var body = {};
      for (var i = 0; i < POLE.length; i++) {
        var f = POLE[i]; if (!znama[f.key]) continue;
        var v = String($(f.id).value || "").replace(/\s+/g, "").replace(",", ".");
        if (!f.re.test(v)) { stav(f.msg, true); return; }
        body[f.key] = Number(v);
      }
      uloz(body);
    });
    $("pravVychozi").addEventListener("click", function () { var body = {}; POLE.forEach(function (f) { if (znama[f.key]) body[f.key] = ""; }); uloz(body); });
  }

  // ---------------------------------------------------------------- vychozi konfigurace pro admina: "Ulozit jako vychozi" (PUT /api/shop/products/<id>/configurator/default) a "Vratit puvodni" (DELETE)
  function initVychozi() {
    var bs = $("defSave"), br = $("defReset"), st = $("defStatus"), url = "/api/shop/products/" + S.productId + "/configurator", armed = null, timer = null;
    function stav(t, chyba) { st.textContent = t; st.style.color = chyba ? "var(--error)" : "var(--muted)"; }
    function ukaz(ulozeno) { br.hidden = !ulozeno; stav(ulozeno ? "Výchozí konfigurace je uložená (jiná než původní)." : "Platí původní výchozí konfigurace.", false); }
    fetch(url + "?lang=cs", { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; }).then(function (sc) {
      if (!sc || typeof sc.default_saved !== "boolean") return;                    // PROBE: starsi backend (jeste nenasazene API) pole `default_saved` nezna - okno zustane skryte (statika je zive hned, api/*.py az pri nasazeni 0:00 / 12:30)
      S.L.wins.defcfg.box.hidden = false;
      ukaz(sc.default_saved);
      if ("view" in sc) pohled(sc.view);                                         // PROBE: starsi backend pole `view` nezna - blok pohledu zustane skryty
    });
    function odzbroj() { if (armed) { armed.btn.textContent = armed.text; clearTimeout(timer); armed = null; } }
    function potvrdit(btn, text, akce) {                          // dvoukrokove potvrzeni (zmena plati pro vsechny navstevniky): prvni klik zmeni popisek, druhy klik do 6 s provede akci
      btn.addEventListener("click", function () {
        if (armed && armed.btn === btn) { odzbroj(); akce(); return; }
        odzbroj(); armed = { btn: btn, text: btn.textContent }; btn.textContent = text; timer = setTimeout(odzbroj, 6000);
      });
    }
    function odpoved(r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok, status: r.status, d: d }; }); }
    function hotovo(x, text, bezHashe) {
      if (!x.ok) { stav(x.status === 401 || x.status === 403 ? "Na změnu výchozí konfigurace nemáš oprávnění (jen admin)." : (x.d.error || "Uložení se nepovedlo."), true); return; }
      stav(text, false);
      if (bezHashe) { try { history.replaceState(null, "", location.pathname + location.search); } catch (e) { /* ignoruj */ } }          // po "vratit puvodni" se stranka otevre s puvodni vychozi, ne s hashem posledniho vyberu
      setTimeout(function () { location.reload(); }, 700);          // modul nacte nove schema (vychozi hodnoty, tlacitko "Vychozi hodnoty"); konfigurace zustane v hashi odkazu
    }
    potvrdit(bs, "Opravdu uložit pro všechny?", function () {
      if (!S.sel) { stav("Konfigurace se ještě nenačetla.", true); return; }
      stav("Ukládám…", false);
      fetch(url + "/default", { method: "PUT", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ selection: S.sel }) })
        .then(odpoved).then(function (x) { hotovo(x, "Uloženo – tahle konfigurace je teď výchozí pro všechny. Načítám znovu…", false); }).catch(function () { stav("Spojení selhalo.", true); });
    });
    potvrdit(br, "Opravdu vrátit původní?", function () {
      stav("Vracím…", false);
      fetch(url + "/default", { method: "DELETE", credentials: "same-origin" })
        .then(odpoved).then(function (x) { hotovo(x, "Vráceno původní výchozí nastavení. Načítám znovu…", true); }).catch(function () { stav("Spojení selhalo.", true); });
    });
    // ---- vychozi uhel pohledu 3D (viewer 1.17.0: currentAngles / setIsoAngles; PUT / DELETE /api/shop/configurator/view = jedno nastaveni pro vsechny generatory)
    function pohled(ulozeny) {
      var bsp = $("pohledSave"), brp = $("pohledReset"), stp = $("pohledStatus"), akt = $("pohledAktualni"), blok = $("pohledBlok"), vurl = "/api/shop/configurator/view", odhlasit = null;
      function stavP(t, chyba) { stp.textContent = t; stp.style.color = chyba ? "var(--error)" : "var(--muted)"; }
      function txt(a) { return "otočení " + a.az + "°, náklon " + a.el + "°"; }
      function viewer() { return S.ctl && S.ctl.viewer ? S.ctl.viewer() : null; }
      function ukazP(a) { brp.hidden = !a; stavP(a ? "Výchozí pohled je uložený: " + txt(a) + "." : "Platí původní výchozí pohled (otočení 35°, náklon 25°).", false); }
      function sleduj() {                                                           // aktualni uhel kamery (po otoceni modelu): co se ulozi
        var v = viewer();
        if (!v || !v.onCamera) return;
        if (odhlasit) odhlasit();
        var posledni = "";
        odhlasit = v.onCamera(function () { var a = v.currentAngles && v.currentAngles(); var t = a ? "Aktuální pohled: " + txt(a) : ""; if (t !== posledni) { posledni = t; akt.textContent = t; } });
      }
      blok.hidden = false; ukazP(ulozeny); sleduj();
      S.pohledSleduj = sleduj;                                                      // hostitel ho zavola po novem mountu prohlizece (onViewer)
      function odpovedP(r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok, status: r.status, d: d }; }); }
      function chybaP(x) { return x.status === 401 || x.status === 403 ? "Na změnu výchozího pohledu nemáš oprávnění (jen admin)." : (x.d.error || "Uložení se nepovedlo."); }
      potvrdit(bsp, "Opravdu uložit pro všechny?", function () {
        var v = viewer(), a = v && v.currentAngles && v.currentAngles();
        if (!a) { stavP("Model se ještě nenačetl.", true); return; }
        stavP("Ukládám…", false);
        fetch(vurl, { method: "PUT", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(a) })
          .then(odpovedP).then(function (x) {
            if (!x.ok) { stavP(chybaP(x), true); return; }
            ukazP(x.d.view); stavP("Uloženo – generátory se teď otevírají s pohledem: " + txt(x.d.view) + ".", false);
            if (v.setIsoAngles) v.setIsoAngles(x.d.view, false);                    // tlacitko 3D se vraci na novy pohled (kamera uz tam je)
          }).catch(function () { stavP("Spojení selhalo.", true); });
      });
      potvrdit(brp, "Opravdu vrátit původní?", function () {
        stavP("Vracím…", false);
        fetch(vurl, { method: "DELETE", credentials: "same-origin" })
          .then(odpovedP).then(function (x) {
            if (!x.ok) { stavP(chybaP(x), true); return; }
            ukazP(null); stavP("Vrácen původní pohled (otočení 35°, náklon 25°).", false);
            var v = viewer(); if (v && v.setIsoAngles) v.setIsoAngles(null, true);
          }).catch(function () { stavP("Spojení selhalo.", true); });
      });
    }
  }

  // ---------------------------------------------------------------- start
  function start() {
    var lay = buildLayout();
    $("loginLink").setAttribute("href", "/login.html?next=" + encodeURIComponent(location.pathname + location.hash));
    $("copyBtn").addEventListener("click", function () {
      var url = location.href;
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(function () { $("staffCode").textContent = "Odkaz je zkopírovaný."; }, function () { $("staffCode").textContent = url; });
      else $("staffCode").textContent = url;
    });
    $("bomCopy").addEventListener("click", function () {
      var txt = S.bomRows.map(function (r) { return r.join("\t"); }).join("\n");
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(function () { $("staffCode").textContent = "Kusovník je zkopírovaný (vlož do tabulky)."; });
    });
    fetch("/api/auth/me", { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : { user: null }; }).catch(function () { return { user: null }; }).then(function (me) {
      if (!me.user) { $("login").style.display = "block"; $("stageMsg").textContent = "Pro zobrazení se přihlas."; $("shGrid").style.display = "none"; return; }
      S.admin = me.user.role === "admin";
      if (S.admin) { S.L.wins.rules.box.hidden = false; initPravidla(); initVzhled(); }          // Pravidla stolu vidi JEN ADMIN (Robert 2026-10-05; GET i PUT /api/stul/pravidla hlida server): ostatni je nenacitaji ani nevidi
      nactiSystemy().then(function (systems) {
      S.systems = systems;
      var pid = produktSystemu(systems, SYSTEM);
      if (!pid) { $("stageMsg").textContent = "Generátor stolu " + GEN[SYSTEM].no + " (" + sysNazev(SYSTEM) + ") zatím není zapnutý."; return; }
      S.productId = pid;
      if (S.admin) initVychozi();          // Ulozit jako vychozi vidi a pouzije JEN ADMIN (Robert 2026-10-05; PUT / DELETE .../configurator/default hlida server); okno se ukaze az kdyz backend umi (probe v initVychozi)
      zobrazPrepinac();
      var lux = window.StulLuxy ? window.StulLuxy.create({ lang: "cs" }) : null;                    // pocitadlo luxu ve 3D nahledu (js/stul-luxy.js; Robert 2026-10-05)
      var ctx = {
        product: { id: pid, configurator: { available: true, default_view: "configurator" } },
        noTurntable: true, lang: "cs", labels: LABELS, initialSelection: parseHash(location.hash), resolveExtra: { staff: true },
        dom: { tabsBefore: null, visual: [], stageHost: lay.media, panelHost: lay.panel, groupHost: lay.groupHost, summaryHost: lay.sumHost, reveal: lay.reveal, dependsOn: window.PdcLayout.DEPENDS },
        page: {
          setPrice: function () {}, setBuyState: function () { if (S.nabidka) S.nabidka.sync(); if (S.karta) S.karta.sync(); }, toast: function () {}, onActivate: function () {}, track: function () {},
          onResolved: function (r) { $("stageMsg").style.display = "none"; renderStaff(r); if (S.ctl && S.ctl.viewer) initEnv(S.ctl.viewer()); if (lux) lux.onResolved(r); if (S.nabidka) S.nabidka.sync(); if (S.karta) S.karta.sync(); },
          onViewer: function (v) { initEnv(v); if (S.pohledSleduj) S.pohledSleduj(); },
          onSelection: function (sel) { S.sel = sel; zapisHash(sel); },
          viewerPlugins: lux ? lux.viewerPlugins : undefined, onModel: function (url, hash) { lay.gate.unlock(); if (typeof url === "string" && url.indexOf("/api/shop/configurator/glb/") === 0) { S.modelUrl = url; if (S.vzhledModel) S.vzhledModel(); } if (lux && lux.onModel) lux.onModel(url, hash); }, onDrag: lux ? lux.onDrag : undefined
        },
        assets: { cssNow: ["/css/product-configurator.css?v=55f3678f8f"], css: ["/css/v3d.css?v=c76cbe7292"], viewer: "/js/v3d/viewer3d.js?v=e6b94b904a", ovladani: "/js/v3d-ovladani.js?v=1bc0d2b6ba" },
        viewerOpts: (window.matchMedia && window.matchMedia("(max-width: 700px)").matches)
          ? { hudDock: "top", hudKoty: true, dims: 0 }                     // uzke okno (mobil): maly nahled by kóty zahltily - prepinac Koty je, ale kóty jsou po nacteni vypnute (nestavi se)
          : { hudDock: "top", hudKoty: true }                              // Koty ve 3D nahledu (Robert 2026-10-05): prepinac Koty v HUD, koty z modelu (api/stul_koty.py); od 2026-10-05 stejne i v mini-shopu a ve vlozenem generatoru (modul voleb to dela vychozi)
      };
      window.PdConfigurator.init(ctx).then(function (ctl) {
        S.ctl = ctl;
        if (S.nabidka) S.nabidka.sync(); if (S.karta) S.karta.sync();                                              // prvni resolve mohl skoncit DRIV, nez se ovladac ulozil do S.ctl (stranka systemu 41): tlacitko Do online nabidky by zustalo zakazane
        if (!ctl) { $("stageMsg").textContent = "Generátor stolu " + GEN[SYSTEM].no + " není zapnutý."; return; }
        var prof = ctl.profile ? ctl.profile() : null;                                // profil ze schematu ("30x30"); bez animace / schematu pro profil se okna neukazuji
        if (prof) {
          window.PdcLayout.profileWindow(lay.profile, { profile: prof, version: TILE_JS.split("?v=")[1], text: function (mm, g) { return DOPLNKY.profileText.replace(/\{mm\}/g, mm).replace(/\{g\}/g, g); } });
          window.PdcLayout.attachWindow(lay.attach, { profile: prof, lang: "cs", accent: (getComputedStyle(document.documentElement).getPropertyValue("--accent") || "").trim() || undefined,
            getEnv: function () { return ctl.envConfig ? ctl.envConfig() : null; }, gate: lay.gate, tileUrl: TILE_JS, cssUrl: V3D_CSS });
        }
      });
      });
    });
  }
  window.StulHost = { state: S, parseHash: parseHash, system: SYSTEM };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
