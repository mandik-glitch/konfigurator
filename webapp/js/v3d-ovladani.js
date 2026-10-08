/*
 * v3d-ovladani.js - OBECNE ovladani primo ve 3D pohledu (bot8, 2026-10-03). Zadani: docs/OVLADANI_3D.md.
 *
 * Generator (server) jen POPISE, co se ve 3D da chytit a co nabidnout (`vodici.ovladani` = {deska, casti[], tahy[]}), tenhle modul to vykresli
 * a zpracuje. V modulu NENI zadny kod pro konkretni produkt (stul, vozik, stojan...): novy generator dostane totez ovladani tim, ze vrati stejny popis.
 *
 *   var ov = V3DOvladani.create({
 *     stage,                                   // prvek s platnem prohlizece (V3D.mount(stage, ...)); jeho <canvas> modul najde sam
 *     overlay,                                 // prvek NAD nim (position:absolute; inset:0; pointer-events:none) - sem se vlozi vrstva uchytu
 *     getParams(),                             // aktualni parametry stranky {nazev: hodnota} (null = vychozi)
 *     applyPatch(patch, {live, cancel, source}),   // stranka slouci patch do parametru, prekresli ovladace a naplanuje obnovu modelu
 *     dragState(on, tah, {live}),              // true na zacatku / false na konci tazeni; live = vrcholy se hybou primo v modelu (stranka NEvola server do pusteni)
 *     onLink(params[]),                        // co ma stranka v panelu zvyraznit (parametry casti / uchytu, ktere mys prave ukazuje)
 *     focusParam(param),                       // polozka nabidky "fokus": posunout panel k ovladaci a zablikat
 *     handleIds: { "id_tahu": "id_prvku" },    // volitelne: pevna DOM id uchytu (stranka stolu: stredni_noha -> midHandle)
 *     texts: {...}                             // volitelne: prepis ceskych textu (TEXTS)
 *   });
 *   V3D.mount(stage, {..., plugins: [ov.plugin]})   // ZIVE tazeni: plugin dostane scenu nactenych modelu (ctx.model) - viz "ZIVE tazeni" nize
 *   ov.setViewer(viewer)                       // viewer3d (cameraInfo(), onCamera(cb)); null = odpojit
 *   ov.setDescription(ovladani | null)         // po KAZDE obnove modelu (pri tazeni se popis pozdrzi az na jeho konec)
 *   ov.hoverParam(param | null)                // opacny smer: mys v panelu na ovladaci -> zvyrazneni casti a uchytu ve 3D
 *   ov.debug() ; ov.destroy()
 *
 * Co modul umi: najeti na cast = obrys + popisek + zvyrazneni radku v panelu; pravé tlacitko (dotyk: dlouhy stisk 450 ms) = nabidka casti;
 * uchyty ("tahy") typu osa / rovina s drag and drop (mys, dotyk, pero), pri tazeni stitek s NOVOU hodnotou, ROZDILEM proti zacatku a radky `mereni`;
 * zakazana pasma (zastaveni 10 mm pred prekazkou), Esc vrati puvodni hodnotu; sipky na focusovanem uchytu posouvaji o `krok`.
 */
