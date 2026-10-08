/*
 * Otocny (sfericky) nahled sestavy z predrenderovanych snimku - bot16,
 * 2026-09-02 (Robert: "otocny nahled 360 ze 3D sceny, k nerozeznani svou
 * kvalitou, zadne rozmazani"; musi fungovat BEZ WebGL - Robertuv Firefox
 * WebGL nema - a na iPhonu).
 *
 * Ciste <img> + CSS transform, zadne zavislosti, zadny canvas/WebGL.
 * Data dodava GET /api/shop/products/<id>/turntable (api/turntable.py):
 *   {available, step_deg, elevations:[0,20,40,60,80], default_elevation,
 *    default_azimuth (60; stara davka bez klice -> 30), aspect:[1,1]
 *    (ctverec 2048x2048/1024x1024; stara davka [4,3] - vse se odvozuje z
 *    meta.aspect, nic natvrdo), tiers:[1024,2048], hero_url (kopie snimku
 *    e<default_elevation>/a<default_azimuth>), hero_width/hero_height,
 *    hero_srcset (1x1 varianty),
 *    rings:[{elevation, frames:[{azimuth, urls:{"1024":..,"2048":..}, bytes:{..}}]}]}
 * 5 prstencu elevace x 36 azimutu po 10 deg = 180 snimku, kazdy ve dvou
 * tierech (1024x768 a 2048x1536 JPEG).
 *
 * Klicove principy (proc je to napsane takhle):
 * - NIKDY neupscalovat: tier se voli podle sirky kontejneru x devicePixelRatio
 *   (x zoom) a <img> se nikdy nezobrazi vetsi nez nativni rozliseni/DPR
 *   (max-width korene = maxTier/DPR). Pri zoomu >1 se bere vzdy nejvyssi
 *   tier. Jediny pripusteny mirny upscale: iPhone DPR3 pri plnem 2x zoomu
 *   (390*2*3 = 2340 > 2048) - krajni pripad, zapsano v AGENTS_LOG.md.
 * - Datovy rozpocet pred interakci (mobil ~2-3 MB) + LCP: pri mountu se
 *   stahne JEN hero snimek (meta.hero_url = 2048, elevace 20 / azimut 30).
 *   Kdyz uz v kontejneru <img> je (SSR hero od bot14 - img[data-tt-hero]
 *   nebo prvni img), widget ho POVYSI: prevezme ho jako prvni snimek bez
 *   opetovneho stazeni a jen kolem nej postavi ovladani. Bez SSR si ho
 *   vytvori sam (src=hero_url, width/height, alt) - chovani shodne.
 *   Vychozi prstenec (1024) se stahuje na desktopu az po window.load +
 *   requestIdleCallback (fallback 1500 ms), na mobilu (pointer: coarse) az
 *   pri prvnim dotyku; sousedni prstence (+1, -1) az po dokonceni
 *   vychoziho; ostatni prstence az pri prvnim svislem gestu / sipce
 *   nahoru-dolu. Bez tehle politiky by stranka tahala 10+ MB a kazila LCP.
 * - Bez blikani: vymena snimku se dela az po img.decode() (fallback onload
 *   pro stare Safari) a nahrazenim DOM uzlu uz dekodovanym <img>, ne
 *   prepisem src (to v Safari kratce blikne prazdnem).
 * - Chybejici/rozbity snimek -> zustava posledni dobry; stav (azimut/
 *   elevace) se ale posune a snimek se dohraje, jakmile je k dispozici.
 *
 * API (zavazny kontrakt dohodnuty s bot14 - modul zakresleni pripominky
 * v product.html na nem stavi, viz AGENTS_LOG.md 2026-09-02):
 *   const tt = Turntable.mount(containerEl, meta, {
 *     initialAzimuth (default = meta.default_azimuth, tj. hero), initialElevation
 *     (default = meta.default_elevation), alt, onViewChange(az, el),
 *     onAngleChange(az), onFrameShown({azimuth, elevation, tier, url, img}),
 *     dragDirection: -1|1, maxZoom: 2, maxViewportHeight: 0.6 });
 *   tt.ready -> Promise (prvni snimek zobrazen / reject kdyz nejde nacist)
 *   tt.getAngle() == tt.getAzimuth(), tt.getElevation(), tt.getZoom()
 *   tt.setView(az, el) (alias goTo bez promise), tt.setAngle(az)
 *   tt.goTo(az, el) -> Promise<frame> (skok bez animace, resolve az je snimek
 *       zobrazeny - v klidu 2048)
 *   tt.getCurrentFrame() -> {azimuth, elevation, azimuth_deg, elevation_deg,
 *       url (VZDY 2048 tier aktualniho az/el, i kdyz je zrovna videt 1024),
 *       width, height (rozmery url), tier, displayedUrl, img, naturalWidth,
 *       naturalHeight (co je prave videt), zoom, pan:[u,v] (zlomek snimku
 *       0..1 v levem hornim rohu vyrezu), panX, panY (CSS px), angle}
 *   tt.ensureHiRes() -> Promise<frame> (pocka, az je pro aktualni az/el
 *       nacteny+dekodovany+zobrazeny 2048 snimek; bot14 vola pred zakresem)
 *   tt.resetZoom(), tt.setZoom(z), tt.getStats(), tt.destroy()
 *   tt.actionsEl = prazdny <div class="tt-actions"> (pravy dolni roh) pro
 *       cizi tlacitka (bot14: "Zakreslit tento pohled"), tt.el = koren
 *   Udalosti na containerEl (bubbles:true, jde je chytit i na document):
 *   CustomEvent "turntable:change" (detail =
 *       getCurrentFrame()) pri kazde zmene snimku/zoomu, "turntable:ready"
 *       po prvnim snimku (detail = tt). Mobil: koren ma max-height 60vh
 *       (pres max-width = 60vh/aspect, centrovano margin:auto), aby vedle
 *       widgetu slo scrollovat.
 *
 * Ovladani: vodorovne tazeni = azimut (cely prutah pres sirku = 1 otocka),
 * svisle tazeni = prstenec elevace (prah 40 px a |dy| > 1.5*|dx| od zacatku
 * gesta; jednou zvoleny rezim drzi do pointerup). Kolecko = zoom (az po
 * prvnim kliknuti/focusu do widgetu, aby widget nekradl scroll stranky pri
 * prujezdu), Shift+kolecko = prstenec, sipky <- -> = azimut, sipky nahoru/
 * dolu = prstenec, +/- zoom, 0/Esc reset zoomu, dvojklik/dvojtap = zoom 1x/2x,
 * pinch = zoom, tazeni v zoomu = posun (pan). Tlacitka < > (azimut) a
 * nahoru/dolu (prstenec) jsou vzdy viditelna - svisle gesto na mobilu
 * vyzaduje touch-action:none uvnitr widgetu (tj. pres widget nejde
 * scrollovat stranku prstem), tlacitka jsou jistota, ze se k prstencum
 * dostane kazdy.
 */
