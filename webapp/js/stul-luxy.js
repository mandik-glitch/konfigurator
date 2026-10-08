/* Pocitadlo luxu v Generatoru stolu (bot10, 2026-10-05; Robert: "zakomponuj to pocitadlo luxu do generatoru"). Napojeni Johnova pluginu (`V3D.luxPlugin`, js/lux/*,
 * vystup `pocitadlo_luxu_v2`) na product-configurator.js: tlacitko "Osvetleni · lux" ve 3D nahledu (jen kdyz ma stul LED), stupen svitidla 33 W / 21 W, vypocet nad
 * SKUTECNOU geometrii z `resolve.vodici.osvetleni` (api/stul_osvetleni.py; polohy uz ve stejnem posunu jako GLB).
 *
 * Pouziti (hostitel):
 *   var lux = StulLuxy.create({ lang: "cs" });                                  // lang: cs | en | sk
 *   ctx.page = { ..., viewerPlugins: lux.viewerPlugins, onResolved: function (r) { ...; lux.onResolved(r); }, onModel: lux.onModel, onDrag: lux.onDrag };
 * Skripty pocitadla (lux-core, lux-data, lux-plugin, css/lux.css) se nacitaji AZ pri prvnim zapnuti (generator se kvuli nim nezpomali); bez zapnuti se do 3D nic neprida.
 *
 * Konzistence cifer a modelu (Johnova podminka): cifry se ukazuji jen nad modelem, ke kteremu patri jejich payload (podle hashe konfigurace); behem zivého tazeni ve 3D
 * (model se meni jen v prohlizeci) se vypnou a vraci se s presnym modelem ze serveru. Plugin se pri kazde vymene modelu ukonci a znovu se spusti az po `onModel`. */