(function (global) {
  "use strict";

  var VERSION = "1.2.0";
  var SVGNS = "http://www.w3.org/2000/svg";
  var TEXTS = {
    menuHint: "pravé tlačítko = nabídka",
    obstacle: "překážka – zastaveno, mezera {n} mm",
    toObstacle: "do překážky {n} mm",
    atMin: "minimum", atMax: "maximum", atLimit: "na mezi",
    esc: "Esc vrátí původní hodnotu",
    unit: "mm"
  };

  var CSS = [
    ".v3do-layer{position:absolute;left:0;top:0;overflow:hidden;pointer-events:none;z-index:6;-webkit-tap-highlight-color:transparent}",
    ".v3do-svg{position:absolute;left:0;top:0;overflow:visible;pointer-events:none}",
    ".v3do-svg .halo{fill:none;stroke:rgba(16,20,26,.62);stroke-width:5;stroke-linejoin:round;stroke-linecap:round}",
    ".v3do-svg .line{fill:none;stroke:#ffd34d;stroke-width:2.2;stroke-linejoin:round;stroke-linecap:round}",
    ".v3do-svg .fill{fill:rgba(255,211,77,.14);stroke:none}",
    ".v3do-svg .edge{fill:none;stroke:rgba(255,211,77,.6);stroke-width:1;stroke-linecap:round}",
    ".v3do-svg .rel .line{stroke:#7fc4ff}.v3do-svg .rel .fill{fill:rgba(127,196,255,.14)}.v3do-svg .rel .edge{stroke:rgba(127,196,255,.6)}",
    ".v3do-lbl{position:absolute;left:0;top:0;display:none;background:rgba(24,28,34,.93);color:#fff;font:600 12px/1.3 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;",
    "padding:4px 9px;border-radius:7px;white-space:nowrap;pointer-events:none;box-shadow:0 2px 8px rgba(0,0,0,.4);z-index:2}",
    ".v3do-lbl small{display:block;font-weight:400;font-size:10.5px;opacity:.72}",
    // uchyt = pruhledna CHYTACI plocha (mys 28 px, dotyk 44 px), viditelny je jen maly kruh (::after, --vis): Robert "zmensi ty ikony protazeni" + "je to pres cely mobil"
    ".v3do-h{position:absolute;left:0;top:0;width:28px;height:28px;margin:-14px 0 0 -14px;border-radius:50%;background:none;color:#fff;--vis:20px;",
    "display:flex;align-items:center;justify-content:center;pointer-events:auto;cursor:grab;touch-action:none;user-select:none;-webkit-user-select:none;outline:none;will-change:transform}",
    ".v3do-h::after{content:\"\";position:absolute;left:50%;top:50%;width:var(--vis);height:var(--vis);margin:calc(var(--vis) / -2) 0 0 calc(var(--vis) / -2);border-radius:50%;",
    "background:rgba(255,122,61,.94);box-shadow:0 0 0 1.5px rgba(255,255,255,.6),0 2px 7px rgba(0,0,0,.45);z-index:0}",
    ".v3do-h:hover::after{background:#ff8a52}",
    ".v3do-h:focus-visible::after{box-shadow:0 0 0 3px #fff,0 0 0 6px #2c7be5}",
    "@media (pointer:coarse){.v3do-h{width:44px;height:44px;margin:-22px 0 0 -22px;--vis:16px}.v3do-h .cap{margin-top:-6px}}",
    ".v3do-h .ico{position:relative;z-index:1;display:block;width:calc(var(--vis) * .64);height:calc(var(--vis) * .64);pointer-events:none}",
    ".v3do-h .ico svg{display:block;width:100%;height:100%;overflow:visible}",
    ".v3do-h .cap{position:absolute;top:100%;left:50%;margin-top:5px;transform:translateX(-50%);white-space:nowrap;font:600 10.5px/1.2 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;",
    "background:rgba(30,34,40,.9);color:#fff;padding:2px 8px;border-radius:10px;pointer-events:none;opacity:0;transition:opacity .12s}",
    ".v3do-h:hover .cap,.v3do-h.rel .cap,.v3do-h:focus-visible .cap{opacity:1}",
    ".v3do-h.rel::after{box-shadow:0 0 0 3px #ffd34d,0 3px 10px rgba(0,0,0,.45)}",
    ".v3do-h.drag{cursor:grabbing;z-index:3}",
    ".v3do-h.drag::after{background:#ff5a1a;box-shadow:0 0 0 5px rgba(255,255,255,.85),0 6px 18px rgba(0,0,0,.55)}",
    ".v3do-h.drag .cap{opacity:0}",
    ".v3do-h.stop::after{background:#d93a3a}",
    ".v3do-layer.dragging .v3do-h:not(.drag){opacity:.25;pointer-events:none}",
    ".v3do-tip{position:absolute;left:0;top:0;display:none;min-width:150px;max-width:270px;background:rgba(22,26,32,.95);color:#fff;border:1px solid rgba(255,255,255,.18);",
    "border-radius:10px;padding:7px 11px 8px;font:12px/1.35 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;pointer-events:none;z-index:4;box-shadow:0 6px 20px rgba(0,0,0,.5)}",
    ".v3do-tip .t{font-weight:700;margin-bottom:3px}",
    ".v3do-tip .r{display:flex;align-items:baseline;gap:8px;white-space:nowrap}",
    ".v3do-tip .l{color:#b6bec9;flex:1}",
    ".v3do-tip .v{font-weight:700;font-size:15px;font-variant-numeric:tabular-nums}",
    ".v3do-tip .dl{min-width:64px;text-align:right;font-weight:700;font-variant-numeric:tabular-nums;color:#9fd0ff}",
    ".v3do-tip .dl.neg{color:#ffb38a}.v3do-tip .dl.zero{color:#8b93a1;font-weight:400}",
    ".v3do-tip .st{margin-top:4px;font-size:11.5px;color:#e0a870}",
    ".v3do-tip .st.bad{color:#ff7b7b;font-weight:700}",
    ".v3do-tip .esc{margin-top:4px;font-size:10.5px;color:#8b93a1}",
    "@media (pointer:coarse){.v3do-tip .esc{display:none}}",
    ".v3do-menu{position:fixed;z-index:60;min-width:210px;max-width:min(330px,calc(100vw - 16px));max-height:calc(100vh - 16px);overflow:auto;background:#242830;color:#e8eaed;",
    "border:1px solid #3d4452;border-radius:10px;padding:5px;box-shadow:0 10px 30px rgba(0,0,0,.55);font:13px/1.3 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}",
    ".v3do-menu:focus{outline:none}.v3do-menu .mh{padding:6px 10px 5px;font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:#8b93a1}",
    ".v3do-menu .mi{display:block;width:100%;text-align:left;background:none;border:0;color:inherit;font:inherit;padding:8px 10px;border-radius:7px;cursor:pointer}",
    ".v3do-menu .mi:hover,.v3do-menu .mi:focus{background:#35507a;outline:none}",
    ".v3do-menu .mi.dis{color:#7b8392;cursor:default}.v3do-menu .mi.dis:hover{background:none}",
    ".v3do-menu .mi small{display:block;font-size:11px;color:#c58b5a;margin-top:2px}",
    "@media (pointer:coarse){.v3do-menu .mi{padding:12px;min-height:44px}}",
    ".v3do-lnk{box-shadow:0 0 0 2px rgba(255,211,77,.75);background-color:rgba(255,211,77,.12)!important;border-radius:6px}",
    "@keyframes v3do-flash{0%{background-color:rgba(255,211,77,.55)}100%{background-color:rgba(255,211,77,0)}}",
    ".v3do-flash{animation:v3do-flash 1.2s ease-out 1;border-radius:6px}",
    "@media (prefers-reduced-motion:reduce){.v3do-flash{animation:none;background-color:rgba(255,211,77,.3)}}"
  ].join("");

  function injectCss() {
    if (document.getElementById("v3do-css")) return;
    var s = document.createElement("style");
    s.id = "v3do-css"; s.textContent = CSS;
    document.head.appendChild(s);
  }

  // ---------------------------------------------------------------------------------------------------------------
  // matematika (mm, souradnice GLB: X hloubka dozadu, Y nahoru, Z sirka doprava)
  // ---------------------------------------------------------------------------------------------------------------
  function vec(a) { return { x: +a[0], y: +a[1], z: +a[2] }; }
  function dot(a, b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
  function sub(a, b) { return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z }; }
  function cross(a, b) { return { x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x }; }
  function norm(a) { var l = Math.sqrt(dot(a, a)) || 1; return { x: a.x / l, y: a.y / l, z: a.z / l }; }
  function addk(a, b, k) { return { x: a.x + b.x * k, y: a.y + b.y * k, z: a.z + b.z * k }; }
  function num(v, fb) { return typeof v === "number" && isFinite(v) ? v : fb; }

  // kamera z viewer.cameraInfo() ({pos, target, screenUp|up, fov (svisly, stupne), aspect}) -> zakladni vektory
  function camFrom(c) {
    if (!c || !c.pos || !c.target) return null;
    var pos = vec(c.pos), f = norm(sub(vec(c.target), pos)), up = vec(c.screenUp || c.up || [0, 1, 0]);
    var r = norm(cross(f, up)), u = cross(r, f);
    return { pos: pos, f: f, r: r, u: u, tan: Math.tan((c.fov || 45) * Math.PI / 360), aspect: c.aspect || 1 };
  }
  // 3D bod -> pixely platna (w x h); null = za kamerou
  function project(P, cam, w, h) {
    var v = sub(P, cam.pos), z = dot(v, cam.f);
    if (z <= 1) return null;
    var nx = dot(v, cam.r) / (z * cam.tan * cam.aspect), ny = dot(v, cam.u) / (z * cam.tan);
    return { x: (nx + 1) / 2 * w, y: (1 - ny) / 2 * h };
  }
  // paprsek z kamery pres pixel platna (px, py)
  function rayThrough(cam, px, py, w, h) {
    var nx = px / w * 2 - 1, ny = 1 - py / h * 2;
    return { o: cam.pos, d: norm(addk(addk(cam.f, cam.r, nx * cam.tan * cam.aspect), cam.u, ny * cam.tan)) };
  }
  // vstup paprsku do kvadru [lo, hi] (null = mimo); je-li pocatek uvnitr, t = 0
  function rayBox(o, d, lo, hi) {
    var tmin = -Infinity, tmax = Infinity, oa = [o.x, o.y, o.z], da = [d.x, d.y, d.z];
    for (var i = 0; i < 3; i++) {
      if (Math.abs(da[i]) < 1e-12) { if (oa[i] < lo[i] || oa[i] > hi[i]) return null; continue; }
      var t1 = (lo[i] - oa[i]) / da[i], t2 = (hi[i] - oa[i]) / da[i];
      if (t1 > t2) { var tmp = t1; t1 = t2; t2 = tmp; }
      if (t1 > tmin) tmin = t1;
      if (t2 < tmax) tmax = t2;
      if (tmin > tmax) return null;
    }
    return tmax < 0 ? null : Math.max(tmin, 0);
  }
  function rayPlaneY(o, d, y) {
    if (Math.abs(d.y) < 1e-6) return null;
    var t = (y - o.y) / d.y;
    return t > 0 ? { x: o.x + d.x * t, y: y, z: o.z + d.z * t } : null;
  }
  // parametr s bodu primky B + s*A (A jednotkova) nejblizsiho paprsku; null = osa je (temer) rovnobezna s pohledem
  function rayAxis(o, d, B, A) {
    var w0 = sub(B, o), b = dot(A, d), den = 1 - b * b;
    if (den < 1e-3) return null;
    return (b * dot(d, w0) - dot(A, w0)) / den;
  }
  // obalka (konvexni) bodu {x, y}
  function hull(pts) {
    pts = pts.slice().sort(function (p, q) { return p.x - q.x || p.y - q.y; });
    var n = pts.length, i;
    if (n < 3) return pts;
    function cr(o, a, b) { return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x); }
    var lo = [], up = [];
    for (i = 0; i < n; i++) { while (lo.length >= 2 && cr(lo[lo.length - 2], lo[lo.length - 1], pts[i]) <= 0) lo.pop(); lo.push(pts[i]); }
    for (i = n - 1; i >= 0; i--) { while (up.length >= 2 && cr(up[up.length - 2], up[up.length - 1], pts[i]) <= 0) up.pop(); up.push(pts[i]); }
    up.pop(); lo.pop();
    return lo.concat(up);
  }

  // ---------------------------------------------------------------------------------------------------------------
  // hodnota tazeneho uchytu (cista funkce - testuje se zvlast)
  // ---------------------------------------------------------------------------------------------------------------
  function latticeRound(v, base, krok) { return base + Math.round((v - base) / krok) * krok; }

  // tah typu "osa": nova hodnota = v0 + faktor * s (s = posun uchopeneho bodu podel osy, mm), mrizka kroku od zacatku tazeni, meze min..max,
  // zakazana pasma (hodnota se do nich nedostane: zastavi se u nejblizsiho okraje, zaokrouhleneho na bezpecnou stranu)
  function constrainAxis(d, v0, s) {
    var faktor = d.faktor || 1, krok = d.krok || 1, base = Math.round(v0), lo = num(d.min, -Infinity), hi = num(d.max, Infinity);
    var raw = v0 + faktor * s, v = raw, atMin = false, atMax = false, blocked = false;
    if (v <= lo) { v = lo; atMin = true; } else if (v >= hi) { v = hi; atMax = true; } else v = latticeRound(v, base, krok);
    v = Math.min(hi, Math.max(lo, v));
    var bands = d.zakazano || [], i;
    for (i = 0; i < bands.length; i++) {
      var b0 = bands[i][0], b1 = bands[i][1];
      if (v > b0 && v < b1) {
        var low = base + Math.floor((b0 - base) / krok + 1e-9) * krok, up = base + Math.ceil((b1 - base) / krok - 1e-9) * krok;
        var okLow = low >= lo && low <= hi, okUp = up >= lo && up <= hi;
        if (okLow && (!okUp || Math.abs(raw - b0) <= Math.abs(b1 - raw))) v = low; else if (okUp) v = up;
        blocked = true; atMin = false; atMax = false;
      }
    }
    var gap = null, od = num(d.odstup_od_prekazky, 0);
    for (i = 0; i < bands.length; i++) {
      var g = v <= bands[i][0] ? bands[i][0] - v + od : (v >= bands[i][1] ? v - bands[i][1] + od : 0);
      if (gap == null || g < gap) gap = g;
    }
    if (gap != null) gap *= num(d.mm_na_jednotku, 1);                              // tah v jine jednotce nez mm (stredni noha v %): mezera u prekazky se uvadi v mm
    v = Math.round(v * 100) / 100;
    var A = d.osa || [0, 0, 0], k = (v - v0) / faktor, bod = d.bod;
    return { value: v, delta: v - v0, blocked: blocked, atMin: atMin, atMax: atMax, gap: gap,
             disp: [bod[0] + A[0] * k, bod[1] + A[1] * k, bod[2] + A[2] * k] };
  }

  // tah typu "rovina": dx, dz = posun uchopeneho bodu ve vodorovne rovine (mm; +X dozadu, +Z doprava)
  function constrainPlane(d, v0x, v0z, dx, dz) {
    var krok = d.krok || 1;
    function one(v0, fak, mn, mx, delta) {
      var base = Math.round(v0), lo = num(mn, -Infinity), hi = num(mx, Infinity), v = v0 + (fak || 1) * delta, lim = false;
      if (v <= lo) { v = lo; lim = true; } else if (v >= hi) { v = hi; lim = true; } else v = latticeRound(v, base, krok);
      v = Math.min(hi, Math.max(lo, v));
      return { v: Math.round(v * 100) / 100, lim: lim };
    }
    var rx = one(v0x, d.faktor_x, d.min_x, d.max_x, dx), rz = one(v0z, d.faktor_z, d.min_z, d.max_z, dz), bod = d.bod;
    return { valueX: rx.v, valueZ: rz.v, atLimit: rx.lim || rz.lim,
             disp: [bod[0] + (rx.v - v0x) / (d.faktor_x || 1), bod[1], bod[2] + (rz.v - v0z) / (d.faktor_z || 1)] };
  }

  function fmt(v, krok) {
    var dec = krok && krok < 1 ? 1 : 0, f = Math.pow(10, dec), n = Math.round(v * f) / f + 0;
    try { return n.toLocaleString("cs-CZ", { minimumFractionDigits: dec, maximumFractionDigits: dec }); } catch (e) { return String(n); }
  }
  function fmtDelta(d, krok) {
    var dec = krok && krok < 1 ? 1 : 0, f = Math.pow(10, dec);
    if (Math.round(Math.abs(d) * f) === 0) return "±0";
    return (d > 0 ? "+" : "−") + fmt(Math.abs(d), krok);
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function svgEl(tag, attrs) {
    var n = document.createElementNS(SVGNS, tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    return n;
  }
  function validPoint(a) { return Array.isArray(a) && a.length === 3 && a.every(function (v) { return typeof v === "number" && isFinite(v); }); }
  function validBox(b) { return Array.isArray(b) && b.length === 2 && validPoint(b[0]) && validPoint(b[1]); }
  function copy(o) { var c = {}; Object.keys(o).forEach(function (k) { c[k] = o[k]; }); return c; }

  var ICON_ARROW = '<svg viewBox="0 0 24 24" aria-hidden="true"><g fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">' +
                   '<path d="M3.5 12h17M7.5 7.5 3 12l4.5 4.5M16.5 7.5 21 12l-4.5 4.5"/></g></svg>';
  var ICON_MOVE = '<svg viewBox="0 0 24 24" aria-hidden="true"><g fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">' +
                  '<path d="M12 3v18M3 12h18M9 6l3-3 3 3M9 18l3 3 3-3M6 9l-3 3 3 3M18 9l3 3-3 3"/></g></svg>';

  // ---------------------------------------------------------------------------------------------------------------
  function create(opts) {
    opts = opts || {};
    var stage = opts.stage, host = opts.overlay;
    if (!stage || !host) throw new Error("V3DOvladani.create: chybi stage nebo overlay");
    injectCss();
    var T = copy(TEXTS);
    Object.keys(opts.texts || {}).forEach(function (k) { T[k] = opts.texts[k]; });
    var LP_MS = opts.longPressMs || 450, LP_MOVE = 8, RC_MOVE = 5;
    var coarse = !!(global.matchMedia && global.matchMedia("(pointer: coarse)").matches);

    var viewer = null, offCam = null, canvas = null, ro = null, destroyed = false;
    var cam = null;                                       // kamera posledniho snimku
    var rel = { l: 0, t: 0, w: 0, h: 0 };                 // platno vuci hostiteli; meri se mimo vykreslovaci smycku (resize, nova data, zacatek gesta)
    var desc = null, parts = {}, handles = {}, pending = null, hasPending = false;
    var hov = null, hovPt = null, hovHandle = null, panelParam = null;
    var menu = null, drag = null;
    var lp = null, rc = null, swallowTouch = false, raf = 0, rafEv = null;
    var live = { ctx: null, nodes: {} };                  // plugin viewer3d: ctx.model = nactena scena; nodes: uzel -> {mesh, attr} (cache do dalsiho setModel)
    var linkKey = "", lblFor = null, lblW = 0, lblH = 0, tipW = 0, tipH = 0, tipRows = null, tipSt = null;

    var layer = el("div", "v3do-layer"), svg = svgEl("svg", { "class": "v3do-svg" }), lbl = el("div", "v3do-lbl"), tip = el("div", "v3do-tip");
    layer.appendChild(svg); layer.appendChild(lbl); layer.appendChild(tip);
    host.appendChild(layer);

    // -------------------------------------------------------------------------------------------------------------
    // zaklad: platno, kamera, popis
    // -------------------------------------------------------------------------------------------------------------
    function measure() {
      if (!canvas) return false;
      var cr = canvas.getBoundingClientRect(), hr = host.getBoundingClientRect();
      rel.l = cr.left - hr.left; rel.t = cr.top - hr.top; rel.w = cr.width; rel.h = cr.height;
      layer.style.left = rel.l + "px"; layer.style.top = rel.t + "px"; layer.style.width = rel.w + "px"; layer.style.height = rel.h + "px";
      svg.setAttribute("width", rel.w); svg.setAttribute("height", rel.h);
      return rel.w > 0 && rel.h > 0;
    }
    function camNow() { return viewer && viewer.cameraInfo ? camFrom(viewer.cameraInfo()) : null; }
    // paprsek z kamery pres bod obrazovky (clientX/Y); cerstva kamera i rozmer platna (volano z udalosti, ne ze smycky)
    function rayAtClient(cx, cy) {
      var c = camNow();
      if (!c || !canvas) return null;
      var r = canvas.getBoundingClientRect();
      return r.width > 0 && r.height > 0 ? rayThrough(c, cx - r.left, cy - r.top, r.width, r.height) : null;
    }
    function getParams() { return (opts.getParams && opts.getParams()) || {}; }

    function setViewer(v) {
      if (offCam) { try { offCam(); } catch (e) { /* odhlaseni nesmi shodit stranku */ } offCam = null; }
      if (ro) { ro.disconnect(); ro = null; }
      viewer = v || null; cam = null;
      canvas = viewer ? stage.querySelector("canvas") : null;
      if (!viewer || !canvas) { layer.style.display = "none"; return; }
      layer.style.display = "";
      if (global.ResizeObserver) { ro = new ResizeObserver(function () { measure(); update(); }); ro.observe(canvas); ro.observe(host); }
      measure();
      if (viewer.onCamera) offCam = viewer.onCamera(function (info) { update(info); });
      update();
    }

    function paramsOfDef(d) {
      var out = [];
      function add(p) { if (p && out.indexOf(p) < 0) out.push(p); }
      add(d.param); add(d.param_x); add(d.param_z);
      (d.mereni || []).forEach(function (m) { add(m.param); });
      return out;
    }

    function setDescription(d) {
      if (drag) { pending = d; hasPending = true; return; }       // behem tazeni se popis nemeni (obnovi se po jeho konci)
      applyDesc(d);
    }

    function applyDesc(d) {
      desc = d && ((d.casti && d.casti.length) || (d.tahy && d.tahy.length)) ? d : null;
      parts = {};
      ((desc && desc.casti) || []).forEach(function (c) { if (c && c.id && validBox(c.aabb)) parts[c.id] = { def: c }; });
      var seen = {};
      ((desc && desc.tahy) || []).forEach(function (t) {
        if (!t || !t.id || !validPoint(t.bod) || (t.typ === "rovina" ? !t.param_x || !t.param_z : !t.param || !validPoint(t.osa))) return;      // poskozeny zaznam se preskoci
        seen[t.id] = true;
        var h = handles[t.id];
        if (!h) h = handles[t.id] = buildHandle(t); else h.def = t;
        h.params = paramsOfDef(t);
      });
      Object.keys(handles).forEach(function (id) { if (!seen[id]) removeHandle(id); });
      if (hov && !parts[hov]) hov = null;
      if (hovHandle && !handles[hovHandle]) hovHandle = null;
      if (menu) { if (parts[menu.partId]) buildMenu(); else closeMenu(); }
      lblFor = null;
      measure(); updateCaps(); update(); relink();
    }

    // -------------------------------------------------------------------------------------------------------------
    // uchyty
    // -------------------------------------------------------------------------------------------------------------
    function buildHandle(def) {
      var id = (opts.handleIds && opts.handleIds[def.id]) || ("v3do_" + def.id);
      var node = el("div", "v3do-h handle");
      node.id = id; node.setAttribute("data-tah", def.id); node.setAttribute("role", "slider"); node.setAttribute("aria-label", def.label || def.id);
      node.tabIndex = 0;
      node.style.display = "none";                                   // zobrazi se az po prvnim umisteni podle kamery (placeHandles)
      var ico = el("span", "ico");
      ico.innerHTML = def.ikona === "presun" ? ICON_MOVE : ICON_ARROW;
      var cap = el("span", "cap");
      node.appendChild(ico); node.appendChild(cap);
      layer.appendChild(node);
      var h = { def: def, el: node, ico: ico.firstChild, cap: cap, params: paramsOfDef(def), vis: false, x: 0, y: 0, ang: null, tf: "", rel: false };
      node.addEventListener("pointerdown", function (e) { onHandleDown(h, e); });
      node.addEventListener("pointermove", function (e) { onHandleMove(h, e); });
      node.addEventListener("pointerup", function (e) { onHandleUp(h, e, false); });
      node.addEventListener("pointercancel", function (e) { onHandleUp(h, e, true); });
      node.addEventListener("pointerenter", function (e) { if (e.pointerType === "mouse" && !drag) { hovHandle = h.def.id; relink(); draw(); } });
      node.addEventListener("pointerleave", function (e) { if (e.pointerType === "mouse" && hovHandle === h.def.id) { hovHandle = null; relink(); draw(); } });
      node.addEventListener("keydown", function (e) { onHandleKey(h, e); });
      node.addEventListener("contextmenu", function (e) { e.preventDefault(); });
      return h;
    }
    function removeHandle(id) {
      var h = handles[id];
      if (h && h.el.parentNode) h.el.parentNode.removeChild(h.el);
      delete handles[id];
    }

    // hodnota parametru: pri tazeni nova hodnota, jinak aktualni parametr stranky (null = hodnota z popisu)
    function valueOf(h, name, map) {
      if (map && typeof map[name] === "number") return map[name];
      var d = h.def, fb = null;
      if (name === d.param) fb = d.hodnota; else if (name === d.param_x) fb = d.hodnota_x; else if (name === d.param_z) fb = d.hodnota_z;
      return num(getParams()[name], fb);
    }
    // radky mereni uchytu: [{label, param, value}]; bez `mereni` jeden radek z nazvu
    function rowsOf(h, map) {
      var d = h.def, rows = [];
      (d.mereni || []).forEach(function (m) {
        var v = valueOf(h, m.param, map);
        if (v != null) rows.push({ label: m.label, param: m.param, value: num(m.add, 0) + (m.mul == null ? 1 : m.mul) * v });
      });
      if (!rows.length) {
        if (d.typ === "rovina") {
          [d.param_x, d.param_z].forEach(function (p) { var v = valueOf(h, p, map); if (v != null) rows.push({ label: p, param: p, value: v }); });
        } else {
          var v = valueOf(h, d.param, map);
          if (v != null) rows.push({ label: d.label || d.param, param: d.param, value: v });
        }
      }
      return rows;
    }
    function rowText(r, krok) { return r.label + " " + fmt(r.value, krok) + " " + T.unit; }

    function updateCaps() {
      Object.keys(handles).forEach(function (id) {
        var h = handles[id], rows = rowsOf(h, null), txt = rows.length ? rowText(rows[0], h.def.krok) : (h.def.label || "");
        if (h.cap.textContent !== txt) h.cap.textContent = txt;
        h.el.setAttribute("aria-valuetext", txt);
        if (rows.length) h.el.setAttribute("aria-valuenow", String(Math.round(rows[0].value)));
        if (h.def.min != null) h.el.setAttribute("aria-valuemin", String(h.def.min));
        if (h.def.max != null) h.el.setAttribute("aria-valuemax", String(h.def.max));
      });
    }

    function iconAngle(h, P) {
      var d = h.def, dirv;
      if (d.ikona === "presun") return 0;
      if (d.typ === "rovina") dirv = [1, 0, 1]; else dirv = d.osa || [1, 0, 0];     // roh: uhlopricka (hloubka + sirka vzrusta ven)
      var a = project(vec(P), cam, rel.w, rel.h), b = project(addk(vec(P), vec(dirv), 150), cam, rel.w, rel.h);
      if (!a || !b || Math.hypot(b.x - a.x, b.y - a.y) < 2) return h.ang;
      var ang = Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI;
      if (ang > 90) ang -= 180; else if (ang <= -90) ang += 180;
      return ang;
    }

    function placeHandles() {
      Object.keys(handles).forEach(function (id) {
        var h = handles[id], P = drag && drag.h === h && drag.disp ? drag.disp : h.def.bod;
        var s = project(vec(P), cam, rel.w, rel.h);
        var vis = !!s && s.x > -20 && s.x < rel.w + 20 && s.y > -20 && s.y < rel.h + 20;
        if (vis !== h.vis) { h.vis = vis; h.el.style.display = vis ? "" : "none"; }
        if (!vis) return;
        h.x = s.x; h.y = s.y;
        var tf = "translate(" + s.x.toFixed(1) + "px," + s.y.toFixed(1) + "px)";
        if (tf !== h.tf) { h.tf = tf; h.el.style.transform = tf; }
        var ang = iconAngle(h, P);
        if (ang != null && h.ico && (h.ang == null || Math.abs(ang - h.ang) >= 1)) { h.ang = ang; h.ico.style.transform = "rotate(" + ang.toFixed(0) + "deg)"; }
      });
    }

    // -------------------------------------------------------------------------------------------------------------
    // obrysy, popisek, propojeni s panelem
    // -------------------------------------------------------------------------------------------------------------
    function relatedIds() {
      var ids = {};
      function add(id, kind) { if (parts[id] && !ids[id]) ids[id] = kind; }
      if (drag) return ids;                                        // behem tazeni se model meni, obrysy z puvodniho popisu by neseděly
      if (menu) add(menu.partId, "menu");
      if (hov && !menu) add(hov, "hover");
      if (panelParam) Object.keys(parts).forEach(function (id) { if ((parts[id].def.param || []).indexOf(panelParam) >= 0) add(id, "rel"); });
      var hh = hovHandle && handles[hovHandle];
      if (hh) (hh.def.casti || []).forEach(function (id) { add(id, "rel"); });
      return ids;
    }

    function drawBox(def, kind) {
      var lo = def.aabb[0], hi = def.aabb[1], pts = [], i;
      for (i = 0; i < 8; i++) {
        var s = project({ x: (i & 1) ? hi[0] : lo[0], y: (i & 2) ? hi[1] : lo[1], z: (i & 4) ? hi[2] : lo[2] }, cam, rel.w, rel.h);
        if (!s) return;                                            // roh za kamerou: obrys se nekresli
        pts.push(s);
      }
      function pt(p) { return p.x.toFixed(1) + " " + p.y.toFixed(1); }
      var hl = hull(pts), dh = "M" + hl.map(pt).join("L") + "Z", E = [[0, 1], [2, 3], [4, 5], [6, 7], [0, 2], [1, 3], [4, 6], [5, 7], [0, 4], [1, 5], [2, 6], [3, 7]];
      var de = E.map(function (e) { return "M" + pt(pts[e[0]]) + "L" + pt(pts[e[1]]); }).join("");
      var g = svgEl("g", { "class": "bx " + kind, "data-id": def.id });
      g.appendChild(svgEl("path", { "class": "fill", d: dh }));
      g.appendChild(svgEl("path", { "class": "edge", d: de }));
      g.appendChild(svgEl("path", { "class": "halo", d: dh }));
      g.appendChild(svgEl("path", { "class": "line", d: dh }));
      svg.appendChild(g);
    }

    function draw() {
      if (!cam || !rel.w) { while (svg.firstChild) svg.removeChild(svg.firstChild); lbl.style.display = "none"; return; }
      var ids = relatedIds(), keys = Object.keys(ids);
      if (!keys.length && !svg.firstChild) { placeLabel(); return; }
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      keys.forEach(function (id) { drawBox(parts[id].def, ids[id]); });
      placeLabel();
    }

    function placeLabel() {
      var p = hov && !menu && !drag && parts[hov];
      if (!p || !hovPt) { lbl.style.display = "none"; lblFor = null; return; }
      if (lblFor !== hov) {
        lbl.textContent = "";
        lbl.appendChild(document.createTextNode(p.def.label || p.def.id));
        if ((p.def.menu || []).length && !coarse) lbl.appendChild(el("small", null, T.menuHint));
        lbl.style.display = "block";
        lblW = lbl.offsetWidth; lblH = lbl.offsetHeight; lblFor = hov;
      }
      var x = hovPt.x + 14, y = hovPt.y + 20;
      if (x + lblW > rel.w - 4) x = hovPt.x - 14 - lblW;
      if (y + lblH > rel.h - 4) y = hovPt.y - 14 - lblH;
      lbl.style.transform = "translate(" + Math.max(2, x).toFixed(0) + "px," + Math.max(2, y).toFixed(0) + "px)";
    }

    function markRelatedHandles() {
      Object.keys(handles).forEach(function (id) {
        var h = handles[id], on = false, casti = h.def.casti || [];
        if (panelParam && h.params.indexOf(panelParam) >= 0) on = true;
        if (hov && casti.indexOf(hov) >= 0) on = true;
        if (menu && casti.indexOf(menu.partId) >= 0) on = true;
        if (on !== h.rel) { h.rel = on; h.el.classList.toggle("rel", on); }
      });
    }

    // co ma stranka zvyraznit v panelu: parametry casti pod mysi / s nabidkou a parametry uchytu pod mysi / v tazeni
    function relink() {
      var set = {};
      function addAll(arr) { (arr || []).forEach(function (p) { set[p] = 1; }); }
      if (hov && parts[hov]) addAll(parts[hov].def.param);
      if (menu && parts[menu.partId]) addAll(parts[menu.partId].def.param);
      var hh = drag ? drag.h : (hovHandle && handles[hovHandle]);
      if (hh) addAll(hh.params);
      var list = Object.keys(set).sort(), key = list.join("|");
      if (key !== linkKey) { linkKey = key; if (opts.onLink) opts.onLink(list); }
      markRelatedHandles();
    }

    function update(info) {
      if (destroyed) return;
      if (info) cam = camFrom(info); else if (!cam) cam = camNow();
      if (!cam || !rel.w) return;
      placeHandles();
      draw();
      if (drag) placeTip();
    }

    // -------------------------------------------------------------------------------------------------------------
    // najeti mysi na cast
    // -------------------------------------------------------------------------------------------------------------
    function pickPart(cx, cy) {
      var ray = rayAtClient(cx, cy);
      if (!ray) return null;
      var hits = [];
      Object.keys(parts).forEach(function (id) {
        var d = parts[id].def, t = rayBox(ray.o, ray.d, d.aabb[0], d.aabb[1]);
        if (t != null) hits.push({ id: id, t: t, pr: d.priorita || 0 });
      });
      if (!hits.length) return null;
      var tmin = Infinity, best = null;
      hits.forEach(function (h) { if (h.t < tmin) tmin = h.t; });
      hits.forEach(function (h) {                                   // nejblizsi vstup; do 3 mm od nej vyhrava vyssi priorita
        if (h.t > tmin + 3) return;
        if (!best || h.pr > best.pr || (h.pr === best.pr && h.t < best.t)) best = h;
      });
      return best;
    }

    function onStageMove(e) {
      if (e.pointerType !== "mouse" || drag || menu || !canvas) return;
      if (e.buttons || e.target !== canvas) { setHover(null, null); return; }
      rafEv = e;
      if (!raf) raf = global.requestAnimationFrame(doHover);
    }
    function doHover() {
      raf = 0;
      var e = rafEv; rafEv = null;
      if (!e || destroyed || drag || menu || !canvas) return;
      var hit = pickPart(e.clientX, e.clientY), r = canvas.getBoundingClientRect();
      setHover(hit ? hit.id : null, { x: e.clientX - r.left, y: e.clientY - r.top });
    }
    function setHover(id, pt) {
      hovPt = pt;
      if (id !== hov) { hov = id; relink(); draw(); } else placeLabel();
    }

    // -------------------------------------------------------------------------------------------------------------
    // nabidka (pravé tlacitko / dlouhy stisk)
    // -------------------------------------------------------------------------------------------------------------
    function deskaPoint(cx, cy) {
      if (!desc || !desc.deska || !desc.deska.pocatek) return null;
      var ray = rayAtClient(cx, cy);
      return ray ? rayPlaneY(ray.o, ray.d, desc.deska.pocatek[1]) : null;
    }
    function openMenu(partId, cx, cy) {
      var p = parts[partId];
      if (!p || !(p.def.menu || []).length) return false;
      closeMenu();
      setHover(null, null);
      menu = { partId: partId, cx: cx, cy: cy, hit: deskaPoint(cx, cy), el: null };
      buildMenu();
      relink(); draw();
      return true;
    }
    function buildMenu() {
      var p = parts[menu.partId], old = menu.el;
      var box = el("div", "v3do-menu");
      box.setAttribute("role", "menu"); box.setAttribute("aria-label", p.def.label || p.def.id);
      box.appendChild(el("div", "mh", p.def.label || p.def.id));
      (p.def.menu || []).forEach(function (it) {
        var n;
        if (it.zakazano) {
          n = el("div", "mi dis", it.text);
          n.setAttribute("aria-disabled", "true");
          if (it.duvod) n.appendChild(el("small", null, it.duvod));
        } else {
          n = el("button", "mi", it.text);
          n.type = "button";
          n.addEventListener("click", function (e) { e.preventDefault(); chooseItem(it); });
        }
        n.setAttribute("role", "menuitem");
        box.appendChild(n);
      });
      box.addEventListener("keydown", onMenuKey);
      box.addEventListener("contextmenu", function (e) { e.preventDefault(); });
      if (old && old.parentNode) old.parentNode.removeChild(old);
      document.body.appendChild(box);
      menu.el = box;
      var vw = document.documentElement.clientWidth || global.innerWidth, vh = global.innerHeight, w = box.offsetWidth, h = box.offsetHeight;
      box.style.left = Math.max(8, Math.min(vw - w - 8, menu.cx + 4)) + "px";
      box.style.top = Math.max(8, Math.min(vh - h - 8, menu.cy + 4)) + "px";
      box.tabIndex = -1;
      if (!old) box.focus({ preventScroll: true });                    // sipky pak vybiraji polozky (zadna polozka neni predvybrana)
    }
    function closeMenu() {
      if (!menu) return;
      if (menu.el && menu.el.parentNode) menu.el.parentNode.removeChild(menu.el);
      menu = null;
      relink(); draw();
    }
    function chooseItem(it) {
      var hit = menu && menu.hit;
      closeMenu();
      if (it.fokus && opts.focusParam) opts.focusParam(it.fokus);
      if (it.nastav && opts.applyPatch) {
        var patch = copy(it.nastav), b = it.bod_na_desce, dk = desc && desc.deska && desc.deska.pocatek;
        if (b && hit && dk) {                                           // "Pridat vyrez sem": bod kliknuti na desce -> poloha stredu otvoru, po 10 mm
          var P = getParams(), d = num(P[b.stred_o[0]], 0), w = num(P[b.stred_o[1]], 0);
          patch[b.x] = Math.round((hit.x - dk[0] - d / 2) / 10) * 10;
          patch[b.z] = Math.round((hit.z - dk[2] - w / 2) / 10) * 10;
        }
        opts.applyPatch(patch, { live: false, source: "menu" });
      }
    }
    function onMenuKey(e) {
      if (!menu || !menu.el) return;                                  // Esc uz nabidku zavrel (document, capture) driv, nez dorazila sem
      var items = [].slice.call(menu.el.querySelectorAll("button.mi")), i = items.indexOf(document.activeElement);
      if (e.key === "ArrowDown") i = i < 0 ? 0 : (i + 1) % items.length;
      else if (e.key === "ArrowUp") i = i <= 0 ? items.length - 1 : i - 1;
      else if (e.key === "Home") i = 0;
      else if (e.key === "End") i = items.length - 1;
      else if (e.key === "Tab") { e.preventDefault(); i = e.shiftKey ? (i <= 0 ? items.length - 1 : i - 1) : (i + 1) % items.length; }
      else return;
      e.preventDefault();
      if (items[i]) items[i].focus({ preventScroll: true });
    }

    // pravé tlacitko: nabidka se otevre po pusteni, kdyz se mys nehnula (jinak je to posun modelu pravym tlacitkem); dotyk: dlouhy stisk
    function onStageDown(e) {
      if (!canvas || e.target !== canvas || drag) return;
      if (e.pointerType === "touch") {
        if (!e.isPrimary) { cancelLp(); return; }
        cancelLp();
        if (pickPart(e.clientX, e.clientY)) lp = { id: e.pointerId, x: e.clientX, y: e.clientY, timer: global.setTimeout(fireLp, LP_MS) };     // dlouhy stisk jen na casti modelu
      } else if (e.pointerType === "mouse" && e.button === 2) {
        rc = { id: e.pointerId, x: e.clientX, y: e.clientY, moved: false };
      }
    }
    function onStageMoveCapture(e) {
      if (lp && e.pointerId === lp.id && Math.hypot(e.clientX - lp.x, e.clientY - lp.y) > LP_MOVE) cancelLp();
      if (rc && e.pointerId === rc.id && Math.hypot(e.clientX - rc.x, e.clientY - rc.y) > RC_MOVE) rc.moved = true;
    }
    function onStageUp(e) {
      if (lp && e.pointerId === lp.id) cancelLp();
      if (rc && e.pointerId === rc.id && e.button === 2) {
        var r = rc; rc = null;
        if (!r.moved) { var hit = pickPart(e.clientX, e.clientY); if (hit) openMenu(hit.id, e.clientX, e.clientY); else closeMenu(); }
      }
    }
    function onStageCancel(e) { if (lp && e.pointerId === lp.id) cancelLp(); if (rc && e.pointerId === rc.id) rc = null; }
    function cancelLp() { if (lp) { global.clearTimeout(lp.timer); lp = null; } }
    function fireLp() {
      var p = lp; lp = null;
      if (!p || drag) return;
      var hit = pickPart(p.x, p.y);
      if (hit && openMenu(hit.id, p.x, p.y)) swallowTouch = true;          // model se pri dalsim pohybu prstu neotaci
    }
    // OrbitControls (r128) ovlada dotyk udalostmi touch*, ne pointer*: po dlouhem stisku se touchmove nepusti dal; behem cekani na dlouhy stisk
    // (prst se nehnul o vic nez LP_MOVE) take ne, aby chveni prstu model neotacelo (pri vetsim pohybu se timer zrusi a otaceni zacne normalne)
    function onTouchMoveCapture(e) { if (swallowTouch || lp) { e.stopImmediatePropagation(); if (e.cancelable) e.preventDefault(); } }
    function onTouchEndCapture(e) { if (swallowTouch && (!e.touches || e.touches.length === 0)) swallowTouch = false; }
    function onDocDown(e) { if (menu && menu.el && !menu.el.contains(e.target)) closeMenu(); }

    // -------------------------------------------------------------------------------------------------------------
    // ZIVE tazeni: server u tahu popisuje operace `zive` ({op: posun|natahni|roztahni, ix: [indexy dilu], k, strana?}) a v `zive_rozsahy[index dilu]`
    // = [uzel, od, pocet] kde jsou vrcholy dilu v nactenem modelu (GLB je slepeny po materialech: uzel n<uzel>, vrcholy `od..od+pocet` v POSITION).
    // Behem tazeni se vrcholy hybou PRIMO v modelu (bez dotazu na server): d = k * s * osa, s = (nova hodnota - hodnota na zacatku) / faktor (mm).
    //   posun: vsechny vrcholy dilu o d; natahni: jen vrcholy na strane `strana` (vuci STREDU dilu podel osy: u = v.osa, stred = (min+max)/2) o d;
    //   roztahni: u > stred o +d, u < stred o -d. Vrcholy PRESNE uprostred (|u - stred| <= 0,05 mm, mesh desky ma stredovy vrchol): natahni o d/2, roztahni nic.
    //   Operace se aplikuji popradku na kopii puvodnich vrcholu (stejna pravidla jako api test_stul_zive.py).
    // -------------------------------------------------------------------------------------------------------------
    function plugin(ctx) {                                          // opts.plugins viewer3d: vola se po KAZDEM postaveni modelu (setModel), konec = dispose
      live.ctx = ctx; live.nodes = {};
      return function () { if (live.ctx === ctx) { live.ctx = null; live.nodes = {}; } };
    }
    function liveNode(uzel) {
      if (live.nodes[uzel]) return live.nodes[uzel];
      var root = live.ctx && live.ctx.model, mesh = null;
      if (!root) return null;
      var obj = root.getObjectByName ? root.getObjectByName("n" + uzel) : null;
      if (obj) { if (obj.isMesh) mesh = obj; else obj.traverse(function (o) { if (!mesh && o.isMesh) mesh = o; }); }
      if (!mesh) { var all = []; root.traverse(function (o) { if (o.isMesh) all.push(o); }); mesh = all[uzel] || null; }       // zaloha: poradi meshu
      var attr = mesh && mesh.geometry && mesh.geometry.attributes && mesh.geometry.attributes.position;
      if (!attr || attr.isInterleavedBufferAttribute || attr.itemSize !== 3 || !attr.array || attr.array.constructor !== Float32Array) return null;
      return (live.nodes[uzel] = { mesh: mesh, attr: attr });
    }
    // priprava: vsechny dily dotcene operacemi musi mit rozsah vrcholu a uzel v modelu, jinak se nezive (null -> stranka se chova jako dosud)
    function liveBegin(d) {
      var roz = desc && desc.zive_rozsahy;
      if (!live.ctx || !roz || !d.zive || !d.zive.length || d.typ === "rovina") return null;
      var dily = {}, ok = true, nodes = {}, extra = desc && desc.zive_rozsahy_extra;
      d.zive.forEach(function (op) {
        (op.ix || []).forEach(function (i) {
          var r = roz[i];
          if (!r || dily[i]) return;                               // null = dil se nehybe (deska s otvory)
          var nd = liveNode(r[0]);
          if (!nd || r[1] + r[2] > nd.attr.count) { ok = false; return; }
          dily[i] = { nd: nd, from: r[1] * 3, to: (r[1] + r[2]) * 3, orig: nd.attr.array.slice(r[1] * 3, (r[1] + r[2]) * 3) };
          nodes[r[0]] = nd;
          ((extra && extra[i]) || []).forEach(function (r2, k) {   // dil rozdeleny do vice uzlu (horni suplik boxu je vlastni uzel kvuli pohybu na klik): dalsi rozsahy se hybou spolu s dilem
            var nd2 = liveNode(r2[0]);
            if (!nd2 || r2[1] + r2[2] > nd2.attr.count) { ok = false; return; }
            dily[i + "+" + k] = { nd: nd2, from: r2[1] * 3, to: (r2[1] + r2[2]) * 3, orig: nd2.attr.array.slice(r2[1] * 3, (r2[1] + r2[2]) * 3) };
            nodes[r2[0]] = nd2;
          });
        });
      });
      if (!ok || !Object.keys(dily).length) return null;
      var rig = {};                                                // razitka (logo = uzel n<i>, vypln drazky = vrcholy v uzlu hlinik) na dilech, ktere se hybou, se hybou s nimi (Robert 2026-10-08: "razitka pri tazeni zustavaji na miste")
      ((desc && desc.razitka) || []).forEach(function (z) {
        if (!z || !dily[z.dil]) return;
        var obj = live.ctx.model && live.ctx.model.getObjectByName ? live.ctx.model.getObjectByName("n" + z.uzel) : null, v = null, nd2 = z.vypln && liveNode(z.vypln[0]);
        if (nd2 && z.vypln[1] + z.vypln[2] <= nd2.attr.count) { v = { nd: nd2, from: z.vypln[1] * 3, to: (z.vypln[1] + z.vypln[2]) * 3 }; v.orig = nd2.attr.array.slice(v.from, v.to); nodes[z.vypln[0]] = nd2; }
        if (!obj && !v) return;
        var r = { obj: obj, v: v, p0: obj ? [obj.position.x, obj.position.y, obj.position.z] : null, c: null };
        if (obj) r.c = r.p0.slice();
        else { var sx = 0, sy = 0, sz = 0, nn = (v.to - v.from) / 3, jj, aa = v.nd.attr.array; for (jj = v.from; jj < v.to; jj += 3) { sx += aa[jj]; sy += aa[jj + 1]; sz += aa[jj + 2]; } r.c = [sx / nn, sy / nn, sz / nn]; }
        r.c0 = r.c.slice();
        (rig[z.dil] = rig[z.dil] || []).push(r);
      });
      Object.keys(nodes).forEach(function (k) { nodes[k].mesh.frustumCulled = false; });
      var ops = d.zive.map(function (op) {                         // operace plati i pro dalsi rozsahy dilu (klic "i+k"); puvodni popis od serveru se nemeni
        var o2 = {}, ix = [];
        Object.keys(op).forEach(function (kk) { o2[kk] = op[kk]; });
        (op.ix || []).forEach(function (i) { ix.push(i); for (var k = 0; dily[i + "+" + k]; k++) ix.push(i + "+" + k); });
        o2.ix = ix;
        return o2;
      });
      return { ctx: live.ctx, ops: ops, dily: dily, nodes: nodes, osa: norm(vec(d.osa)), s: 0, rig: rig };
    }
    function rigReset(L) {                                        // razitka zpet na vychozi misto (kazdy liveApply pocita od puvodnich poloh)
      var k, i, r, rs;
      for (k in L.rig) { rs = L.rig[k]; for (i = 0; i < rs.length; i++) { r = rs[i]; if (r.obj) r.obj.position.set(r.p0[0], r.p0[1], r.p0[2]); if (r.v) r.v.nd.attr.array.set(r.v.orig, r.v.from); r.c = r.c0.slice(); } }
    }
    function rigMove(r, f, dx, dy, dz) {                          // razitko se posune jako tuhe teleso o f * (dx, dy, dz)
      if (!f) return;
      var a, j;
      if (r.obj) r.obj.position.set(r.obj.position.x + f * dx, r.obj.position.y + f * dy, r.obj.position.z + f * dz);
      if (r.v) { a = r.v.nd.attr.array; for (j = r.v.from; j < r.v.to; j += 3) { a[j] += f * dx; a[j + 1] += f * dy; a[j + 2] += f * dz; } }
      r.c[0] += f * dx; r.c[1] += f * dy; r.c[2] += f * dz;
    }
    function liveApply(L, s) {
      if (!live.ctx || live.ctx !== L.ctx) return false;           // model se mezitim vymenil
      var A = L.osa, ax = A.x, ay = A.y, az = A.z, ix;
      for (ix in L.dily) { var q = L.dily[ix]; q.nd.attr.array.set(q.orig, q.from); }
      rigReset(L);
      L.ops.forEach(function (op) {
        var dx = op.k * s * ax, dy = op.k * s * ay, dz = op.k * s * az;
        (op.ix || []).forEach(function (i) {
          var q = L.dily[i];
          if (!q) return;
          var a = q.nd.attr.array, j, u, n = q.to;
          if (op.op === "posun") { for (j = q.from; j < n; j += 3) { a[j] += dx; a[j + 1] += dy; a[j + 2] += dz; } (L.rig[i] || []).forEach(function (r) { rigMove(r, 1, dx, dy, dz); }); return; }
          var mn = Infinity, mx = -Infinity;
          for (j = q.from; j < n; j += 3) { u = a[j] * ax + a[j + 1] * ay + a[j + 2] * az; if (u < mn) mn = u; if (u > mx) mx = u; }
          var st = (mn + mx) / 2, side, f;
          (L.rig[i] || []).forEach(function (r) {                  // razitka na tomto dile: stejne pravidlo jako pro vrcholy, rozhoduje poloha STREDU razitka vuci stredu dilu podel osy
            var us = r.c[0] * ax + r.c[1] * ay + r.c[2] * az, sd = us > st + 0.05 ? 1 : (us < st - 0.05 ? -1 : 0), ff = op.op === "natahni" ? (sd === 0 ? 0.5 : (sd === (op.strana > 0 ? 1 : -1) ? 1 : 0)) : sd;
            rigMove(r, ff, dx, dy, dz);
          });
          for (j = q.from; j < n; j += 3) {
            u = a[j] * ax + a[j + 1] * ay + a[j + 2] * az;
            side = u > st + 0.05 ? 1 : (u < st - 0.05 ? -1 : 0);       // 0 = vrchol PRESNE uprostred dilu (mesh desky ma stredovy vrchol plochy): o jeho strane by jinak rozhodl zaokrouhlovaci sum
            if (op.op === "natahni") f = side === 0 ? 0.5 : (side === (op.strana > 0 ? 1 : -1) ? 1 : 0);      // stred natazeneho dilu se pohne o pulku
            else f = side;                                              // roztahni: + strana o +d, - strana o -d, stred zustava
            if (f) { a[j] += f * dx; a[j + 1] += f * dy; a[j + 2] += f * dz; }
          }
        });
      });
      Object.keys(L.nodes).forEach(function (k) { L.nodes[k].attr.needsUpdate = true; });
      L.s = s;
      live.ctx.requestRender();
      return true;
    }
    // konec: pusteni = nahled zustava (server model zpresni), obalka se prepocita jednou; zruseni = vrcholy zpet z kopie
    function liveEnd(L, restore) {
      if (!live.ctx || live.ctx !== L.ctx) return;
      if (restore) {
        for (var ix in L.dily) { var q = L.dily[ix]; q.nd.attr.array.set(q.orig, q.from); }
        rigReset(L);
        Object.keys(L.nodes).forEach(function (k) { L.nodes[k].attr.needsUpdate = true; });
      }
      Object.keys(L.nodes).forEach(function (k) {
        var g = L.nodes[k].mesh.geometry;
        if (!restore) { g.computeBoundingSphere(); g.computeBoundingBox(); }
        L.nodes[k].mesh.frustumCulled = true;
      });
      live.ctx.requestRender();
    }
    // zkousky: aktualni poloha stredu kazdeho razitka v nactenem modelu (logo = poloha uzlu, vypln = teziste vrcholu)
    function liveRazitka() {
      var out = [];
      ((desc && desc.razitka) || []).forEach(function (z) {
        var obj = live.ctx && live.ctx.model && live.ctx.model.getObjectByName ? live.ctx.model.getObjectByName("n" + z.uzel) : null, nd = z.vypln && live.ctx ? liveNode(z.vypln[0]) : null, c = null, a, n, sx = 0, sy = 0, sz = 0, j;
        if (nd) { a = nd.attr.array; n = z.vypln[2]; for (j = z.vypln[1] * 3; j < (z.vypln[1] + n) * 3; j += 3) { sx += a[j]; sy += a[j + 1]; sz += a[j + 2]; } c = [sx / n, sy / n, sz / n]; }
        out.push({ dil: z.dil, uzel: z.uzel, logo: obj ? [obj.position.x, obj.position.y, obj.position.z] : null, vypln: c });
      });
      return out;
    }
    // zkousky: obalka a stred vrcholu dilu cteny primo z atributu v nactenem modelu
    function liveBox(i) {
      var r = desc && desc.zive_rozsahy && desc.zive_rozsahy[i], nd = r && live.ctx && liveNode(r[0]);
      if (!nd) return null;
      var a = nd.attr.array, mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity], sum = [0, 0, 0], j, c;
      for (j = r[1] * 3; j < (r[1] + r[2]) * 3; j += 3) for (c = 0; c < 3; c++) { var v = a[j + c]; if (v < mn[c]) mn[c] = v; if (v > mx[c]) mx[c] = v; sum[c] += v; }
      return { min: mn, max: mx, mean: sum.map(function (x) { return x / r[2]; }) };
    }

    // -------------------------------------------------------------------------------------------------------------
    // tazeni uchytu
    // -------------------------------------------------------------------------------------------------------------
    // posun uchopeneho bodu proti zacatku tazeni: osa -> {s} (mm podel osy), rovina -> {x, z} (mm); null = nelze urcit (pohled podel osy)
    function dragDelta(cx, cy) {
      var ray = rayAtClient(cx, cy), d = drag.def;
      if (!ray) return null;
      if (d.typ === "rovina") {
        var hit = rayPlaneY(ray.o, ray.d, d.bod[1]);
        if (!hit) return null;
        if (!drag.hit0) drag.hit0 = hit;
        return { x: hit.x - drag.hit0.x, z: hit.z - drag.hit0.z };
      }
      var s = rayAxis(ray.o, ray.d, vec(d.bod), norm(vec(d.osa)));
      if (s == null) return null;
      if (drag.s0 == null) drag.s0 = s;
      return { s: s - drag.s0 };
    }

    function onHandleDown(h, e) {
      if (drag || !viewer || (e.pointerType === "mouse" && e.button !== 0)) return;
      e.preventDefault(); e.stopPropagation();
      closeMenu(); cancelLp();
      measure();
      var d = h.def, P = getParams(), orig = {}, start = {};
      h.params.forEach(function (p) { orig[p] = P[p] === undefined ? null : P[p]; });
      if (d.typ === "rovina") { start[d.param_x] = d.hodnota_x; start[d.param_z] = d.hodnota_z; } else start[d.param] = d.hodnota;
      drag = { h: h, id: e.pointerId, def: d, orig: orig, start: start, cur: copy(start), s0: null, hit0: null, disp: null, info: null, rows0: null,
               tap: { x: e.clientX, y: e.clientY, t: e.timeStamp || Date.now(), moved: false } };           // tap: klepnuti bez tazeni se preda prohlizeci (forwardTap)
      dragDelta(e.clientX, e.clientY);                                  // zapamatuje pocatecni bod
      drag.rows0 = rowsOf(h, start);
      try { h.el.setPointerCapture(e.pointerId); } catch (x) { /* neni kriticke */ }
      h.el.classList.add("drag"); layer.classList.add("dragging");
      hovHandle = null; setHover(null, null);
      buildTip();
      drag.live = liveBegin(d);                                          // null = bez zivych vrcholu (starsi server, vyrez...): stranka obnovuje model ze serveru
      if (opts.dragState) opts.dragState(true, d, { live: !!drag.live });
      relink(); update();
    }

    function onHandleMove(h, e) {
      if (!drag || drag.h !== h || e.pointerId !== drag.id) return;
      e.preventDefault();
      if (drag.tap && Math.hypot(e.clientX - drag.tap.x, e.clientY - drag.tap.y) > 6) drag.tap.moved = true;
      var dl = dragDelta(e.clientX, e.clientY);
      if (!dl) return;
      var d = drag.def, patch = {}, info;
      if (d.typ === "rovina") {
        var c = constrainPlane(d, drag.start[d.param_x], drag.start[d.param_z], dl.x, dl.z);
        patch[d.param_x] = c.valueX; patch[d.param_z] = c.valueZ;
        info = { atLimit: c.atLimit, disp: c.disp };
      } else {
        var a = constrainAxis(d, drag.start[d.param], dl.s);
        patch[d.param] = a.value;
        info = a;
        if (drag.live && a.value !== drag.cur[d.param] && !liveApply(drag.live, (a.value - drag.start[d.param]) / (d.faktor || 1))) drag.live = null;
      }
      drag.info = info; drag.disp = info.disp;
      var changed = Object.keys(patch).some(function (k) { return drag.cur[k] !== patch[k]; });
      if (changed) { drag.cur = patch; if (opts.applyPatch) opts.applyPatch(copy(patch), { live: true, source: "drag" }); }
      renderTip(); update();
    }

    function onHandleUp(h, e, cancelled) {
      if (!drag || drag.h !== h || e.pointerId !== drag.id) return;
      try { h.el.releasePointerCapture(e.pointerId); } catch (x) { /* uz uvolneno */ }
      var tap = !cancelled && drag.tap && !drag.tap.moved && ((e.timeStamp || Date.now()) - drag.tap.t) < 900 && Object.keys(drag.start).every(function (k) { return drag.cur[k] === drag.start[k]; });
      if (cancelled) cancelDrag(); else endDrag();
      if (tap) forwardTap(e);
    }
    // klepnuti na uchyt BEZ tazeni (nic se nezmenilo) = klepnuti na dil pod nim: uchyt boxu lezi na celu supliku a klik na suplik ho ma otevrit (viewer3d.js: pohyb k=drawer) - predat prohlizeci jako
    // dvojici pointerdown / pointerup na platne (stejny ukazatel); prohlizec ji rozpozna jako klepnuti (do 6 px a 0,9 s) a udela vyber dilu
    function forwardTap(e) {
      var cv = canvas || (stage.querySelector && stage.querySelector("canvas"));
      if (!cv || typeof global.PointerEvent !== "function") return;
      var init = { bubbles: true, cancelable: true, clientX: e.clientX, clientY: e.clientY, pointerId: e.pointerId, pointerType: e.pointerType, isPrimary: e.isPrimary !== false, button: 0, buttons: 1 };
      try {
        cv.dispatchEvent(new global.PointerEvent("pointerdown", init));
        init.buttons = 0;
        cv.dispatchEvent(new global.PointerEvent("pointerup", init));
      } catch (x) { /* neni kriticke */ }
    }
    function finishDrag(restore) {
      var h = drag.h;
      if (drag.live) liveEnd(drag.live, !!restore);
      drag = null;
      h.el.classList.remove("drag", "stop"); layer.classList.remove("dragging");
      tip.style.display = "none";
      if (opts.dragState) opts.dragState(false, h.def);
      if (hasPending) { var p = pending; pending = null; hasPending = false; applyDesc(p); }      // popis, ktery prisel behem tazeni
      else { updateCaps(); update(); }
      relink();
    }
    function endDrag() { finishDrag(); }
    function cancelDrag() {
      var orig = drag.orig;
      // nejdriv vrat puvodni hodnoty (live: bez dotazu na server), TEPRVE potom ukonci tazeni: stranka pri dragState(false) hned dotazuje server s aktualnimi hodnotami -
      // kdyby se vracelo az po nem, odesla by se tazena hodnota a pozdni odpoved by puvodni hodnoty prepsala (Esc by tazenou hodnotu nechal)
      if (opts.applyPatch) opts.applyPatch(copy(orig), { live: true, cancel: true, source: "drag" });
      finishDrag(true);
    }

    function onKey(e) {
      if (e.key !== "Escape") return;
      if (drag) { e.preventDefault(); cancelDrag(); } else if (menu) { e.preventDefault(); closeMenu(); }
    }

    // sipky na uchytu: o `krok` (Shift = 10x); osa: <- -> / dolu nahoru, rovina: <- -> = podel Z, dolu nahoru = podel X
    function onHandleKey(h, e) {
      if (drag) return;
      var kx = 0, kz = 0, k = e.key, mult = e.shiftKey ? 10 : 1;
      if (k === "ArrowRight") kz = 1; else if (k === "ArrowLeft") kz = -1; else if (k === "ArrowUp") kx = 1; else if (k === "ArrowDown") kx = -1; else return;
      e.preventDefault();
      var d = h.def, krok = (d.krok || 1) * mult, patch = {};
      if (d.typ === "rovina") {
        var vx = valueOf(h, d.param_x, null), vz = valueOf(h, d.param_z, null);
        var c = constrainPlane(d, vx, vz, kx * krok * (d.faktor_x || 1), kz * krok * (d.faktor_z || 1));
        patch[d.param_x] = c.valueX; patch[d.param_z] = c.valueZ;
      } else {
        var v0 = valueOf(h, d.param, null), step = (kx + kz) * krok;
        var a = constrainAxis(d, v0, step / (d.faktor || 1));
        if (a.blocked) return;
        patch[d.param] = a.value;
      }
      if (opts.applyPatch) opts.applyPatch(patch, { live: false, source: "klavesnice" });
    }

    // -------------------------------------------------------------------------------------------------------------
    // stitek u uchytu pri tazeni
    // -------------------------------------------------------------------------------------------------------------
    function buildTip() {
      var d = drag.def, rows = drag.rows0;
      tip.textContent = ""; tipRows = [];
      tip.setAttribute("data-for", d.id);
      if (!(rows.length === 1 && String(rows[0].label).toLowerCase() === String(d.label || "").toLowerCase())) tip.appendChild(el("div", "t", d.label || d.id));
      rows.forEach(function (r) {
        var line = el("div", "r"), v = el("span", "v"), dl = el("span", "dl");
        line.setAttribute("data-param", r.param);
        line.appendChild(el("span", "l", r.label)); line.appendChild(v); line.appendChild(dl);
        tip.appendChild(line);
        tipRows.push({ r: r, line: line, v: v, dl: dl });
      });
      tip.appendChild(tipSt = el("div", "st"));
      tip.appendChild(el("div", "esc", T.esc));
      tip.style.display = "block";
      renderTip();
    }
    function renderTip() {
      if (!drag || !tipRows) return;
      var h = drag.h, d = drag.def, krok = d.krok, rows = rowsOf(h, drag.cur), info = drag.info || {};
      rows.forEach(function (r, i) {
        var t = tipRows[i];
        if (!t) return;
        var delta = r.value - t.r.value, dtxt = fmtDelta(delta, krok);
        var ju = (d.mereni && d.mereni.length) ? T.unit : (d.jednotka != null ? d.jednotka : T.unit);       // radky `mereni` jsou vzdy v mm; hlavni hodnota tahu v jednotce tahu (jednotka, napr. %)
        t.v.textContent = fmt(r.value, krok) + " " + ju;
        t.dl.textContent = dtxt + (dtxt === "±0" ? "" : " " + ju);
        t.dl.className = "dl" + (dtxt === "±0" ? " zero" : (delta < 0 ? " neg" : ""));
        t.line.setAttribute("data-value", String(Math.round(r.value * 100) / 100));
        t.line.setAttribute("data-delta", String(Math.round(delta * 100) / 100));
      });
      var st = "", bad = false, state = "";
      var gap = info.gap == null ? null : Math.floor(info.gap + 1e-6);          // mezera se uvadi zaokrouhlena dolu ("aspon N mm")
      if (info.blocked) { st = T.obstacle.replace("{n}", fmt(gap || 0)); bad = true; state = "blocked"; }
      else if (gap != null && gap <= 100) { st = T.toObstacle.replace("{n}", fmt(gap)); state = "near"; }
      else if (info.atMin) { st = T.atMin; state = "min"; }
      else if (info.atMax) { st = T.atMax; state = "max"; }
      else if (info.atLimit) { st = T.atLimit; state = "limit"; }
      tipSt.textContent = st; tipSt.className = "st" + (bad ? " bad" : "");
      tipSt.style.display = st ? "" : "none";
      tip.setAttribute("data-state", state);
      h.el.classList.toggle("stop", bad);
      tipW = tip.offsetWidth; tipH = tip.offsetHeight;
    }
    function placeTip() {
      if (!drag || !tipRows) return;
      var h = drag.h, off = coarse ? 42 : 26;
      var x = h.x - tipW / 2, y = h.y - tipH - off;
      if (y < 4) y = h.y + off;
      x = Math.max(4, Math.min(rel.w - tipW - 4, x)); y = Math.max(4, Math.min(rel.h - tipH - 4, y));
      tip.style.transform = "translate(" + x.toFixed(0) + "px," + y.toFixed(0) + "px)";
    }

    // -------------------------------------------------------------------------------------------------------------
    // opacny smer: mys v panelu na ovladaci -> cast a uchyty ve 3D
    // -------------------------------------------------------------------------------------------------------------
    function hoverParam(p) {
      p = p || null;
      if (p === panelParam) return;
      panelParam = p;
      markRelatedHandles(); draw();
    }

    // -------------------------------------------------------------------------------------------------------------
    // udalosti
    // -------------------------------------------------------------------------------------------------------------
    var passiveOff = { capture: true, passive: false }, passiveOn = { capture: true, passive: true };
    stage.addEventListener("pointermove", onStageMove);
    stage.addEventListener("pointerleave", function () { if (!menu) setHover(null, null); });
    stage.addEventListener("pointerdown", onStageDown, true);
    stage.addEventListener("pointermove", onStageMoveCapture, true);
    stage.addEventListener("pointerup", onStageUp, true);
    stage.addEventListener("pointercancel", onStageCancel, true);
    stage.addEventListener("contextmenu", function (e) { if (e.target === canvas) e.preventDefault(); }, true);
    stage.addEventListener("touchmove", onTouchMoveCapture, passiveOff);
    stage.addEventListener("touchend", onTouchEndCapture, passiveOn);
    stage.addEventListener("touchcancel", onTouchEndCapture, passiveOn);
    document.addEventListener("keydown", onKey, true);
    document.addEventListener("pointerdown", onDocDown, true);
    function closeOnResize() { if (menu) closeMenu(); }
    function closeOnWheel(e) { if (menu && !(menu.el && menu.el.contains(e.target))) closeMenu(); }
    global.addEventListener("resize", closeOnResize);
    global.addEventListener("wheel", closeOnWheel, { passive: true });

    function destroy() {
      destroyed = true;
      cancelLp();
      if (menu) closeMenu();
      setViewer(null);
      stage.removeEventListener("pointermove", onStageMove);
      stage.removeEventListener("pointerdown", onStageDown, true);
      stage.removeEventListener("pointermove", onStageMoveCapture, true);
      stage.removeEventListener("pointerup", onStageUp, true);
      stage.removeEventListener("pointercancel", onStageCancel, true);
      stage.removeEventListener("touchmove", onTouchMoveCapture, passiveOff);
      stage.removeEventListener("touchend", onTouchEndCapture, passiveOn);
      stage.removeEventListener("touchcancel", onTouchEndCapture, passiveOn);
      document.removeEventListener("keydown", onKey, true);
      document.removeEventListener("pointerdown", onDocDown, true);
      global.removeEventListener("resize", closeOnResize);
      global.removeEventListener("wheel", closeOnWheel);
      if (layer.parentNode) layer.parentNode.removeChild(layer);
    }

    // stav pro testy a ladeni
    function debug() {
      var hs = {};
      Object.keys(handles).forEach(function (id) {
        var h = handles[id];
        hs[id] = { dom: h.el.id, x: h.x, y: h.y, visible: h.vis, cap: h.cap.textContent, rel: h.rel, ang: h.ang };
      });
      return { handles: hs, parts: Object.keys(parts), hover: hov, hoverHandle: hovHandle, panelParam: panelParam, link: linkKey ? linkKey.split("|") : [],
               menu: menu ? { part: menu.partId, hit: menu.hit, items: [].map.call(menu.el.querySelectorAll(".mi"), function (n) { return { text: n.firstChild ? n.firstChild.textContent : "", disabled: n.classList.contains("dis") }; }) } : null,
               drag: drag ? { tah: drag.def.id, cur: drag.cur, start: drag.start, info: drag.info, live: !!drag.live } : null, rel: rel, hasDesc: !!desc, liveModel: !!live.ctx,
               tip: tip.style.display === "block" ? { text: tip.textContent, state: tip.getAttribute("data-state") } : null,
               outlines: [].map.call(svg.querySelectorAll("g.bx"), function (g) { return { id: g.getAttribute("data-id"), kind: g.getAttribute("class").replace("bx ", "") }; }) };
    }

    return { setViewer: setViewer, setDescription: setDescription, hoverParam: hoverParam, destroy: destroy, debug: debug, relayout: function () { measure(); update(); },
             plugin: plugin, liveBox: liveBox, liveRazitka: liveRazitka, version: VERSION };
  }

  global.V3DOvladani = { create: create, version: VERSION, TEXTS: TEXTS,
                         _t: { camFrom: camFrom, project: project, rayThrough: rayThrough, rayBox: rayBox, rayPlaneY: rayPlaneY, rayAxis: rayAxis, hull: hull,
                               constrainAxis: constrainAxis, constrainPlane: constrainPlane, fmt: fmt, fmtDelta: fmtDelta } };
})(typeof window !== "undefined" ? window : this);
