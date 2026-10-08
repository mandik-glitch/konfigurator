/*
 * product-configurator.js - interaktivni volba komponent na produktove strance (bot16, 2026-10-02).
 *
 * Zadani: Robert pres bot3 - sestavy NE do auta se vystavuji jako zive 3D modely s volbou komponent (vedomy vyjimka z ochrany
 * modelu 2026-09-06, jen pro sestavy, ktere server oznaci jako konfigurovatelne). Strana NIC neodvozuje z dat produktu: bezi jen
 * kdyz product.configurator.available vrati server. Kontrakt dat: viz dokument s kontraktem dat (schema, resolve, model/<hash>).
 *
 * Verejna stranka NESMI nacitat scene.html ani nic z katalog/*.glb: model prichazi JEN jako kratce platny podepsany odkaz z
 * resolve (model.url). Hlida QA (kontrola, ze tenhle soubor nema zadny odkaz na scene.html ani katalog/).
 *
 * Co se nacita kdy:
 *   pri nacteni stranky: schema + jeden resolve s default_selection (JSON, zadne GLB, zadna knihovna) - cena a "Do kosiku" funguji;
 *   az po kliknuti na "Upravit komponenty": v3d.css, product-configurator.css, viewer3d.js a three.js (jsdelivr) a model.
 *
 * API:
 *   PdConfigurator.init(ctx) -> Promise<controller | null>   (null = stranka zustane beze zmeny)
 *   controller: active(), view(), refresh(), summary(), cartPayload(), openConfigurator(), openTurntable(), destroy()
 * ctx (adapter stranky):
 *   product:{id, configurator:{available, default_view}}
 *   dom:{tabsBefore, visual:[elementy otocky/posuvniku provedeni], stageHost, panelHost}
 *       volitelny OKENNI REZIM (mini-shop, mrizka oken): groupHost(skupina) -> {body, box?} | null = kazda skupina voleb se vykresli do vlastniho okna
 *       (body = obsah, box = cele okno, schova se, kdyz v nem neni nic videt; null = skupina se nevykresli); summaryHost = kam jde shrnuti voleb
 *       (cena a kod se pak do panelu nevkladaji, cenu ukazuje stranka); reveal(uzel) = stranka okno s uzlem otevre (klik na dil v 3D).
 *       panelHost pak nese jen tenky pruh (nazev, "Obnovit vychozi", upozorneni).
 *       OVLADANI VE 3D (bot8, docs/OVLADANI_3D.md): assets.ovladani = '/js/v3d-ovladani.js' (volitelne) -> tazeni uchytu, nabidka pravym tlacitkem a obousmerne
 *       zvyrazneni s panelem; popis ovladani nese resolve.vodici.ovladani; ctx.ovladaniTexty = prepis textu modulu (jazyk stranky).
 *       Schema muze nest slots[].depends_on (pole toggle slotu, VSECHNY musi byt zapnute); fallback dependsOn nize pro starsi server.
 *       dependsOn:{slotId: nadrazenySlotId} (volitelne) = slot (a jeho shrnuti) se vubec neukazuje, dokud neni nadrazena volba zapnuta; retezi se
 *       (napr. rozmery vyrezu 1 az kdyz je zapnuty vyrez 1, vyrez 2 az kdyz je zapnuty vyrez 1).
 *   page:{setPrice(price, state), setBuyState(ok, reason), toast(msg, type), onActivate(bool), track(key, detail)}
 *   assets:{cssNow:[...], css:[...], viewer:'/js/v3d/viewer3d.js'}
 *   schema slots[].auto_on {when:{slot, above}, message}: slot (toggle) se po resolve zapne SAM, kdyz selection[when.slot] > when.above, je vypnuty, server ho nezakazal
 *   (options.<slot>.on.disabled false) a zakaznik ho sam nevypnul (userOff: rucni odskrtnuti / nabidka "odebrat" / vypnuti ve 3D); max 1x za kombinaci (when.slot, w);
 *   zprava se ukazuje mezi oznamenimi, dokud je slot zapnuty.
 *   options.<slot>.hidden === true: slot se vubec nevykresli ani nejde do shrnuti (jako nesplnene depends_on); slider s selection[slot] == null (= "automaticky") ukaze
 *   options.<slot>.value (a poznamku, kdyz options.<slot>.auto) a nic neodesila, dokud ho zakaznik nepohne; "Zpet na vychozi" vraci null.
 *   schema.view (null | {az, el}) = ulozeny vychozi uhel pohledu 3D (stupne od cela modelu / naklon; viewer 1.17.0) -> V3D.mount({isoAngles}) (viewerOpts.isoAngles ma prednost);
 *   schema.env (null | {hdri, strength, rot_deg, hemi}) = ulozene prostredi 3D prohlizece -> V3D.mount({envConfig}) (viewerOpts.envConfig ma prednost);
 *   page.viewerPlugins() -> [factory(ctx)]: dalsi pluginy 3D prohlizece hostitele (za pluginem ovladani; viz opts.plugins ve viewer3d.js); page.onDrag(on) = zacatek / konec tazeni ve 3D;
 *   page.onModel(url, hash) po zobrazeni modelu ve 3D (druhy argument = hash konfigurace zobrazeneho modelu) (poprve = prvni hotovy snimek stolu; hostitel s tim muze odlozit dalsi tezke prvky stranky),
 *   page.onViewer(viewer) po kazdem V3D.mount, controller.viewer() = aktualni prohlizec (hostitel na nej muze pověsit V3D.envPicker).
 *   volitelne (stranka zamestnancu / dalsi stranky na stejnem modulu): ctx.resolveExtra {priznak: hodnota} se pridava do tela kazdeho resolve (napr. {staff:true};
 *   product_id, selection, rules_version a lang prepsat nejdou), page.onResolved(resp) po kazdem uspesnem resolve (cela odpoved, vc. resp.staff),
 *   initialSelection {slot: hodnota} (pocatecni vyber, napr. z hashe v URL; server ho po resolve pripadne upravi), page.onSelection(sel) po kazde zmene vyberu
 *   (potvrzene serverem), ctx.noTurntable (bez zalozek otocky). Pod posuvnikem se ukazuje "Povoleno od X do Y", kdyz je rozsah z options uzsi nez ve schematu.
 *   volitelne: viewerOpts (dalsi volby V3D.mount, napr. {hudDock:'top'}), lang ("cs"|"en": jazyk textu voleb ze serveru), labels (preklad textu), viewerLabels (slovnik textu 3D prohlizece, viz docs/VIEWER3D_SETMODEL.md), money(n) (format ceny), noTurntable (bez zalozek, rovnou volby)
 *   KOTY (Robert 2026-10-05, "prvky napric generatory na vsech mistech"): prepinac Koty v HUD a koty z modelu (spec v3d dims) jsou VZDY - Generator stolu pro zamestnance, mini-shop i vlozeny generator;
 *   stranka je smi vypnout jen vyslovne (viewerOpts.hudKoty:false); na okne <= 700 px jsou po nacteni vypnute (prepinac zustava); viewerOpts.dims (0|1|2) ma prednost.
 *   controller.profile() = profil produktu ze schematu ("30x30"); hostitel s nim paruje okno Hlavni profil a ukazku Pripni cokoli (js/pdc-layout.js: PdcLayout.profileWindow / attachWindow).
 */
