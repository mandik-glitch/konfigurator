// render-materialy-katalogu.js - panel "Materiály katalogu pro render": ÚČINNÁ PŘIŘAZOVACÍ TABULKA renderovacích
// materiálů (všechny položky katalogu mimo karoserie -> materiál z knihovny Vandr materiálů).
//
// Robert 2026-10-01: hliník všude alumi2, laminodesky cub_seda, elektrožlab bílá, perfopanely grey, neaktivní díly SSE
// nechat. Panel je VIZUÁLNÍ (výchozí pohled = mřížka miniatur + knihovna materiálů jako koule), tabulkový režim je
// přepínač pro hledání a filtry. Přiřazení klikem: vyber položky (nebo celou skupinu) a klepni na kartu materiálu,
// nebo přetáhni položku na kartu.
//
// KONTRAKT (stejný vzor jako render-panel.js): GLOBÁLNÍ materialyKataloguHtml() vrací HTML panelu a
// materialyKataloguInit(wrap) ho oživí (volá se po každém překreslení složky, panel se vytváří znovu - stav
// filtrů/výběru drží modul). Žádná závislost na jiných souborech admina (escape, API volání jsou tady).
// Backend: api/render_materialy.py (/api/admin/render-materialy*). Render materiál z téhle tabulky zatím NEBERE
// (vypnuto, dokud se nezapojí render_material_key() a nezapne app_settings.render_materialy_katalogu_aktivni).
//
// Písmo a velikosti: WORKFLOW pravidlo 6 (systémové písmo se dědí, názvy a formulářová pole 16px, drobné popisky
// a značky 10.5-14px). Vzhled: HUD (pravidlo 34) - seříznuté rohy + zelené rohové závorky --hud-accent jako
// .dash-card v admin.html, mono popisky. Mobil 390 px: 2 sloupce dlaždic, tabulka se skládá do karet.
(function () {
  "use strict";

  var API = "/api/admin/render-materialy";
  var THREE_CDN = "https://cdn.jsdelivr.net/npm/three@0.128.0/";

  // ---------- stav modulu (přežívá překreslení složky) ----------
  var st = {
    data: null,            // odpověď GET /api/admin/render-materialy
    nacitam: false,
    chyba: null,           // { text, ddl }
    vse: false,            // i neaktivní SSE
    rezim: "mrizka",       // "mrizka" | "tabulka"
    skup: "stav",          // "stav" | "material" | "kategorie" | "zadne"
    hledej: "", fStav: "", fMat: "", fKat: "",
    razeni: { k: "nazev", d: 1 },
    vyber: new Set(),      // klíče "zdroj:id"
    zprava: null,          // { text, typ: "ok"|"chyba" }
    detail: null,          // { id, data, nacitam }
  };
  var root = null;         // aktuální #rmkPanel
  var dragIds = null;      // id právě tažených položek

  // ---------- pomocné ----------
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[c];
    });
  }
  function q(sel, ctx) { return (ctx || root).querySelector(sel); }
  function qa(sel, ctx) { return Array.prototype.slice.call((ctx || root).querySelectorAll(sel)); }
  function kl(p) { return p.zdroj + ":" + p.id; }
  function pocetText(n, a, b, c) { return n === 1 ? a : (n >= 2 && n <= 4 ? b : c); }

  var STAV_TEXT = { OK: "OK", SPORNE: "SPORNÉ", VYNECHANO: "VYNECHÁNO", NOVE: "NOVÉ" };
  var ODKUD_TEXT = {
    cast: "z části", karta: "z karty", cfg: "z dílu katalogu", kategorie: "z kategorie", mapa: "z mapy barev",
    vychozi: "beze změny", neplatny: "neplatný klíč", nativni: "nativní (Vandr)", vypnuto: "beze změny",
  };

  function api(method, url, body) {
    var opt = { method: method, credentials: "same-origin" };
    if (body !== undefined) { opt.headers = { "Content-Type": "application/json" }; opt.body = JSON.stringify(body); }
    return fetch(url, opt).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        if (!r.ok) {
          var e = new Error(d.error || ("HTTP " + r.status));
          e.status = r.status; e.data = d;
          throw e;
        }
        return d;
      });
    });
  }

  function mapaMaterialu() {
    var m = {};
    ((st.data && st.data.knihovna) || []).forEach(function (k) { m[k.klic] = k; });
    return m;
  }

  // ---------- náhled materiálu: koule vykreslená three.js (r128, RoomEnvironment), fallback barevný kruh ----------
  function mix(hex, k, cil) {
    var m = /^#?([0-9a-f]{6})$/i.exec(hex || "");
    if (!m) return hex || "#888888";
    var n = parseInt(m[1], 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    function f(c) { return Math.max(0, Math.min(255, Math.round(c + (cil - c) * k))); }
    return "#" + [f(r), f(g), f(b)].map(function (c) { return ("0" + c.toString(16)).slice(-2); }).join("");
  }
  function cssKoule(three) {
    var c = (three && three.color) || "#888888";
    var kov = (three && three.metalness) || 0;
    var svetlo = mix(c, kov > 0.6 ? 0.78 : 0.5, 255);
    var tmave = mix(c, kov > 0.6 ? 0.7 : 0.5, 0);
    return "radial-gradient(circle at 34% 28%, " + svetlo + " 0%, " + c + " 48%, " + tmave + " 100%)";
  }

  var sphere = { stav: "nezacato", url: {} };   // url[klic] = dataURL (jednou na material)

  function nactiSkript(src) {
    return new Promise(function (ok, ne) {
      var s = document.createElement("script");
      s.src = src; s.async = false;
      s.onload = function () { ok(); };
      s.onerror = function () { ne(new Error("skript " + src)); };
      document.head.appendChild(s);
    });
  }
  function nactiThree() {
    if (window.THREE && window.THREE.RoomEnvironment) return Promise.resolve(true);
    if (sphere.threePromise) return sphere.threePromise;
    sphere.threePromise = Promise.resolve()
      .then(function () { return window.THREE ? null : nactiSkript(THREE_CDN + "build/three.min.js"); })
      .then(function () { return window.THREE && window.THREE.RoomEnvironment ? null : nactiSkript(THREE_CDN + "examples/js/environments/RoomEnvironment.js"); })
      .then(function () { return !!(window.THREE && window.THREE.RoomEnvironment); })
      .catch(function () { return false; });
    return sphere.threePromise;
  }
  function vykresliKoule(knihovna) {
    var T = window.THREE;
    var canvas = document.createElement("canvas");
    canvas.width = canvas.height = 160;
    var r = new T.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
    r.setPixelRatio(1); r.setSize(160, 160, false);
    r.outputEncoding = T.sRGBEncoding;
    // r128: hex barva je v "linearnim" prostoru, proto .convertSRGBToLinear() u barvy materialu (jinak vyblednou)
    r.toneMapping = T.NoToneMapping;       // bez ACES: barva koule ma odpovidat barve materialu (cervena nesmi vyblednout do ruzova)
    r.setClearColor(0x000000, 0);
    var pm = new T.PMREMGenerator(r);
    var scene = new T.Scene();
    scene.environment = pm.fromScene(new T.RoomEnvironment(), 0.04).texture;
    var cam = new T.PerspectiveCamera(32, 1, 0.1, 20);
    cam.position.set(0, 0, 4.3);
    var key = new T.DirectionalLight(0xffffff, 0.35);
    key.position.set(-2, 3, 4);
    scene.add(key);
    var geo = new T.SphereGeometry(1, 56, 40);
    var out = {};
    knihovna.forEach(function (m) {
      var p = m.three || {};
      var mat = new T.MeshPhysicalMaterial({
        color: new T.Color(p.color || "#888888").convertSRGBToLinear(), metalness: +p.metalness || 0, roughness: p.roughness == null ? 0.5 : +p.roughness,
        clearcoat: +p.clearcoat || 0, clearcoatRoughness: +p.clearcoatRoughness || 0, envMapIntensity: 0.55,
      });
      var mesh = new T.Mesh(geo, mat);
      scene.add(mesh);
      r.render(scene, cam);
      out[m.klic] = canvas.toDataURL("image/png");
      scene.remove(mesh);
      mat.dispose();
    });
    geo.dispose(); pm.dispose(); r.dispose();
    return out;
  }
  function zajistiKoule() {
    var kn = (st.data && st.data.knihovna) || [];
    var chybi = kn.filter(function (m) { return !sphere.url[m.klic]; });
    if (!chybi.length || sphere.stav === "selhalo") return;
    nactiThree().then(function (ok) {
      if (!ok) { sphere.stav = "selhalo"; return; }
      try {
        var vysl = vykresliKoule(chybi);
        Object.keys(vysl).forEach(function (k) { sphere.url[k] = vysl[k]; });
        sphere.stav = "ok";
        if (root && root.isConnected) aplikujKoule();
      } catch (e) {
        sphere.stav = "selhalo";
      }
    });
  }
  // Pozadí koulí/koleček se nastavuje JEDNÍM stylesheetem (pravidlo na materiál podle atributu data-k), ne inline
  // v každém prvku: data URL koule má desítky kB a prvků je stovky. Dokud koule není vykreslená, je tam CSS gradient.
  function aplikujKoule() {
    var el = q("#rmkKouleCss");
    if (!el) return;
    el.textContent = ((st.data && st.data.knihovna) || []).map(function (m) {
      var u = sphere.url[m.klic];
      return ".rmk [data-k=\"" + String(m.klic).replace(/[^a-z0-9_]/gi, "") + "\"]{background-image:" + (u ? "url(" + u + ")" : cssKoule(m.three)) + ";}";
    }).join("");
  }
  function stylKoule() { return ""; }

  // ---------- HTML panelu ----------
  var CSS = [
    ".rmk{--rmk-a:var(--hud-accent,#0e8a45);position:relative;margin:0 0 12px;padding:14px 16px;color:var(--text,inherit);",
    "background:var(--panel-bg,rgba(127,127,127,.08));border:1px solid var(--border-soft2,rgba(127,127,127,.3));",
    "clip-path:polygon(0 12px,12px 0,100% 0,100% calc(100% - 12px),calc(100% - 12px) 100%,0 100%);box-sizing:border-box;}",
    ".rmk *{box-sizing:border-box;}",
    ".rmk::before,.rmk::after{content:'';position:absolute;width:14px;height:14px;pointer-events:none;}",
    ".rmk::before{top:1px;right:1px;border-top:2px solid var(--rmk-a);border-right:2px solid var(--rmk-a);}",
    ".rmk::after{bottom:1px;left:1px;border-bottom:2px solid var(--rmk-a);border-left:2px solid var(--rmk-a);}",
    ".rmk-mono{font-family:'SF Mono','Cascadia Code','Consolas',monospace;}",
    ".rmk-lab{font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--text-muted,#888);font-family:'SF Mono','Cascadia Code','Consolas',monospace;}",
    ".rmk-hlava{display:flex;gap:10px 16px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:6px;}",
    ".rmk-titul{font-size:16px;font-weight:600;}",
    ".rmk-pod{font-size:12px;color:var(--text-muted,#888);line-height:1.45;margin:2px 0 10px;max-width:70em;} .rmk-pod summary{cursor:pointer;font-size:14px;min-height:28px;color:var(--text2,inherit);}",
    ".rmk-chips{display:flex;gap:6px;flex-wrap:wrap;align-items:center;}",
    ".rmk-chip{font-size:12px;padding:3px 9px;border:1px solid var(--border-soft2,#8884);background:transparent;color:var(--text2,inherit);cursor:pointer;",
    "font-family:'SF Mono','Cascadia Code','Consolas',monospace;clip-path:polygon(0 5px,5px 0,100% 0,100% calc(100% - 5px),calc(100% - 5px) 100%,0 100%);min-height:30px;}",
    ".rmk-chip[aria-pressed=true]{border-color:var(--rmk-a);color:var(--text,inherit);box-shadow:inset 0 0 0 1px var(--rmk-a);}",
    ".rmk-chip.sporne{color:var(--error,#d44);border-color:var(--error,#d44);}",
    ".rmk-chip.nove{color:var(--warn,#d90);}",
    ".rmk-flag{font-size:12px;color:var(--text-muted,#888);}",
    ".rmk-flag.zap{color:var(--success,#2a7);}",
    ".rmk-zprava{min-height:22px;font-size:14px;margin:4px 0 8px;color:var(--text2,inherit);}",
    ".rmk-zprava.ok{color:var(--success,#2a7);} .rmk-zprava.chyba{color:var(--error,#d44);font-weight:600;}",
    ".rmk-ddl{border:1px solid var(--error,#d44);padding:10px 12px;font-size:14px;line-height:1.5;color:var(--text,inherit);}",
    /* knihovna */
    ".rmk-knihovna{display:grid;grid-template-columns:repeat(auto-fill,minmax(128px,1fr));gap:8px;margin:6px 0 12px;}",
    ".rmk-karta{position:relative;display:flex;flex-direction:column;align-items:center;gap:3px;padding:8px 6px 7px;text-align:center;cursor:pointer;",
    "border:1px solid var(--border-soft2,#8885);background:var(--panel-bg-alt,rgba(127,127,127,.1));min-height:44px;",
    "clip-path:polygon(0 8px,8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%);}",
    ".rmk-karta:hover,.rmk-karta:focus-visible{border-color:var(--rmk-a);outline:none;}",
    ".rmk-karta.cil{border-color:var(--rmk-a);box-shadow:inset 0 0 0 2px var(--rmk-a);}",
    ".rmk-karta.filtr{box-shadow:inset 0 0 0 2px var(--accent,#6af);}",
    ".rmk-karta.vypnuta{opacity:.45;cursor:not-allowed;}",
    ".rmk-karta.zrusit{justify-content:center;border-style:dashed;}",
    ".rmk-koule{display:block;width:64px;height:64px;border-radius:50%;background-size:cover;background-position:center;background-repeat:no-repeat;}",
    ".rmk-zrusit-ikona{display:block;width:64px;height:64px;border-radius:50%;border:1px dashed var(--text-muted,#888);background-image:repeating-linear-gradient(45deg,#8886 0 3px,transparent 3px 6px);}",
    ".rmk-bod.zadna{background-image:repeating-linear-gradient(45deg,#8886 0 3px,transparent 3px 6px);}",
    ".rmk-karta-nazev{font-size:14px;line-height:1.25;font-weight:600;color:var(--text,inherit);}",
    ".rmk-meta{font-size:12px;color:var(--text-muted,#888);line-height:1.35;}",
    ".rmk-vlajka{font-size:10.5px;padding:1px 6px;color:var(--warn,#d90);border:1px solid var(--warn,#d90);}",
    /* nástroje */
    ".rmk-nastroje{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:6px 0 10px;}",
    ".rmk-nastroje input[type=search],.rmk-nastroje select,.rmk-modal select,.rmk-tab select,.rmk-lista select{font-size:16px;min-height:38px;max-width:100%;}",
    ".rmk-nastroje input[type=search]{flex:1 1 200px;min-width:0;}",
    ".rmk-btn{font-size:14px;min-height:38px;padding:4px 12px;cursor:pointer;}",
    ".rmk-btn.hlavni{border-color:var(--rmk-a);}",
    ".rmk-prepinac{display:inline-flex;}",
    ".rmk-prepinac .rmk-btn[aria-pressed=true]{box-shadow:inset 0 0 0 2px var(--rmk-a);}",
    ".rmk-popis-vyberu{font-size:12px;color:var(--text-muted,#888);}",
    /* mřížka */
    ".rmk-skup{margin:0 0 14px;}",
    ".rmk-skup-hlava{display:flex;gap:10px;align-items:center;justify-content:space-between;margin:0 0 6px;padding:4px 0;border-bottom:1px solid var(--border-soft2,#8884);}",
    ".rmk-skup-nazev{font-size:16px;font-weight:600;display:flex;gap:8px;align-items:center;}",
    ".rmk-mrizka{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;}",
    ".rmk-dlazdice{position:relative;display:flex;flex-direction:column;gap:4px;padding:6px 6px 8px;cursor:pointer;user-select:none;",
    "border:1px solid var(--border-soft2,#8885);background:var(--panel-bg-alt,rgba(127,127,127,.08));",
    "clip-path:polygon(0 8px,8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%);}",
    ".rmk-dlazdice:hover,.rmk-dlazdice:focus-visible{border-color:var(--rmk-a);outline:none;}",
    ".rmk-dlazdice.vybrano{border-color:var(--rmk-a);box-shadow:inset 0 0 0 2px var(--rmk-a);background:color-mix(in srgb,var(--rmk-a) 14%,var(--panel-bg-alt,transparent));}",
    ".rmk-dlazdice.sporne{border-color:var(--error,#d44);}",
    ".rmk-dlazdice.sporne.vybrano{box-shadow:inset 0 0 0 2px var(--error,#d44);}",
    ".rmk-dlazdice.vynechano{opacity:.62;}",
    ".rmk-nahled{position:relative;aspect-ratio:1/1;width:100%;display:flex;align-items:center;justify-content:center;overflow:hidden;",
    "background:var(--thumb-bg,#1114);color:var(--text-muted,#888);font-size:28px;}",
    ".rmk-nahled img{width:100%;height:100%;object-fit:contain;display:block;}",
    ".rmk-tecka{position:absolute;top:5px;right:5px;width:26px;height:26px;border-radius:50%;background-size:cover;background-position:center;",
    "border:2px solid var(--panel-bg,#fff);box-shadow:0 0 0 1px var(--text-muted,#888);}",
    ".rmk-tecka.zadna{background-image:repeating-linear-gradient(45deg,#8886 0 3px,transparent 3px 6px)!important;}",
    ".rmk-tecka.sporna{box-shadow:0 0 0 2px var(--error,#d44);}",
    ".rmk-nazev{font-size:16px;line-height:1.3;word-break:break-word;color:var(--text,inherit);}",
    ".rmk-odznak{display:inline-block;font-size:10.5px;padding:1px 6px;letter-spacing:.04em;font-family:'SF Mono','Cascadia Code','Consolas',monospace;border:1px solid currentColor;}",
    ".rmk-odznak.SPORNE{color:var(--error,#d44);} .rmk-odznak.NOVE{color:var(--warn,#d90);} .rmk-odznak.OK{color:var(--success,#2a7);} .rmk-odznak.VYNECHANO{color:var(--text-muted,#888);}",
    ".rmk-detail-btn{position:absolute;top:5px;left:5px;min-width:34px;min-height:34px;font-size:16px;line-height:1;padding:0;cursor:pointer;opacity:.9;}",
    ".rmk-vyber-mark{position:absolute;top:44px;left:7px;display:none;font-size:12px;padding:0 5px;background:var(--rmk-a);color:#fff;}",
    ".rmk-dlazdice.vybrano .rmk-vyber-mark{display:block;}",
    /* tabulka */
    ".rmk-tab-obal{overflow-x:auto;}",
    ".rmk-tab{width:100%;border-collapse:collapse;font-size:14px;}",
    ".rmk-tab th{text-align:left;font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;font-weight:600;color:var(--text-muted,#888);",
    "padding:6px 8px;border-bottom:1px solid var(--border-soft2,#8884);white-space:nowrap;cursor:pointer;font-family:'SF Mono','Cascadia Code','Consolas',monospace;}",
    ".rmk-tab td{padding:5px 8px;border-bottom:1px solid var(--border-faint,#8883);vertical-align:middle;}",
    ".rmk-tab tr.sporne td{background:color-mix(in srgb,var(--error,#d44) 12%,transparent);}",
    ".rmk-tab tr.vybrano td{background:color-mix(in srgb,var(--rmk-a) 16%,transparent);}",
    ".rmk-tab tr.vynechano td{opacity:.65;}",
    ".rmk-tab td.nazev{font-size:16px;line-height:1.3;}",
    ".rmk-mini{width:40px;height:40px;object-fit:contain;background:var(--thumb-bg,#1114);display:block;}",
    ".rmk-bod{display:inline-block;width:16px;height:16px;border-radius:50%;vertical-align:middle;margin-right:6px;background-size:cover;border:1px solid var(--text-muted,#888);}",
    ".rmk-sw{display:inline-block;width:14px;height:14px;vertical-align:middle;margin-right:5px;border:1px solid var(--text-muted,#888);}",
    /* lišta */
    ".rmk-lista{position:sticky;bottom:0;z-index:5;display:none;gap:8px 12px;align-items:center;flex-wrap:wrap;margin:10px -16px -14px;padding:10px 16px;",
    "background:var(--panel-bg,#222);border-top:2px solid var(--rmk-a);}",
    ".rmk-lista.zap{display:flex;}",
    /* detail */
    ".rmk-modal-pozadi{position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;padding:12px;}",
    ".rmk-modal{position:relative;width:min(760px,100%);max-height:calc(100vh - 24px);overflow:auto;padding:16px;background:var(--panel-bg,#222);color:var(--text,inherit);",
    "border:1px solid var(--rmk-a);clip-path:polygon(0 12px,12px 0,100% 0,100% calc(100% - 12px),calc(100% - 12px) 100%,0 100%);}",
    ".rmk-modal h3{margin:0 0 4px;font-size:16px;line-height:1.3;padding-right:44px;}",
    ".rmk-zavrit{position:absolute;top:8px;right:10px;min-width:40px;min-height:40px;font-size:18px;cursor:pointer;}",
    ".rmk-modal-telo{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start;margin-top:8px;}",
    ".rmk-fotky{display:flex;flex-direction:column;gap:10px;width:min(360px,100%);}",
    ".rmk-fotky .rmk-velky{width:100%;}",
    ".rmk-velky{width:200px;max-width:100%;aspect-ratio:1/1;background:var(--thumb-bg,#1114);display:flex;align-items:center;justify-content:center;font-size:44px;color:var(--text-muted,#888);}",
    ".rmk-velky img{width:100%;height:100%;object-fit:contain;}",
    ".rmk-info{flex:1 1 280px;min-width:0;font-size:14px;line-height:1.5;}",
    ".rmk-info dl{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;margin:0 0 8px;}",
    ".rmk-info dt{color:var(--text-muted,#888);font-size:12px;} .rmk-info dd{margin:0;word-break:break-word;}",
    ".rmk-navrh{border:1px dashed var(--border-soft2,#8886);padding:8px 10px;margin:8px 0;font-size:14px;}",
    ".rmk-casti{width:100%;border-collapse:collapse;margin-top:6px;font-size:14px;}",
    ".rmk-casti td,.rmk-casti th{padding:4px 6px;border-bottom:1px solid var(--border-faint,#8883);text-align:left;vertical-align:middle;}",
    ".rmk-casti th{font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--text-muted,#888);font-weight:600;}",
    "@media (max-width:700px){",
    ".rmk{padding:12px 12px;} .rmk-lista{margin:10px -12px -12px;padding:8px 12px;}",
    ".rmk-mrizka{grid-template-columns:repeat(2,minmax(0,1fr));}",
    ".rmk-knihovna{grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;} .rmk-koule{width:52px;height:52px;} .rmk-karta-nazev{font-size:12.5px;}",
    ".rmk-tab thead{display:none;} .rmk-tab,.rmk-tab tbody,.rmk-tab tr,.rmk-tab td{display:block;width:100%;}",
    ".rmk-tab tr{display:grid;grid-template-columns:auto 44px 1fr;gap:2px 8px;padding:8px 0;border-bottom:1px solid var(--border-soft2,#8884);}",
    ".rmk-tab td{border:0;padding:1px 0;} .rmk-tab td.nazev{grid-column:3;} .rmk-tab td.sel{grid-column:1;grid-row:1;} .rmk-tab td.mini{grid-column:2;grid-row:1;}",
    ".rmk-tab td.dalsi{grid-column:1/-1;font-size:12px;}",
    ".rmk-modal{padding:12px;} .rmk-velky{width:100%;max-width:240px;} .rmk-modal select{width:100%;}",
    ".rmk-casti,.rmk-casti tbody,.rmk-casti tr,.rmk-casti td{display:block;width:100%;} .rmk-casti thead{display:none;}",
    ".rmk-casti tr{padding:6px 0;border-bottom:1px solid var(--border-soft2,#8884);} .rmk-casti td{border:0;padding:1px 0;}",
    ".rmk-hlava{align-items:flex-start;}",
    "}",
  ].join("");

  function materialyKataloguHtml() {
    return "<div id=\"rmkPanel\" class=\"rmk\" data-rmk=\"1\"><style>" + CSS + "</style><style id=\"rmkKouleCss\"></style>" +
      "<div class=\"rmk-hlava\"><div><div class=\"rmk-lab\">Render · katalog</div><div class=\"rmk-titul\">Materiály katalogu pro render</div></div>" +
      "<div class=\"rmk-chips\" id=\"rmkSouhrn\"></div></div>" +
      "<details class=\"rmk-pod\" id=\"rmkNapoveda\"><summary>Jak to funguje</summary>Účinná přiřazovací tabulka: každá položka katalogu (mimo karoserie) a materiál z knihovny Vandr materiálů, " +
      "který se pro ni použije. Vyber položky (klepnutím, nebo celou skupinu) a klepni na materiál v knihovně = přiřazení; " +
      "položku jde i přetáhnout na materiál. Bez výběru klepnutí na materiál jen filtruje. Pořadí hledání materiálu: část tělesa, karta, díl katalogu, " +
      "kategorie, mapa barev, jinak beze změny.</details>" +
      "<div class=\"rmk-flag\" id=\"rmkFlag\"></div>" +
      "<div class=\"rmk-zprava\" id=\"rmkZprava\" role=\"status\" aria-live=\"polite\"></div>" +
      "<div id=\"rmkDdl\"></div>" +
      "<div class=\"rmk-lab\">Knihovna materiálů</div><div class=\"rmk-knihovna\" id=\"rmkKnihovna\"><div class=\"rmk-meta\">načítám…</div></div>" +
      "<div class=\"rmk-nastroje\">" +
        "<span class=\"rmk-prepinac\" role=\"group\" aria-label=\"Režim zobrazení\">" +
          "<button type=\"button\" class=\"rmk-btn\" data-rmk-rezim=\"mrizka\">▦ Mřížka</button>" +
          "<button type=\"button\" class=\"rmk-btn\" data-rmk-rezim=\"tabulka\">☰ Tabulka</button></span>" +
        "<input type=\"search\" id=\"rmkHledej\" placeholder=\"Hledat název, SKU, kategorii…\" aria-label=\"Hledat\">" +
        "<select id=\"rmkFStav\" aria-label=\"Stav\"><option value=\"\">všechny stavy</option><option value=\"SPORNE\">sporné</option>" +
          "<option value=\"NOVE\">nové (bez návrhu)</option><option value=\"OK\">OK</option><option value=\"VYNECHANO\">vynechané</option></select>" +
        "<select id=\"rmkFMat\" aria-label=\"Materiál\"></select>" +
        "<select id=\"rmkFKat\" aria-label=\"Kategorie\"></select>" +
        "<select id=\"rmkSkup\" aria-label=\"Seskupit\"><option value=\"stav\">seskupit: stav</option><option value=\"material\">seskupit: materiál</option>" +
          "<option value=\"kategorie\">seskupit: kategorie</option><option value=\"zadne\">bez seskupení</option></select>" +
        "<label class=\"rmk-popis-vyberu\"><input type=\"checkbox\" id=\"rmkVse\"> i neaktivní díly SSE</label>" +
        "<button type=\"button\" class=\"rmk-btn\" data-rmk-akce=\"vybrat-vse\">Vybrat zobrazené</button>" +
      "</div>" +
      "<div id=\"rmkObsah\"></div>" +
      "<div class=\"rmk-lista\" id=\"rmkLista\"></div>" +
      "<div id=\"rmkDetail\"></div>" +
      "</div>";
  }

  // ---------- filtrování, řazení, seskupování ----------
  function polozky() { return (st.data && st.data.polozky) || []; }
  function filtrovane() {
    var h = st.hledej.trim().toLowerCase();
    var vys = polozky().filter(function (p) {
      if (st.fStav && p.stav !== st.fStav) return false;
      if (st.fMat === "__zadny__") { if (p.klic_efektivni) return false; }
      else if (st.fMat && p.klic_efektivni !== st.fMat) return false;
      if (st.fKat && String(p.category_id == null ? "__bez__" : p.category_id) !== st.fKat) return false;
      if (h) {
        var s = (p.nazev + " " + (p.sku || "") + " " + (p.kategorie || "") + " " + p.id).toLowerCase();
        if (s.indexOf(h) < 0) return false;
      }
      return true;
    });
    var k = st.razeni.k, d = st.razeni.d;
    var mapa = mapaMaterialu();
    function hodnota(p) {
      switch (k) {
        case "kategorie": return p.kategorie || "";
        case "barva": return p.barva_dnes || "";
        case "vlastni": return p.klic_vlastni || "";
        case "efektivni": return p.klic_efektivni ? (mapa[p.klic_efektivni] ? mapa[p.klic_efektivni].poradi : 999) : 9999;
        case "odkud": return p.odkud || "";
        case "stav": return ["SPORNE", "NOVE", "OK", "VYNECHANO"].indexOf(p.stav);
        case "telesa": return p.telesa || 0;
        default: return (p.nazev || "").toLowerCase();
      }
    }
    vys.sort(function (a, b) {
      var x = hodnota(a), y = hodnota(b);
      if (x < y) return -d;
      if (x > y) return d;
      return (a.nazev || "").localeCompare(b.nazev || "", "cs");
    });
    return vys;
  }
  function skupiny(vys) {
    if (st.skup === "zadne") return [{ nazev: "", polozky: vys }];
    var mapa = mapaMaterialu(), g = {}, poradi = [];
    vys.forEach(function (p) {
      var n;
      if (st.skup === "material") n = p.klic_efektivni ? (mapa[p.klic_efektivni] ? mapa[p.klic_efektivni].nazev : p.klic_efektivni) : "— beze změny (bez materiálu)";
      else if (st.skup === "kategorie") n = p.kategorie || "— bez kategorie";
      else n = STAV_TEXT[p.stav] || p.stav;
      if (!g[n]) { g[n] = []; poradi.push(n); }
      g[n].push(p);
    });
    if (st.skup === "stav") {
      var o = ["SPORNÉ", "NOVÉ", "OK", "VYNECHÁNO"];
      poradi.sort(function (a, b) { return o.indexOf(a) - o.indexOf(b); });
    } else if (st.skup === "material") {
      var poradiMat = {};
      ((st.data && st.data.knihovna) || []).forEach(function (m) { poradiMat[m.nazev] = m.poradi; });
      poradi.sort(function (a, b) { return (poradiMat[a] == null ? 9999 : poradiMat[a]) - (poradiMat[b] == null ? 9999 : poradiMat[b]); });
    } else {
      poradi.sort(function (a, b) { return a.localeCompare(b, "cs"); });
    }
    return poradi.map(function (n) { return { nazev: n, polozky: g[n] }; });
  }

  // ---------- vykreslení ----------
  function renderSouhrn() {
    var el = q("#rmkSouhrn");
    if (!el) return;
    var s = st.data && st.data.souhrn;
    if (!s) { el.innerHTML = ""; return; }
    function chip(stav, text, cls) {
      return "<button type=\"button\" class=\"rmk-chip " + (cls || "") + "\" data-rmk-chip=\"" + stav + "\" aria-pressed=\"" + (st.fStav === stav) + "\">" + text + "</button>";
    }
    el.innerHTML = chip("OK", "OK " + s.OK) + chip("SPORNE", "sporné " + s.SPORNE, "sporne") + chip("NOVE", "nové " + s.NOVE, "nove") +
      chip("VYNECHANO", "vynecháno " + s.VYNECHANO) + (s.skryto_sse ? "<span class=\"rmk-meta\">skryto SSE: " + s.skryto_sse + "</span>" : "");
    var f = q("#rmkFlag");
    if (f) {
      f.className = "rmk-flag" + (st.data.flag_aktivni ? " zap" : "");
      f.textContent = st.data.flag_aktivni
        ? "Render tuto tabulku POUŽÍVÁ (app_settings." + st.data.flag_klic + " je zapnuto)."
        : "Render tuto tabulku zatím NEPOUŽÍVÁ (vypnuto) - tady se jen připravuje přiřazení, nic se nerenderuje jinak.";
    }
  }

  function renderKnihovna() {
    var el = q("#rmkKnihovna");
    if (!el) return;
    var kn = (st.data && st.data.knihovna) || [];
    var s = (st.data && st.data.souhrn && st.data.souhrn.po_materialech) || {};
    var vyb = st.vyber.size;
    el.innerHTML = kn.map(function (m) {
      var cls = "rmk-karta" + (!m.aktivni ? " vypnuta" : "") + (vyb && m.aktivni ? " cil" : "") + (st.fMat === m.klic ? " filtr" : "");
      var tit = m.nazev + (m.nazev_blender ? " - materiál v Blenderu: '" + m.nazev_blender + "'" : "") + (m.knihovna_soubor ? " (" + m.knihovna_soubor + ")" : "") +
        (m.poznamka ? "\n" + m.poznamka : "");
      return "<div class=\"" + cls + "\" role=\"button\" tabindex=\"0\" data-rmk-mat=\"" + esc(m.klic) + "\" title=\"" + esc(tit) + "\" aria-label=\"" + esc(vyb ? "Přiřadit " + m.nazev + " (" + vyb + " vybraných)" : "Filtrovat podle " + m.nazev) + "\">" +
        "<span class=\"rmk-koule\" data-k=\"" + esc(m.klic) + "\"></span>" +
        "<div class=\"rmk-karta-nazev\">" + esc(m.nazev) + "</div>" +
        "<div class=\"rmk-meta\"><span class=\"rmk-mono\">" + esc(m.klic) + "</span> · <b>" + (s[m.klic] || 0) + "</b> pol.</div>" +
        (!m.knihovna_ok ? "<span class=\"rmk-vlajka\" title=\"Soubor " + esc(m.knihovna_soubor || "?") + " na Sdíleném disku zatím není - render s tímto materiálem nemá co načíst.\">knihovna chybí</span>" : "") +
        "</div>";
    }).join("") +
      "<div class=\"rmk-karta zrusit" + (vyb ? " cil" : " vypnuta") + "\" role=\"button\" tabindex=\"0\" data-rmk-mat=\"__zrusit__\" aria-label=\"Zrušit přiřazení vybraným\">" +
      "<span class=\"rmk-zrusit-ikona\"></span><div class=\"rmk-karta-nazev\">Zrušit přiřazení</div><div class=\"rmk-meta\">beze změny</div></div>";
  }

  // Robert 2026-10-02: "musis mi ukazat produkty, abych k nim mohl rict material" - misto katalogove ikony
  // (nahled) se u karet e-shopu ukazuje FOTKA produktu z galerie (/content-files/gallery/products/<id>/2.jpg =
  // hlavni, 1.jpg = schema/druha), a kdyz neexistuje, spadne se na nahled.
  function fotoUrl(p, n) {
    return p.zdroj === "product" && p.id != null ? "/content-files/gallery/products/" + encodeURIComponent(p.id) + "/" + n + ".jpg" : "";
  }
  function imgHtml(p, n, extra) {
    var u = fotoUrl(p, n);
    var zaloha = p.nahled ? esc(p.nahled) : "";
    if (!u) return zaloha ? "<img src=\"" + zaloha + "\" alt=\"\" loading=\"lazy\"" + (extra || "") + ">" : "<span aria-hidden=\"true\">◫</span>";
    return "<img src=\"" + esc(u) + "\" alt=\"\" loading=\"lazy\"" + (extra || "") + " data-zaloha=\"" + zaloha + "\" onerror=\"if(this.dataset.zaloha&&this.src.indexOf(this.dataset.zaloha)<0){this.src=this.dataset.zaloha;}else{this.style.visibility='hidden';}\">";
  }
  function nahledHtml(p, trida) {
    return imgHtml(p, 2);
  }
  function teckaHtml(p, mapa) {
    var m = p.klic_efektivni ? mapa[p.klic_efektivni] : null;
    var tit = (m ? m.nazev : (p.odkud === "nativni" ? "nativní materiál (Vandr)" : "beze změny (materiál z modelu)")) + " · " + (ODKUD_TEXT[p.odkud] || p.odkud) +
      (p.odkud === "kategorie" && p.odkud_nazev ? " (" + p.odkud_nazev + ")" : "") + (p.neplatny_klic ? " · neplatný klíč '" + p.neplatny_klic + "'" : "");
    if (!m) return "<span class=\"rmk-tecka zadna" + (p.stav === "SPORNE" ? " sporna" : "") + "\" title=\"" + esc(tit) + "\"></span>";
    return "<span class=\"rmk-tecka" + (p.stav === "SPORNE" ? " sporna" : "") + "\" data-k=\"" + esc(m.klic) + "\" title=\"" + esc(tit) + "\"></span>";
  }
  function dlazdiceHtml(p, mapa) {
    var vyb = st.vyber.has(kl(p));
    var meta = "<span class=\"rmk-mono\">" + esc(p.sku || p.id) + "</span> <span class=\"rmk-odznak " + p.stav + "\">" + STAV_TEXT[p.stav] + "</span>" +
      (p.telesa > 1 ? " <span class=\"rmk-meta\">" + p.telesa + " těles" + (p.casti_pocet ? " (" + p.casti_pocet + " ručně)" : "") + "</span>" : "");
    var tit = p.nazev + (p.pravidlo ? "\n" + p.pravidlo : "");
    return "<div class=\"rmk-dlazdice " + (vyb ? "vybrano " : "") + (p.stav === "SPORNE" ? "sporne " : "") + (p.stav === "VYNECHANO" ? "vynechano" : "") + "\" role=\"button\" tabindex=\"0\" aria-pressed=\"" + vyb + "\" draggable=\"true\" data-rmk-id=\"" + esc(kl(p)) + "\" title=\"" + esc(tit) + "\">" +
      "<div class=\"rmk-nahled\">" + nahledHtml(p) + teckaHtml(p, mapa) + "</div>" +
      "<button type=\"button\" class=\"rmk-detail-btn\" data-rmk-detail=\"" + esc(kl(p)) + "\" aria-label=\"Detail: " + esc(p.nazev) + "\" title=\"Detail" + (p.telesa > 1 ? " a materiál po tělesech" : "") + "\">" + (p.telesa > 1 ? "⧉" : "ⓘ") + "</button>" +
      "<span class=\"rmk-vyber-mark\">✓</span>" +
      "<div class=\"rmk-nazev\">" + esc(p.nazev) + "</div><div class=\"rmk-meta\">" + meta + "</div></div>";
  }

  function radekHtml(p, mapa) {
    var vyb = st.vyber.has(kl(p));
    var m = p.klic_efektivni ? mapa[p.klic_efektivni] : null;
    var opts = "<option value=\"\">— žádný (dědí / beze změny) —</option>" + ((st.data && st.data.knihovna) || []).filter(function (k) { return k.aktivni; }).map(function (k) {
      return "<option value=\"" + esc(k.klic) + "\"" + (p.klic_vlastni && p.klic_vlastni.toLowerCase() === k.klic ? " selected" : "") + ">" + esc(k.nazev) + "</option>";
    }).join("");
    return "<tr class=\"" + (vyb ? "vybrano " : "") + (p.stav === "SPORNE" ? "sporne " : "") + (p.stav === "VYNECHANO" ? "vynechano" : "") + "\" data-rmk-id=\"" + esc(kl(p)) + "\">" +
      "<td class=\"sel\"><input type=\"checkbox\" data-rmk-radek-vyber=\"" + esc(kl(p)) + "\"" + (vyb ? " checked" : "") + " aria-label=\"Vybrat " + esc(p.nazev) + "\"></td>" +
      "<td class=\"mini\">" + (p.nahled || p.zdroj === "product" ? imgHtml(p, 2, " class=\"rmk-mini\"") : "<span class=\"rmk-mini\"></span>") + "</td>" +
      "<td class=\"nazev\">" + esc(p.nazev) + "<div class=\"rmk-meta rmk-mono\">" + esc(p.sku || p.id) + (p.telesa > 1 ? " · " + p.telesa + " těles" : "") + "</div></td>" +
      "<td class=\"dalsi\">" + esc(p.kategorie || "") + "</td>" +
      "<td class=\"dalsi\">" + (p.barva_dnes ? "<span class=\"rmk-sw\" style=\"background:" + esc(p.barva_dnes) + "\"></span><span class=\"rmk-mono\">" + esc(p.barva_dnes) + "</span>" : "<span class=\"rmk-meta\">—</span>") + "</td>" +
      "<td class=\"dalsi\"><select data-rmk-radek-mat=\"" + esc(kl(p)) + "\" aria-label=\"Materiál pro " + esc(p.nazev) + "\">" + opts + "</select></td>" +
      "<td class=\"dalsi\">" + (m ? "<span class=\"rmk-bod\" data-k=\"" + esc(m.klic) + "\"></span>" + esc(m.nazev) : "<span class=\"rmk-meta\">beze změny</span>") + "</td>" +
      "<td class=\"dalsi\"><span class=\"rmk-meta\">" + esc((ODKUD_TEXT[p.odkud] || p.odkud) + (p.odkud === "kategorie" && p.odkud_nazev ? " (" + p.odkud_nazev + ")" : "")) + "</span></td>" +
      "<td class=\"dalsi\"><span class=\"rmk-odznak " + p.stav + "\">" + STAV_TEXT[p.stav] + "</span></td>" +
      "<td class=\"dalsi\"><button type=\"button\" class=\"rmk-btn\" data-rmk-detail=\"" + esc(kl(p)) + "\" style=\"min-height:34px;\">" + (p.telesa > 1 ? p.telesa + " těles" : "detail") + "</button></td></tr>";
  }
  function tabulkaHtml(vys, mapa) {
    function th(k, t) {
      var sip = st.razeni.k === k ? (st.razeni.d > 0 ? " ▲" : " ▼") : "";
      return "<th data-rmk-razeni=\"" + k + "\" scope=\"col\" aria-sort=\"" + (st.razeni.k === k ? (st.razeni.d > 0 ? "ascending" : "descending") : "none") + "\">" + t + sip + "</th>";
    }
    return "<div class=\"rmk-tab-obal\"><table class=\"rmk-tab\"><thead><tr><th><input type=\"checkbox\" data-rmk-vse-radky aria-label=\"Vybrat všechny zobrazené\"></th><th></th>" +
      th("nazev", "Název") + th("kategorie", "Kategorie") + th("barva", "Barva dnes") + th("vlastni", "Vlastní klíč") + th("efektivni", "Účinný materiál") +
      th("odkud", "Odkud") + th("stav", "Stav") + th("telesa", "Detail") + "</tr></thead><tbody>" +
      vys.map(function (p) { return radekHtml(p, mapa); }).join("") + "</tbody></table></div>";
  }

  function renderObsah() {
    var el = q("#rmkObsah");
    if (!el) return;
    if (!st.data) { el.innerHTML = st.nacitam ? "<div class=\"rmk-meta\">načítám…</div>" : ""; return; }
    var vys = filtrovane(), mapa = mapaMaterialu();
    qa("[data-rmk-rezim]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-rmk-rezim") === st.rezim)); });
    var pocet = "<div class=\"rmk-popis-vyberu\" style=\"margin:0 0 8px;\">Zobrazeno " + vys.length + " z " + polozky().length + " položek" + (st.vyber.size ? " · vybráno " + st.vyber.size : "") + "</div>";
    if (!vys.length) { el.innerHTML = pocet + "<div class=\"rmk-meta\" style=\"font-size:14px;\">Filtru neodpovídá žádná položka.</div>"; return; }
    if (st.rezim === "tabulka") { el.innerHTML = pocet + tabulkaHtml(vys, mapa); return; }
    el.innerHTML = pocet + skupiny(vys).map(function (g, i) {
      var vsechnyVybrane = g.polozky.every(function (p) { return st.vyber.has(kl(p)); });
      return "<section class=\"rmk-skup\">" + (g.nazev ? "<div class=\"rmk-skup-hlava\"><div class=\"rmk-skup-nazev\">" + esc(g.nazev) + " <span class=\"rmk-meta\">" + g.polozky.length + " pol.</span></div>" +
        "<button type=\"button\" class=\"rmk-btn\" data-rmk-skupina=\"" + i + "\" aria-pressed=\"" + vsechnyVybrane + "\">" + (vsechnyVybrane ? "Zrušit výběr skupiny" : "Vybrat celou skupinu") + "</button></div>" : "") +
        "<div class=\"rmk-mrizka\">" + g.polozky.map(function (p) { return dlazdiceHtml(p, mapa); }).join("") + "</div></section>";
    }).join("");
    el._skupiny = skupiny(vys);
  }

  function renderLista() {
    var el = q("#rmkLista");
    if (!el) return;
    var n = st.vyber.size;
    el.classList.toggle("zap", n > 0);
    if (!n) { el.innerHTML = ""; return; }
    var opts = "<option value=\"\">vyber materiál…</option>" + ((st.data && st.data.knihovna) || []).filter(function (k) { return k.aktivni; }).map(function (k) {
      return "<option value=\"" + esc(k.klic) + "\">" + esc(k.nazev) + "</option>";
    }).join("");
    el.innerHTML = "<b>Vybráno " + n + " " + pocetText(n, "položka", "položky", "položek") + "</b>" +
      "<select id=\"rmkListaMat\" aria-label=\"Materiál pro vybrané\">" + opts + "</select>" +
      "<button type=\"button\" class=\"rmk-btn hlavni\" data-rmk-akce=\"priradit\">Přiřadit</button>" +
      "<button type=\"button\" class=\"rmk-btn\" data-rmk-akce=\"zrusit-prirazeni\">Zrušit přiřazení</button>" +
      "<button type=\"button\" class=\"rmk-btn\" data-rmk-akce=\"pouzit-navrh\" title=\"Vybraným položkám, které mají návrh z analýzy, nastaví navržený materiál\">Použít návrh</button>" +
      "<button type=\"button\" class=\"rmk-btn\" data-rmk-akce=\"zrusit-vyber\">Zrušit výběr</button>";
  }

  function renderFiltry() {
    var kn = (st.data && st.data.knihovna) || [];
    var fm = q("#rmkFMat");
    if (fm) {
      fm.innerHTML = "<option value=\"\">všechny materiály</option><option value=\"__zadny__\">— beze změny (bez materiálu)</option>" +
        kn.map(function (m) { return "<option value=\"" + esc(m.klic) + "\">" + esc(m.nazev) + "</option>"; }).join("");
      fm.value = st.fMat;
    }
    var fk = q("#rmkFKat");
    if (fk) {
      var kats = ((st.data && st.data.kategorie) || []).slice().sort(function (a, b) { return a.cesta.localeCompare(b.cesta, "cs"); });
      fk.innerHTML = "<option value=\"\">všechny kategorie</option><option value=\"__bez__\">— bez kategorie</option>" +
        kats.filter(function (k) { return k.polozek > 0; }).map(function (k) { return "<option value=\"" + k.id + "\">" + esc(k.cesta) + " (" + k.polozek + ")</option>"; }).join("");
      fk.value = st.fKat;
    }
    var ff = q("#rmkFStav"); if (ff) ff.value = st.fStav;
    var fs = q("#rmkSkup"); if (fs) fs.value = st.skup;
    var h = q("#rmkHledej"); if (h && h.value !== st.hledej) h.value = st.hledej;
    var v = q("#rmkVse"); if (v) v.checked = st.vse;
  }

  function renderZprava() {
    var el = q("#rmkZprava");
    if (!el) return;
    el.className = "rmk-zprava" + (st.zprava ? " " + st.zprava.typ : "");
    el.textContent = st.zprava ? st.zprava.text : "";
    var d = q("#rmkDdl");
    if (d) {
      d.innerHTML = st.chyba && st.chyba.ddl ? "<div class=\"rmk-ddl\" role=\"alert\"><b>Tabulky pro materiály ještě nejsou založené.</b><br>" + esc(st.chyba.text) +
        "<br><span class=\"rmk-meta\">Dokud se nespustí DDL, panel nic neukáže ani neukládá a render se chová jako dnes.</span></div>" : "";
    }
  }
  function zprava(text, typ) { st.zprava = text ? { text: text, typ: typ || "ok" } : null; renderZprava(); }

  function renderVse() {
    if (!root || !root.isConnected) return;
    renderZprava();
    if (st.chyba && st.chyba.ddl) {
      var k = q("#rmkKnihovna"); if (k) k.innerHTML = "";
      var o = q("#rmkObsah"); if (o) o.innerHTML = "";
      renderLista(); renderSouhrn();
      return;
    }
    renderSouhrn(); renderFiltry(); renderKnihovna(); renderObsah(); renderLista();
    if (st.detail) renderDetail();
    aplikujKoule();
  }

  // ---------- načtení ----------
  function nacti() {
    st.nacitam = true;
    if (!st.data) renderVse();
    return api("GET", API + (st.vse ? "?vse=1" : "")).then(function (d) {
      st.data = d; st.chyba = null; st.nacitam = false;
      // výběr jen z položek, které ještě existují
      var ex = new Set(d.polozky.map(kl));
      st.vyber.forEach(function (k) { if (!ex.has(k)) st.vyber.delete(k); });
      renderVse();
      zajistiKoule();
    }).catch(function (e) {
      st.nacitam = false;
      st.chyba = { text: e.message, ddl: e.status === 503 && e.data && e.data.code === "tabulky_nejsou" };
      if (!st.chyba.ddl) zprava("Načtení selhalo: " + e.message, "chyba");
      renderVse();
    });
  }

  // ---------- přiřazování ----------
  function polozkaPodleId(id) {
    var r = null;
    polozky().forEach(function (p) { if (kl(p) === id) r = p; });
    return r;
  }
  function nazevMat(klic) {
    var m = mapaMaterialu()[klic];
    return m ? m.nazev : klic;
  }
  function priradit(idecka, klic) {
    var seznam = idecka.map(polozkaPodleId).filter(Boolean);
    if (!seznam.length) return Promise.resolve();
    var jmeno = klic ? nazevMat(klic) : "beze změny";
    var vlajka = klic && mapaMaterialu()[klic] && !mapaMaterialu()[klic].knihovna_ok ? " ⚠ knihovna tohoto materiálu zatím na Sdíleném disku není." : "";
    var po;
    if (seznam.length === 1) {
      var p = seznam[0];
      po = api("PUT", API + "/polozka", { zdroj: p.zdroj, id: p.id, klic: klic || null, pred: p.klic_vlastni || null });
    } else {
      po = api("PUT", API + "/hromadne", { polozky: seznam.map(function (p) { return { zdroj: p.zdroj, id: p.id }; }), klic: klic || null });
    }
    zprava("Ukládám…", "ok");
    return po.then(function () {
      idecka.forEach(function (i) { st.vyber.delete(i); });
      zprava("Uloženo: " + seznam.length + " " + pocetText(seznam.length, "položka", "položky", "položek") + " → " + jmeno + "." + vlajka, "ok");
      return nacti();
    }).catch(function (e) {
      zprava("Uložení se nepovedlo: " + e.message, "chyba");
      return nacti();
    });
  }
  function vybraneId() { return Array.from(st.vyber); }

  function pouzitNavrh(idecka) {
    var zmeny = [];
    idecka.map(polozkaPodleId).filter(Boolean).forEach(function (p) {
      if (p.navrzeny_klic && p.stav_navrhu !== "VYNECHANO") zmeny.push({ zdroj: p.zdroj, id: p.id, klic: p.navrzeny_klic });
    });
    if (!zmeny.length) { zprava("Vybrané položky nemají návrh z analýzy.", "chyba"); return Promise.resolve(); }
    zprava("Ukládám…", "ok");
    return api("PUT", API + "/hromadne", { zmeny: zmeny }).then(function () {
      zprava("Použit návrh u " + zmeny.length + " " + pocetText(zmeny.length, "položky", "položek", "položek") + ".", "ok");
      return nacti();
    }).catch(function (e) { zprava("Uložení se nepovedlo: " + e.message, "chyba"); return nacti(); });
  }

  // ---------- detail položky + materiál po tělesech ----------
  function otevriDetail(id) {
    var p = polozkaPodleId(id);
    if (!p) return;
    st.detail = { id: id, data: null, nacitam: true, opener: String(id).replace(/["\\]/g, "") };
    document.removeEventListener("keydown", escDetail);
    document.addEventListener("keydown", escDetail);
    renderDetail();
    api("GET", API + "/dil/" + encodeURIComponent(p.zdroj) + "/" + encodeURIComponent(p.id)).then(function (d) {
      if (!st.detail || st.detail.id !== id) return;
      st.detail.data = d; st.detail.nacitam = false;
      renderDetail();
    }).catch(function (e) {
      if (!st.detail || st.detail.id !== id) return;
      st.detail.nacitam = false; st.detail.chyba = e.message;
      renderDetail();
    });
  }
  // Escape zavírá detail i když fokus po překreslení detailu spadl na <body> (listener je na dokumentu jen při otevřeném detailu)
  function escDetail(ev) { if (ev.key === "Escape" && st.detail) { ev.preventDefault(); zavriDetail(); } }
  function zavriDetail() {
    document.removeEventListener("keydown", escDetail);
    var opener = st.detail && st.detail.opener;
    st.detail = null;
    var d = q("#rmkDetail"); if (d) d.innerHTML = "";
    if (opener && root && root.isConnected) { var o = q("[data-rmk-detail=\"" + opener + "\"]"); if (o && o.focus) o.focus(); }
  }

  function moznosti(vybrano, prazdny) {
    return "<option value=\"\">" + esc(prazdny) + "</option>" + ((st.data && st.data.knihovna) || []).filter(function (k) { return k.aktivni; }).map(function (k) {
      return "<option value=\"" + esc(k.klic) + "\"" + (vybrano === k.klic ? " selected" : "") + ">" + esc(k.nazev) + "</option>";
    }).join("");
  }
  function bodHtml(klic) {
    var m = klic ? mapaMaterialu()[klic] : null;
    return m ? "<span class=\"rmk-bod\" data-k=\"" + esc(m.klic) + "\" title=\"" + esc(m.nazev) + "\"></span>" :
      "<span class=\"rmk-bod zadna\" title=\"beze změny\"></span>";
  }
  function renderDetail() {
    var el = q("#rmkDetail");
    if (!el || !st.detail) return;
    var p = polozkaPodleId(st.detail.id);
    if (!p) { zavriDetail(); return; }
    var d = st.detail.data;
    var mapa = mapaMaterialu();
    var m = p.klic_efektivni ? mapa[p.klic_efektivni] : null;
    var html = "<div class=\"rmk-modal-pozadi\" data-rmk-zavrit-pozadi>" +
      "<div class=\"rmk-modal\" role=\"dialog\" aria-modal=\"true\" aria-labelledby=\"rmkDetailNadpis\">" +
      "<button type=\"button\" class=\"rmk-zavrit rmk-btn\" data-rmk-zavrit aria-label=\"Zavřít\">✕</button>" +
      "<div class=\"rmk-lab\">" + (p.zdroj === "product" ? "karta e-shopu" : "díl katalogu (cfg)") + " · " + esc(p.sku || p.id) + "</div>" +
      "<h3 id=\"rmkDetailNadpis\">" + esc(p.nazev) + "</h3>" +
      "<div class=\"rmk-modal-telo\"><div class=\"rmk-fotky\"><div class=\"rmk-velky\">" + imgHtml(p, 2) + "</div>" +
      (p.zdroj === "product" ? "<div class=\"rmk-velky rmk-druhy\">" + imgHtml(p, 1) + "</div>" : "") + "</div>" +
      "<div class=\"rmk-info\"><dl>" +
      "<dt>Kategorie</dt><dd>" + esc(p.kategorie || "—") + "</dd>" +
      "<dt>Barva dnes</dt><dd>" + (p.barva_dnes ? "<span class=\"rmk-sw\" style=\"background:" + esc(p.barva_dnes) + "\"></span><span class=\"rmk-mono\">" + esc(p.barva_dnes) + "</span>" : "—") + "</dd>" +
      "<dt>Aktivní</dt><dd>" + (p.aktivni ? "ano" : "ne") + "</dd>" +
      "<dt>Stav</dt><dd><span class=\"rmk-odznak " + p.stav + "\">" + STAV_TEXT[p.stav] + "</span></dd>" +
      "<dt>Účinný materiál</dt><dd>" + bodHtml(p.klic_efektivni) + (m ? esc(m.nazev) : "beze změny") + " <span class=\"rmk-meta\">(" + esc(ODKUD_TEXT[p.odkud] || p.odkud) + (p.odkud === "kategorie" && p.odkud_nazev ? ": " + esc(p.odkud_nazev) : "") + ")</span></dd>" +
      "<dt>Vlastní klíč</dt><dd><select data-rmk-detail-mat aria-label=\"Materiál celého dílu\">" + moznosti(p.klic_vlastni ? p.klic_vlastni.toLowerCase() : "", "— žádný (dědí / beze změny) —") + "</select></dd></dl>" +
      (p.pravidlo ? "<div class=\"rmk-navrh\"><div class=\"rmk-lab\">Návrh z analýzy · " + esc(STAV_TEXT[p.stav_navrhu] || p.stav_navrhu || "") + "</div>" +
        (p.navrzeny_klic ? bodHtml(p.navrzeny_klic) + "<b>" + esc(nazevMat(p.navrzeny_klic)) + "</b> " : "<b>bez materiálu</b> ") +
        "<div class=\"rmk-meta\" style=\"margin-top:3px;\">" + esc(p.pravidlo) + "</div>" +
        (p.navrzeny_klic && p.stav_navrhu !== "VYNECHANO" && (p.klic_vlastni || "").toLowerCase() !== p.navrzeny_klic ?
          "<button type=\"button\" class=\"rmk-btn hlavni\" style=\"margin-top:6px;\" data-rmk-detail-navrh>Použít návrh</button>" : "") + "</div>" : "") +
      "</div></div>";
    if (p.telesa > 1) {
      html += "<div class=\"rmk-lab\" style=\"margin-top:10px;\">Materiál po tělesech (" + p.telesa + ")</div>";
      if (st.detail.nacitam) html += "<div class=\"rmk-meta\">načítám tělesa…</div>";
      else if (st.detail.chyba) html += "<div class=\"rmk-meta\" style=\"color:var(--error,#d44)\">" + esc(st.detail.chyba) + "</div>";
      else if (d && d.telesa) {
        html += "<table class=\"rmk-casti\"><thead><tr><th>Těleso</th><th>Rozměr (mm)</th><th>Materiál</th><th>Návrh</th></tr></thead><tbody>" + d.telesa.map(function (t) {
          return "<tr><td class=\"rmk-mono\">" + esc(t.mesh_klic) + "</td><td class=\"rmk-meta\">" + (t.rozmer ? t.rozmer.join(" × ") : "—") + "</td>" +
            "<td>" + bodHtml(t.klic_efektivni) + "<select data-rmk-cast=\"" + esc(t.mesh_klic) + "\" aria-label=\"Materiál tělesa " + esc(t.mesh_klic) + "\">" +
            moznosti(t.klic_cast || "", t.klic_cast ? "— zrušit (celý díl) —" : "— jako celý díl —") + "</select></td>" +
            "<td class=\"rmk-meta\">" + (t.navrh_klic ? "<button type=\"button\" class=\"rmk-btn\" style=\"min-height:30px;padding:1px 8px;font-size:12px;\" data-rmk-cast-navrh=\"" + esc(t.mesh_klic) + "\" data-k2=\"" + esc(t.navrh_klic) + "\" title=\"" + esc(t.navrh_proc || "") + "\">" + esc(t.navrh_klic) + "</button> " + esc(t.navrh_proc || "") : "—") + "</td></tr>";
        }).join("") + "</tbody></table>" +
          "<div style=\"display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;\">" +
          (d.navrh_casti ? "<button type=\"button\" class=\"rmk-btn hlavni\" data-rmk-casti-navrh>Použít návrh po částech</button>" : "") +
          "<button type=\"button\" class=\"rmk-btn\" data-rmk-casti-zrusit>Zrušit všechny části</button></div>";
      } else if (d && !d.telesa) html += "<div class=\"rmk-meta\" style=\"color:var(--error,#d44)\">" + esc(d.chyba_glb || "Tělesa se nepodařilo načíst.") + "</div>";
    }
    html += "</div></div>";
    el.innerHTML = html;
    aplikujKoule();
    var zbtn = q("[data-rmk-zavrit]", el);
    if (zbtn && !st.detail.zamereno) { zbtn.focus(); st.detail.zamereno = true; }
  }
  function ulozCasti(mapa) {
    var p = polozkaPodleId(st.detail.id);
    return api("PUT", API + "/dil/" + encodeURIComponent(p.zdroj) + "/" + encodeURIComponent(p.id) + "/casti", { casti: mapa }).then(function () {
      zprava("Uloženo: materiál po tělesech (" + Object.keys(mapa).length + ").", "ok");
      return nacti();
    }).then(function () {
      var id = st.detail && st.detail.id;
      if (id) { st.detail.data = null; st.detail.nacitam = true; st.detail.zamereno = true; renderDetail(); return api("GET", API + "/dil/" + encodeURIComponent(p.zdroj) + "/" + encodeURIComponent(p.id)).then(function (d) { if (st.detail && st.detail.id === id) { st.detail.data = d; st.detail.nacitam = false; renderDetail(); } }); }
    }).catch(function (e) { zprava("Uložení se nepovedlo: " + e.message, "chyba"); });
  }

  // ---------- události (delegace; žádné inline handlery) ----------
  function prepniVyber(id) {
    if (st.vyber.has(id)) st.vyber.delete(id); else st.vyber.add(id);
  }
  function prekresliVyber(fokusId) {
    renderObsah(); renderLista(); renderKnihovna(); aplikujKoule();
    if (fokusId) { var f = q("[data-rmk-id=\"" + String(fokusId).replace(/["\\]/g, "") + "\"]"); if (f && f.focus) f.focus(); }
  }

  function onClick(ev) {
    var t = ev.target;
    var c;
    if ((c = t.closest("[data-rmk-zavrit]")) || (t.hasAttribute && t.hasAttribute("data-rmk-zavrit-pozadi"))) { zavriDetail(); return; }
    if ((c = t.closest("[data-rmk-detail]"))) { ev.stopPropagation(); otevriDetail(c.getAttribute("data-rmk-detail")); return; }
    if ((c = t.closest("[data-rmk-detail-navrh]"))) {
      var pn = polozkaPodleId(st.detail.id);
      priradit([st.detail.id], pn && pn.navrzeny_klic).then(function () { if (st.detail) renderDetail(); });
      return;
    }
    if ((c = t.closest("[data-rmk-cast-navrh]"))) {
      var mp = {}; mp[c.getAttribute("data-rmk-cast-navrh")] = c.getAttribute("data-k2");
      ulozCasti(mp);
      return;
    }
    if (t.closest("[data-rmk-casti-navrh]")) {
      var mm = {};
      (st.detail.data.telesa || []).forEach(function (x) { if (x.navrh_klic) mm[x.mesh_klic] = x.navrh_klic; });
      ulozCasti(mm);
      return;
    }
    if (t.closest("[data-rmk-casti-zrusit]")) {
      var nulls = {};
      (st.detail.data.telesa || []).forEach(function (x) { if (x.klic_cast) nulls[x.mesh_klic] = null; });
      if (Object.keys(nulls).length) ulozCasti(nulls); else zprava("Žádné těleso nemá vlastní materiál.", "ok");
      return;
    }
    if ((c = t.closest("[data-rmk-rezim]"))) { st.rezim = c.getAttribute("data-rmk-rezim"); renderObsah(); return; }
    if ((c = t.closest("[data-rmk-chip]"))) {
      var s = c.getAttribute("data-rmk-chip");
      st.fStav = st.fStav === s ? "" : s;
      renderFiltry(); renderSouhrn(); renderObsah();
      return;
    }
    if ((c = t.closest("[data-rmk-mat]"))) {
      var klic = c.getAttribute("data-rmk-mat");
      if (c.classList.contains("vypnuta") && klic !== "__zrusit__") return;
      if (st.vyber.size) {
        if (klic === "__zrusit__") priradit(vybraneId(), null); else priradit(vybraneId(), klic);
      } else if (klic !== "__zrusit__") {
        st.fMat = st.fMat === klic ? "" : klic;
        renderFiltry(); renderKnihovna(); renderObsah(); aplikujKoule();
      }
      return;
    }
    if ((c = t.closest("[data-rmk-skupina]"))) {
      var g = q("#rmkObsah")._skupiny && q("#rmkObsah")._skupiny[+c.getAttribute("data-rmk-skupina")];
      if (g) {
        var vse = g.polozky.every(function (p) { return st.vyber.has(kl(p)); });
        g.polozky.forEach(function (p) { if (vse) st.vyber.delete(kl(p)); else st.vyber.add(kl(p)); });
        prekresliVyber();
      }
      return;
    }
    if ((c = t.closest("[data-rmk-akce]"))) {
      var a = c.getAttribute("data-rmk-akce");
      if (a === "vybrat-vse") { filtrovane().forEach(function (p) { st.vyber.add(kl(p)); }); prekresliVyber(); }
      else if (a === "zrusit-vyber") { st.vyber.clear(); prekresliVyber(); }
      else if (a === "priradit") {
        var sel = q("#rmkListaMat");
        if (!sel || !sel.value) { zprava("Vyber materiál v seznamu, nebo klepni na kartu materiálu nahoře.", "chyba"); return; }
        priradit(vybraneId(), sel.value);
      }
      else if (a === "zrusit-prirazeni") priradit(vybraneId(), null);
      else if (a === "pouzit-navrh") pouzitNavrh(vybraneId());
      return;
    }
    if ((c = t.closest("[data-rmk-razeni]"))) {
      var k = c.getAttribute("data-rmk-razeni");
      st.razeni = st.razeni.k === k ? { k: k, d: -st.razeni.d } : { k: k, d: 1 };
      renderObsah();
      return;
    }
    if (t.closest("[data-rmk-vse-radky]")) {
      var vse2 = t.checked;
      filtrovane().forEach(function (p) { if (vse2) st.vyber.add(kl(p)); else st.vyber.delete(kl(p)); });
      prekresliVyber();
      return;
    }
    if (t.closest("[data-rmk-radek-vyber]") || t.closest("select") || t.closest("input")) return;
    if ((c = t.closest(".rmk-dlazdice[data-rmk-id]"))) { prepniVyber(c.getAttribute("data-rmk-id")); prekresliVyber(); return; }
  }

  function onChange(ev) {
    var t = ev.target;
    if (t.id === "rmkFStav") { st.fStav = t.value; renderSouhrn(); renderObsah(); return; }
    if (t.id === "rmkFMat") { st.fMat = t.value; renderKnihovna(); renderObsah(); aplikujKoule(); return; }
    if (t.id === "rmkFKat") { st.fKat = t.value; renderObsah(); return; }
    if (t.id === "rmkSkup") { st.skup = t.value; renderObsah(); return; }
    if (t.id === "rmkVse") { st.vse = t.checked; nacti(); return; }
    if (t.hasAttribute("data-rmk-radek-vyber")) {
      var id = t.getAttribute("data-rmk-radek-vyber");
      if (t.checked) st.vyber.add(id); else st.vyber.delete(id);
      renderLista(); renderKnihovna(); aplikujKoule();
      var tr = t.closest("tr"); if (tr) tr.classList.toggle("vybrano", t.checked);
      return;
    }
    if (t.hasAttribute("data-rmk-radek-mat")) { priradit([t.getAttribute("data-rmk-radek-mat")], t.value || null); return; }
    if (t.hasAttribute("data-rmk-detail-mat")) { priradit([st.detail.id], t.value || null).then(function () { if (st.detail) renderDetail(); }); return; }
    if (t.hasAttribute("data-rmk-cast")) {
      var mp = {}; mp[t.getAttribute("data-rmk-cast")] = t.value || null;
      ulozCasti(mp);
    }
  }
  function onInput(ev) {
    if (ev.target.id === "rmkHledej") { st.hledej = ev.target.value; renderObsah(); }
  }
  function onKey(ev) {
    if (ev.key !== "Enter" && ev.key !== " ") return;
    var t = ev.target;
    if (t.matches && t.matches("button,select,input,textarea")) return;
    var c;
    if ((c = t.closest && t.closest(".rmk-dlazdice[data-rmk-id]"))) { ev.preventDefault(); prepniVyber(c.getAttribute("data-rmk-id")); prekresliVyber(c.getAttribute("data-rmk-id")); }
    else if ((c = t.closest && t.closest("[data-rmk-mat]"))) { ev.preventDefault(); c.click(); }
  }
  // tažení položky na kartu materiálu (myš); na dotykovém zařízení se přiřazuje klepnutím
  function onDragStart(ev) {
    var c = ev.target.closest && ev.target.closest(".rmk-dlazdice[data-rmk-id]");
    if (!c) return;
    var id = c.getAttribute("data-rmk-id");
    dragIds = st.vyber.has(id) ? vybraneId() : [id];
    try { ev.dataTransfer.setData("text/plain", "rmk:" + dragIds.length); ev.dataTransfer.effectAllowed = "copy"; } catch (e) { /* ignore */ }
    qa(".rmk-karta:not(.vypnuta)").forEach(function (k) { k.classList.add("cil"); });
  }
  function onDragEnd() {
    dragIds = null;
    renderKnihovna(); aplikujKoule();
  }
  function onDragOver(ev) {
    if (!dragIds) return;
    var c = ev.target.closest && ev.target.closest("[data-rmk-mat]");
    if (c && !c.classList.contains("vypnuta")) { ev.preventDefault(); ev.dataTransfer.dropEffect = "copy"; }
  }
  function onDrop(ev) {
    if (!dragIds) return;
    var c = ev.target.closest && ev.target.closest("[data-rmk-mat]");
    if (!c || c.classList.contains("vypnuta")) return;
    ev.preventDefault();
    var klic = c.getAttribute("data-rmk-mat"), ids = dragIds;
    dragIds = null;
    priradit(ids, klic === "__zrusit__" ? null : klic);
  }
  // nenačtený obrázek -> ikona
  function onImgError(ev) {
    var im = ev.target;
    if (!im || im.tagName !== "IMG" || !root || !root.contains(im)) return;
    var span = document.createElement("span");
    span.setAttribute("aria-hidden", "true"); span.textContent = "◫";
    if (im.classList.contains("rmk-mini")) { span.className = "rmk-mini"; }
    im.replaceWith(span);
  }

  function materialyKataloguInit(wrap) {
    var r = (wrap && wrap.querySelector && wrap.querySelector("#rmkPanel")) || document.getElementById("rmkPanel");
    if (!r) return;
    root = r;
    r.addEventListener("click", onClick);
    r.addEventListener("change", onChange);
    r.addEventListener("input", onInput);
    r.addEventListener("keydown", onKey);
    r.addEventListener("dragstart", onDragStart);
    r.addEventListener("dragend", onDragEnd);
    r.addEventListener("dragover", onDragOver);
    r.addEventListener("drop", onDrop);
    r.addEventListener("error", onImgError, true);
    var nap = r.querySelector("#rmkNapoveda");
    if (nap && window.innerWidth > 700) nap.open = true;      // na mobilu zavřená (šetří první obrazovku)
    renderFiltry();
    renderZprava();
    if (st.data) renderVse();      // hned ukáže, co už modul zná, pak čerstvá data
    nacti();
  }

  window.materialyKataloguHtml = materialyKataloguHtml;
  window.materialyKataloguInit = materialyKataloguInit;
  window.materialyKataloguStav = st;   // jen pro ladění / testy
})();
