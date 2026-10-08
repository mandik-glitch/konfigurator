/*
 * pdc-layout.js - MRIZKA OKEN (karta stolu) sdilena strankami nad modulem voleb (js/product-configurator.js): stranka produktu mini-shopu (miniweb-pages.js)
 * a stranka Generator stolu pro zamestnance (js/stul-host.js) - bot8, 2026-10-04. Vyjmuto z miniweb-pages.js (P.product), aby se rozlozeni NEDUPLIKOVALO
 * (Robert 2026-10-04: "udelat stejnou strukturu stranky generatoru stolu pro staff stejne jako je uz nyni nasazena na baliace-stoly").
 *
 *   var L = PdcLayout.create({ E: MW.el, narrow: matchMedia("(max-width: 899px)").matches });   // E = pomocnik na prvky (volitelny)
 *   var wDim = L.win("dim", "", { fold: true, mobileOpen: true, hidden: true });                  // okno = zahlavi + telo; o.fold = sklopitelne, o.closed, o.hidden, o.mobileOpen
 *   L.grid.appendChild(wDim.box); ...                                                             // L.grid = <div class="mw-pdg"> (CSS: miniweb.css, 12 sloupcu)
 *   var groupHost = L.groupHosts({ map: { g_size: wDim, g_frame: wFrame, g_extras: wExtras, g_cuts: wAdv, g_bearings: wAdv }, adv: wAdv, before: wDesc.box });  // -> ctx.dom.groupHost
 *   var sumHost = L.summaryHost(wSum, { all: function (n) { return "Cela konfigurace (" + n + ")"; }, less: "Mene" });                                    // -> ctx.dom.summaryHost
 *   L.reveal                                                                                                                                           // -> ctx.dom.reveal
 *   PdcLayout.DEPENDS                                                                                                                                  // fallback ctx.dom.dependsOn (starsi server bez schema.depends_on)
 * Pravidla (z mini-shopu): okno se skupinou voleb se ukaze, az kdyz modul skupinu vykresli (groupHost); vice skupin v jednom okne (`adv`) ma kazda podnadpis;
 * na mobilu je z sklopitelnych oken otevrene jen to s `mobileOpen`; shrnuti voleb ukazuje 4 radky a zbytek na tlacitko.
 *
 * DOPLNKY GENERATORU NA VSECH MISTECH (Robert 2026-10-05: "prvky napric generatory na vsech mistech: interni stranky, minishopy, vlozeny generator (iframe)"; bot16):
 * okno "Hlavni profil" (schema pruzezu + jedna veta) a okno "Pripni cokoli" (samopohybliva 3D ukazka pripevneni dilu do T-drazky, js/pripni-cokoli-tile.js). Hostitel si okna vyrobi pres
 * L.win(...), umisti je do SVEHO rozlozeni a naplni je temito funkcemi - zadny hostitel nema vlastni kopii; novy prvek generatoru patri sem (nebo do modulu voleb), ne do jednotlivych stranek.
 * Koty ve 3D resi modul voleb sam (product-configurator.js, mountOpts), prepinac Koty maji vsechna mista.
 *   var gate = PdcLayout.modelGate();                                  // page.onModel: gate.unlock - tezka ukazka se nacita az po prvnim hotovem modelu stolu (nebo po 15 s)
 *   PdcLayout.profileWindow(wProfile, { profile: ctl.profile(), text: function (mm, g) { return "..."; } });   // profil -> drazka z registru /pripni-cokoli/texty.json (aliasy); bez schematu pro profil zustane okno skryte
 *   PdcLayout.profileWindow(wProfile, { mm: p.profil_mm, groove: g1, text: fn });                                // mini-shop: profil a drazka z dat produktu
 *   PdcLayout.attachWindow(wAttach, { profile: "30x30", lang: "cs", accent: "#ff7b29", getEnv: fn, gate: gate, tileUrl: "/js/pripni-cokoli-tile.js?v=...", cssUrl: "/css/v3d.css?v=..." });
 */