(function (global) {
  "use strict";

  var PC = global.PdConfigurator = global.PdConfigurator || {};

  // Vyber pro URL (#v=...): hostitel s nim preklapi TENTYZ vyber mezi strankami systemu stolu (30 <-> 40); do hashe jdou jen volby, ktere se lisi od vychozich
  PC.packSelection = function (sel) {
    try { return "v=" + btoa(unescape(encodeURIComponent(JSON.stringify(sel || {})))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""); } catch (e) { return ""; }
  };
  PC.unpackSelection = function (hash) {
    var m = /(?:^|[#&])v=([A-Za-z0-9_-]{1,8000})(?:&|$)/.exec(String(hash || ""));
    if (!m) return null;
    try {
      var b = m[1].replace(/-/g, "+").replace(/_/g, "/"); while (b.length % 4) b += "=";
      var o = JSON.parse(decodeURIComponent(escape(atob(b)))), out = {}, n = 0;
      if (!o || typeof o !== "object" || Array.isArray(o)) return null;
      Object.keys(o).forEach(function (k) {                 // jen ploche hodnoty (cislo, boolean, kratky text); znamy slot a platnost overi az modul (sanitizeSel) a server
        var v = o[k];
        if (n < 200 && k !== "__proto__" && /^[A-Za-z0-9_]{1,40}$/.test(k) && ((typeof v === "number" && isFinite(v)) || typeof v === "boolean" || (typeof v === "string" && v.length <= 80))) { out[k] = v; n++; }
      });
      return n ? out : null;
    } catch (e) { return null; }
  };

  // Vychozi texty jsou ANGLICKE a bez jmena znacky; stranka je prepisuje pres ctx.labels (product.html cesky, mini-shop z i18n/<jazyk>.json).
  var T0 = {
    tabTurntable: "Turntable", tabConfigurator: "Configurator", cta: "Edit components", title: "Your configuration",
    reset: "Reset to default", price: "Configuration price", noVat: "excl. VAT", withVat: "incl. VAT", pending: "Calculating…",
    code: "Configuration code", summary: "Summary", unavailable: "This option is not available right now.",
    turntableNote: "The turntable shows the basic version, your configuration is in the Configurator tab.",
    errLoad: "The configurator could not be loaded. Please try again.", errNet: "Connection failed. Please try again.",
    retry: "Try again", rateLimit: "Too many changes at once, please wait a moment…", rulesChanged: "The available options changed, loading the new ones.",
    modelPrep: "Preparing model…", modelErr: "The model could not be loaded, the price is valid.", noWebgl: "This browser does not support the 3D preview, options and price still work.",
    viewerErr: "The 3D preview could not be loaded, options and price still work.", lock: "Tap to control the 3D view", invalid: "Please choose a valid configuration.",
    lockHint: "", yes: "yes", no: "no", auto: "automatic", allowed: "Allowed from {min} to {max} {unit}",
    sysLabel: "Profile system", sysOpt: "System {n}"
  };

  // ---------------------------------------------------------------- pomocne
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (!Object.prototype.hasOwnProperty.call(attrs, k) || attrs[k] == null || attrs[k] === false) continue;
      if (k === "text") n.textContent = attrs[k];
      else if (k === "class") n.className = attrs[k];
      else n.setAttribute(k, attrs[k] === true ? "" : String(attrs[k]));
    }
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function kc(n) {        // vychozi format ceny bez meny; stranka dodava vlastni pres ctx.money
    return Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  function validColor(c) { return typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : ""; }
  function same(a, b) { return JSON.stringify(a) === JSON.stringify(b); }

  function http(method, url, body, signal) {
    var opt = { method: method, credentials: "same-origin", headers: { "Accept": "application/json" }, signal: signal };
    if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
    return fetch(url, opt).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        if (!r.ok) { var err = { status: r.status, body: data, retryAfter: parseFloat(r.headers.get("Retry-After")) || 0 }; throw err; }
        return data;
      });
    });
  }

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = src; s.async = false;
      s.onload = function () { resolve(); };
      s.onerror = function () { reject(new Error("script " + src)); };
      document.head.appendChild(s);
    });
  }
  function loadCss(href) {
    return new Promise(function (resolve) {
      var l = document.createElement("link");
      l.rel = "stylesheet"; l.href = href;
      l.onload = function () { resolve(); };
      l.onerror = function () { resolve(); }; // vzhled je vylepseni, ne podminka funkce
      document.head.appendChild(l);
    });
  }
  function webglOk() {
    try { var c = document.createElement("canvas"); return !!(global.WebGLRenderingContext && (c.getContext("webgl") || c.getContext("experimental-webgl"))); } catch (e) { return false; }
  }

  // ---------------------------------------------------------------- init
  PC.init = function (ctx) {
    var product = ctx && ctx.product;
    if (!product || !product.id || !product.configurator || !product.configurator.available) return Promise.resolve(null);
    if (ctx.__started) return Promise.resolve(null);

    var base = "/api/shop/products/" + encodeURIComponent(product.id) + "/configurator";
    var RESOLVE = "/api/shop/configurator/resolve";
    var MODEL = "/api/shop/configurator/model/";
    var lang = typeof ctx.lang === "string" && /^[a-z]{2}(-[A-Za-z]{2})?$/.test(ctx.lang) ? ctx.lang : "";     // jazyk textu ze serveru (schema ?lang=, resolve body.lang); prazdne = vychozi serveru
    var S = {
      schema: null, defaults: {}, sel: {}, last: null, seq: 0, abort: null, pending: false, pendingTimer: null,
      view: "turntable", ui: {}, viewer: null, viewerFailed: false, assets: null, modelHash: null, modelReq: 0, poll: null, rulesRetry: 0,
      stage: null, panel: null, tabs: null, cta: null, mini: null, notice: null, priceBox: null, summary: null, codeEl: null, noticeTimer: null,
      userOff: {}, autoDone: {}, autoLast: {}, autoMsg: {},
      viewerOpts: ctx.viewerOpts && typeof ctx.viewerOpts === "object" ? ctx.viewerOpts : {},   // dalsi volby V3D.mount (napr. {hudDock:'top'} pro mobil)
      viewerLabels: ctx.viewerLabels && typeof ctx.viewerLabels === "object" ? ctx.viewerLabels : undefined     // texty HUD 3D prohlizece (V3D.mount labels), jinak cesky jako dosud
    };
    if (global.__pdcDebug) global.__pdcState = S; // jen pro testy
    var money = typeof ctx.money === "function" ? ctx.money : kc;       // format cen: stranka muze dodat vlastni (mena, jazyk)
    var T = Object.assign({}, T0, ctx.labels || {});          // preklad: stranka muze prepsat kterykoli text (mini-shop v jinem jazyce)
    var page = ctx.page || {};
    var noop = function () {};
    var pg = { setPrice: page.setPrice || noop, setBuyState: page.setBuyState || noop, toast: page.toast || noop, onActivate: page.onActivate || noop, track: page.track || noop, onResolved: page.onResolved || noop, onModel: page.onModel || noop, onSelection: page.onSelection || noop, onViewer: page.onViewer || noop, onDrag: page.onDrag || noop };

    // -------------------------------------------------------------- schema
    function slotsOf(schema) {
      var ok = { chips: 1, swatch: 1, select: 1, toggle: 1, slider: 1 };
      return (Array.isArray(schema && schema.slots) ? schema.slots : []).filter(function (s) {
        if (!s || !s.id || !s.label || !ok[s.type]) return false;
        if (s.type === "slider") return s.slider && isFinite(s.slider.min) && isFinite(s.slider.max);
        if (s.type === "toggle") return true;
        return Array.isArray(s.options) && s.options.length > 0;
      });
    }
    function loadSchema() {
      return http("GET", base + (lang ? "?lang=" + encodeURIComponent(lang) : "")).then(function (sc) {
        if (!sc || !slotsOf(sc).length || !sc.default_selection) throw new Error("schema");
        S.schema = sc; S.defaults = clone(sc.default_selection);
        return sc;
      });
    }

    // -------------------------------------------------------------- resolve
    function setPending(on) {
      S.pending = on;
      clearTimeout(S.pendingTimer);
      if (on) {
        S.pendingTimer = setTimeout(function () { if (S.pending) { renderPrice(true); } }, 400);
        pg.setBuyState(false, T.pending);
      }
      if (S.priceBox) S.priceBox.setAttribute("aria-busy", on ? "true" : "false");
    }
    function resolve(sel) {
      var seq = ++S.seq;
      S.commitPending = false;                       // dotaz uz odchazi: zmena z posuvniku v cekani na odeslani (setValue) je v nem zahrnuta
      if (S.abort && S.abort.abort) { try { S.abort.abort(); } catch (e) {} }
      var ctrl = global.AbortController ? new AbortController() : null;
      S.abort = ctrl;
      setPending(true);
      // strazce: zadny dotaz nesmi nechat stranku viset na "Pocitam..." (zaseknute spojeni) - po 15 s se zrusi a nabidne se opakovani
      var timedOut = false;
      var watchdog = setTimeout(function () { if (seq === S.seq && ctrl) { timedOut = true; try { ctrl.abort(); } catch (e) {} } }, 15000);
      var body = Object.assign({}, ctx.resolveExtra && typeof ctx.resolveExtra === "object" ? ctx.resolveExtra : {}, { product_id: product.id, selection: sel, rules_version: S.schema.rules_version });   // resolveExtra: priznaky stranky (napr. {staff:true}); zakladni pole prepsat nelze
      if (lang) body.lang = lang;
      return http("POST", RESOLVE, body, ctrl ? ctrl.signal : undefined).then(function (r) {
        clearTimeout(watchdog);
        if (seq !== S.seq) return null;
        S.rulesRetry = 0;
        if (S.commitPending) {                         // zakaznik mezitim dalsi zmenou v panelu (ceka na odeslani): odpoved neprepise jeho hodnoty, dalsi dotaz je na ceste
          S.last = r; return r;                       // stav zustava "pocita se", dokud neprijde odpoved na dalsi dotaz
        }
        if (S.drag) {                                  // behem tazeni ve 3D odpoved neprepisuje hodnoty ani ovladace (mohly by uskocit); popis ovladani se predava a modul ho pozdrzi
          S.last = r; setPending(false);
          handleModel(r); giveDescription(r); pg.onResolved(r);
          return r;
        }
        S.last = r; S.sel = clone(r.selection || sel);
        setPending(false);
        prefetchModel(r);
        applyState();
        handleModel(r);
        giveDescription(r);
        pg.onResolved(r); pg.onSelection(clone(S.sel));
        autoOn();
        return r;
      }).catch(function (e) {
        clearTimeout(watchdog);
        if (seq !== S.seq) return null;
        if (e && e.name === "AbortError" && !timedOut) return null;
        if (timedOut) e = { name: "Timeout" };
        setPending(false);
        if (e && e.status === 409 && e.body && e.body.error === "rules_changed" && S.rulesRetry < 1) {
          S.rulesRetry++;
          showNotice(T.rulesChanged);
          return loadSchema().then(function () { rebuildPanel(); return resolve(sanitizeSel(S.sel)); }).catch(function () { showError(T.errLoad, function () { resolve(sel); }); return null; });
        }
        if (e && e.status === 429) {
          var wait = Math.min(Math.max(e.retryAfter || 2, 1), 10);
          showNotice(T.rateLimit);
          return new Promise(function (ok) { setTimeout(ok, wait * 1000); }).then(function () { return seq === S.seq ? resolve(sel) : null; });
        }
        showError(e && e.status ? T.errLoad : T.errNet, function () { resolve(sel); });
        pg.setBuyState(false, T.errNet);
        return null;
      });
    }
    function autoOn() {                // schema slots[].auto_on: zapnout slot sam po resolve (viz hlavicka souboru); max 1x za kombinaci (when.slot, w)
      if (S.autoBusy || S.drag) return;
      var changed = false;
      slotsOf(S.schema).forEach(function (slot) {
        var a = slot.auto_on; if (!a || !a.when || !a.when.slot || !isFinite(a.when.above)) return;
        var st = optState(slot.id, "on"), key = slot.id + ":" + S.sel[a.when.slot] + ":" + S.sel.w;
        if (S.autoLast[slot.id] !== key) { delete S.autoDone[S.autoLast[slot.id]]; S.autoLast[slot.id] = key; }       // pojistka smycky plati jen pro stejnou kombinaci; po zmene a navratu (zuzit/rozsirit stul) se muze zapnout znovu
        if (Number(S.sel[a.when.slot]) > Number(a.when.above) && !S.sel[slot.id] && st && st.disabled === false && !S.userOff[slot.id] && !S.autoDone[key]) {
          S.autoDone[key] = true; S.sel[slot.id] = true; S.autoMsg[slot.id] = a.message || ""; changed = true;
        }
      });
      if (!changed) return;
      S.autoBusy = true; applyState();
      resolve(clone(S.sel)).then(function () { S.autoBusy = false; }, function () { S.autoBusy = false; });
    }
    function sanitizeSel(sel) {
      // po zmene schematu nech jen sloty, ktere existuji, zbytek doplni vychozi hodnoty
      var out = clone(S.defaults);
      slotsOf(S.schema).forEach(function (s) { if (sel && sel[s.id] !== undefined) out[s.id] = sel[s.id]; });
      return out;
    }
    var commitTimer = null;
    function setValue(slotId, value, immediate) {
      if (same(S.sel[slotId], value)) return;
      S.sel[slotId] = value;
      pg.track("configurator_change", { slot: slotId });
      clearTimeout(commitTimer);
      if (immediate) resolve(clone(S.sel)); else { S.commitPending = true; commitTimer = setTimeout(function () { resolve(clone(S.sel)); }, 250); }
    }

    // -------------------------------------------------------------- stav -> UI
    function optState(slotId, optId) {
      var o = S.last && S.last.options && S.last.options[slotId];
      return (o && o[optId]) || null;
    }
    function deltaText(d) {
      if (!d || !isFinite(d)) return "";
      return (d > 0 ? "+ " : "− ") + money(Math.abs(d));
    }
    // server odebral nevejdouci se prislusenstvi (resolve.notices: {slot, action:"removed", message}) a pri kolizi nabizi odebrani
    // (resolve.offers: {slot, action:"remove", label, message}) - po kliknuti se posle vyber s timto slotem false
    function renderNotices() {
      var box = S.noticesBox; if (!box) return;
      var notices = (S.last && Array.isArray(S.last.notices)) ? S.last.notices : [], offers = (S.last && Array.isArray(S.last.offers)) ? S.last.offers : [];
      box.textContent = "";
      notices.forEach(function (n) { if (n && n.message) box.appendChild(el("p", { class: "pdc-notice-item", text: n.message })); });
      Object.keys(S.autoMsg).forEach(function (id) { if (S.sel[id] && S.autoMsg[id]) box.appendChild(el("p", { class: "pdc-notice-item pdc-auto-item", text: S.autoMsg[id] })); });     // automaticky zapnuto (auto_on)
      offers.forEach(function (o) {
        if (!o || !o.slot || !o.label) return;
        var b = el("button", { type: "button", class: "pdc-link pdc-offer-btn", text: o.label });
        b.addEventListener("click", function () { S.sel[o.slot] = false; S.userOff[o.slot] = true; applyState(); resolve(clone(S.sel)); });
        box.appendChild(el("p", { class: "pdc-offer" }, [el("span", { text: (o.message || "") + " " }), b]));
      });
      box.hidden = !box.childNodes.length;
    }
    function applyState() {
      renderNotices();
      var errBySlot = {};
      ((S.last && S.last.errors) || []).forEach(function (e) { if (e && e.slot) (errBySlot[e.slot] = errBySlot[e.slot] || []).push(e.message); });
      slotsOf(S.schema).forEach(function (slot) {
        var ui = S.ui[slot.id];
        if (ui) { ui.root.hidden = false; ui.update(S.sel[slot.id], errBySlot[slot.id] || []); if (depHidden(slot.id) || optHidden(slot.id)) ui.root.hidden = true; }
      });
      (S.groupEls || []).forEach(function (g) {      // skupina (okno), ve ktere neni nic videt, se schova
        var slots = g.el.querySelectorAll(".pdc-slot");
        if (slots.length) { var none = Array.prototype.every.call(slots, function (n) { return n.hidden; }); g.el.hidden = none; if (g.box) g.box.hidden = none; }
      });
      renderPrice(false);
      renderSummary();
      var general = ((S.last && S.last.errors) || []).filter(function (e) { return !e.slot; }).map(function (e) { return e.message; });
      if (S.last && S.last.valid === false && !general.length && !Object.keys(errBySlot).length) general.push(T.invalid);
      showNotice(general.join(" "), true);
      pg.setBuyState(!!(S.last && S.last.valid !== false), T.invalid);
      pg.setPrice(S.last && S.last.price, { pending: false, valid: !S.last || S.last.valid !== false, kod: S.last && S.last.kod });
      updateMini();
    }
    function renderPrice(pendingLabel) {
      if (!S.priceBox) return;
      S.priceBox.textContent = "";
      var p = S.last && S.last.price;
      if (pendingLabel || !p) { S.priceBox.appendChild(el("span", { class: "pdc-price-main", text: T.pending })); return; }
      S.priceBox.appendChild(el("span", { class: "pdc-price-lbl", text: T.price }));
      S.priceBox.appendChild(el("span", { class: "pdc-price-main", text: money(p.net) }));
      S.priceBox.appendChild(el("span", { class: "pdc-price-vat", text: T.noVat + (p.gross != null ? " (" + money(p.gross) + " " + T.withVat + ")" : "") }));
      if (S.codeEl) S.codeEl.textContent = S.last && S.last.kod ? T.code + ": " + S.last.kod : "";
    }
    function labelOf(slot, val) {
      if (slot.type === "slider" && val == null) {                      // "automaticky": ukazat hodnotu, kterou server dopocital
        var o = S.last && S.last.options && S.last.options[slot.id];
        return o && isFinite(o.value) ? o.value + " " + (slot.slider.unit || "") + " (" + T.auto + ")" : T.auto;
      }
      if (slot.type === "slider") return val + " " + (slot.slider.unit || "");
      if (slot.type === "toggle") return val ? T.yes : T.no;
      var o = (slot.options || []).filter(function (x) { return String(x.id) === String(val); })[0];
      return o ? o.label : "";
    }
    function slotDeps(id) {            // nadrazene toggle sloty (schema depends_on, jinak fallback dom.dependsOn)
      var slot = slotById(id), deps = slot && Array.isArray(slot.depends_on) && slot.depends_on.length ? slot.depends_on : null;
      if (!deps) { var fb = (ctx.dom.dependsOn || {})[id]; deps = fb ? [fb] : []; }
      return deps;
    }
    function optHidden(id) { var o = S.last && S.last.options && S.last.options[id]; return !!(o && o.hidden === true); }          // options.<slot>.hidden: neexistujici polozka (napr. police c. 7 u stolu se 3 policemi)
    function slotById(id) { return slotsOf(S.schema).filter(function (x) { return x.id === id; })[0]; }
    function depHidden(id, depth) {    // nadrazena volba neni zapnuta -> slot se neukazuje (retezi se); schema slots[].depends_on = pole toggle slotu (AND), jinak fallback dom.dependsOn
      depth = depth || 0; if (depth > 8) return false;
      var slot = slotById(id), deps = slot && Array.isArray(slot.depends_on) && slot.depends_on.length ? slot.depends_on : null;
      if (!deps) { var fb = (ctx.dom.dependsOn || {})[id]; deps = fb ? [fb] : null; }
      return !!deps && deps.some(function (d) { return !S.sel[d] || depHidden(d, depth + 1); });
    }
    function shownSlots() {            // slot, ktery panel neukazuje (zamceny posuvnik, vypnuta nadrazena volba), neni ani v shrnuti
      return slotsOf(S.schema).filter(function (slot) { var ui = S.ui[slot.id]; return !(ui && ui.root.hidden); });
    }
    function renderSummary() {
      if (!S.summary) return;
      S.summary.textContent = "";
      shownSlots().forEach(function (slot) {
        S.summary.appendChild(el("dt", { text: slot.label }));
        S.summary.appendChild(el("dd", { text: labelOf(slot, S.sel[slot.id]) }));
      });
    }

    // -------------------------------------------------------------- ovladace slotu
    function mkChips(slot) {
      var name = "pdc_" + slot.id;
      var group = el("div", { class: "pd-pillgroup", role: "radiogroup", "aria-label": slot.label });
      var inputs = {};
      slot.options.forEach(function (o) {
        var inp = el("input", { type: "radio", name: name, value: String(o.id) });
        var sw = slot.type === "swatch" && validColor(o.swatch) ? el("i", { class: "pdc-sw" }) : null;
        if (sw) sw.style.background = o.swatch;
        var delta = el("small", { class: "pdc-delta" });
        var span = el("span", null, [sw, document.createTextNode(o.label), delta]);
        var lab = el("label", { class: "pd-pill" }, [inp, span]);
        inputs[o.id] = { inp: inp, delta: delta, lab: lab };
        inp.addEventListener("change", function () {
          var st = optState(slot.id, o.id);
          if (st && st.disabled) { inp.checked = false; setSel(); showNotice(st.reason || T.unavailable); return; }
          setValue(slot.id, o.id, true);
        });
        group.appendChild(lab);
      });
      function setSel() { slot.options.forEach(function (o) { inputs[o.id].inp.checked = String(S.sel[slot.id]) === String(o.id); }); }
      var root = el("fieldset", { class: "pdc-slot" }, [el("legend", { class: "pd-opt-sub-label", text: slot.label }), group]);
      var err = el("div", { class: "pdc-err", role: "status" });
      root.appendChild(err);
      return { root: root, update: function (val, errs) {
        setSel();
        slot.options.forEach(function (o) {
          var st = optState(slot.id, o.id), it = inputs[o.id], cur = String(val) === String(o.id);
          it.delta.textContent = !cur && st ? deltaText(st.price_delta) : "";
          var na = !!(st && st.disabled);
          it.lab.classList.toggle("pdc-na", na);
          it.inp.setAttribute("aria-disabled", na ? "true" : "false");
          if (na && st.reason) it.lab.setAttribute("title", st.reason); else it.lab.removeAttribute("title");
        });
        err.textContent = errs.join(" ");
      } };
    }
    function mkSelect(slot) {
      var sel = el("select", { class: "pdc-select", "aria-label": slot.label });
      var opts = {};
      slot.options.forEach(function (o) { var op = el("option", { value: String(o.id), text: o.label }); opts[o.id] = op; sel.appendChild(op); });
      sel.addEventListener("change", function () {
        var st = optState(slot.id, sel.value);
        if (st && st.disabled) { sel.value = String(S.sel[slot.id]); showNotice(st.reason || T.unavailable); return; }
        setValue(slot.id, sel.value, true);
      });
      var root = el("div", { class: "pdc-slot" }, [el("label", { class: "pd-opt-sub-label", text: slot.label }), sel]);
      var err = el("div", { class: "pdc-err", role: "status" }); root.appendChild(err);
      return { root: root, update: function (val, errs) {
        sel.value = String(val);
        slot.options.forEach(function (o) {
          var st = optState(slot.id, o.id), cur = String(val) === String(o.id);
          opts[o.id].textContent = o.label + (!cur && st && st.price_delta ? " (" + deltaText(st.price_delta) + ")" : "") + (st && st.disabled ? " – nedostupné" : "");
        });
        err.textContent = errs.join(" ");
      } };
    }
    function mkToggle(slot) {
      var inp = el("input", { type: "checkbox", role: "switch" });
      var delta = el("small", { class: "pdc-delta" });
      var lab = el("label", { class: "pd-opt" }, [
        el("span", { class: "pd-switch" }, [inp, el("span", { class: "pd-switch-track" }, [el("span", { class: "pd-switch-thumb" })])]),
        el("span", { class: "pd-opt-text" }, [document.createTextNode(slot.label), delta])
      ]);
      inp.addEventListener("change", function () {
        var st = optState(slot.id, "on");
        if (inp.checked && st && st.disabled) {                                               // zapnuti by se hned odebralo: neprovest, ukazat duvod u radku a zablikat
          inp.checked = false; showNotice(st.reason || T.unavailable);
          err.textContent = st.reason || T.unavailable; root.classList.add("pdc-flash"); setTimeout(function () { root.classList.remove("pdc-flash"); }, 1200);
          return;
        }
        if (inp.checked) delete S.userOff[slot.id]; else S.userOff[slot.id] = true;          // rucni odskrtnuti = zakaznik to nechce, auto_on to uz nezapne
        setValue(slot.id, inp.checked, true);
      });
      var root = el("div", { class: "pdc-slot" }, [lab]);
      var err = el("div", { class: "pdc-err", role: "status" }); root.appendChild(err);
      // zakazany prepinac, ktery server umi povolit zmenou rozmeru: options.<slot>.on.suggest {w|d} + suggest_label ("Roztahnout stul ... a zapnout")
      var sugBtn = el("button", { type: "button", class: "pdc-link pdc-suggest-btn" }), sugBox = el("div", { class: "pdc-suggest", hidden: true }, [sugBtn]);
      sugBtn.addEventListener("click", function () {
        var st = optState(slot.id, "on");
        if (!st || !st.suggest) return;
        Object.keys(st.suggest).forEach(function (k) { S.sel[k] = st.suggest[k]; });
        S.sel[slot.id] = true; delete S.userOff[slot.id];
        applyState(); resolve(clone(S.sel));
      });
      root.appendChild(sugBox);
      return { root: root, update: function (val, errs) {
        inp.checked = !!val;
        var st = optState(slot.id, "on");
        delta.textContent = st && !val ? (" " + deltaText(st.price_delta)).trimEnd() : "";
        lab.classList.toggle("pdc-na", !!(st && st.disabled));
        err.textContent = errs.join(" ");
        var sug = !val && st && st.disabled && st.suggest && st.suggest_label;
        sugBox.hidden = !sug; sugBtn.textContent = sug ? st.suggest_label : "";
      } };
    }
    function mkSlider(slot) {
      var unit = slot.slider.unit || "";
      var rng = el("input", { type: "range", class: "pdc-range", "aria-label": slot.label });
      var num = el("input", { type: "number", class: "pdc-num", "aria-label": slot.label + " (" + unit + ")", inputmode: "numeric" });
      function meze() {
        var st = S.last && S.last.options && S.last.options[slot.id];
        var mn = st && isFinite(st.min) ? st.min : slot.slider.min, mx = st && isFinite(st.max) ? st.max : slot.slider.max;
        return { min: mn, max: Math.max(mn, mx) };
      }
      function stepNow() {              // polozky s automatickou hodnotou (options.<slot> nese value/auto, napr. police sh1..sh10) maji meze na 0,1 mm a zadnou mrizku schematu
        var st = S.last && S.last.options && S.last.options[slot.id];
        return st && isFinite(st.step) ? st.step : (st && "auto" in st ? 0.1 : (slot.slider.step || 1));
      }
      function clamp(v) {
        var m = meze(), step = stepNow();
        v = Number(v);
        if (!isFinite(v)) v = m.min;
        v = Math.min(m.max, Math.max(m.min, v));
        var snapped = m.min + Math.round((v - m.min) / step) * step;
        if (snapped > m.max) snapped = m.min + Math.floor((m.max - m.min) / step) * step;
        return step < 1 ? Number(snapped.toFixed(1)) : snapped;
      }
      [rng, num].forEach(function (i) { i.setAttribute("step", String(slot.slider.step || 1)); });
      var dirty = false;                                              // zakaznik prave pise / tahne hodnotu (input bez change): applyState() (odpoved serveru, model) mu ji nesmi prepsat puvodni
      rng.addEventListener("input", function () { dirty = true; num.value = rng.value; });
      num.addEventListener("input", function () { dirty = true; });
      [rng, num].forEach(function (i) { i.addEventListener("blur", function () { dirty = false; }); });
      rng.addEventListener("change", function () { dirty = false; setValue(slot.id, clamp(rng.value), false); });
      num.addEventListener("change", function () { dirty = false; var v = clamp(num.value); num.value = v; rng.value = v; setValue(slot.id, v, false); });
      var root = el("div", { class: "pdc-slot" }, [
        el("label", { class: "pd-opt-sub-label", text: slot.label }),
        el("div", { class: "pdc-sliderrow" }, [rng, num, el("span", { class: "pdc-unit", text: unit })])
      ]);
      var note = el("div", { class: "pdc-range-note" }); root.appendChild(note);
      var autoNote = el("div", { class: "pdc-range-note pdc-auto-note" }); root.appendChild(autoNote);
      var err = el("div", { class: "pdc-err", role: "status" }); root.appendChild(err);
      return { root: root, update: function (val, errs) {
        var m = meze();
        [rng, num].forEach(function (i) { i.min = m.min; i.max = m.max; i.setAttribute("step", String(stepNow())); });
        var st0 = S.last && S.last.options && S.last.options[slot.id];
        var isAuto = val == null;                                          // selection[slot] == null = automaticky: ukazat dopocitanou hodnotu serveru (options.value), neodesilat
        var v = clamp(isAuto ? (st0 && isFinite(st0.value) ? st0.value : m.min) : val); if (!dirty) { rng.value = v; num.value = v; }
        rng.setAttribute("aria-valuetext", v + " " + unit);
        autoNote.textContent = isAuto && st0 && st0.auto ? T.auto : "";
        var narrower = m.min > slot.slider.min || m.max < slot.slider.max;                  // rozsah z odpovedi je uzsi nez ve schematu: ukaz ho (jinak clovek netusi, proc hodnota nejde)
        note.textContent = narrower && m.max > m.min ? T.allowed.replace("{min}", String(m.min)).replace("{max}", String(m.max)).replace("{unit}", unit).trim() : "";
        err.textContent = errs.join(" ");
        root.hidden = m.max <= m.min || !!(st0 && st0.hidden);                      // zamceny posuvnik (min = max: volba je vypnuta / se nepouziva, napr. vyrez bez zapnuti, stredni noha u uzkeho stolu) se neukazuje
      } };
    }

    // -------------------------------------------------------------- panel, zalozky
    function showNotice(text, soft) {
      if (!S.notice) return;
      clearTimeout(S.noticeTimer);
      S.notice.textContent = text || "";
      S.notice.hidden = !text;
      if (text && !soft) S.noticeTimer = setTimeout(function () { if (S.notice) { S.notice.textContent = ""; S.notice.hidden = true; } }, 6000);
    }
    function showError(text, retry) {
      if (!S.notice) { pg.toast(text, "error"); return; }
      S.notice.textContent = ""; S.notice.hidden = false;
      S.notice.appendChild(document.createTextNode(text + " "));
      if (retry) { var b = el("button", { type: "button", class: "pdc-link", text: T.retry }); b.addEventListener("click", function () { S.notice.hidden = true; retry(); }); S.notice.appendChild(b); }
    }
    function buildPanel() {
      var groups = Array.isArray(S.schema.groups) && S.schema.groups.length ? S.schema.groups : [{ id: "_", label: "" }];
      var byGroup = {};
      slotsOf(S.schema).forEach(function (s) { var g = s.group && groups.some(function (x) { return x.id === s.group; }) ? s.group : groups[0].id; (byGroup[g] = byGroup[g] || []).push(s); });
      S.ui = {};
      var panel = el("section", { class: "pdc-panel pd-options-card", "aria-label": T.title, hidden: true });
      var reset = el("button", { type: "button", class: "pdc-link", text: T.reset });
      reset.addEventListener("click", function () { S.sel = clone(S.defaults); S.userOff = {}; S.autoDone = {}; S.autoLast = {}; S.autoMsg = {}; applyState(); resolve(clone(S.sel)); });
      panel.appendChild(el("div", { class: "pdc-head" }, [el("span", { class: "pd-opt-sub-label", text: T.title }), reset]));
      S.notice = el("div", { class: "pdc-notice", role: "status", "aria-live": "polite", hidden: true });
      panel.appendChild(S.notice);
      S.noticesBox = el("div", { class: "pdc-notices", role: "status", "aria-live": "polite", hidden: true });   // notices[] (server sam odebral) + offers[] (nabidka odebrat)
      panel.appendChild(S.noticesBox);
      var narrow = global.matchMedia && global.matchMedia("(max-width: 800px)").matches;
      var first = true, gh = typeof ctx.dom.groupHost === "function" ? ctx.dom.groupHost : null;
      S.groupEls = [];
      if (gh) panel.classList.add("pdc-panel-bar");
      groups.forEach(function (g) {
        var slots = byGroup[g.id]; if (!slots || !slots.length) return;
        var host = null, det;
        if (gh) {                                                  // okenni rezim: skupina je obsah okna stranky (bez <details>)
          host = gh(g); if (!host || !host.body) return;
          det = el("div", { class: "pdc-group pdc-group-win" });
        } else {
          det = el("details", { class: "pdc-group" });
          if (!narrow || first) det.setAttribute("open", "");
          first = false;
          if (g.label) det.appendChild(el("summary", { class: "pdc-group-h", text: g.label }));
        }
        slots.forEach(function (slot) {
          var ui = slot.type === "slider" ? mkSlider(slot) : slot.type === "toggle" ? mkToggle(slot) : slot.type === "select" ? mkSelect(slot) : mkChips(slot);
          ui.root.setAttribute("data-slot", slot.id);
          ui.root.addEventListener("pointerenter", function () { if (S.ov) S.ov.hoverParam(slot.id); });      // opacny smer: mys na ovladaci v panelu -> zvyrazneni casti a uchytu ve 3D
          ui.root.addEventListener("pointerleave", function () { if (S.ov) S.ov.hoverParam(null); });
          if (slot.g != null) ui.root.setAttribute("data-g", String(slot.g));
          S.ui[slot.id] = ui;
          det.appendChild(ui.root);
        });
        if (host) { if (host.fresh !== false) host.body.textContent = ""; host.body.appendChild(det); S.groupEls.push({ el: det, box: host.box || null }); }
        else { panel.appendChild(det); S.groupEls.push({ el: det, box: null }); }
      });
      S.priceBox = el("div", { class: "pdc-price", "aria-live": "polite", "aria-atomic": "true" });
      S.codeEl = el("div", { class: "pdc-code" });
      S.summary = el("dl", { class: "pdc-summary", "aria-label": T.summary });
      if (ctx.dom.summaryHost) { ctx.dom.summaryHost.textContent = ""; ctx.dom.summaryHost.appendChild(S.summary); }   // cenu a kod ukazuje stranka
      else {
        panel.appendChild(S.priceBox); panel.appendChild(S.codeEl);
        panel.appendChild(el("details", { class: "pdc-group" }, [el("summary", { class: "pdc-group-h", text: T.summary }), S.summary]));
      }
      return panel;
    }
    function rebuildPanel() {
      var old = S.panel; S.panel = buildPanel();
      if (old && old.parentNode) old.parentNode.replaceChild(S.panel, old);
      S.panel.hidden = S.view !== "configurator";
      applyState();
    }
    function updateMini() {
      if (!S.mini) return;
      var changed = !same(S.sel, S.defaults);
      S.mini.hidden = !changed || S.view !== "turntable";
      if (changed) S.mini.textContent = T.turntableNote;
    }
    function buildTabs() {
      var bar = el("div", { class: "pdc-tabs", role: "tablist" });
      var t1 = el("button", { type: "button", class: "pd-gallery-tab active", role: "tab", "aria-selected": "true", text: T.tabTurntable });
      var t2 = el("button", { type: "button", class: "pd-gallery-tab", role: "tab", "aria-selected": "false", text: T.tabConfigurator });
      t1.addEventListener("click", openTurntable); t2.addEventListener("click", openConfigurator);
      bar.appendChild(t1); bar.appendChild(t2);
      S.tabs = { bar: bar, t1: t1, t2: t2 };
      S.cta = el("button", { type: "button", class: "pdc-cta", text: T.cta });
      S.cta.addEventListener("click", openConfigurator);
      S.mini = el("p", { class: "pdc-mini", hidden: true });
    }

    // -------------------------------------------------------------- pohledy
    function setView(v) {
      S.view = v;
      var conf = v === "configurator";
      S.tabs.t1.classList.toggle("active", !conf); S.tabs.t2.classList.toggle("active", conf);
      S.tabs.t1.setAttribute("aria-selected", conf ? "false" : "true"); S.tabs.t2.setAttribute("aria-selected", conf ? "true" : "false");
      (ctx.dom.visual || []).forEach(function (e) { if (e) e.hidden = conf && !S.viewerFailed; });
      S.stage.hidden = !conf || S.viewerFailed;
      S.panel.hidden = !conf;
      S.cta.hidden = conf;
      document.body.classList.toggle("pdc-active", conf);
      pg.onActivate(conf);
      updateMini();
    }
    function openTurntable() { setView("turntable"); }
    function openConfigurator() {
      if (S.view === "configurator") return;
      pg.track("configurator_open", {});
      setView("configurator");
      ensureViewer().then(function () { if (S.last) handleModel(S.last); });
    }

    // -------------------------------------------------------------- 3D
    // Sitove stahovani a spusteni skriptu prohlizece (bez vazby na DOM stranky). Zacina HNED pri init (souběžně se schématem a prvním resolve), ne až po sestavení stránky:
    // viewer3d.js, jeho CSS i závislosti three z CDN se stahují PARALELNĚ (skripty se vkládají naráz s async=false - stahují se najednou, spouštějí v pořadí vložení).
    // Dřív se závislosti (7 skriptů) stahovaly SÉRIOVĚ a model začal až po nich (bot8 2026-10-04: model na baliace-stoly.top se načítá dlouho).
    function fetchAssets() {
      if (S.assetsFetch) return S.assetsFetch;
      var a = ctx.assets || {};
      var cssP = Promise.all((a.css || []).map(loadCss));
      var viewerP = global.V3D && global.V3D.mount ? Promise.resolve() : loadScript(a.viewer || "/js/v3d/viewer3d.js");
      S.assetsFetch = viewerP.then(function () {
        var all = ((global.V3D && global.V3D.deps) || []).slice(), T3 = global.THREE;
        var have = !!(T3 && T3.OrbitControls && T3.GLTFLoader && T3.CSS2DRenderer);                         // uz nactene jinym prvkem stranky (napr. Pripni cokoli): neopakovat, three se nesmi nacist dvakrat
        var deps = have ? [] : all.slice();
        if (all.length && /build\/three\.min\.js$/.test(all[0]) && !(T3 && T3.RGBELoader)) deps.push(all[0].replace(/build\/three\.min\.js$/, "examples/js/loaders/RGBELoader.js"));    // prostredi z HDRI si ho jinak dotahne viewer az pri mountu (dalsi kolo po modelu)
        var jobs = deps.map(function (u, i) { var pr = loadScript(u); return i === deps.length - 1 && /RGBELoader/.test(u) ? pr.catch(function () { /* viewer si ho dotahne sam / pouzije zalozni prostredi */ }) : pr; });
        if (a.ovladani && !global.V3DOvladani) jobs.push(loadScript(a.ovladani).catch(function () { /* bez ovladani ve 3D volby funguji dal */ }));
        return Promise.all(jobs);
      }).then(function () { return cssP; });
      return S.assetsFetch;
    }
    function ensureAssets() {
      if (S.assets) return S.assets;
      S.assets = fetchAssets().then(function () { createOvladani(); });
      return S.assets;
    }
    // hotovy model (stav "hotovo") se zacne stahovat uz po prvnim resolve - GLTFLoader ho pak vezme z mezipameti prohlizece (Cache-Control private, max-age) misto aby cekal na konec stahovani skriptu
    function prefetchModel(r) {
      var m = r && r.model;
      if (!m || m.stav !== "hotovo" || !m.url || S.viewer || S.prefetched === m.url || !global.fetch) return;
      S.prefetched = m.url;
      try { global.fetch(m.url, { credentials: "same-origin" }).catch(function () { /* jen predstahnuti */ }); } catch (e) { /* nic */ }
    }
    function ensureViewer() {
      if (S.viewer || S.viewerFailed) return Promise.resolve();
      if (!webglOk()) { failViewer(T.noWebgl); return Promise.resolve(); }
      return ensureAssets().catch(function () { failViewer(T.viewerErr); });
    }
    function failViewer(msg) {
      S.viewerFailed = true;
      showNotice(msg, true);
      if (S.view === "configurator") { (ctx.dom.visual || []).forEach(function (e) { if (e) e.hidden = false; }); S.stage.hidden = true; }
    }
    function handleModel(r) {
      if (S.view !== "configurator" || S.viewerFailed || !r || !r.model) return;
      var m = r.model, hash = r.hash;
      clearTimeout(S.poll);
      if (m.stav === "hotovo" && m.url) return showModel(m.url, hash);
      if (m.stav === "chyba") { setStageMsg(T.modelErr); return; }
      setStageMsg(T.modelPrep);
      pollModel(hash, m.odhad_ms || 600, Date.now());
    }
    function pollModel(hash, wait, t0) {
      S.poll = setTimeout(function () {
        if (!S.last || S.last.hash !== hash || S.view !== "configurator") return; // zatim prisel novejsi vyber
        http("GET", MODEL + encodeURIComponent(hash)).then(function (d) {
          if (!S.last || S.last.hash !== hash) return;
          var m = d && d.model;
          if (m && m.stav === "hotovo" && m.url) return showModel(m.url, hash);
          if (m && m.stav === "chyba") return setStageMsg(T.modelErr);
          if (Date.now() - t0 > 30000) return setStageMsg(T.modelErr);
          pollModel(hash, 500, t0);
        }).catch(function (e) {
          if (e && e.status === 429 && Date.now() - t0 <= 30000) return pollModel(hash, Math.min((e.retryAfter || 2), 10) * 1000, t0);
          setStageMsg(T.modelErr);
        });
      }, Math.max(wait, 200));
    }
    function setStageMsg(text) { if (S.stageMsg) { S.stageMsg.textContent = text || ""; S.stageMsg.hidden = !text; } }
    function pluginList() {            // pluginy 3D prohlizece: ovladani ve 3D + pluginy hostitele (page.viewerPlugins(), napr. pocitadlo luxu Generatoru stolu)
      var l = S.ov ? [S.ov.plugin] : [];
      if (typeof page.viewerPlugins === "function") {
        try { [].concat(page.viewerPlugins() || []).forEach(function (p) { if (typeof p === "function") l.push(p); }); } catch (e) { /* hostitel nesmi shodit volby */ }
      }
      return l.length ? l : undefined;
    }
    function mountOpts(o) {
      var x = S.viewerOpts || {}; Object.keys(x).forEach(function (k) { if (!(k in o)) o[k] = x[k]; });
      // KOTY NA VSECH MISTECH (Robert 2026-10-05; drive jen Generator stolu pro zamestnance, bot8): prepinac Koty a koty z modelu maji vsechna mista, kde modul bezi; vypnout je smi stranka jen vyslovne
      if (x.hudKoty === false) { o.hudKoty = false; o.dims = 0; }
      else {
        o.hudKoty = true;
        if (x.dims === 0 || x.dims === 1 || x.dims === 2) o.dims = x.dims;
        else if (global.matchMedia && global.matchMedia("(max-width: 700px)").matches) o.dims = 0;         // maly nahled by koty zahltily: prepinac je, koty jsou po nacteni vypnute
        else delete o.dims;                                                                                // bez `dims` plati vychozi viewer (model s koty ve spec = uroven 1)
      }
      if (!("envConfig" in o) && S.schema && S.schema.env && typeof S.schema.env === "object") o.envConfig = S.schema.env;     // ulozene prostredi (HDRI) z verejneho schematu; bez `env` se nic nemeni
      if (!("isoAngles" in o) && S.schema && S.schema.view && typeof S.schema.view === "object") o.isoAngles = S.schema.view;      // vychozi uhel pohledu 3D {az, el} (Robert 2026-10-08; viewer 1.17.0); bez `view` plati puvodnich 35 / 25
      return o;
    }     // volby stranky nepřepisují zakladni
    // Koty (stranky s hudKoty, tj. Generator stolu pro zamestnance): behem tazeni ve 3D se model meni jen v prohlizeci a koty by ukazovaly puvodni cisla - na dobu tazeni se vypnou a vraci se
    // s presnym modelem (po dotazeni modelu, pri chybe nebo nejpozdeji 8 s po pusteni). Volba "Vyp" od uzivatele se nikdy nezapina: vraci se jen uroven, kterou tazeni vypnulo.
    function kotyBehemTazeni() {
      try {
        var st = S.viewer && S.viewer.state ? S.viewer.state() : null;
        if (st && st.dims > 0 && S.kotyPredTazenim == null && typeof S.viewer.setDims === "function") { S.kotyPredTazenim = st.dims; S.viewer.setDims(0); }
      } catch (e) { /* koty nesmi shodit tazeni */ }
    }
    function kotyZpet() {
      if (S.kotyPredTazenim == null || S.drag) return;
      var d = S.kotyPredTazenim; S.kotyPredTazenim = null; clearTimeout(S.kotyTimer);
      try { if (S.viewer && typeof S.viewer.setDims === "function") S.viewer.setDims(d); } catch (e) { /* nic */ }
    }
    function showModel(url, hash) {
      if (S.modelHash === hash) { setStageMsg(""); kotyZpet(); return; }
      var req = ++S.modelReq;
      function done() { if (req === S.modelReq) { S.modelHash = hash; setStageMsg(""); giveDescription(S.last); kotyZpet(); try { pg.onModel(url, hash); } catch (e) { /* hostitel nesmi shodit volby */ } } }
      function fail() { if (req === S.modelReq) { setStageMsg(T.modelErr); kotyZpet(); } }
      try {
        if (!S.viewer) {
          S.viewer = global.V3D.mount(S.stageCanvas, mountOpts({ plugins: pluginList(), modelUrl: url, labels: S.viewerLabels, onPick: onPick, track: function (k, d) { pg.track(k, d); }, onError: fail }));
          if (S.ov) S.ov.setViewer(S.viewer);
          try { pg.onViewer(S.viewer); } catch (e) { /* hostitel nesmi shodit volby */ }
          if (S.viewer && S.viewer.ready) S.viewer.ready.then(done, fail); else done();
        } else if (typeof S.viewer.setModel === "function") {
          Promise.resolve(S.viewer.setModel(url, { keepCamera: true })).then(done, fail);
        } else { // starsi viewer bez setModel: znovu pripojit (kamera se zahodi)
          if (S.ov) S.ov.setViewer(null);
          S.viewer.dispose(); S.stageCanvas.textContent = "";
          S.viewer = global.V3D.mount(S.stageCanvas, mountOpts({ plugins: pluginList(), modelUrl: url, labels: S.viewerLabels, onPick: onPick, onError: fail }));
          if (S.ov) S.ov.setViewer(S.viewer);
          try { pg.onViewer(S.viewer); } catch (e) { /* hostitel nesmi shodit volby */ }
          if (S.viewer && S.viewer.ready) S.viewer.ready.then(done, fail); else done();
        }
      } catch (e) { fail(); }
    }
    function onPick(g) {
      var sel = '[data-g="' + String(g).replace(/"/g, "") + '"]', node = null;
      (S.groupEls || []).some(function (x) { node = x.el.querySelector(sel); return !!node; });
      if (!node && S.panel) node = S.panel.querySelector(sel);
      if (!node) return;
      var det = node.closest("details"); if (det) det.setAttribute("open", "");
      if (typeof ctx.dom.reveal === "function") ctx.dom.reveal(node);
      node.classList.add("pdc-flash");
      setTimeout(function () { node.classList.remove("pdc-flash"); }, 1200);
      try { node.scrollIntoView({ block: "nearest", behavior: "smooth" }); var f = node.querySelector("input,select,button"); if (f) f.focus({ preventScroll: true }); } catch (e) {}
    }

    // -------------------------------------------------------------- ovladani primo ve 3D (obecny modul v3d-ovladani.js, bot8)
    function clampToOptions(slotId, v, schemaOnly) {
      var o = schemaOnly ? null : S.last && S.last.options && S.last.options[slotId], sl = slotById(slotId);       // schemaOnly: meze z options platily pro VYPNUTOU volbu, nová přijdou až z resolve
      if (typeof v !== "number" || !isFinite(v)) return v;
      var lo = o && isFinite(o.min) ? o.min : (sl && sl.slider ? sl.slider.min : null), hi = o && isFinite(o.max) ? o.max : (sl && sl.slider ? sl.slider.max : null);
      if (lo != null && v < lo) v = lo;
      if (hi != null && v > hi) v = hi;
      return v;
    }
    function slotNode(slotId) {
      var q = '[data-slot="' + String(slotId).replace(/"/g, "") + '"]';
      return (S.groupEls || []).reduce(function (f, x) { return f || x.el.querySelector(q); }, null) || (S.panel && S.panel.querySelector(q));
    }
    function scheduleDragResolve() {                  // behem tazeni bez zive nahrady: nejvys jeden dotaz naraz, vzdy s nejnovejsimi hodnotami
      if (S.dragBusy) { S.dragDirty = true; return; }
      S.dragBusy = true; S.dragDirty = false;
      resolve(clone(S.sel)).then(function () { S.dragBusy = false; if (S.dragDirty && S.drag) scheduleDragResolve(); }, function () { S.dragBusy = false; });
    }
    function createOvladani() {
      if (S.ov || !global.V3DOvladani || !S.stage || !S.stageCanvas) return;
      var overlay = el("div", { class: "pdc-ov" }); S.stage.appendChild(overlay);
      var linked = [];
      var applyOvPatch = function (patch, o) {
          Object.keys(patch || {}).forEach(function (k) { if (patch[k] === false && S.sel[k]) S.userOff[k] = true; else if (patch[k] === true) delete S.userOff[k]; });   // vypnuti/zapnuti z nabidky ve 3D je rozhodnuti zakaznika
          var turnsOn = {};                          // patch zapina volbu (napr. cut1:true) -> jeji zavisle sloty (cut1x, cut1z...) se NEoriznou podle starych mezi (min=max, dokud byl vypnuty)
          Object.keys(patch || {}).forEach(function (k) { if (patch[k] && !S.sel[k]) turnsOn[k] = 1; });
          Object.keys(patch || {}).forEach(function (k) {
            S.sel[k] = patch[k] === null ? S.defaults[k] : clampToOptions(k, patch[k], slotDeps(k).some(function (d) { return turnsOn[d]; }));
          });
          applyState();
          if (o && o.live) return;                    // ziva nahrada: vrcholy se hybou v prohlizeci, server az po pusteni
          if (S.drag) scheduleDragResolve(); else { clearTimeout(commitTimer); S.commitPending = true; commitTimer = setTimeout(function () { resolve(clone(S.sel)); }, 250); }      // commitPending jako u panelu: odpoved STARSIHO dotazu (letel pred patchem) patch neprepise
        };
      if (global.__pdcDebug) global.__pdcApplyPatch = applyOvPatch;   // jen pro testy
      S.ov = global.V3DOvladani.create({
        stage: S.stageCanvas, overlay: overlay,
        getParams: function () { return S.sel; },
        applyPatch: applyOvPatch,
        dragState: function (on, tah, o) {
          if (on) { S.drag = { live: !!(o && o.live) }; kotyBehemTazeni(); try { pg.onDrag(true); } catch (e) { /* hostitel nesmi shodit tazeni */ } return; }
          S.drag = null; S.dragBusy = false; clearTimeout(commitTimer);
          try { pg.onDrag(false); } catch (e) { /* hostitel nesmi shodit tazeni */ }
          clearTimeout(S.kotyTimer); S.kotyTimer = setTimeout(kotyZpet, 8000);              // pojistka: koty se vrati, i kdyby presny model dlouho nechodil
          resolve(clone(S.sel));                      // po pusteni presny model se skutecnymi hodnotami (server je pripadne orizne)
        },
        onLink: function (params) {
          linked.forEach(function (n) { n.classList.remove("v3do-lnk"); }); linked = [];
          (params || []).forEach(function (pr) { var n = slotNode(pr); if (n) { n.classList.add("v3do-lnk"); linked.push(n); } });
        },
        focusParam: function (slotId) {
          var n = slotNode(slotId); if (!n) return;
          if (typeof ctx.dom.reveal === "function") ctx.dom.reveal(n);
          var det = n.closest("details"); if (det) det.setAttribute("open", "");
          n.classList.add("pdc-flash"); setTimeout(function () { n.classList.remove("pdc-flash"); }, 1200);
          try { n.scrollIntoView({ block: "nearest", behavior: "smooth" }); var f = n.querySelector("input,select,button"); if (f) f.focus({ preventScroll: true }); } catch (e) { /* nic */ }
        },
        texts: ctx.ovladaniTexty && typeof ctx.ovladaniTexty === "object" ? ctx.ovladaniTexty : undefined
      });
    }
    function giveDescription(r) { if (S.ov && r) { try { S.ov.setDescription(r.vodici && r.vodici.ovladani ? r.vodici.ovladani : null); } catch (e) { /* ovladani nesmi shodit volby */ } } }

    // -------------------------------------------------------------- prepinac systemu profilu (stul 30 / 40; Robert 2026-10-05 "prepinac dame klientovi")
    // Hostitel da ctx.systemSwitch {go(target, vyber), available(system) = smi se nabidnout, mount(box) = kam prepinac vlozit}; modul ho ukaze jen kdyz jsou aktivni 2+ systemy
    // (schema.systems) a hostitel umi na dalsi prejit. Do hashe se posila jen to, co se lisi od vychozich voleb TOHOTO systemu: ostatni zustane vychozi hodnotou druheho systemu.
    function sysName(n) { return T["sys" + n] || T.sysOpt.replace("{n}", n); }
    function diffSel() { var d = {}; Object.keys(S.sel).forEach(function (k) { if (!same(S.sel[k], S.defaults[k])) d[k] = S.sel[k]; }); return d; }
    function buildSystemSwitch() {
      var sw = ctx.systemSwitch;
      if (!sw || typeof sw.go !== "function" || !S.schema || S.schema.system == null) return;
      var cur = Number(S.schema.system);
      var list = (Array.isArray(S.schema.systems) ? S.schema.systems : []).filter(function (x) { return x && x.active && isFinite(Number(x.system)) && (typeof sw.available !== "function" || sw.available(x)); });
      if (list.length < 2 || !list.some(function (x) { return Number(x.system) === cur; })) return;
      var seg = el("div", { class: "pdc-sys-seg" });
      list.forEach(function (x) {
        var n = Number(x.system), on = n === cur;
        var b = el("button", { type: "button", class: "pdc-sys-b", "data-system": String(n), "aria-pressed": on ? "true" : "false", text: sysName(n) });
        if (!on) b.addEventListener("click", function () {
          pg.track("configurator_system_switch", { from: cur, to: n });
          Array.prototype.forEach.call(seg.children, function (c) { c.disabled = true; });
          try { sw.go({ system: n, card_id: x.card_id }, diffSel()); } catch (e) { Array.prototype.forEach.call(seg.children, function (c) { c.disabled = false; }); }
        });
        seg.appendChild(b);
      });
      S.sysBox = el("div", { class: "pdc-sys", role: "group", "aria-label": T.sysLabel }, [el("span", { class: "pdc-sys-l", text: T.sysLabel }), seg]);
      if (typeof sw.mount === "function") sw.mount(S.sysBox); else ctx.dom.panelHost.insertBefore(S.sysBox, ctx.dom.panelHost.firstChild);
    }

    // -------------------------------------------------------------- sestaveni
    ctx.__started = true;
    if ((ctx.noTurntable || product.configurator.default_view === "configurator") && webglOk()) fetchAssets().catch(function () { /* chybu ukaze ensureViewer pri zobrazeni */ });
    var now = (ctx.assets && ctx.assets.cssNow) || [];
    return Promise.all(now.map(loadCss)).then(loadSchema).then(function () {
      S.sel = clone(S.defaults);
      if (ctx.initialSelection && typeof ctx.initialSelection === "object") {            // pocatecni vyber (hash v URL...): jen znamé sloty, zbytek vychozi
        var ini = sanitizeSel(ctx.initialSelection); Object.keys(ini).forEach(function (k) { S.sel[k] = ini[k]; });
      }
      return resolve(clone(S.sel));
    }).then(function (r) {
      if (!r) throw new Error("resolve");
      buildTabs();
      S.stage = el("div", { class: "pdc-stage", hidden: true });
      S.stageCanvas = el("div", { class: "pdc-stage-canvas" });
      S.stageMsg = el("div", { class: "pdc-stage-msg", role: "status", hidden: true });
      var lock = el("button", { type: "button", class: "pdc-lock", text: T.lock });
      lock.addEventListener("click", function () { S.stage.classList.add("pdc-unlocked"); });
      document.addEventListener("touchstart", function (e) { if (S.stage && !S.stage.contains(e.target)) S.stage.classList.remove("pdc-unlocked"); }, { passive: true });
      S.stage.appendChild(S.stageCanvas); S.stage.appendChild(S.stageMsg); S.stage.appendChild(lock);
      S.panel = buildPanel();
      var before = ctx.dom.tabsBefore;
      if (before && before.parentNode && !ctx.noTurntable) { before.parentNode.insertBefore(S.tabs.bar, before); }
      ctx.dom.stageHost.appendChild(S.stage);
      if (!ctx.noTurntable) { ctx.dom.stageHost.appendChild(S.cta); ctx.dom.stageHost.appendChild(S.mini); }
      ctx.dom.panelHost.appendChild(S.panel);
      buildSystemSwitch();
      document.body.classList.add("pdc-configurable"); // CSS skryje posuvnik provedeni a karty montaze/boxu, volby je nahrazuji
      applyState();
      if (ctx.noTurntable || product.configurator.default_view === "configurator") openConfigurator();
      var ctl = {
        active: function () { return true; },
        view: function () { return S.view; },
        refresh: function () { return resolve(clone(S.sel)); },     // znovu overit vyber (napr. po 409 rules_changed z kosiku -> modul nacte nove schema)
        envConfig: function () { return S.schema && S.schema.env && typeof S.schema.env === "object" ? S.schema.env : null; },     // ulozene prostredi (HDRI) hlavniho prohlizece - hostitel ho muze dat dalsimu 3D prvku, at HDR nestahuje podruhe
        profile: function () { return S.schema && typeof S.schema.profile === "string" && S.schema.profile ? S.schema.profile : null; },       // profil produktu ze schematu ("30x30"): okno Hlavni profil a ukazka Pripni cokoli na stejnem modulu
        system: function () { return S.schema && S.schema.system != null ? S.schema.system : null; },                            // system profilu produktu (stul: 30 | 40); produkt bez systemu = null
        systems: function () { return S.schema && Array.isArray(S.schema.systems) ? clone(S.schema.systems) : []; },       // [{system, card_id, active}] karty vsech systemu tehoz stolu (prepinac systemu)
        viewer: function () { return S.viewer || null; },      // 3D prohlizec (pro hostitele, napr. admin-only panel V3D.envPicker na strance stolu); null, dokud se nenacetl
        summary: function () {            // [{label, value}] pro souhrn v kosiku (cteni jen z aktualniho vyberu)
          return shownSlots().map(function (slot) { return { label: slot.label, value: labelOf(slot, S.sel[slot.id]) }; });
        },
        cartPayload: function () {
          if (S.pending || !S.last || S.last.valid === false || !S.last.hash) return null;
          return { configuration: { selection: clone(S.sel), hash: S.last.hash, rules_version: S.last.rules_version || S.schema.rules_version }, kod: S.last.kod || null };
        },
        openConfigurator: openConfigurator, openTurntable: openTurntable,
        destroy: function () {
          if (S.ov) { try { S.ov.destroy(); } catch (e) { /* nic */ } S.ov = null; }
          clearTimeout(S.poll); clearTimeout(commitTimer);
          if (S.viewer && S.viewer.dispose) { try { S.viewer.dispose(); } catch (e) {} }
          [S.tabs && S.tabs.bar, S.stage, S.cta, S.mini, S.panel, S.sysBox].concat((S.groupEls || []).map(function (x) { return x.el; })).forEach(function (n) { if (n && n.parentNode) n.parentNode.removeChild(n); });
          document.body.classList.remove("pdc-active", "pdc-configurable");
          (ctx.dom.visual || []).forEach(function (e) { if (e) e.hidden = false; });
          pg.onActivate(false);
        }
      };
      return ctl;
    }).catch(function () { return null; });
  };
})(window);