(function (global) {
  "use strict";
  var ASSETS = { core: "/js/lux/lux-core.js?v=2b553fac74", data: "/js/lux/lux-data.js?v=2bfe1d243f", plugin: "/js/lux/lux-plugin.js?v=9deea13164", css: "/css/lux.css?v=5df1a17c40" };
  var TYP_SKU = { led_1200: "LED1200", led_600: "LED600" };          // `typ` svitidla z resolve.vodici.osvetleni -> katalog Johna (LuxData); verejna odpoved SKU ani cisla produktu nenese
  var TEXTY = {
    cs: { btn: "Osvětlení · lux", btnKratky: "Lux", title: "Orientační výpočet osvětlení pracovní plochy (LED svítidlo, bez denního světla)", power: "Výkon svítidla", loading: "Načítám…", fail: "Počítadlo luxů se nepodařilo načíst" },
    en: { btn: "Lighting · lux", btnKratky: "Lux", title: "Indicative lighting calculation for the work surface (LED luminaire, no daylight)", power: "Luminaire power", loading: "Loading…", fail: "The lux counter could not be loaded" },
    sk: { btn: "Osvetlenie · lux", btnKratky: "Lux", title: "Orientačný výpočet osvetlenia pracovnej plochy (LED svietidlo, bez denného svetla)", power: "Výkon svietidla", loading: "Načítavam…", fail: "Počítadlo luxov sa nepodarilo načítať" }
  };
  var CSS = ".stl-lux-bar{position:absolute;right:10px;bottom:10px;z-index:6;display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end;max-width:calc(100% - 20px)}" +
    ".stl-lux-bar[hidden]{display:none}" +
    ".stl-lux-bar button{min-height:40px;padding:0 12px;border:1px solid #1f5c53;background:#0f1d27;color:#e9f4f1;font:600 13px/1 system-ui,sans-serif;letter-spacing:.03em;cursor:pointer;border-radius:0}" +
    ".stl-lux-bar button:focus-visible{outline:2px solid #87edcc;outline-offset:1px}" +
    ".stl-lux-bar button[aria-pressed=true]{border-color:#87edcc;box-shadow:inset 0 0 0 1px #87edcc;color:#87edcc}" +
    ".stl-lux-bar button[disabled]{opacity:.55;cursor:default}" +
    ".stl-lux-modes{display:flex;gap:0}.stl-lux-modes button+button{border-left:0}" +
    // nizke platno (mobil, staff stranka: ~200 px): souhrn jen nazev + prumer + minimum + normy, aby nelezl pod listu tlacitek
    ".stl-lux-compact .lux-hud{max-height:calc(100% - 62px);overflow:hidden}" +
    ".stl-lux-compact .lux-hud small:not(.lux-norms-caption):not(:first-of-type){display:none}.stl-lux-compact .lux-hud .lux-norms{display:none}" +
    // panel svitidla: dole nezasahuje pod listu; behem otevreneho panelu se schovaji uchyty a napovedy ovladani ve 3D a kóty (lezely by pres nej)
    // souhrn a panel nad zamkem 3D (.pdc-lock, z-index 4, na dotyku je 3D po nacteni zamcene) a nad uchyty ovladani (.pdc-ov, z-index 5): bez toho klepnuti na tlacitko "Cinnosti pri tomto osvetleni" trefilo
    // zamek nebo uchyt a panel se na mobilu neotevrel (panel v3, 2026-10-06; .lux-overlay ma pointer-events:none, interaktivni jsou jen tlacitko a panel)
    ".pdc-stage .lux-overlay{z-index:7}" +
    ".pdc-stage .lux-hover{max-height:calc(100% - 70px)}.pdc-stage.stl-lux-panel-open .pdc-ov,.pdc-stage.stl-lux-panel-open .v3d-dim{visibility:hidden}";
  var assetsP = null;

  function nactiAssets() {
    if (assetsP) return assetsP;
    function skript(url) {
      return new Promise(function (res, rej) {
        var s = document.createElement("script");
        s.src = url; s.onload = res; s.onerror = function () { rej(new Error("nenačteno " + url)); };
        document.head.appendChild(s);
      });
    }
    assetsP = new Promise(function (res) {
      var l = document.createElement("link");
      l.rel = "stylesheet"; l.href = ASSETS.css; l.onload = res; l.onerror = res; document.head.appendChild(l);          // chybejici CSS nesmi zablokovat vypocet
    }).then(function () { return skript(ASSETS.core); }).then(function () { return skript(ASSETS.data); }).then(function () { return skript(ASSETS.plugin); })
      .then(function () { if (!global.V3D || typeof global.V3D.luxPlugin !== "function" || !global.LuxCore || !global.LuxData) throw new Error("počítadlo luxů není úplné"); });
    assetsP.catch(function () { assetsP = null; });            // dalsi zapnuti zkusi nacist znovu
    return assetsP;
  }

  function create(opts) {
    opts = opts || {};
    var lang = TEXTY[opts.lang] ? opts.lang : "cs", T = TEXTY[lang];
    var enabled = false, loading = false, ready = false, dragging = false, stale = false;
    var mode = null, shownHash = null, payloads = {}, order = [];
    var luxObj = null, run = null, ctxP = null, bar = null, btn = null, modesEl = null, kratky = false, panelObs = null;

    function payloadShown() { return shownHash && payloads[shownHash] && payloads[shownHash].lights && payloads[shownHash].lights.length ? payloads[shownHash] : null; }
    function zapisPayload(hash, o) {
      if (!(hash in payloads)) { order.push(hash); if (order.length > 12) delete payloads[order.shift()]; }
      payloads[hash] = o || null;
    }
    function build(o) {                      // vstup LuxCore: geometrie ze serveru + udaje svitidla z katalogu v2 (jedna kopie), stupen podle volby
      var LD = global.LuxData;
      return {
        version: o.version, units: o.units, workplane: o.workplane,
        lights: o.lights.map(function (g) {
          var sku = TYP_SKU[g.typ];
          if (!sku) throw new Error("Neznámý typ svítidla: " + g.typ);
          var entry = LD.catalogue.filter(function (l) { return l.sku === sku; })[0];
          var m = mode && entry && entry.powerModes && entry.powerModes.some(function (x) { return x.id === mode; }) ? mode : undefined;       // stupen, ktery typ nema (1200: 33 W / 21 W, 600: 16 W) -> vychozi stupen typu
          return Object.assign({}, LD.selectLight(sku, m), g, { dimmingFactor: 1 });
        })
      };
    }
    function stop() {
      if (panelObs) { panelObs.stop(); panelObs = null; }
      if (run) { try { run(); } catch (e) { /* uklid pluginu */ } run = null; }
    }
    function sledujPanel(root) {          // trida na .pdc-stage, dokud je otevreny panel svitidla (CSS schova uchyty ovladani ve 3D)
      var panel = root.querySelector && root.querySelector(".lux-hover"), st = root.closest && root.closest(".pdc-stage");
      if (!panel || !st || !global.MutationObserver) return;
      var set = function () { st.classList.toggle("stl-lux-panel-open", !panel.hidden); };
      var mo = new global.MutationObserver(set); mo.observe(panel, { attributes: true, attributeFilter: ["hidden"] }); set();
      panelObs = { stop: function () { mo.disconnect(); st.classList.remove("stl-lux-panel-open"); } };
    }
    function sync() {
      postavModes();                       // typ svitidla se mohl zmenit (volba delky): tlacitka stupnu odpovidaji typu v aktualnim modelu
      updateBar();
      var o = payloadShown();
      if (!(enabled && ready && !dragging && !stale && ctxP && o && luxObj)) { stop(); return; }
      var input;
      try { input = build(o); } catch (e) { if (global.console) global.console.warn("lux:", e && e.message); stop(); return; }
      luxObj.setInput(input);
      if (!run) {
        var c2 = Object.assign({}, ctxP, { root: ctxP.stage || ctxP.root });      // prekryv jen nad platnem (u hudDock:'top' ne nad pruhem tlacitek prohlizece)
        run = luxObj.plugin(c2);
        sledujPanel(c2.root);
      }
    }
    function updateBar() {
      if (!bar) return;
      var o = payloadShown();
      bar.hidden = !o;
      if (btn) {
        btn.setAttribute("aria-pressed", String(enabled));
        btn.disabled = loading;
        btn.textContent = loading ? T.loading : (kratky ? T.btnKratky : T.btn);
        btn.setAttribute("aria-label", T.btn);
      }
      if (modesEl) {
        modesEl.hidden = !(enabled && ready && o) || modesEl.childNodes.length < 2;               // typ s jedinym stupnem (LED 600: 16 W) volbu stupne nema
        [].forEach.call(modesEl.querySelectorAll("button"), function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-mode") === mode)); });
      }
    }
    var modesSku = null;
    function postavModes() {
      if (!modesEl || !ready) return;
      var o = payloadShown(), sku = o && TYP_SKU[o.lights[0].typ], entry = sku && global.LuxData.catalogue.filter(function (l) { return l.sku === sku; })[0];
      if (!entry || !entry.powerModes) return;
      if (modesSku === sku && modesEl.childNodes.length) return;                   // tlacitka uz odpovidaji typu svitidla
      modesEl.textContent = ""; modesSku = sku;
      if (!mode || !entry.powerModes.some(function (m) { return m.id === mode; })) mode = entry.defaultModeId;          // stupen predchoziho typu tento typ nema
      entry.powerModes.forEach(function (m) {
        var b = document.createElement("button");
        b.type = "button"; b.setAttribute("data-mode", m.id); b.textContent = m.powerW + " W";
        b.title = m.powerW + " W · " + m.luminousFluxLm + " lm";
        b.addEventListener("click", function () { mode = m.id; sync(); });
        modesEl.appendChild(b);
      });
    }
    function zapni() {
      enabled = true; updateBar();
      if (ready) { postavModes(); sync(); return; }
      loading = true; updateBar();
      nactiAssets().then(function () {
        luxObj = global.V3D.luxPlugin({ lang: lang, allowEstimate: true, onError: function (e) { if (global.console) global.console.warn("lux:", e && e.message); } });
        ready = true; loading = false; postavModes(); sync();
      }).catch(function (e) {
        loading = false; enabled = false; updateBar();
        if (btn) { btn.title = T.fail; }
        if (global.console) global.console.warn("lux:", e && e.message);
      });
    }
    function vypni() { enabled = false; stop(); updateBar(); }
    function ensureBar(ctx) {
      var stage = (ctx.root && ctx.root.closest && ctx.root.closest(".pdc-stage")) || (ctx.root && ctx.root.parentNode);
      if (!stage) return;
      if (bar && bar.parentNode === stage) return;
      if (!document.getElementById("stl-lux-css")) {
        var st = document.createElement("style"); st.id = "stl-lux-css"; st.textContent = CSS; document.head.appendChild(st);
      }
      bar = document.createElement("div"); bar.className = "stl-lux-bar"; bar.hidden = true;
      modesEl = document.createElement("div"); modesEl.className = "stl-lux-modes"; modesEl.setAttribute("role", "group"); modesEl.setAttribute("aria-label", T.power); modesEl.hidden = true;
      btn = document.createElement("button"); btn.type = "button"; btn.className = "stl-lux-btn"; btn.title = T.title; btn.textContent = T.btn; btn.setAttribute("aria-pressed", "false");
      btn.addEventListener("click", function () { if (enabled) vypni(); else zapni(); });
      bar.appendChild(modesEl); bar.appendChild(btn);
      stage.appendChild(bar);
      var vstage = ctx.stage || stage;
      function kompakt() {
        var k = vstage.clientHeight > 0 && vstage.clientHeight < 320;
        vstage.classList.toggle("stl-lux-compact", k);
        if (k !== kratky) { kratky = k; updateBar(); }
      }
      kompakt();
      if (global.ResizeObserver) new global.ResizeObserver(kompakt).observe(vstage); else global.addEventListener("resize", kompakt);
      if (ready) postavModes();
      updateBar();
    }

    var api = {
      // page.viewerPlugins: jeden "proxy" plugin; jen si pamatuje ctx aktualniho modelu (spusteni pocitadla az po onModel, viz hlavicka)
      viewerPlugins: function () {
        return [function (ctx) {
          ctxP = ctx; ensureBar(ctx);
          return function dispose() { stop(); ctxP = null; };
        }];
      },
      onResolved: function (r) {
        if (!r || !r.hash) return;
        zapisPayload(r.hash, r.vodici && r.vodici.osvetleni ? r.vodici.osvetleni : null);
        if (!dragging && stale && r.hash === shownHash) stale = false;      // po tazeni: odpoved ze serveru pro tentyz model (hodnota se nezmenila)
        sync();
      },
      onModel: function (url, hash) {
        if (!hash) return;
        shownHash = hash; stale = false;
        sync();
      },
      onDrag: function (on) {
        dragging = !!on;
        if (on) { stale = true; stop(); }
        sync();
      },
      setLang: function (l) { if (TEXTY[l]) { lang = l; T = TEXTY[l]; if (luxObj) luxObj.setLanguage(l); } },
      // jen pro testy
      _state: function () { return { enabled: enabled, ready: ready, running: !!run, mode: mode, shownHash: shownHash, stale: stale, dragging: dragging, payload: !!payloadShown() }; }
    };
    if (global.__pdcDebug) global.__stulLux = api;
    return api;
  }

  global.StulLuxy = { create: create, ASSETS: ASSETS };
})(window);