(function (global) {
  "use strict";

  function defaultE(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      var v = attrs[k];
      if (v === false || v == null) return;
      if (k === "class") e.className = v;
      else if (k === "text") e.textContent = v;
      else if (k === "i18n") e.setAttribute("data-i18n", v);
      else e.setAttribute(k, v === true ? "" : v);
    });
    (kids == null ? [] : (Array.isArray(kids) ? kids : [kids])).forEach(function (c) { if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }

  // volby, ktere se ukazuji az po zapnuti nadrazene (fallback, dokud schema nenese slots[].depends_on): rozmery a police vyrezu N az kdyz je vyrez N, vyrez N+1 az kdyz je vyrez N; loziska
  var DEPENDS = {};
  [1, 2, 3].forEach(function (n) { ["w", "d", "x", "z", "shelf"].forEach(function (k) { DEPENDS["cut" + n + k] = "cut" + n; }); if (n > 1) DEPENDS["cut" + n] = "cut" + (n - 1); });
  ["pitch", "edge"].forEach(function (k) { DEPENDS["bear" + k] = "bearings"; });
  DEPENDS.bracelen = "braces"; DEPENDS.braces = "posts"; DEPENDS.boxpos = "drawers"; DEPENDS.drawleft = "drawers"; DEPENDS.ledlight = "led"; DEPENDS.petpos = "pet"; DEPENDS.arm = "led"; DEPENDS.panels = "posts"; DEPENDS.led = "posts"; DEPENDS.socket = "panels";

  function create(o) {
    o = o || {};
    var E = o.E || defaultE, narrow = !!o.narrow;
    var grid = E("div", { class: "mw-pdg" }), wins = {};

    // ---- okno: zahlavi + telo; sklopitelne okno ma zahlavi jako tlacitko (na mobilu je otevrene jen prvni s `mobileOpen`)
    function win(key, title, opt) {
      opt = opt || {};
      var body = E("div", { class: "mw-win-b" }), head;
      var box = E("section", { class: "mw-win mw-win-" + key, "data-win": key });
      if (opt.fold) {
        head = E("button", { type: "button", class: "mw-win-h mw-win-fold", "aria-expanded": "true" }, [E("span", { text: title }), E("span", { class: "mw-chev", "aria-hidden": "true", text: "▾" })]);
        head.addEventListener("click", function () { var c = box.classList.toggle("is-closed"); head.setAttribute("aria-expanded", c ? "false" : "true"); });
      } else head = E("div", { class: "mw-win-h" }, [E("span", { text: title })]);
      box.appendChild(head); box.appendChild(body);
      if (opt.fold && (opt.closed || (narrow && !opt.mobileOpen))) { box.classList.add("is-closed"); head.setAttribute("aria-expanded", "false"); }
      if (opt.hidden) box.hidden = true;
      wins[key] = { box: box, body: body };
      return wins[key];
    }

    // klik na dil ve 3D: okno s uzlem se otevre
    function reveal(node) {
      var b = node.closest(".mw-win");
      if (b && b.classList.contains("is-closed")) { b.classList.remove("is-closed"); var h = b.querySelector(".mw-win-fold"); if (h) h.setAttribute("aria-expanded", "true"); }
    }

    // skupiny voleb -> okna (idempotentni: modul vola groupHost pri kazde prestavbe panelu). cfg.map = {idSkupiny: okno}; cfg.adv = okno s vice skupinami (kazda ma podnadpis);
    // neznama skupina dostane vlastni okno pred cfg.before (uzel v gridu)
    function groupHosts(cfg) {
      var hosts = {};
      return function groupHost(g) {
        if (hosts[g.id]) return hosts[g.id];
        var w = cfg.map[g.id];
        if (!w) { w = win("grp-" + g.id, g.label || "", { fold: true }); if (cfg.before && cfg.before.parentNode === grid) grid.insertBefore(w.box, cfg.before); else grid.appendChild(w.box); }
        w.box.hidden = false;
        if (w === cfg.adv) {
          var sub = E("div", {}), h = E("h3", { class: "mw-win-sub", text: g.label || "" });
          w.body.appendChild(h); w.body.appendChild(sub);
          return (hosts[g.id] = { body: sub });
        }
        if (!w.head) { var hd = w.box.firstChild.firstChild; if (hd) hd.textContent = g.label || ""; w.head = true; }
        return (hosts[g.id] = { body: w.body, box: w.box });
      };
    }

    // zhrnuti voleb: 4 hlavni radky, zbytek na tlacitko; okno se ukaze, az kdyz je co ukazat. lbl = { all: function (n) -> text, less: text }
    function summaryHost(wSum, lbl) {
      var host = E("div", { class: "mw-sum-host" }), btn = E("button", { type: "button", class: "mw-link", hidden: true });
      btn.addEventListener("click", function () { var all = wSum.box.classList.toggle("sum-all"); btn.textContent = all ? lbl.less : btn.dataset.label; });
      wSum.body.appendChild(host); wSum.body.appendChild(btn);
      new MutationObserver(function () {
        var dl = host.querySelector("dl"), n = dl ? dl.querySelectorAll("dt").length : 0;
        btn.hidden = n <= 4; btn.dataset.label = lbl.all(n);
        if (!wSum.box.classList.contains("sum-all")) btn.textContent = btn.dataset.label;
        wSum.box.hidden = !n;
      }).observe(host, { childList: true, subtree: true });
      return host;
    }

    return { grid: grid, wins: wins, win: win, reveal: reveal, groupHosts: groupHosts, summaryHost: summaryHost };
  }

  // ---- doplnky generatoru (viz hlavicka) -------------------------------------------------------------------------------------------------------------------------------
  // brana "po prvnim hotovem modelu": tezke prvky stranky (ukazka Pripni cokoli) se nacitaji az po modelu stolu, aby nebrzdily hlavni 3D (bot16 2026-10-04, mereni nacitani)
  function modelGate() {
    var g = { done: false, cbs: [] };
    return {
      unlock: function () {
        if (g.done) return;
        g.done = true;
        var go = function () { g.cbs.splice(0).forEach(function (f) { f(); }); };
        if (global.requestIdleCallback) global.requestIdleCallback(go, { timeout: 3000 }); else setTimeout(go, 600);
      },
      after: function (fn) { if (g.done) fn(); else g.cbs.push(fn); }
    };
  }

  var REG_URL = "/pripni-cokoli/texty.json", regP = {};                      // registr profilu s animaci a schematem (stejny soubor cte prvek Pripni cokoli, se stejnym ?v=; prohlizec ho drzi v mezipameti)
  function registry(version) {
    var u = REG_URL + (version ? "?v=" + encodeURIComponent(version) : "");
    return regP[u] || (regP[u] = fetch(u).then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; }));
  }
  function profileKey(profs, profile) {                                      // "30x30" | "30" | "30 x 30" -> klic registru ("30x30-d8"), stejne aliasy jako v prvku Pripni cokoli
    var n = String(profile == null ? "" : profile).toLowerCase().replace(/\s+/g, "");
    if (!n || !profs) return null;
    var keys = Object.keys(profs);
    for (var i = 0; i < keys.length; i++) { if (keys[i] === n || (profs[keys[i]].aliasy || []).indexOf(n) >= 0) return keys[i]; }
    return null;
  }

  // okno "Hlavni profil": schema pruzezu (/pripni-cokoli/schema-<mm>x<mm>-d<drazka>.svg) a veta. o: { mm, groove } (mini-shop: z dat produktu) NEBO { profile } (ostatni: z registru);
  // o.text(mm, g) = veta v jazyce hostitele, o.version = ?v= ukazky (registr se bere se stejnou verzi). Bez schematu (jiny profil, soubor chybi) okno zustane skryte.
  function profileWindow(w, o) {
    o = o || {};
    function show(mm, g) {
      mm = String(mm); g = String(g);
      if (!/^\d{1,2}$/.test(mm) || !/^\d{1,2}$/.test(g)) return false;
      var text = typeof o.text === "function" ? o.text(mm, g) : "Profil " + mm + "×" + mm + " mm, drážka " + g + " mm.";
      var img = defaultE("img", { class: "mw-profile-img", alt: text, loading: "lazy", width: "180", height: "180", src: "/pripni-cokoli/schema-" + mm + "x" + mm + "-d" + g + ".svg" });
      img.addEventListener("error", function () { w.box.hidden = true; });
      w.body.textContent = "";
      w.body.appendChild(defaultE("div", { class: "mw-profile" }, [img, defaultE("p", { text: text })]));
      w.box.hidden = false;
      return true;
    }
    if (o.mm != null && o.groove != null && show(o.mm, o.groove)) return;
    var profile = o.profile != null ? o.profile : (o.mm != null ? o.mm + "x" + o.mm : null);
    if (!profile) return;
    registry(o.version).then(function (all) {
      var profs = all && all._profily, k = profileKey(profs, profile), m = k && /^(\d{1,2})x\d{1,2}-d(\d{1,2})$/.exec(k);
      if (m) show(m[1], profs[k].drazka_mm != null ? profs[k].drazka_mm : m[2]);
    });
  }

  // okno "Pripni cokoli": prvek se nacte az po modelu stolu a az je okno na obrazovce (IntersectionObserver); bez schvalene animace pro profil (nebo kdyz se nenacte) okno zmizi.
  // o: { profile, lang, accent, getEnv, gate, tileUrl, cssUrl, onReady }  (tileUrl / cssUrl nesou ?v= hostitele, verzovani resi scripts/miniweb_verze.py a stul_verze.py)
  function attachWindow(w, o) {
    o = o || {};
    var gate = o.gate || modelGate();
    function mount() {
      var cssBase = String(o.cssUrl || "/css/v3d.css").split("?")[0];
      if (!document.querySelector('link[href^="' + cssBase + '"]')) {          // prvek potrebuje CSS prohlizece, i kdyz volby komponent ho nacitaji az pozdeji
        var l = document.createElement("link"); l.rel = "stylesheet"; l.href = o.cssUrl || cssBase; document.head.appendChild(l);
      }
      var sc = document.createElement("script"); sc.src = o.tileUrl || "/js/pripni-cokoli-tile.js";
      sc.onload = function () {
        if (!global.PripniCokoliTile) return;
        var version = String(o.tileUrl || "").split("?v=")[1], lang = String(o.lang || "en").slice(0, 2);
        registry(version).then(function (all) {                                   // jazyky dlazdice jsou DATA (texty.json: _aktivni): novy jazyk shopu (de, hu ...) nepotrebuje zmenu kodu; jazyk mimo seznam -> anglicky
          var act = all && Array.isArray(all._aktivni) ? all._aktivni : ["cs", "sk", "en"];        // registr se nenacetl -> dosavadni trojice
          var opts = { lang: act.indexOf(lang) >= 0 ? lang : "en", accent: o.accent || "#2dd4bf", version: version };
          var env = o.getEnv && o.getEnv(); if (env) opts.viewerOpts = { envConfig: env };        // stejne prostredi (HDRI) jako hlavni prohlizec: HDR se nestahuje podruhe (cache prohlizece je sdilena)
          if (o.profile) opts.profile = o.profile;                                 // animace se paruje na profil: 30x30 -> animace 30x30, jiny profil bez animace -> nic (nikdy animace jineho profilu)
          return global.PripniCokoliTile.mount(w.body, opts).then(function (ctl) {
            w.body.style.minHeight = "";                                            // misto drzene pro dlazdici uz neni potreba (ma vlastni vysku)
            if (!ctl) { w.box.hidden = true; return; }
            var hideIfFailed = function () { if (w.body.querySelector(".failed")) w.box.hidden = true; };       // model/texty se nenacetly: rozbite okno se neukazuje
            if (ctl.ready && ctl.ready.then) ctl.ready.then(hideIfFailed, function () { w.box.hidden = true; }); else hideIfFailed();
            if (typeof o.onReady === "function") { try { o.onReady(ctl); } catch (e) { /* hostitel nesmi shodit okno */ } }
          });
        }).catch(function () { w.box.hidden = true; });
      };
      sc.onerror = function () { w.box.hidden = true; };
      document.head.appendChild(sc);
    }
    function start() {
      w.box.hidden = false; w.body.style.minHeight = "260px";                // misto drzene pro dlazdici; box musi byt videt, jinak by IntersectionObserver nikdy nezareagoval
      gate.after(function () {
        if ("IntersectionObserver" in global) {
          var io = new IntersectionObserver(function (es) { if (es.some(function (e) { return e.isIntersecting; })) { io.disconnect(); mount(); } }, { rootMargin: "300px" });
          io.observe(w.box);
        } else mount();
      });
      setTimeout(gate.unlock, 15000);                                         // model se nenacetl / hostitel brane nevola: ukazka se nacte nejpozdeji po 15 s
    }
    if (!o.profile) { start(); return; }                                      // bez profilu plati vychozi animace prvku (jako dosud v mini-shopu)
    registry(String(o.tileUrl || "").split("?v=")[1]).then(function (all) {   // profil bez schvalene animace (napr. 35x35): okno se vubec neukaze (zadny skok rozlozeni)
      var profs = all && all._profily, k = profileKey(profs, o.profile);
      if (k && profs[k].zive !== false) start();
    });
  }

  global.PdcLayout = { create: create, DEPENDS: DEPENDS, modelGate: modelGate, profileWindow: profileWindow, attachWindow: attachWindow };
})(window);