(function (global) {
  "use strict";

  var STYLE_ID = "tt-widget-style";
  var CSS = [
    ".tt-root{position:relative;width:100%;margin:0 auto;overflow:hidden;touch-action:none;",
    "user-select:none;-webkit-user-select:none;-webkit-touch-callout:none;outline:none;",
    "background:var(--panel-bg,#eceef1);cursor:grab;box-sizing:border-box}",
    ".tt-root:focus-visible{box-shadow:0 0 0 2px var(--accent,#1a6fd4) inset}",
    ".tt-root.tt-dragging{cursor:grabbing}",
    ".tt-root.tt-zoomed{cursor:move}",
    ".tt-sizer{width:100%;padding-top:75%}",
    ".tt-stage{position:absolute;left:0;top:0;width:100%;height:100%;transform-origin:0 0;will-change:transform}",
    ".tt-stage img{position:absolute;left:0;top:0;width:100%;height:100%;display:block;object-fit:contain;",
    "pointer-events:none;-webkit-user-drag:none}",
    ".tt-stage img[hidden]{display:none}",
    ".tt-hint{position:absolute;left:8px;bottom:10px;max-width:52%;padding:5px 10px;border-radius:12px;",
    "background:rgba(20,22,27,.62);color:#fff;font:11.5px/1.3 system-ui,sans-serif;pointer-events:none;",
    "transition:opacity .4s;opacity:1}",
    ".tt-actions{position:absolute;right:8px;bottom:10px;display:flex;gap:6px;align-items:center;pointer-events:auto;",
    "font:12px/1.2 system-ui,sans-serif}",
    ".tt-hint.tt-hidden{opacity:0}",
    ".tt-progress{position:absolute;left:0;bottom:0;height:3px;width:0;background:var(--accent,#1a6fd4);opacity:.9;",
    "transition:width .15s linear,opacity .4s;pointer-events:none}",
    ".tt-progress.tt-hidden{opacity:0}",
    ".tt-btns{position:absolute;right:8px;top:8px;display:grid;grid-template-columns:28px 28px 28px;grid-template-rows:28px 28px;gap:3px;",
    "opacity:.55;transition:opacity .2s}",
    ".tt-root:hover .tt-btns,.tt-root:focus-within .tt-btns{opacity:.95}",
    ".tt-btn{appearance:none;-webkit-appearance:none;border:0;border-radius:4px;background:rgba(20,22,27,.62);color:#fff;",
    "font:14px/1 system-ui,sans-serif;cursor:pointer;padding:0;width:28px;height:28px;display:flex;align-items:center;justify-content:center;touch-action:manipulation}",
    ".tt-btn:hover{background:rgba(20,22,27,.85)}",
    ".tt-btn[disabled]{opacity:.3;cursor:default}",
    ".tt-btn-up{grid-column:2;grid-row:1}.tt-btn-left{grid-column:1;grid-row:2}.tt-btn-down{grid-column:2;grid-row:2}.tt-btn-right{grid-column:3;grid-row:2}",
    ".tt-badge{position:absolute;left:8px;top:8px;padding:3px 7px;border-radius:3px;background:rgba(20,22,27,.55);color:#fff;",
    "font:11px/1.2 system-ui,sans-serif;pointer-events:none;letter-spacing:.02em}",
    "@media (prefers-reduced-motion: reduce){.tt-hint,.tt-progress,.tt-btns{transition:none}}"
  ].join("");

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var s = document.createElement("style");
    s.id = STYLE_ID;
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function clamp(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }
  function mod(a, n) { return ((a % n) + n) % n; }

  function requestIdle(fn, timeout) {
    if (typeof global.requestIdleCallback === "function") return global.requestIdleCallback(fn, { timeout: timeout || 3000 });
    return setTimeout(fn, 1500);
  }

  // "Desktop" = presne ukazovatko s hoverem a bez Save-Data. Rozhoduje,
  // jestli se vychozi prstenec zacne stahovat uz v idle case (desktop),
  // nebo az pri prvnim dotyku (mobil - datovy limit pred interakci).
  function detectDesktop() {
    try {
      var conn = navigator.connection;
      if (conn && conn.saveData) return false;
      return global.matchMedia && global.matchMedia("(hover: hover) and (pointer: fine)").matches;
    } catch (e) { return false; }
  }

  function afterWindowLoad(fn) {
    if (document.readyState === "complete") fn();
    else global.addEventListener("load", fn, { once: true });
  }

  // Najde v prstencich snimek, jehoz URL (libovolny tier) odpovida dane URL
  // (porovnani pres pathname - SSR muze mit absolutni i relativni src).
  function findFrameByUrl(ringFrames, url) {
    if (!url) return null;
    var want;
    try { want = new URL(url, global.location.href).pathname; } catch (e) { want = url; }
    for (var ei = 0; ei < ringFrames.length; ei++) {
      for (var a in ringFrames[ei]) {
        var urls = ringFrames[ei][a].urls || {};
        for (var t in urls) {
          var pn; try { pn = new URL(urls[t], global.location.href).pathname; } catch (e) { pn = urls[t]; }
          if (pn === want) return { ei: ei, az: Number(a), tier: Number(t) };
        }
      }
    }
    return null;
  }

  function samePath(a, b) {
    if (!a || !b) return false;
    var pa, pb;
    try { pa = new URL(a, global.location.href).pathname; pb = new URL(b, global.location.href).pathname; } catch (e) { return a === b; }
    return pa === pb;
  }

  function prefersReducedMotion() {
    try { return global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return false; }
  }

  function mount(container, meta, opts) {
    if (!container) throw new Error("Turntable.mount: chybi kontejner");
    if (!meta || !meta.available || !Array.isArray(meta.rings) || !meta.rings.length) {
      throw new Error("Turntable.mount: meta.available=false nebo prazdne rings");
    }
    opts = opts || {};
    injectStyle();

    // ---------- normalizace metadat ----------
    var step = Number(meta.step_deg) || 10;
    var tiers = (meta.tiers || []).map(Number).filter(function (t) { return t > 0; }).sort(function (a, b) { return a - b; });
    var rings = meta.rings.slice().sort(function (a, b) { return a.elevation - b.elevation; });
    var elevations = rings.map(function (r) { return Number(r.elevation); });
    // ring index -> Map(azimuth -> frame)
    var ringFrames = rings.map(function (r) {
      var m = {};
      (r.frames || []).forEach(function (f) {
        if (!tiers.length) tiers = Object.keys(f.urls || {}).map(Number).sort(function (a, b) { return a - b; });
        m[mod(Math.round(f.azimuth), 360)] = f;
      });
      return m;
    });
    if (!tiers.length) throw new Error("Turntable.mount: zadne tiery");
    var minTier = tiers[0], maxTier = tiers[tiers.length - 1];
    var azimuths = Object.keys(ringFrames[0]).map(Number).sort(function (a, b) { return a - b; });
    var nAz = azimuths.length || Math.round(360 / step);
    var aspect = (meta.aspect && meta.aspect.length === 2) ? (meta.aspect[1] / meta.aspect[0]) : 0.75;

    var maxZoom = opts.maxZoom || 2;
    var dragDir = opts.dragDirection === 1 ? 1 : -1; // -1 = tazeni doprava toci azimut dolu (jako OrbitControls: kamera obiha doleva, objekt se toci doprava)
    var reduced = prefersReducedMotion();
    var isDesktop = opts.preload === "idle" ? true : (opts.preload === "interaction" ? false : detectDesktop());

    // ---------- stav ----------
    var defaultIdx = elevations.indexOf(Number(meta.default_elevation));
    if (defaultIdx < 0) defaultIdx = Math.min(1, elevations.length - 1);
    // Vychozi pohled = hero: meta.default_azimuth/default_elevation (ctvercova
    // davka, 2026-09-02: hero = e20/a060); stara davka klice nema -> 30/default.
    var defaultAz = normAz(meta.default_azimuth != null ? meta.default_azimuth : 30);
    if (!ringFrames[defaultIdx] || !ringFrames[defaultIdx][defaultAz]) defaultAz = azimuths[0] || 0;
    // Hero = SSR <img> v kontejneru (data-tt-hero / prvni img), jinak meta.hero_url.
    // Jeho az/el se odvodi z URL (shoda s nekterym snimkem prstence); hero_url je
    // ale typicky samostatna kopie (content-files/turntable/<slug>/...-zepredu.jpg),
    // pak plati kontrakt: hero = vychozi pohled (default_azimuth/default_elevation).
    var ssrImg = container.querySelector("img[data-tt-hero]") || container.querySelector("img");
    var heroUrl = (ssrImg && ssrImg.getAttribute("src")) || meta.hero_url || null;
    var heroPos = findFrameByUrl(ringFrames, heroUrl);
    if (!heroPos) {
      var hAz = meta.hero_azimuth != null ? normAz(meta.hero_azimuth) : defaultAz;
      var hEi = meta.hero_elevation != null ? elevations.indexOf(Number(meta.hero_elevation)) : defaultIdx;
      if (hEi < 0) hEi = defaultIdx;
      if (!ringFrames[hEi] || !ringFrames[hEi][hAz]) hAz = defaultAz;
      heroPos = { ei: hEi, az: hAz, tier: Number(meta.hero_width) || tiers[tiers.length - 1] };
    }
    // meta.hero_srcset ("url 1024w, url 2048w" - kopie hero v ruznych sirkach, ne
    // prstencove snimky): mapa pathname -> sirka, aby se u SSR <img srcset> dal
    // z currentSrc urcit skutecny tier prevzateho obrazku.
    var heroSrcsetW = {};
    String(meta.hero_srcset || (ssrImg && ssrImg.getAttribute("srcset")) || "").split(",").forEach(function (part) {
      var m = part.trim().match(/^(\S+)\s+(\d+)w$/);
      if (!m) return;
      var pn; try { pn = new URL(m[1], global.location.href).pathname; } catch (e) { pn = m[1]; }
      heroSrcsetW[pn] = Number(m[2]);
    });
    function tierForWidth(w) { var r = tiers[0]; for (var i = 0; i < tiers.length; i++) if (tiers[i] <= w) r = tiers[i]; return r; }
    var elIdx = opts.initialElevation != null ? elevations.indexOf(Number(opts.initialElevation)) : (meta.default_elevation != null ? defaultIdx : heroPos.ei);
    if (elIdx < 0) elIdx = defaultIdx;
    var az = normAz(opts.initialAzimuth != null ? opts.initialAzimuth : (opts.initialAngle != null ? opts.initialAngle : (meta.default_azimuth != null ? defaultAz : heroPos.az)));
    // Robert 2026-09-13 (product.html: "nezobrazi se zadna fotka" pri
    // posouvani variant): opts.initialAzimuth/initialElevation muzou prijit
    // z JINE (drivejsi) instance widgetu (viz product.html pdMountTurntable,
    // "zachovat uhel pri prepnuti"). Uvnitr JEDNE instance smi az/elIdx
    // legitimne "odplout" mimo skutecne zachycene snimky (viz komentar v
    // hlavicce souboru - "stav se posune, snimek se dohraje az je k
    // dispozici", napr. tazenim smerem k nezachycene zadni casti) - snimek
    // casem dohraje, jakmile existuje. Jenze predana pozice pak sedi jako
    // POCATECNI stav UPLNE NOVE instance, ktera zadne "casem dohraje" nema -
    // render() nize ticho nic nezobrazi, kdyz frameAt(elIdx, az) neexistuje.
    // Domysli se na nejblizsi SKUTECNE existujici snimek v cilovem prstenci
    // misto slepe duverovat cizi/drivejsi pozici.
    if (!ringFrames[elIdx] || !ringFrames[elIdx][az]) {
      var fallbackAz = nearestAzInRing(elIdx, az);
      if (fallbackAz != null) az = fallbackAz;
      else { elIdx = defaultIdx; az = defaultAz; }
    }
    var zoom = 1, panX = 0, panY = 0;
    var shown = null;           // {azimuth, elevation, tier, url, img, frame}
    var heroImg = null;         // prevzaty/vytvoreny hero <img data-tt-hero> - zustava v DOM (skryty) i kdyz neni zobrazeny
    var destroyed = false;
    var interacted = false;
    var wheelArmed = false;
    var verticalUsed = false;
    var ringRequested = {};     // elevation index -> true (ring tier)
    var defaultRingDone = false;
    var hiTimer = null;
    var stats = { requested: 0, loaded: 0, failed: 0, bytesByMeta: 0 };

    function normAz(a) { return mod(Math.round(a / step) * step, 360); }
    // Nejblizsi SKUTECNE existujici azimut v danem prstenci (viz pouziti
    // vyse u initialAzimuth) - null jen kdyz prstenec nema zadny snimek.
    function nearestAzInRing(ei, wantAz) {
      var frames = ringFrames[ei];
      if (!frames) return null;
      var keys = Object.keys(frames).map(Number);
      if (!keys.length) return null;
      var best = keys[0], bestD = Infinity;
      keys.forEach(function (k) {
        var d = Math.abs(mod(k - wantAz, 360));
        d = Math.min(d, 360 - d);
        if (d < bestD) { bestD = d; best = k; }
      });
      return best;
    }

    // ---------- DOM ----------
    var root = document.createElement("div");
    root.className = "tt-root";
    root.tabIndex = 0;
    root.setAttribute("role", "img");
    root.setAttribute("aria-roledescription", "otočný náhled");
    var sizer = document.createElement("div");
    sizer.className = "tt-sizer";
    sizer.style.paddingTop = (aspect * 100) + "%";
    var stage = document.createElement("div");
    stage.className = "tt-stage";
    var hint = document.createElement("div");
    hint.className = "tt-hint";
    hint.textContent = elevations.length > 1 ? "Táhněte pro otočení · svisle pro náklon" : "Táhněte pro otočení";
    var progress = document.createElement("div");
    progress.className = "tt-progress tt-hidden";
    var badge = document.createElement("div");
    badge.className = "tt-badge";
    badge.setAttribute("aria-hidden", "true");
    var btns = document.createElement("div");
    btns.className = "tt-btns";
    function mkBtn(cls, label, title) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "tt-btn " + cls; b.textContent = label; b.title = title; b.setAttribute("aria-label", title);
      b.tabIndex = -1; // klavesnice jde pres root (sipky), tlacitka jsou pro mys/prst
      btns.appendChild(b);
      return b;
    }
    // Robert pres bot3, 2026-09-26 ("ať mají ty šipky stejné velikosti") -
    // ‹›  (U+2039/203A, "single angle quotation mark") jsou typograficke
    // interpunkcni znaky navrzene jako drobne, ne sipky - i pri stejnem
    // font-size vizualne mensi nez plne trojuhelniky ▲▼. Nahrazeno ◀▶
    // (U+25C0/25B6, "black left/right-pointing triangle") - stejna
    // glyfova rodina jako ▲▼, jen otocena, stejna vizualni vaha.
    var btnUp = mkBtn("tt-btn-up", "▲", "Pohled více shora");
    var btnLeft = mkBtn("tt-btn-left", "◀", "Otočit doleva");
    var btnDown = mkBtn("tt-btn-down", "▼", "Pohled více zdola");
    var btnRight = mkBtn("tt-btn-right", "▶", "Otočit doprava");
    if (elevations.length <= 1) { btnUp.style.display = "none"; btnDown.style.display = "none"; }
    // Hook pro cizi tlacitka (bot14 sem vklada "Zakreslit tento pohled") -
    // pointerdown uvnitr NEstartuje tazeni (viz onPointerDown).
    var actions = document.createElement("div");
    actions.className = "tt-actions";

    root.appendChild(sizer);
    root.appendChild(stage);
    root.appendChild(badge);
    root.appendChild(progress);
    root.appendChild(hint);
    root.appendChild(btns);
    root.appendChild(actions);
    container.appendChild(root);

    // ---------- rozmery / tier ----------
    function dpr() { return Math.max(1, Math.min(4, global.devicePixelRatio || 1)); }
    var maxVh = opts.maxViewportHeight == null ? 0.6 : Number(opts.maxViewportHeight);
    function applyMaxWidth() {
      // Nikdy nezobrazit snimek vetsi nez nativni rozliseni nejvyssiho tieru / DPR
      // + strop vysky 60vh (mobil: widget nesmi zabrat celou obrazovku, vedle
      // nej se musi dat scrollovat - touch-action:none uvnitr). Vyska plyne
      // ze sirky (sizer padding-top), proto strop pres max-width = vh/aspect.
      // Druhe prirazeni s min() stare prohlizece ignoruji -> zustane px.
      var px = Math.floor(maxTier / dpr());
      root.style.maxWidth = px + "px";
      if (maxVh > 0) root.style.maxWidth = "min(" + px + "px, " + (maxVh * 100 / aspect).toFixed(2) + "vh)";
    }
    applyMaxWidth();
    function rootWidth() { return root.clientWidth || container.clientWidth || 320; }
    function rootHeight() { return root.clientHeight || Math.round(rootWidth() * aspect); }
    // Nejmensi tier, ktery pokryje sirku kontejneru v zarizenych pixelech
    // (x zoom). Pri zoomu > 1 vzdy max tier (zadani).
    function tierFor(cssWidth, z) {
      if (z > 1.001) return maxTier;
      var need = cssWidth * dpr() * z;
      for (var i = 0; i < tiers.length; i++) if (tiers[i] >= need) return tiers[i];
      return maxTier;
    }
    function displayTier() { return tierFor(rootWidth(), zoom); }

    // ---------- cache + fronta nacitani ----------
    var cache = {}; // key -> {img, status, promise, resolve, reject, frame, tier, ei, az}
    var queue = []; // entries cekajici na start
    var active = 0;
    var MAX_PARALLEL = 6;

    function frameAt(ei, a) { return ringFrames[ei] ? ringFrames[ei][a] : null; }
    function urlFor(frame, tier) { return frame && frame.urls ? (frame.urls[String(tier)] || frame.urls[tier]) : null; }
    function keyOf(ei, a, tier) { return ei + "/" + a + "/" + tier; }

    function entryFor(ei, a, tier, kind) {
      var k = keyOf(ei, a, tier);
      var e = cache[k];
      if (e) return e;
      var frame = frameAt(ei, a);
      var url = urlFor(frame, tier);
      if (!url) return null;
      e = { key: k, ei: ei, az: a, tier: tier, url: url, frame: frame, status: "queued", img: null, kind: kind || "ring" };
      e.promise = new Promise(function (res, rej) { e.resolve = res; e.reject = rej; });
      e.promise.catch(function () {}); // neverbalizovat unhandled rejection - chyby resi volajici
      cache[k] = e;
      queue.push(e);
      stats.requested++;
      pump();
      return e;
    }

    function ringDist(a) { var d = Math.abs(mod(a - az, 360)); return Math.min(d, 360 - d); }
    function priority(e) {
      var same = e.ei === elIdx;
      if (same && e.az === az) return e.tier === displayTier() ? -1 : 0;
      var base = same ? 10 : 100 + Math.abs(e.ei - elIdx) * 20;
      return base + ringDist(e.az) / step;
    }

    function pump() {
      if (destroyed) return;
      while (active < MAX_PARALLEL && queue.length) {
        // Hi-res upgrady pro snimek, ktery uz neni aktualni, zahodit (uzivatel se posunul).
        for (var i = queue.length - 1; i >= 0; i--) {
          var q = queue[i];
          if (q.kind === "hires" && !(q.ei === elIdx && q.az === az)) {
            queue.splice(i, 1); delete cache[q.key]; q.status = "dropped"; q.reject(new Error("dropped"));
          }
        }
        if (!queue.length) break;
        var best = 0, bestP = Infinity;
        for (var j = 0; j < queue.length; j++) { var p = priority(queue[j]); if (p < bestP) { bestP = p; best = j; } }
        var e = queue.splice(best, 1)[0];
        startLoad(e);
      }
    }

    function startLoad(e) {
      active++;
      e.status = "loading";
      var img = new Image();
      img.decoding = "async";
      img.draggable = false;
      img.alt = "";
      e.img = img;
      var done = function (ok) {
        if (e.status !== "loading") return;
        active--;
        if (ok) {
          e.status = "ok"; stats.loaded++;
          if (e.frame && e.frame.bytes) stats.bytesByMeta += Number(e.frame.bytes[String(e.tier)] || 0);
          e.resolve(e);
        } else {
          e.status = "error"; stats.failed++;
          delete cache[e.key]; // pristi pokus muze projit (docasny vypadek)
          e.reject(new Error("load failed: " + e.url));
        }
        onLoadProgress();
        pump();
      };
      img.onload = function () {
        // decode() = zarucene dekodovany bitmap pred vlozenim do DOM (bez bliknuti);
        // stare Safari decode nema -> onload staci.
        if (typeof img.decode === "function") img.decode().then(function () { done(true); }, function () { done(true); });
        else done(true);
      };
      img.onerror = function () { done(false); };
      img.src = e.url;
    }

    // Entry z existujiciho <img> (SSR hero / vlastni hero img) - mimo frontu,
    // zadne dalsi stahovani; img se hned presune do stage, aby SSR obrazek
    // nebyl ani na okamzik dvakrat (v kontejneru + prazdny box widgetu).
    function adoptImage(ei, a, tier, img) {
      var k = keyOf(ei, a, tier);
      var e = cache[k];
      if (e && e.status === "ok") return e;
      var frame = frameAt(ei, a);
      e = { key: k, ei: ei, az: a, tier: tier, url: img.getAttribute("src"), frame: frame, status: "loading", img: img, kind: "hero" };
      heroImg = img;
      e.promise = new Promise(function (res, rej) { e.resolve = res; e.reject = rej; });
      e.promise.catch(function () {});
      cache[k] = e;
      stats.requested++;
      img.decoding = "async";
      img.draggable = false;
      if (stage.firstChild !== img) { while (stage.firstChild) stage.removeChild(stage.firstChild); stage.appendChild(img); }
      var finish = function (ok) {
        if (e.status !== "loading") return;
        if (ok) {
          // SSR hero muze mit srcset (bot14 SEO plan: 1024w+2048w) a prohlizec
          // si vybere mensi variantu - pak by se 1024 px obrazek tvaril jako
          // 2048 tier a hires by se nikdy nedotahl. Skutecny tier se proto
          // urci podle currentSrc (shoda s URL prstencoveho snimku daneho
          // tieru); naturalWidth je u srcset s "w" deskriptory prepoctena
          // hustotou (340 px misto 1024), takze slouzi jen jako zaloha bez
          // srcset. Zaznam se pak v cache prekliceuje.
          var real = tier, cs = img.currentSrc || "";
          var hit = cs ? findFrameByUrl(ringFrames, cs) : null;
          var csPath = null; if (cs) { try { csPath = new URL(cs, global.location.href).pathname; } catch (e) { csPath = cs; } }
          if (hit && hit.ei === ei && hit.az === a) real = hit.tier;
          else if (csPath && heroSrcsetW[csPath]) real = tierForWidth(heroSrcsetW[csPath]); // varianta z hero_srcset -> tier podle deklarovane sirky
          else if (img.getAttribute("srcset") && cs && !samePath(cs, heroUrl)) real = tiers[0]; // neznama varianta ze srcset -> radeji nejnizsi tier (hires se dotahne, nejhur jeden snimek navic)
          else if (!img.getAttribute("srcset") && img.naturalWidth > 0 && img.naturalWidth < tier) real = tierForWidth(img.naturalWidth);
          if (real !== tier) { delete cache[k]; tier = real; e.tier = real; e.key = k = keyOf(ei, a, real); if (!cache[k] || cache[k].status !== "ok") cache[k] = e; }
          if (img.currentSrc) e.url = img.currentSrc;
          e.status = "ok"; stats.loaded++; if (frame && frame.bytes) stats.bytesByMeta += Number(frame.bytes[String(tier)] || 0); e.resolve(e);
        }
        else { e.status = "error"; stats.failed++; delete cache[k]; e.reject(new Error("hero load failed: " + e.url)); }
        onLoadProgress();
      };
      var afterLoad = function () {
        if (typeof img.decode === "function") img.decode().then(function () { finish(true); }, function () { finish(img.naturalWidth > 0); });
        else finish(true);
      };
      if (img.complete && img.naturalWidth > 0) afterLoad();
      else if (img.complete && img.getAttribute("src")) finish(false); // complete + 0x0 = rozbity src
      else { img.addEventListener("load", afterLoad, { once: true }); img.addEventListener("error", function () { finish(false); }, { once: true }); }
      return e;
    }

    function ringProgress(ei, tier) {
      var tot = 0, ok = 0;
      for (var a in ringFrames[ei]) {
        tot++;
        var e = cache[keyOf(ei, Number(a), tier)];
        if (e && e.status === "ok") ok++;
      }
      return { total: tot, loaded: ok };
    }

    function onLoadProgress() {
      var pr = ringProgress(elIdx, minTier);
      var pending = ringRequested[elIdx] && pr.loaded < pr.total;
      if (pending) {
        progress.classList.remove("tt-hidden");
        progress.style.width = Math.round(pr.loaded / pr.total * 100) + "%";
      } else {
        progress.style.width = "100%";
        progress.classList.add("tt-hidden");
      }
      // po dokonceni vychoziho prstence -> sousedni (+1, pak -1) na pozadi
      if (!defaultRingDone) {
        var d = ringProgress(defaultIdx, minTier);
        if (ringRequested[defaultIdx] && d.loaded + failedIn(defaultIdx) >= d.total) {
          defaultRingDone = true;
          if (defaultIdx + 1 < elevations.length) requestRing(defaultIdx + 1);
          if (defaultIdx - 1 >= 0) requestRing(defaultIdx - 1);
        }
      }
    }
    function failedIn(ei) {
      // pocet snimku prstence, ktere se nepodarilo stahnout (aby se "dokonceni"
      // prstence nezaseklo na jednom rozbitem souboru)
      var n = 0;
      for (var a in ringFrames[ei]) { if (!cache[keyOf(ei, Number(a), minTier)]) n++; }
      return ringRequested[ei] ? n : 0;
    }

    function requestRing(ei) {
      if (ei < 0 || ei >= elevations.length || ringRequested[ei]) return;
      ringRequested[ei] = true;
      // sousede aktualniho azimutu prednostne - poradi resi priority() pri dequeue
      for (var a in ringFrames[ei]) entryFor(ei, Number(a), minTier, "ring");
      onLoadProgress();
    }
    function requestAllRings() {
      // nejdriv aktualni, pak podle vzdalenosti od nej
      var order = [];
      for (var i = 0; i < elevations.length; i++) order.push(i);
      order.sort(function (a, b) { return Math.abs(a - elIdx) - Math.abs(b - elIdx); });
      order.forEach(requestRing);
    }
    function ensureRingOnInteraction() {
      if (!ringRequested[elIdx]) requestRing(elIdx);
    }

    // ---------- zobrazeni ----------
    function bestLoaded(ei, a) {
      // preferuj display tier, pak cokoliv nacteneho (od nejvyssiho)
      var want = displayTier();
      var e = cache[keyOf(ei, a, want)];
      if (e && e.status === "ok") return e;
      for (var i = tiers.length - 1; i >= 0; i--) {
        e = cache[keyOf(ei, a, tiers[i])];
        if (e && e.status === "ok") return e;
      }
      return null;
    }

    function place(e) {
      if (destroyed) return;
      if (shown && shown.img === e.img) return;
      var old = shown ? shown.img : stage.firstChild;
      // uz dekodovany <img> - vlozeni je okamzite, zadne bliknuti. Hero <img
      // data-tt-hero> se z DOM NEODSTRANUJE, jen skryje: product.html (bot14)
      // na nem stavi layout pres `:has(#pdTurntable img[data-tt-hero])` a jeho
      // odstraneni pri prvnim otoceni by zuzilo sloupec uprostred gesta
      // (zmena sirky = zmena px/krok, skok layoutu). Skryty dekodovany <img>
      // nic nestoji.
      if (old !== e.img) {
        if (old && old !== heroImg && old.parentNode === stage) stage.removeChild(old);
        // bot16, 2026-09-13 (Robert primo, opakovane: "nezobrazi se zadna
        // fotka", i po fixu nearestAzInRing) - SKUTECNY crash root cause:
        // `heroImg` je NULL, dokud instance nikdy neprosla hero-adoption
        // vetvi (loadFirst() vyse) - to je PRESNE pripad, kdy initialAzimuth/
        // initialElevation (zachovany uhel z predchozi varianty) NESEDI s
        // touhle variantou vlastnim hero/default pohledem, tedy presne kdyz
        // zachovani uhlu opravdu neco dela. Na UPLNE PRVNI place() volani je
        // "old" (radek vyse) `stage.firstChild`, coz je na prazdnem stage
        // TAKY null - `old === heroImg` pak vyjde `null === null` -> true, a
        // `heroImg.hidden = true` spadne na TypeError. Vyjimka se stane
        // uvnitr `first.promise.then(...)` v loadFirst(), TAKZE se nikdy
        // nedobehne k `announceReady()` - `ready` uz nikdy nevyresi,
        // `pd-turntable-pending` (height:0;visibility:hidden) v product.html
        // se nikdy neodstrani - vysledek presne "zadna fotka", trvale.
        if (heroImg && old === heroImg) heroImg.hidden = true;
        if (e.img === heroImg) heroImg.hidden = false;
        if (stage.firstChild !== e.img) stage.insertBefore(e.img, stage.firstChild);
      }
      shown = { azimuth: e.az, elevation: elevations[e.ei], ei: e.ei, tier: e.tier, url: e.url, img: e.img, frame: e.frame };
      updateLabel();
      if (typeof opts.onFrameShown === "function") {
        try { opts.onFrameShown({ azimuth: e.az, angle: e.az, elevation: elevations[e.ei], tier: e.tier, url: e.url, img: e.img }); } catch (err) { /* callback volajiciho */ }
      }
      dispatchChange();
    }

    function dispatchChange() {
      if (destroyed || !shown || typeof CustomEvent !== "function") return;
      try { container.dispatchEvent(new CustomEvent("turntable:change", { detail: api.getCurrentFrame(), bubbles: true })); } catch (err) {}
    }

    function updateLabel() {
      var s = shown || {};
      var label = "Otočný náhled, azimut " + az + "°" + (elevations.length > 1 ? ", elevace " + elevations[elIdx] + "°" : "") +
        (zoom > 1 ? ", zoom " + zoom.toFixed(1) + "×" : "") + ". Šipkami otáčejte.";
      root.setAttribute("aria-label", label);
      badge.textContent = az + "°" + (elevations.length > 1 ? " / " + elevations[elIdx] + "°" : "") + (zoom > 1.001 ? " · " + zoom.toFixed(1) + "×" : "");
      if (s.tier && s.tier !== displayTier() && zoom <= 1) { /* hi-res dohrava, nic nezobrazujeme */ }
      btnUp.disabled = elIdx >= elevations.length - 1;
      btnDown.disabled = elIdx <= 0;
    }

    // Zobraz aktualni (az, elIdx): co je nactene hned, jinak vyzadej a
    // zustan na poslednim dobrem snimku.
    function render() {
      var e = bestLoaded(elIdx, az);
      if (e) { place(e); }
      else {
        var want = shown ? minTier : displayTier(); // prvni snimek vzdy v plnem tieru
        if (!ringRequested[elIdx] && shown) want = minTier;
        var ent = entryFor(elIdx, az, want, shown ? "ring" : "first");
        if (ent) {
          var myAz = az, myEi = elIdx;
          ent.promise.then(function (x) { if (!destroyed && myAz === az && myEi === elIdx) { place(x); scheduleHiRes(); } }, function () {});
        }
      }
      updateLabel();
      scheduleHiRes();
    }

    // Po ~150 ms klidu dohraj aktualni snimek v display tieru (2048 na
    // retina/mobilu, pri zoomu vzdy) a vymen bez bliknuti.
    function scheduleHiRes() {
      if (hiTimer) clearTimeout(hiTimer);
      hiTimer = setTimeout(upgradeHiRes, 150);
    }
    function upgradeHiRes() {
      hiTimer = null;
      if (destroyed || dragging) return;
      var want = displayTier();
      if (shown && shown.ei === elIdx && shown.azimuth === az && shown.tier >= want) return;
      var e = cache[keyOf(elIdx, az, want)];
      if (e && e.status === "ok") { place(e); return; }
      var ent = entryFor(elIdx, az, want, "hires");
      if (!ent) return;
      var myAz = az, myEi = elIdx;
      ent.promise.then(function (x) { if (!destroyed && myAz === az && myEi === elIdx) place(x); }, function () {});
    }

    function setViewInternal(newAz, newEi, source) {
      newAz = normAz(newAz);
      newEi = clamp(Math.round(newEi), 0, elevations.length - 1);
      var changed = newAz !== az || newEi !== elIdx;
      if (newEi !== elIdx) {
        // prvni zmena prstence -> vsechny prstence (podle vzdalenosti)
        if (!verticalUsed) { verticalUsed = true; requestAllRings(); }
        else requestRing(newEi);
      }
      az = newAz; elIdx = newEi;
      if (changed) {
        render();
        if (typeof opts.onViewChange === "function") { try { opts.onViewChange(az, elevations[elIdx], source); } catch (e) {} }
        if (typeof opts.onAngleChange === "function") { try { opts.onAngleChange(az, elevations[elIdx]); } catch (e) {} }
      } else {
        updateLabel();
      }
    }

    // ---------- zoom / pan ----------
    function applyTransform() {
      var W = rootWidth(), H = rootHeight();
      if (zoom <= 1.0001) { zoom = 1; panX = 0; panY = 0; }
      panX = clamp(panX, W - W * zoom, 0);
      panY = clamp(panY, H - H * zoom, 0);
      stage.style.transform = zoom === 1 ? "" : "translate3d(" + panX.toFixed(2) + "px," + panY.toFixed(2) + "px,0) scale(" + zoom.toFixed(4) + ")";
      root.classList.toggle("tt-zoomed", zoom > 1);
      updateLabel();
      dispatchChange();
    }
    function zoomAround(newZoom, cx, cy) {
      newZoom = clamp(newZoom, 1, maxZoom);
      if (cx == null) { cx = rootWidth() / 2; cy = rootHeight() / 2; }
      var f = newZoom / zoom;
      panX = cx - (cx - panX) * f;
      panY = cy - (cy - panY) * f;
      var prev = zoom;
      zoom = newZoom;
      applyTransform();
      if (zoom !== prev) scheduleHiRes(); // pri zoomu vzdy max tier
    }

    // ---------- interakce ----------
    var pointers = {}; // pointerId -> {x,y}
    var nPointers = 0;
    var dragging = false;
    var gesture = null; // {mode:'undecided'|'az'|'elev'|'pan'|'pinch'|'ended', startX, startY, startAz, startEi, startPanX, startPanY, lastX, lastY, moved, startDist, startZoom}
    var lastTap = { t: 0, x: 0, y: 0 };
    var MODE_V_PX = 40, MODE_RATIO = 1.5, DEAD_PX = 6;

    function firstInteraction() {
      if (!interacted) { interacted = true; hint.classList.add("tt-hidden"); }
      wheelArmed = true;
      ensureRingOnInteraction();
    }

    function localXY(ev) {
      var r = root.getBoundingClientRect();
      return { x: ev.clientX - r.left, y: ev.clientY - r.top };
    }
    function dist(a, b) { var dx = a.x - b.x, dy = a.y - b.y; return Math.sqrt(dx * dx + dy * dy); }

    function onPointerDown(ev) {
      if (ev.button != null && ev.button !== 0 && ev.pointerType === "mouse") return;
      if (ev.target && ev.target.closest && ev.target.closest(".tt-btn, .tt-actions")) return;
      firstInteraction();
      var p = localXY(ev);
      pointers[ev.pointerId] = p; nPointers++;
      try { root.setPointerCapture(ev.pointerId); } catch (e) {}
      if (nPointers === 1) {
        dragging = true;
        root.classList.add("tt-dragging");
        gesture = { mode: zoom > 1 ? "pan" : "undecided", startX: p.x, startY: p.y, startAz: az, startEi: elIdx, startWidth: rootWidth(),
          startPanX: panX, startPanY: panY, lastX: p.x, lastY: p.y, moved: 0, pointerType: ev.pointerType };
        if (hiTimer) { clearTimeout(hiTimer); hiTimer = null; }
      } else if (nPointers === 2 && gesture) {
        var ids = Object.keys(pointers);
        var a = pointers[ids[0]], b = pointers[ids[1]];
        gesture.mode = "pinch";
        gesture.startDist = Math.max(10, dist(a, b));
        gesture.startZoom = zoom;
        gesture.lastMid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      }
      ev.preventDefault();
    }

    function onPointerMove(ev) {
      if (!gesture || !pointers[ev.pointerId]) return;
      var p = localXY(ev);
      pointers[ev.pointerId] = p;
      if (gesture.mode === "pinch") {
        var ids = Object.keys(pointers);
        if (ids.length < 2) return;
        var a = pointers[ids[0]], b = pointers[ids[1]];
        var mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
        var nz = gesture.startZoom * dist(a, b) / gesture.startDist;
        panX += mid.x - gesture.lastMid.x; panY += mid.y - gesture.lastMid.y;
        gesture.lastMid = mid;
        zoomAround(nz, mid.x, mid.y);
        gesture.moved = 99;
        return;
      }
      if (gesture.mode === "ended") return;
      var dx = p.x - gesture.startX, dy = p.y - gesture.startY;
      gesture.moved = Math.max(gesture.moved, Math.abs(dx), Math.abs(dy));
      if (gesture.mode === "pan") {
        panX = gesture.startPanX + dx; panY = gesture.startPanY + dy;
        applyTransform();
        return;
      }
      if (gesture.mode === "undecided") {
        if (Math.abs(dx) < DEAD_PX && Math.abs(dy) < DEAD_PX) return;
        // Svisly zamer: |dy| > 1.5*|dx|. Rezim "elev" se ale zamkne az kdyz
        // svisly posun prekroci 40 px; do te doby drzime "undecided", aby
        // kratke svisle cuknuti neroztocilo azimut a naopak.
        if (Math.abs(dy) > Math.abs(dx) * MODE_RATIO) {
          if (Math.abs(dy) > MODE_V_PX) gesture.mode = "elev"; else return;
        } else {
          gesture.mode = "az";
        }
      }
      if (gesture.mode === "az") {
        var pxPerStep = Math.max(4, (gesture.startWidth || rootWidth()) / nAz); // cely prutah pres sirku = 1 otocka; sirka z pocatku gesta (kdyby se layout behem tahu zmenil)
        var steps = Math.round(dx / pxPerStep) * dragDir;
        setViewInternal(gesture.startAz + steps * step, elIdx, "drag");
      } else if (gesture.mode === "elev") {
        // kazdych 40 px svisleho tahu = jeden prstenec; tah dolu = pohled vic
        // shora (jako OrbitControls - "stahuju vrsek objektu k sobe")
        var rsteps = Math.round(dy / MODE_V_PX);
        setViewInternal(az, gesture.startEi + rsteps, "drag");
      }
    }

    function onPointerUp(ev) {
      if (!pointers[ev.pointerId]) return;
      var p = pointers[ev.pointerId];
      delete pointers[ev.pointerId]; nPointers = Math.max(0, nPointers - 1);
      try { root.releasePointerCapture(ev.pointerId); } catch (e) {}
      if (gesture && gesture.mode === "pinch") {
        gesture.mode = "ended"; // po pinchi uz zbyly prst nic nedela (jinak by skocil pan/azimut)
      }
      if (nPointers > 0) return;
      var g = gesture; gesture = null;
      dragging = false;
      root.classList.remove("tt-dragging");
      // tap/klik bez pohybu -> dvojtap/dvojklik = toggle zoom 1x/2x
      if (g && g.moved < 8 && g.mode !== "pinch" && g.mode !== "ended" && ev.type === "pointerup") {
        var now = Date.now();
        if (now - lastTap.t < 320 && Math.abs(p.x - lastTap.x) < 25 && Math.abs(p.y - lastTap.y) < 25) {
          lastTap.t = 0;
          zoomAround(zoom > 1 ? 1 : maxZoom, p.x, p.y);
        } else {
          lastTap = { t: now, x: p.x, y: p.y };
        }
      }
      scheduleHiRes();
    }

    function onKeyDown(ev) {
      var handled = true;
      switch (ev.key) {
        case "ArrowLeft": firstInteraction(); setViewInternal(az - step, elIdx, "key"); break;
        case "ArrowRight": firstInteraction(); setViewInternal(az + step, elIdx, "key"); break;
        case "ArrowUp": firstInteraction(); setViewInternal(az, elIdx + 1, "key"); break;
        case "ArrowDown": firstInteraction(); setViewInternal(az, elIdx - 1, "key"); break;
        case "+": case "=": zoomAround(zoom + 0.25); break;
        case "-": case "_": zoomAround(zoom - 0.25); break;
        case "0": zoomAround(1); break;
        case "Escape": if (zoom > 1) zoomAround(1); else handled = false; break;
        default: handled = false;
      }
      if (handled) ev.preventDefault();
    }

    function onWheel(ev) {
      if (ev.shiftKey) {
        // Shift+kolecko = prstenec (na trackpadech chodi horizontalni delta)
        var d = Math.abs(ev.deltaY) >= Math.abs(ev.deltaX) ? ev.deltaY : ev.deltaX;
        if (d === 0) return;
        firstInteraction();
        setViewInternal(az, elIdx + (d > 0 ? 1 : -1), "wheel");
        ev.preventDefault();
        return;
      }
      // Kolecko = zoom, ale az kdyz uzivatel do widgetu klikl/focusnul -
      // jinak by widget kradl scroll stranky pri kazdem prujezdu mysi.
      if (!wheelArmed && document.activeElement !== root) return;
      wheelArmed = true;
      var p = localXY(ev);
      var factor = Math.exp(-ev.deltaY * (ev.deltaMode === 1 ? 0.05 : 0.0025));
      var newZoom = clamp(zoom * factor, 1, maxZoom);
      // Zivy nalez (bot3 2026-09-02): jednou "armovane" kolecko krade
      // scroll stranky NATRVALO, i kdyz je zoom uz na minimu (1) a dalsi
      // otoceni kolecka dolu by stejne nic nezmenilo - uzivatel pak
      // nemuze prejet strankou pres widget. PreventDefault jen kdyz je
      // zoom uz > 1 (jasne zoomovano, kolecko dava smysl zachytit), nebo
      // kdyz tenhle konkretni pohyb zoom skutecne zmeni.
      if (zoom <= 1 && newZoom <= 1) return;
      zoomAround(newZoom, p.x, p.y);
      ev.preventDefault();
    }

    function onFocus() { wheelArmed = true; }

    btnLeft.addEventListener("click", function () { firstInteraction(); setViewInternal(az - step, elIdx, "button"); });
    btnRight.addEventListener("click", function () { firstInteraction(); setViewInternal(az + step, elIdx, "button"); });
    btnUp.addEventListener("click", function () { firstInteraction(); setViewInternal(az, elIdx + 1, "button"); });
    btnDown.addEventListener("click", function () { firstInteraction(); setViewInternal(az, elIdx - 1, "button"); });

    root.addEventListener("pointerdown", onPointerDown);
    root.addEventListener("pointermove", onPointerMove);
    root.addEventListener("pointerup", onPointerUp);
    root.addEventListener("pointercancel", onPointerUp);
    root.addEventListener("lostpointercapture", function (ev) { if (pointers[ev.pointerId]) onPointerUp(ev); });
    root.addEventListener("keydown", onKeyDown);
    root.addEventListener("wheel", onWheel, { passive: false });
    root.addEventListener("focus", onFocus);
    root.addEventListener("dragstart", function (ev) { ev.preventDefault(); });
    root.addEventListener("contextmenu", function (ev) { if (gesture) ev.preventDefault(); });
    // gesturestart (Safari) - zabranit nativnimu pinch-zoomu stranky nad widgetem
    root.addEventListener("gesturestart", function (ev) { ev.preventDefault(); });

    // ---------- resize ----------
    var lastTier = displayTier();
    var ro = null;
    function onResize() {
      applyMaxWidth();
      applyTransform();
      var t = displayTier();
      if (t !== lastTier) { lastTier = t; scheduleHiRes(); }
    }
    if (global.ResizeObserver) { ro = new ResizeObserver(onResize); ro.observe(root); }
    global.addEventListener("resize", onResize);
    global.addEventListener("orientationchange", onResize);

    // ---------- start ----------
    var readyResolve, readyReject;
    var ready = new Promise(function (res, rej) { readyResolve = res; readyReject = rej; });
    ready.catch(function () {});
    function announceReady() {
      readyResolve(api);
      if (typeof CustomEvent === "function") { try { container.dispatchEvent(new CustomEvent("turntable:ready", { detail: api, bubbles: true })); } catch (err) {} }
      // LCP: prstenec nikdy pred window.load + idle; mobil az pri interakci.
      if (isDesktop) afterWindowLoad(function () { requestIdle(function () { if (!destroyed) requestRing(defaultIdx); }, 4000); });
    }
    (function loadFirst() {
      var first = null;
      var heroIsInitial = heroPos.ei === elIdx && heroPos.az === az;
      if (heroIsInitial && (ssrImg || heroUrl)) {
        var heroTier = tiers.indexOf(heroPos.tier) >= 0 ? heroPos.tier : maxTier;
        var img = ssrImg;
        if (!img) {
          // zadne SSR - vytvorit hero <img> stejne, jak by ho vyrenderoval server
          img = new Image();
          img.setAttribute("data-tt-hero", "");
          img.setAttribute("fetchpriority", "high");
          img.width = Number(meta.hero_width) || heroTier;
          img.height = Number(meta.hero_height) || Math.round(heroTier * aspect);
          img.alt = opts.alt || "";
          img.src = heroUrl;
        } else if (!img.hasAttribute("data-tt-hero")) {
          img.setAttribute("data-tt-hero", "");
        }
        first = adoptImage(heroPos.ei, heroPos.az, heroTier, img);
      } else if (heroUrl) {
        // bot16, 2026-09-13 (Robert, po opravenem crashi vyse: "zobrazuji
        // se ale poloviční velikosti") - kdyz PRVNI zobrazeny snimek NENI
        // hero (zachovany uhel z predchozi varianty se lisi od hero
        // pohledu TETO varianty - presne pripad, kdy zachovani uhlu neco
        // dela), vetev vyse se vubec nespusti a `<img data-tt-hero>` v DOM
        // nikdy nevznikne. product.html na jeho PRITOMNOSTI (ne na tom,
        // jestli je zrovna zobrazeny) stavi CSS `.pd-layout:has(#pdTurntable
        // img[data-tt-hero])` - sirsi sloupec pro ctvercovy widget (viz
        // komentar tamtez). Bez neho `:has()` neplati, sloupec spadne na
        // uzsi vychozi 340px sirku a widget (porad spravne width:100% svych
        // rodicu) se tak jevi jako "poloviční velikost" - neni to bug ve
        // velikosti OBRAZKU, je to bug v sirce SLOUPCE, ktery ho obklopuje.
        // Reseni: skryty "fantomovy" hero <img>, cist jako layout kotva -
        // nikdy se nezobrazi (neni v `cache`, `place()` s nim nepracuje),
        // jen svou pritomnosti splni CSS selektor. heroImg se nastavuje ze
        // stejneho duvodu jako v vetvi vyse (dokumentovany ucel promenne).
        // Prida se do `root` (ne primo do `container`) - `destroy()` nize
        // uklizi jen `root`, pridani do `container` by fantoma pri kazdem
        // dalsim prepnuti varianty osirelo (uniklo by z DOM az pri pristim
        // `holder.innerHTML=""` v product.html, ne hned pri destroy()).
        var phantomHero = new Image();
        phantomHero.setAttribute("data-tt-hero", "");
        phantomHero.hidden = true;
        // bot16, 2026-09-13 (Robert primo, screenshot: druhy, plne
        // viditelny obrazek pod widgetem) - `hidden` atribut SAM O SOBE
        // tady nestaci. CSS ma jen `.tt-stage img[hidden]{display:none}`
        // (viz vyse) - cili jen na obrazky UVNITR `.tt-stage`, ale fantom
        // se schvalne pripojuje do `root` (viz komentar par radku vys,
        // proc ne do `stage`), takze na nej tohle pravidlo nedosahne a
        // fantom se renderuje jako normalni obrazek v tocich dokumentu
        // (`.tt-root` nema pevnou vysku, jen `overflow:hidden` - bez
        // `display:none` se prosti box kolem nej proste zvetsi, aby se
        // vesel). Explicitni inline `display:none` je nezavisly na
        // jakekoli CSS specificite/scope a plati vzdy.
        phantomHero.style.display = "none";
        phantomHero.alt = opts.alt || "";
        phantomHero.src = heroUrl;
        root.appendChild(phantomHero);
        heroImg = phantomHero;
      }
      if (!first) first = entryFor(elIdx, az, displayTier(), "first");
      if (!first) { readyReject(new Error("Turntable: prvni snimek nema URL")); return; }
      first.promise.then(function (e) {
        if (destroyed) return;
        place(e);
        announceReady();
      }, function () {
        // plny tier selhal -> zkus nejnizsi, jinak reject (stranka zustane jak byla)
        var fb = displayTier() !== minTier ? entryFor(elIdx, az, minTier, "first") : null;
        if (!fb) { readyReject(new Error("Turntable: prvni snimek nejde nacist")); return; }
        fb.promise.then(function (e) { if (destroyed) return; place(e); announceReady(); },
          function () { readyReject(new Error("Turntable: prvni snimek nejde nacist")); });
      });
    })();
    updateLabel();

    // Pocka, az je pro AKTUALNI az/el nacteny, dekodovany a zobrazeny snimek
    // v nejvyssim tieru (2048). Kdyz se mezitim pohled zmeni, zkusi to znovu
    // pro novy pohled (bot14 tak vzdy dostane podklad zakresu = to, co vidi).
    function ensureHiRes() {
      return new Promise(function (resolve, reject) {
        (function attempt() {
          if (destroyed) { reject(new Error("destroyed")); return; }
          var myAz = az, myEi = elIdx;
          if (shown && shown.ei === myEi && shown.azimuth === myAz && shown.tier === maxTier) { resolve(api.getCurrentFrame()); return; }
          var e = cache[keyOf(myEi, myAz, maxTier)];
          if (e && e.status === "ok") { place(e); resolve(api.getCurrentFrame()); return; }
          var ent = entryFor(myEi, myAz, maxTier, "hires-forced"); // "forced" = pump ho nezahodi
          if (!ent) { reject(new Error("Turntable: snimek nema URL pro tier " + maxTier)); return; }
          ent.promise.then(function (x) {
            if (myAz === az && myEi === elIdx) { place(x); resolve(api.getCurrentFrame()); } else attempt();
          }, function (err) {
            if (myAz === az && myEi === elIdx) reject(err); else attempt();
          });
        })();
      });
    }

    // ---------- verejne API ----------
    var api = {
      ready: ready,
      el: root,
      actionsEl: actions,
      ensureHiRes: ensureHiRes,
      goTo: function (a, el) { api.setView(a, el); return ensureHiRes(); },
      getAngle: function () { return az; },
      getAzimuth: function () { return az; },
      getElevation: function () { return elevations[elIdx]; },
      getElevations: function () { return elevations.slice(); },
      getStep: function () { return step; },
      setAngle: function (a) { setViewInternal(a, elIdx, "api"); return api; },
      setView: function (a, el) {
        var ei = el == null ? elIdx : elevations.indexOf(Number(el));
        if (ei < 0) { // nejblizsi dostupna elevace
          var best = 0, bd = Infinity;
          elevations.forEach(function (v, i) { var d = Math.abs(v - Number(el)); if (d < bd) { bd = d; best = i; } });
          ei = best;
        }
        setViewInternal(a == null ? az : a, ei, "api");
        return api;
      },
      getCurrentFrame: function () {
        if (!shown) return null;
        var W = rootWidth(), H = rootHeight();
        // azimuth/elevation/url = AKTUALNI stav (cilovy snimek, url vzdy max
        // tier); displayedUrl/tier/img = co je prave fyzicky videt (muze byt
        // 1024 behem otaceni, nebo predchozi snimek, kdyz cilovy jeste neni).
        var curFrame = frameAt(elIdx, az) || shown.frame;
        var hiUrl = urlFor(curFrame, maxTier) || shown.url;
        return {
          azimuth: az, azimuth_deg: az, angle: az, elevation: elevations[elIdx], elevation_deg: elevations[elIdx],
          url: hiUrl, width: maxTier, height: Math.round(maxTier * aspect),
          tier: shown.tier, displayedUrl: shown.url, displayedAzimuth: shown.azimuth, displayedElevation: shown.elevation,
          urls: curFrame ? curFrame.urls : null,
          img: shown.img, naturalWidth: shown.img.naturalWidth, naturalHeight: shown.img.naturalHeight,
          zoom: zoom, panX: panX, panY: panY,
          // normalizovany pan = zlomek snimku (0..1) v levem hornim rohu vyrezu
          pan: [zoom > 1 ? -panX / (W * zoom) : 0, zoom > 1 ? -panY / (H * zoom) : 0],
          displayTier: displayTier(),
        };
      },
      getZoom: function () { return zoom; },
      setZoom: function (z, cx, cy) { zoomAround(z, cx, cy); return api; },
      resetZoom: function () { zoomAround(1); return api; },
      getTier: function () { return displayTier(); },
      getStats: function () {
        var rp = {};
        elevations.forEach(function (v, i) { rp[v] = ringProgress(i, minTier); });
        return { requested: stats.requested, loaded: stats.loaded, failed: stats.failed, bytesByMeta: stats.bytesByMeta,
          displayTier: displayTier(), minTier: minTier, maxTier: maxTier, dpr: dpr(), rootWidth: rootWidth(), isDesktop: isDesktop, rings: rp };
      },
      preloadRing: function (el) { var ei = el == null ? elIdx : elevations.indexOf(Number(el)); if (ei >= 0) requestRing(ei); return api; },
      preloadAll: function () { requestAllRings(); return api; },
      destroy: function () {
        if (destroyed) return;
        destroyed = true;
        if (hiTimer) clearTimeout(hiTimer);
        if (ro) ro.disconnect();
        global.removeEventListener("resize", onResize);
        global.removeEventListener("orientationchange", onResize);
        queue.forEach(function (e) { e.status = "dropped"; e.reject(new Error("destroyed")); });
        queue = [];
        for (var k in cache) { var e = cache[k]; if (e.img && e.status === "loading") { e.img.onload = e.img.onerror = null; e.img.src = ""; } }
        cache = {};
        if (root.parentNode) root.parentNode.removeChild(root);
        shown = null;
      },
    };
    return api;
  }

  global.Turntable = { mount: mount, version: "1.0.0" };
})(typeof window !== "undefined" ? window : this);
