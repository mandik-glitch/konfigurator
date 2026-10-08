/* Mini-shop - obsah stranek (bot16, 2026-10-02). Vsechny texty pres MW.t(klic) (i18n/<jazyk>.json), zadny pevny text. Data (kategorie, produkty,
 * configurator) jdou z API; v demu je dodava demo-api.js. Kosik je mistni, jen po dobu relace (sessionStorage), skutecny kosik/objednavku/dopravu dodava bot5. */
(function (global) {
  "use strict";
  var P = global.MWP = {};
  var E = function () { return MW.el.apply(null, arguments); };
  var CFG_LABEL_KEYS = ["auto", "allowed", "tabTurntable", "tabConfigurator", "cta", "title", "reset", "price", "noVat", "withVat", "pending", "code", "summary", "unavailable", "turntableNote",
                        "errLoad", "errNet", "retry", "rateLimit", "rulesChanged", "modelPrep", "modelErr", "noWebgl", "viewerErr", "lock", "invalid", "lockHint", "yes", "no", "sysLabel", "sys30", "sys35", "sys40", "sys41", "sysOpt"];

  function configuratorLabels() {
    var out = {};
    CFG_LABEL_KEYS.forEach(function (k) { if (Object.prototype.hasOwnProperty.call(MW.dict, "pdc." + k)) out[k] = MW.t("pdc." + k); });
    return out;
  }
  function ovladaniTexty() {                                                       // texty modulu ovladani ve 3D (v3d-ovladani.js) v jazyce shopu
    var o = {}; ["menuHint", "obstacle", "toObstacle", "atMin", "atMax", "atLimit", "esc", "unit"].forEach(function (k) { var key = "v3do." + k; if (MW.dict && Object.prototype.hasOwnProperty.call(MW.dict, key)) o[k] = MW.dict[key]; });
    return o;
  }
  function viewerLabels() {                                                         // slovnik textu 3D prohlizece (viewer3d.js labels): klice v3d.* v i18n
    var out = {};
    Object.keys(MW.dict).forEach(function (k) { if (k.indexOf("v3d.") === 0) out[k.slice(4)] = MW.dict[k]; });
    return out;
  }
  function demoOn() { return MW.params.demo === "1" || (MW.cfg && MW.cfg.demo === true); }
  function api(path, extra) { return MW.api(path, extra); }
  function priceLine(p) {
    if (MW.mode().price === "hidden") return E("p", { class: "mw-price mw-muted", i18n: "price.on_request" });
    if (p.price_from == null) return E("p", { class: "mw-price mw-muted", i18n: "price.by_config" });          // cena se ukaze az v configurator
    return E("p", { class: "mw-price" }, [E("span", { class: "mw-from", text: MW.t("card.from") + " " }), E("strong", { text: MW.money(p.price_from) }), E("small", { text: " " + MW.t("price.excl_vat") })]);
  }
  function itemPayload(it) { return { product_id: it.product_id, qty: it.qty, kod: it.kod, configuration: it.configuration, summary: it.summary }; }   // cena se NIKDY neposila, server ji pocita z konfigurace
  function orderItem(it) { return { product_id: it.product_id, qty: it.qty, montaz: it.montaz === true ? true : undefined, configuration: it.configuration ? { selection: it.configuration.selection, rules_version: it.configuration.rules_version } : undefined }; }   // quote/objednavka: jen volby, zadna cena
  function errKey(e, fallback) { var c = e && e.body && e.body.error; return c && MW.dict && Object.prototype.hasOwnProperty.call(MW.dict, "err." + c) ? "err." + c : fallback; }
  function postInquiry(v) { return MW.postApi("/api/miniweb/inquiry", v); }
  // spravce osobnich udaju u formularu = prodavajici ze serveru (/api/miniweb/legal, jediny zdroj udaju o prodavajicim; staticke soubory nazev firmy nemaji)
  function controllerNote() {
    var p = E("p", { class: "mw-fine mw-controller", hidden: true });
    api("/api/miniweb/legal").then(function (d) {
      var s = d && d.seller;
      if (!s || !s.name) return;
      p.textContent = MW.t("inq.controller", { seller: [s.name, s.address].filter(Boolean).join(", ") }); p.hidden = false;
    }).catch(function () { /* bez udaju se poznamka neukaze */ });
    return p;
  }
  function b2bNote() { return null; }     // veta "jen pro podnikatele" se nezobrazuje (Robert 2026-10-03: staci ceny bez DPH); formular dal vyzaduje firmu a ICO
  function honeypot() { return E("input", { type: "text", name: "website", class: "mw-hp", tabindex: "-1", autocomplete: "off", "aria-hidden": "true" }); }
  // skutecny snimek vychozi konfigurace (3D model, tmave pozadi, bez kot a loga) - nic nakreslenou ikonou (Robert 2026-10-03); chybi-li, blok se vynecha
  // Stitky na karte jako v prehledech hlavniho e-shopu (category.html: drazka .groove-badge, profil .profil-badge) - STEJNE PRAVIDLO: stitek jen kdyz server dodal hodnotu
  // (groove_family "8" nebo "6,8,10" = vice stitku; profil_mm = hlavni prurez; prazdne = zadny stitek). Zavit a umisteni v aute se nepreberaji (stul je nema).
  // Dodani: z textu delivery se vezme rozsah tydnu (napr. "3-5"), nic se nevymysli; bez rozsahu zadny stitek.
  function badge(cls, text) { return E("span", { class: "mw-badge " + cls, text: text }); }
  function grooveBadges(p) {
    return String(p.groove_family || "").split(",").map(function (g) { return g.trim(); }).filter(function (g) { return /^\d{1,2}$/.test(g); })
      .map(function (g) { return badge("mw-badge-groove", MW.t("badge.groove", { n: g })); });
  }
  function deliveryBadge(p) {
    var m = /(\d{1,2})\s*[\u2013-]\s*(\d{1,2})\s*(?:t\u00fd[\u017ed]|week)/i.exec(p.delivery || "");
    return m ? [badge("mw-badge-delivery", MW.t("badge.delivery", { n: m[1] + "\u2013" + m[2] }))] : [];
  }
  function profilBadge(p) { return p.profil_mm ? badge("mw-badge-profil", p.profil_mm + "\u00d7" + p.profil_mm) : null; }
  function productImage(p, overlay) {
    var cpid = p.configurator && p.configurator.product_id, url = p.image_url || (cpid ? "/miniweb/img/produkt-" + cpid + ".jpg" : null);
    if (!url) return null;
    var img = E("img", { src: url, alt: p.name, loading: "lazy", width: "1200", height: "900" });
    var box = E("div", { class: "mw-card-img" }, [img, overlay || null]);
    img.addEventListener("error", function () { if (box.parentNode) box.parentNode.removeChild(box); });
    return box;
  }
  function cardOf(p) {
    var a = E("a", { class: "mw-card", href: MW.link("product.html", { id: p.id, slug: p.slug }) }, [
      productImage(p, profilBadge(p)),
      E("div", { class: "mw-card-body" }, [
        E("h3", { text: p.name }), E("p", { class: "mw-muted", text: p.summary || "" }),
        E("div", { class: "mw-badges" }, grooveBadges(p).concat(deliveryBadge(p))),
        priceLine(p),
        E("span", { class: "mw-btn mw-btn-sm", text: MW.t("card.configure") })
      ])
    ]);
    return a;
  }
  function tree(cats, activeSlug) {
    var byParent = {};
    cats.forEach(function (c) { (byParent[c.parent_id == null ? "root" : c.parent_id] = byParent[c.parent_id == null ? "root" : c.parent_id] || []).push(c); });
    function level(parent) {
      var ul = E("ul", { class: "mw-tree" });
      (byParent[parent] || []).forEach(function (c) {
        var li = E("li", {}, [E("a", { href: MW.link("category.html", { cat: c.slug }), "aria-current": c.slug === activeSlug ? "page" : null, text: c.name + " (" + c.count + ")" })]);
        if (byParent[c.id]) li.appendChild(level(c.id));
        ul.appendChild(li);
      });
      return ul;
    }
    return level("root");
  }
  function mainEl() { var m = document.getElementById("mwMain"); m.textContent = ""; return m; }
  function crumbs(items) {
    return E("nav", { class: "mw-crumbs", "aria-label": MW.t("nav.breadcrumb") }, items.map(function (it, i) {
      return it.href ? E("a", { href: it.href, text: it.text }) : E("span", { "aria-current": "page", text: it.text });
    }));
  }

  // ------------------------------------------------------------------ uvod
  P.home = function () {
    return Promise.all([api("/api/miniweb/categories"), api("/api/miniweb/products")]).then(function (r) {
      var m = mainEl(), cats = r[0].categories || [], prods = r[1].products || [];
      // Dva a vice VEREJNYCH produktu (dva stoly: system 30 a 40): texty uvodu s priponou ".multi" nahradi zakladni klic (zakladni = obchod s jednim stolem), takze text vzdy
      // odpovida tomu, co je v obchode videt, i kdyz Robert druhy produkt schvali az pozdeji. Stejne pravidlo ma server-side HTML (api/miniweb_seo.py::_varianta).
      if (prods.length > 1) Object.keys(MW.dict).forEach(function (k) { if (/\.multi$/.test(k)) MW.dict[k.slice(0, -6)] = MW.dict[k]; });
      // Tri a vice verejnych produktu (stoly 30, 35 a 40): ".multi3" prepise i ".multi" (bot7 2026-10-05); stejne pravidlo ma server-side HTML (api/miniweb_seo.py::_varianta)
      if (prods.length > 2) Object.keys(MW.dict).forEach(function (k) { if (/\.multi3$/.test(k)) MW.dict[k.slice(0, -7)] = MW.dict[k]; });
      var has = function (k) { return Object.prototype.hasOwnProperty.call(MW.dict, k); }, rich = has("home.h1");
      var inq = MW.mode().checkout === "inquiry";
      m.appendChild(E("section", { class: "mw-hero" }, [
        E("p", { class: "mw-kicker", i18n: "home.kicker" }), E("h1", { i18n: rich ? "home.h1" : "home.title" }), E("p", { class: "mw-lead", i18n: "home.lead" }),
        E("div", { class: "mw-actions" }, [E("a", { class: "mw-btn", href: prods[0] ? MW.link("product.html", { id: prods[0].id, slug: prods[0].slug }) : MW.link("category.html"), i18n: "home.cta" }),
                                         E("a", { class: "mw-btn mw-btn-ghost", href: "#how", i18n: "home.how" })])
      ]));
      if (has("home.usp1.t")) m.appendChild(E("section", { class: "mw-section" }, [E("h2", { i18n: "home.why_title" }), E("ul", { class: "mw-steps mw-usp" }, [1, 2, 3, 4].filter(function (n) { return has("home.usp" + n + ".t"); }).map(function (n) {
        return E("li", {}, [E("strong", { i18n: "home.usp" + n + ".t" }), E("p", { i18n: "home.usp" + n + ".d" })]);
      }))]));
      if (!rich && cats.length) m.appendChild(E("section", { class: "mw-section" }, [E("h2", { i18n: "home.categories" }), tree(cats, null)]));
      m.appendChild(E("section", { class: "mw-section" }, [E("h2", { i18n: "home.products" }), E("div", { class: "mw-grid" }, prods.map(cardOf))]));
      if (has("home.extras_title")) m.appendChild(E("section", { class: "mw-section" }, [E("h2", { i18n: "home.extras_title" }), E("p", { class: "mw-pre", i18n: "home.extras" })]));
      m.appendChild(E("section", { class: "mw-section", id: "how" }, [E("h2", { i18n: "home.how_title" }), E("ol", { class: "mw-steps" }, [1, 2, 3].map(function (n) {
        var sfx = inq ? ".inquiry" : "", kt = "home.step" + n + ".t", kd = "home.step" + n + ".d";      // varianta textu pro poptavkovy rezim, kdyz existuje
        if (sfx && has(kt + sfx)) kt += sfx;
        if (sfx && has(kd + sfx)) kd += sfx;
        return E("li", {}, [E("strong", { i18n: kt }), E("p", { i18n: kd })]);
      }))]));
      if (has("faq.1.q")) {
        var faq = [];
        for (var n = 1; has("faq." + n + ".q"); n++) faq.push(E("details", { class: "mw-faq" }, [E("summary", { i18n: "faq." + n + ".q" }), E("p", { class: "mw-pre", i18n: "faq." + n + ".a" })]));
        m.appendChild(E("section", { class: "mw-section", id: "faq" }, [E("h2", { i18n: "home.faq_title" })].concat(faq)));
      }
      if (has("home.cta2.t")) m.appendChild(E("section", { class: "mw-section mw-cta2" }, [E("h2", { i18n: "home.cta2.t" }), E("p", { i18n: "home.cta2.d" }),
        E("a", { class: "mw-btn", href: prods[0] ? MW.link("product.html", { id: prods[0].id, slug: prods[0].slug }) : MW.link("category.html"), i18n: "home.cta" })]));
      document.title = MW.t("home.title") + " – " + MW.t("brand.name");
    });
  };


  // ------------------------------------------------------------------ kategorie
  P.category = function () {
    var slug = new URLSearchParams(location.search).get("cat") || (window.MW_BOOT && window.MW_BOOT.page === "category" ? (window.MW_BOOT.cat || window.MW_BOOT.slug) : null);
    return Promise.all([api("/api/miniweb/categories"), api("/api/miniweb/products", { category: slug })]).then(function (r) {
      var m = mainEl(), cats = r[0].categories || [], prods = (r[1].products || []);
      var current = slug ? cats.filter(function (x) { return x.slug === slug; })[0] : null;
      m.appendChild(crumbs([{ href: MW.link("index.html"), text: MW.t("nav.home") }, { text: current ? current.name : MW.t("nav.shop") }]));
      var side = E("aside", { class: "mw-side", "aria-label": MW.t("nav.categories") }, [E("h2", { class: "mw-side-h", i18n: "nav.categories" }), tree(cats, slug)]);
      var body = prods.length ? E("div", { class: "mw-grid" }, prods.map(cardOf)) : E("p", { class: "mw-muted", i18n: "category.empty" });
      m.appendChild(E("div", { class: "mw-layout" }, [side, E("div", {}, [E("h1", { text: current ? current.name : MW.t("nav.shop") }), body])]));
      document.title = (current ? current.name : MW.t("nav.shop")) + " – " + MW.t("brand.name");
    });
  };

  // ------------------------------------------------------------------ karta sestavy s configurator
  // Zivy 3D prvek "Pripni cokoli" (bot10, docs/PRIPNI_COKOLI_PRVEK.md) jako okno karty stolu: nacte se az kdyz se k nemu doskroluje (three + viewer se zbytecne netahne)
  // Dlazdice se spousti AZ PO PRVNIM ZOBRAZENI MODELU STOLU (bot8 2026-10-04, mereni: druhy 3D prohlizec + 1,15 MB model + HDR se tahly souběžně se stolem a zdrzovaly ho o sekundy):
  // hlavni prohlizec ohlasi page.onModel -> pri nejblizsi necinnosti (requestIdleCallback) se odblokuje; kdyz model nedorazi do 15 s nebo volby neexistuji, odblokuje se taky.
  // ukazka "Pripni cokoli" a okno "Hlavni profil" jsou SDILENE se vsemi misty generatoru (js/pdc-layout.js: PdcLayout.modelGate / attachWindow / profileWindow; Robert 2026-10-05 "prvky napric generatory na vsech mistech")
  var TILE_JS = "/js/pripni-cokoli-tile.js?v=6ed7fc6c7c", V3D_CSS = "/css/v3d.css?v=c76cbe7292";

  P.product = function () {
    var boot = window.MW_BOOT || {}, id = Number(new URLSearchParams(location.search).get("id")) || Number(boot.id) || 0;
    var sibP = api("/api/miniweb/products", { limit: 200 }).catch(function () { return { products: [] }; });          // sourozenecky produkt (druhy system stolu) pro prepinac; bezi souběžně s nactenim produktu
    // hezka adresa /produkt/<slug> bez id (nahled konceptu): id se dohleda podle slugu
    var idP = id || !boot.slug ? Promise.resolve(id || 9001) : api("/api/miniweb/products", { limit: 200 }).then(function (r) {
      var f = (r.products || []).filter(function (x) { return x.slug === boot.slug; })[0];
      return f ? f.id : 0;
    });
    return idP.then(function (pid) { id = pid; return api("/api/miniweb/products/" + id); }).then(function (d) {
      var p = d.product, m = mainEl(), gate = global.PdcLayout.modelGate();          // gate: ukazka Pripni cokoli se nacita az po prvnim hotovem modelu
      var narrow = !!(global.matchMedia && global.matchMedia("(max-width: 899px)").matches);
      var inquiry = MW.mode().checkout === "inquiry", noPrice = MW.mode().price === "hidden";
      var priceNet = E("strong", { class: "mw-price-main", id: "mwPdPrice", text: noPrice ? MW.t("price.on_request") : "…" });
      var qty = E("input", { type: "number", min: "1", max: "99", value: "1", id: "mwQty", "aria-label": MW.t("pd.qty") });
      var addBtn = E("button", { type: "button", class: "mw-btn", id: "mwAdd", disabled: true, i18n: inquiry ? "pd.add_inquiry" : "pd.add" });
      var msg = E("p", { class: "mw-msg", id: "mwPdMsg", role: "status", "aria-live": "polite" });
      var media = E("div", { class: "mw-pd-media", id: "mwPdMedia" }), panel = E("div", { id: "mwPdPanel" });

      // ---- mrizka oken (navrh: Robert 2026-10-03, "Karta stolu - mrizka oken"): 12 sloupcu, okno = zahlavi + telo; stejna okna pod sebou v mobilu
      var L = global.PdcLayout.create({ E: E, narrow: narrow }), grid = L.grid, win = L.win;      // rozlozeni oken je sdilene se strankou Generator stolu (js/pdc-layout.js)
      var side = E("div", { class: "mw-col mw-col-side" }), col3 = E("div", { class: "mw-col mw-col-3" });
      var wStage = win("stage", MW.t("win.view")), wPrice = win("price", MW.t("win.order")), wBadges = win("badges", MW.t("win.badges"), { hidden: true }),
          wProfile = win("profile", MW.t("win.profile"), { hidden: true }), wDim = win("dim", "", { fold: true, mobileOpen: true, hidden: true }),
          wFrame = win("frame", "", { fold: true, hidden: true }), wExtras = win("extras", "", { fold: true, hidden: true }),
          wShip = win("ship", MW.t("pd.shipping_payment"), { fold: true }), wAttach = win("attach", MW.t("win.attach"), { fold: true, hidden: true }),
          wAdv = win("adv", MW.t("win.advanced"), { fold: true, closed: true, hidden: true }), wSum = win("sum", MW.t("win.summary"), { fold: true, hidden: true }),
          wDesc = win("desc", MW.t("win.desc"), { fold: true }), wSave = win("save", "", { hidden: true });          // wSave: Ulozit konfiguraci - vlastni NESTICKY okno (formular by ve sticky liste cény nevesel na obrazovku telefonu)
      var cfgBar = E("div", { class: "mw-cfgbar" }, [panel]);

      // ---- MONTAZ (volitelna; Robert 2026-10-05): cena ze serveru (quote.lines[0].montaz_option_eur = cele EUR bez DPH, null = nenabizi se), zakaznik procento nevidi.
      // Doprovodny text: s montazi smontovano, bez demontovano (pdc.montazOn / pdc.montazOff, zneni bot7). Server bez montaze (klic v odpovedi chybi) = volba se neukaze.
      var mCb = E("input", { type: "checkbox", id: "mwMontaz" }), mAmt = E("span", { class: "mw-montaz-amt" }), mState = E("p", { class: "mw-montaz-state" });
      var mBox = E("div", { class: "mw-montaz", hidden: true }, [E("label", { class: "mw-opt", for: "mwMontaz" }, [mCb, E("span", { class: "mw-montaz-t", i18n: "pdc.montazLabel" }), mAmt]), mState]);
      var mOpt = null, mTimer = null, mSeq = 0;
      function mRender() {
        mBox.hidden = mOpt == null;
        if (mOpt == null) { mCb.checked = false; return; }
        mAmt.textContent = "+" + MW.money(mOpt) + " " + MW.t("price.excl_vat");
        mState.textContent = MW.t(mCb.checked ? "pdc.montazOn" : "pdc.montazOff");
      }
      mCb.addEventListener("change", mRender);
      function mFetch(r) {                                                         // po kazdem platnem vypoctu konfigurace (kratke zpozdeni kvuli tazeni posuvniku)
        clearTimeout(mTimer);
        if (inquiry || !r || r.valid === false || !r.selection) { mSeq++; mOpt = null; mRender(); return; }
        mTimer = setTimeout(function () {
          var my = ++mSeq;
          MW.postApi("/api/miniweb/quote", { country: (MW.cfg.countries || [])[0], items: [{ product_id: p.id, qty: 1, configuration: { selection: r.selection, rules_version: r.rules_version } }] }).then(function (q) {
            if (my !== mSeq) return;
            var ln = q && q.lines && q.lines[0];
            mOpt = ln && ln.montaz_option_eur > 0 ? ln.montaz_option_eur : null; mRender();
          }).catch(function () { if (my === mSeq) { mOpt = null; mRender(); } });
        }, 400);
      }

      wStage.body.appendChild(media);
      wPrice.body.appendChild(E("div", { class: "mw-buy" }, [
        E("div", { class: "mw-buy-price" }, noPrice ? [priceNet] : [priceNet, E("small", { text: " " + MW.t("price.excl_vat") })]),
        E("label", { class: "mw-qty" }, [E("span", { class: "mw-label", i18n: "pd.qty" }), qty]), addBtn
      ]));
      wPrice.body.appendChild(mBox);
      // ---- ulozeni konfigurace (Robert 2026-10-05): ICO + e-mail + telefon, overeni pred ulozenim, odkaz pro navrat; tlacitko se ukaze jen kdyz backend funkci ma a jsou texty ulozeni.* (bot7)
      var ulozenaTok = global.StulUlozeni ? global.StulUlozeni.tokenFromUrl(location.search) : null;
      var saveUi = global.StulUlozeni ? global.StulUlozeni.create({
        t: function (k, v) { return Object.prototype.hasOwnProperty.call(MW.dict, k) ? MW.t(k, v) : ""; },
        getPayload: function () { var pl = ctl && ctl.cartPayload(); return pl ? { product_id: Number((p.configurator && p.configurator.product_id) || p.id), configuration: { selection: pl.configuration.selection, rules_version: pl.configuration.rules_version } } : null; },
        country: (MW.cfg.countries || []).length === 1 ? MW.cfg.countries[0] : undefined,
        privacyHref: MW.link("legal.html"), privacyLabel: MW.t("legal.privacy"), onRulesChanged: function () { if (ctl) ctl.refresh(); }, onChange: function () { syncSave(); },
        onOpen: function (f) { setTimeout(function () { try { f.scrollIntoView({ behavior: "smooth", block: "start" }); } catch (e) { /* nic */ } }, 60); },          // sticky lista ceny zakryva dolni cast obrazovky: formular nahoru
        linkFor: function (token) { var u = new URL(location.href); u.searchParams.set("ulozena", token); u.hash = ""; return u.toString(); }
      }) : null;
      function syncSave() { wSave.box.hidden = !saveUi || saveUi.el.hidden; }
      if (saveUi) wSave.body.appendChild(saveUi.el);
      wPrice.body.appendChild(msg);
      wPrice.body.appendChild(E("p", { class: "mw-delivery" }, [E("strong", { i18n: "pd.delivery" }), " ", p.delivery]));
      var b2 = b2bNote(); if (b2) wPrice.body.appendChild(b2);

      // stitky (pravidlo z category.html: jen co server dodal) a schema hlavniho profilu
      var chips = grooveBadges(p).concat(p.profil_mm ? [badge("mw-badge-profile", MW.t("badge.profile", { n: p.profil_mm }))] : [], deliveryBadge(p));
      if (chips.length) { chips.forEach(function (c) { wBadges.body.appendChild(c); }); wBadges.body.classList.add("mw-badges"); wBadges.box.hidden = false; }
      var g1 = String(p.groove_family || "").split(",")[0].trim();
      if (p.profil_mm) global.PdcLayout.profileWindow(wProfile, { mm: p.profil_mm, groove: g1, version: TILE_JS.split("?v=")[1], text: function (mm, g) { return MW.t("win.profile_text", { mm: mm, g: g }); } });
      wShip.body.appendChild(E("p", { i18n: "pd.shipping_payment_text" }));
      wDesc.body.appendChild(E("p", { class: "mw-pre", text: p.description }));
      if (p.specs && p.specs.length) wDesc.body.appendChild(E("table", { class: "mw-specs" }, p.specs.map(function (s) { return E("tr", {}, [E("th", { scope: "row", text: s.name }), E("td", { text: s.value })]); })));
      var avail = !!(p.configurator && p.configurator.available);
      if (avail) global.PdcLayout.attachWindow(wAttach, { profile: p.profil_mm ? p.profil_mm + "x" + p.profil_mm : null, lang: MW.cfg && MW.cfg.lang, accent: MW.cfg && MW.cfg.accent, getEnv: function () { return ctl && ctl.envConfig ? ctl.envConfig() : null; }, gate: gate, tileUrl: TILE_JS, cssUrl: V3D_CSS });

      // zhrnuti voleb (4 hlavni radky + tlacitko), skupiny voleb -> okna (idempotentni), otevreni okna pri kliknuti na dil ve 3D: vse z PdcLayout
      var sumHost = L.summaryHost(wSum, { all: function (n) { return MW.t("cart.cfg_all", { n: n }); }, less: MW.t("win.sum_less") });
      var groupHost = L.groupHosts({ map: { g_size: wDim, g_frame: wFrame, g_extras: wExtras, g_cuts: wAdv, g_bearings: wAdv }, adv: wAdv, before: wDesc.box });
      var reveal = L.reveal, DEPENDS = global.PdcLayout.DEPENDS;

      side.appendChild(wPrice.box); side.appendChild(wSave.box); side.appendChild(wBadges.box); side.appendChild(wProfile.box);          // desktop: Ulozit hned pod cenou; mobil: poradi urcuje CSS order (Ulozit 1, sticky lista ceny 2)
      col3.appendChild(wAdv.box); col3.appendChild(wSum.box);
      [wStage.box, side, cfgBar, wDim.box, wFrame.box, wExtras.box, wShip.box, wAttach.box, col3, wDesc.box].forEach(function (n) { grid.appendChild(n); });
      m.appendChild(crumbs([{ href: MW.link("index.html"), text: MW.t("nav.home") }, { href: MW.link("category.html"), text: MW.t("nav.shop") }, { text: p.name }]));
      var titleBox = E("div", { class: "mw-pd-title" }, [E("h1", { text: p.name }), E("p", { class: "mw-muted" }, [MW.t("pd.code") + ": " + p.sku])]);
      m.appendChild(titleBox);
      m.appendChild(grid);
      document.title = p.name + " \u2013 " + MW.t("brand.name");

      var ctl = null, lastPrice = null;
      function showPrice(price) { lastPrice = price; if (!noPrice) priceNet.textContent = price ? MW.money(price.net) : "…"; }
      addBtn.addEventListener("click", function () {
        var pl = ctl && ctl.cartPayload();
        if (!pl || (!noPrice && !lastPrice)) { msg.textContent = MW.t("pd.invalid"); return; }
        var n = Math.max(1, Math.min(99, parseInt(qty.value, 10) || 1)), items = MW.cart.read();
        var withM = mCb.checked && mOpt != null;                                   // montaz je soucasti polozky: stejna konfigurace s montazi a bez ni jsou dva radky
        var same = items.filter(function (i) { return i.configuration && i.configuration.hash === pl.configuration.hash && (i.montaz === true) === withM; })[0];
        if (same) same.qty = Math.min(99, same.qty + n);
        else items.push({ product_id: p.id, name: p.name, sku: p.sku, kod: pl.kod, qty: n, montaz: withM ? true : undefined, configuration: pl.configuration, summary: ctl.summary() });
        MW.cart.write(items);
        msg.textContent = MW.t(inquiry ? "pd.added_inquiry" : "pd.added");
      });
      if (!p.configurator || !p.configurator.available) { addBtn.disabled = true; gate.unlock(); return; }
      var PCm = global.PdConfigurator, hashSel = PCm.unpackSelection ? PCm.unpackSelection(location.hash) : null;         // vyber z prepnuti systemu (#v=...)
      if (hashSel) { try { history.replaceState(null, "", location.pathname + location.search); } catch (e) { /* nic */ } }
      var savedP = ulozenaTok ? global.StulUlozeni.load(ulozenaTok) : Promise.resolve(null), ctlSaved = false;
      return Promise.all([sibP, savedP]).then(function (rs) {
      var lr = rs[0], saved = rs[1];
      var sibs = {};                                                              // card_id -> produkt TOHOTO obchodu: druhy system stolu (prepinac nabidne jen to, co obchod opravdu ma verejne)
      (lr.products || []).forEach(function (x) { var cid = x.configurator && x.configurator.product_id; if (cid && x.id !== p.id) sibs[cid] = x; });
      var mine = Number(p.configurator.product_id || p.id);
      if (saved && Number(saved.product_id) !== mine) {                          // ulozena konfigurace jineho systemu: prejit na jeho produkt v tomto shopu (kdyz ho shop ma)
        var other = sibs[saved.product_id], go = other ? MW.link("product.html", { id: other.id, slug: other.slug }) : null;
        if (go) { location.replace(go + (go.indexOf("?") < 0 ? "?" : "&") + "ulozena=" + ulozenaTok); return new Promise(function () {}); }
        saved = null;
      }
      ctlSaved = !!saved;
      var sysSwitch = { available: function (s) { return Number(s.card_id) === mine || !!sibs[s.card_id]; }, mount: function (box) { titleBox.appendChild(box); },
                        go: function (t, sel) { var x = sibs[t.card_id]; if (x) location.href = MW.link("product.html", { id: x.id, slug: x.slug }) + "#" + PCm.packSelection(sel); } };
      return global.PdConfigurator.init({
        product: { id: p.configurator.product_id || p.id, configurator: p.configurator }, noTurntable: true, initialSelection: saved ? saved.selection : (hashSel || undefined), systemSwitch: sysSwitch, labels: configuratorLabels(), viewerLabels: viewerLabels(), viewerOpts: (global.matchMedia && global.matchMedia("(max-width: 800px)").matches) ? { hudDock: "top" } : {}, lang: MW.cfg.lang, money: MW.money,
        dom: { tabsBefore: null, visual: [], stageHost: media, panelHost: panel, groupHost: groupHost, summaryHost: sumHost, reveal: reveal, dependsOn: DEPENDS },
        page: { setPrice: showPrice, setBuyState: function (ok) { addBtn.disabled = !ok; if (saveUi) { saveUi.update(); syncSave(); } }, toast: function (t) { msg.textContent = t; }, onActivate: function () {}, track: function () {}, onModel: gate.unlock, onResolved: function (r) { mFetch(r); if (saveUi) saveUi.update(); } },
        assets: { cssNow: ["/css/product-configurator.css?v=55f3678f8f"], css: ["/css/v3d.css?v=c76cbe7292"], viewer: "/js/v3d/viewer3d.js?v=e6b94b904a", ovladani: "/js/v3d-ovladani.js?v=1bc0d2b6ba" }, ovladaniTexty: ovladaniTexty()
      }); }).then(function (c) { ctl = c; if (!c) { msg.textContent = MW.t("pd.config_unavailable"); gate.unlock(); } else if (ulozenaTok && saveUi) saveUi.notice(MW.dict["ulozeni.obnovena"] ? MW.t(ctlSaved ? "ulozeni.obnovena" : "ulozeni.nenalezena") : ""); });
    });
  };

  // ------------------------------------------------------------------ kosik a pokladna (checkout_mode "order") / poptavkovy kosik ("inquiry")
  // Ceny, doprava a DPH prichazeji VZDY ze serveru (POST /api/miniweb/quote, v demu je pocita demo-api.js); do kosiku se uklada jen vyber voleb.
  P.cart = function () {
    var m = mainEl(), cfg = MW.cfg, inquiry = MW.mode().checkout === "inquiry", items = MW.cart.read();
    m.appendChild(crumbs([{ href: MW.link("index.html"), text: MW.t("nav.home") }, { text: MW.t(inquiry ? "nav.inquiry" : "nav.cart") }]));
    m.appendChild(E("h1", { i18n: inquiry ? "inq.title" : "cart.title" }));
    var wrap = E("div", { id: "mwCartWrap" }), linesHost = E("div"), totalsHost = E("div"), grid = null; m.appendChild(wrap);
    var country = cfg.countries[0], quote = null, quoteState = "idle", seq = 0;

    function requestQuote() {
      if (inquiry || !items.length) { quote = null; quoteState = "idle"; return; }
      var my = ++seq; quote = null; quoteState = "pending";
      MW.postApi("/api/miniweb/quote", { country: country, delivery_zip: deliveryZip(), vat_id: vatIdValue(), items: items.map(orderItem) }).then(function (q) {
        if (my !== seq) return; quote = q; quoteState = "ok"; draw();
        var cf = document.getElementById("mwCheckout"); if (cf && cf._drawShipping) cf._drawShipping();
      }).catch(function (e) {
        if (my !== seq) return;
        if (e && e.body && e.body.error === "montaz_unavailable" && items.some(function (it) { return it.montaz; })) {      // montaz se medtim prestala nabizet: odebrat z polozek a spocitat znovu
          items.forEach(function (it) { delete it.montaz; }); MW.cart.write(items); requestQuote(); return;
        }
        quoteState = "error"; draw();
      });
    }
    var zipTimer = null;
    function vatIdValue() { var f = document.getElementById("mwCheckout"); var v = f ? (f.querySelector("input[name=vat_id]").value || "").replace(/\s+/g, "") : ""; return v.length >= 8 ? v : undefined; }
    function deliveryZip() {                                                       // PSC dodaci adresy (nebo fakturacni, kdyz je dodaci stejna) - z nej server pocita dopravu
      var f = document.getElementById("mwCheckout"); if (!f) return undefined;
      var same = f.querySelector("input[name=delivery_same]").checked, z = (f.querySelector("input[name=" + (same ? "billing_zip" : "delivery_zip") + "]").value || "").replace(/\s+/g, "");
      return z.length >= 4 ? z : undefined;
    }
    function changed() { MW.cart.write(items); requestQuote(); draw(); }
    function dl(rows) { return E("dl", { class: "mw-sum" }, rows.reduce(function (a, s) { a.push(E("dt", { text: s.label }), E("dd", { text: s.value })); return a; }, [])); }
    function cfgSummary(sm) {                                                      // hlavni rozmery vidno hned, zbytek (vsech ~40 parametru) je sbaleny
      if (sm.length <= 5) return dl(sm);
      return E("div", {}, [dl(sm.slice(0, 4)), E("details", { class: "mw-cfg-all" }, [E("summary", { text: MW.t("cart.cfg_all", { n: sm.length }) }), dl(sm.slice(4))])]);
    }
    function row(a, b) { return E("div", { class: "mw-row" }, [E("span", { text: a }), E("span", { text: b })]); }
    function money(n) { return n == null ? "…" : MW.money(n); }

    function totalsBox() {
      if (inquiry) return E("section", { class: "mw-totals" }, [E("h2", { i18n: "inq.title" }), E("p", { class: "mw-muted", i18n: "inq.note" })]);
      var sel = E("select", { id: "mwCountry", "aria-label": MW.t("co.country") }, cfg.countries.map(function (c) { return E("option", { value: c, text: MW.t("country." + c) }); }));
      sel.value = country;
      sel.addEventListener("change", function () { country = sel.value; var cf = document.getElementById("mwCheckout"); if (cf && cf._syncVat) cf._syncVat(); requestQuote(); draw(); });
      var kids = [E("h2", { i18n: "cart.summary" })];
      if (cfg.countries.length > 1) kids.push(E("label", { class: "mw-field" }, [E("span", { class: "mw-label", i18n: "co.country" }), sel]));
      if (quote) {
        kids.push(E("div", { class: "mw-row mw-row-total" }, [E("span", { i18n: "cart.subtotal" }), E("strong", { text: money(quote.total_goods != null ? quote.total_goods : quote.subtotal) })]));
        if (quote.subtotal_montaz > 0) {                                           // montaz je samostatny radek; "Spolu" = zbozi + montaz (bez DPH)
          kids.push(E("div", { class: "mw-row" }, [E("span", { text: MW.t("pdc.montazLabel") + " (" + MW.t("price.excl_vat") + ")" }), E("strong", { text: money(quote.subtotal_montaz) })]));
          kids.push(E("div", { class: "mw-row mw-row-total" }, [E("span", { text: MW.t("cart.total") + " (" + MW.t("price.excl_vat") + ")" }), E("strong", { text: money(quote.subtotal) })]));
        }
        kids.push(E("p", { class: "mw-fine", i18n: "co.ship_note" }));
        if (quote.vat && quote.vat.note) kids.push(E("p", { class: "mw-fine", text: quote.vat.note }));
        (quote.notes || []).forEach(function (n) { var k = "quote.note." + n; if (MW.dict && Object.prototype.hasOwnProperty.call(MW.dict, k)) kids.push(E("p", { class: "mw-fine", text: MW.t(k) })); });   // kody ze serveru -> text; bez textu se nezobrazi
      } else kids.push(E("p", { class: "mw-muted", role: "status", i18n: quoteState === "error" ? "cart.quote_error" : "cart.quote_pending" }));
      return E("section", { class: "mw-totals", "aria-live": "polite" }, kids);
    }
    function draw() {
      linesHost.textContent = ""; totalsHost.textContent = "";
      if (!items.length) {
        wrap.textContent = ""; grid = null;
        wrap.appendChild(E("p", { class: "mw-muted", i18n: inquiry ? "inq.empty" : "cart.empty" })); wrap.appendChild(E("a", { class: "mw-btn", href: MW.link("category.html"), i18n: "cart.continue" })); return;
      }
      var list = E("div", { class: "mw-lines" }, items.map(function (it, idx) {
        var q = E("input", { type: "number", min: "1", max: "99", value: String(it.qty), "aria-label": MW.t("pd.qty") });
        q.addEventListener("change", function () { it.qty = Math.max(1, Math.min(99, parseInt(q.value, 10) || 1)); changed(); });
        var rm = E("button", { type: "button", class: "mw-link", i18n: "cart.remove" });
        rm.addEventListener("click", function () { items.splice(idx, 1); changed(); });
        var ql = quote && quote.lines && quote.lines[idx];
        var right = [E("label", { class: "mw-qty" }, [E("span", { class: "mw-label", i18n: "pd.qty" }), q])];
        if (!inquiry) right.push(E("p", {}, [E("strong", { text: money(ql ? ql.net_total : null) }), E("small", { text: " " + MW.t("price.excl_vat") })]));
        if (!inquiry && ql && ql.montaz_total_eur) right.push(E("p", { class: "mw-fine" }, [MW.t("pdc.montazLabel") + ": +" + money(ql.montaz_total_eur) + " ", E("small", { text: MW.t("price.excl_vat") })]));
        right.push(rm);
        var mLine = null;                                                          // volba montaze u radku (jen kdyz server montaz umi = klic montaz_option_eur v odpovedi) + doprovodny text smontovano / demontovano
        if (!inquiry && ql && Object.prototype.hasOwnProperty.call(ql, "montaz_option_eur")) {
          var kids = [];
          if (ql.montaz_option_eur != null) {
            var cb = E("input", { type: "checkbox", checked: it.montaz === true });
            cb.addEventListener("change", function () { if (cb.checked) it.montaz = true; else delete it.montaz; changed(); });
            kids.push(E("label", { class: "mw-opt" }, [cb, E("span", { class: "mw-montaz-t", text: MW.t("pdc.montazLabel") }), E("span", { class: "mw-montaz-amt", text: "+" + money(ql.montaz_option_eur) + " " + MW.t("price.excl_vat") })]));
          }
          kids.push(E("p", { class: "mw-montaz-state", text: MW.t(it.montaz === true && ql.montaz_zvolena ? "pdc.montazOn" : "pdc.montazOff") }));
          mLine = E("div", { class: "mw-montaz mw-line-montaz" }, kids);
        }
        return E("article", { class: "mw-line" }, [
          E("div", {}, [E("h3", { text: it.name }), E("p", { class: "mw-muted", text: MW.t("pd.code") + ": " + it.sku + (it.kod ? " · " + MW.t("pdc.code") + ": " + it.kod : "") }),
                        cfgSummary(it.summary || []), mLine]),
          E("div", { class: "mw-line-r" }, right)
        ]);
      }));
      linesHost.appendChild(list); totalsHost.appendChild(totalsBox());
      if (!grid) { wrap.textContent = ""; grid = E("div", { class: "mw-cart-grid" }, [E("div", {}, [linesHost, inquiry ? inquiryForm() : checkoutForm()]), totalsHost]); wrap.appendChild(grid); }
    }
    function field(key, type, attrs) {
      var a = attrs || {};
      return E("label", { class: "mw-field" }, [E("span", { class: "mw-label", i18n: a.label || ("co." + key) }), E("input", Object.assign({ type: type || "text", name: key, required: a.required === false ? null : true, autocomplete: a.ac || null }, a.extra || {}))]);
    }
    function formValues(f) { var o = {}; Array.prototype.forEach.call(f.querySelectorAll("input[name],textarea[name],select[name]"), function (i) { if (i.type === "checkbox") o[i.name] = i.checked; else if (i.type !== "radio" || i.checked) o[i.name] = i.value.trim(); }); return o; }
    function missing(f) { return Array.prototype.filter.call(f.querySelectorAll("input[required],textarea[required]"), function (i) { return i.type === "checkbox" ? !i.checked : !i.value.trim(); }); }
    function say(id, key, vars) { document.getElementById(id).textContent = MW.t(key, vars); }

    function checkoutForm() {
      var shipHost = E("fieldset", { class: "mw-pay" }, [E("legend", { class: "mw-label", i18n: "co.shipping" })]);
      function drawShipping() {                                                          // moznosti dopravy dodava server (quote.shipping_options); net null = "po dohode"
        while (shipHost.childNodes.length > 1) shipHost.removeChild(shipHost.lastChild);
        var opts = (quote && quote.shipping_options) || [];
        opts.forEach(function (o, i) {
          shipHost.appendChild(E("label", { class: "mw-opt" }, [E("input", { type: "radio", name: "shipping", value: o.id, checked: i === 0 }), E("span", { text: o.label + (o.net != null ? " (" + money(o.net) + ")" : "") })]));
        });
      }
      var f = E("form", { class: "mw-form", id: "mwCheckout", novalidate: true }, [
        E("h2", { i18n: "co.title" }),
        field("company", "text", { ac: "organization", label: "inq.company" }), field("company_id", "text", { label: "inq.company_id" }), field("vat_id", "text", { required: false, label: "inq.vat_id" }),
        field("name", "text", { ac: "name" }), field("email", "email", { ac: "email" }), field("phone", "tel", { ac: "tel" }),
        E("h3", { i18n: "co.billing_title" }),
        field("billing_street", "text", { ac: "street-address", label: "co.street" }), field("billing_city", "text", { ac: "address-level2", label: "co.city" }), field("billing_zip", "text", { ac: "postal-code", label: "co.zip" }),
        E("label", { class: "mw-opt mw-field" }, [E("input", { type: "checkbox", name: "delivery_same", checked: true }), E("span", { i18n: "co.delivery_same" })]),
        E("div", { class: "mw-delivery-box", hidden: true }, [E("h3", { i18n: "co.delivery_title" }),
          field("delivery_street", "text", { required: false, label: "co.street" }), field("delivery_city", "text", { required: false, label: "co.city" }), field("delivery_zip", "text", { required: false, label: "co.zip" })]),
        shipHost,
        E("label", { class: "mw-field" }, [E("span", { class: "mw-label", i18n: "inq.message" }), E("textarea", { name: "note", rows: "3" })]),
        E("fieldset", { class: "mw-pay" }, [E("legend", { class: "mw-label", i18n: "co.payment" }), E("label", { class: "mw-opt" }, [E("input", { type: "radio", name: "pay", value: "transfer", checked: true }), E("span", { i18n: "co.pay_transfer" })]),
                                            E("p", { class: "mw-fine", i18n: "co.pay_transfer_note" })]),
        E("label", { class: "mw-opt mw-field" }, [E("input", { type: "checkbox", name: "b2b_confirm", required: true }), E("span", { i18n: "co.b2b_confirm" })]),
        E("label", { class: "mw-opt mw-field" }, [E("input", { type: "checkbox", name: "consent", required: true }), E("span", { i18n: "co.consent" })]),
        controllerNote(), honeypot(), E("button", { type: "submit", class: "mw-btn", i18n: "co.place" }), E("p", { class: "mw-msg", id: "mwCoMsg", role: "status", "aria-live": "polite" })
      ]);
      f._drawShipping = drawShipping; drawShipping();
      var dBox = f.querySelector(".mw-delivery-box"), dSame = f.querySelector("input[name=delivery_same]");
      function syncDelivery() { dBox.hidden = dSame.checked; ["delivery_street", "delivery_city", "delivery_zip"].forEach(function (n) { f.querySelector("input[name=" + n + "]").required = !dSame.checked; }); clearTimeout(zipTimer); zipTimer = setTimeout(function () { requestQuote(); }, 300); }
      dSame.addEventListener("change", syncDelivery);
      ["billing_zip", "delivery_zip", "vat_id"].forEach(function (n) { f.querySelector("input[name=" + n + "]").addEventListener("input", function () { clearTimeout(zipTimer); zipTimer = setTimeout(function () { requestQuote(); }, 500); }); });
      var vatIn = f.querySelector("input[name=vat_id]");
      function syncVat() { vatIn.required = false; }                       // DIC / IC DPH je nepovinne (server: bez nej se uctuje DPH; s platnym 0 %)
      f._syncVat = syncVat; syncVat();
      var MISSING_KEY = { company: "err.company_required", company_id: "err.company_id_required", b2b_confirm: "err.co_b2b_confirm_required", consent: "err.consent_required" };
      f.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var bad = missing(f);
        if (bad.length) { say("mwCoMsg", MISSING_KEY[bad[0].name] || "co.fill_required"); bad[0].focus(); return; }
        if (demoOn()) { say("mwCoMsg", "co.demo_done"); return; }                        // v demu se nic neodesila
        if (!quote) { say("mwCoMsg", quoteState === "error" ? "cart.quote_error" : "cart.quote_pending"); return; }
        var v = formValues(f); v.country = country; v.payment = "transfer"; v.items = items.map(orderItem);
        v.billing = { street: v.billing_street, city: v.billing_city, zip: v.billing_zip };
        v.delivery = v.delivery_same ? { same: true } : { same: false, street: v.delivery_street, city: v.delivery_city, zip: v.delivery_zip };
        ["billing_street", "billing_city", "billing_zip", "delivery_same", "delivery_street", "delivery_city", "delivery_zip"].forEach(function (k) { delete v[k]; });
        v.shipping = (f.querySelector("input[name=shipping]:checked") || {}).value || "quote";
        v.expected_total_net = quote.subtotal;                                              // ochrana proti zmene ceny mezi kosikem a odeslanim (od montaze vcetne ni; stary server: subtotal = zbozi)
        delete v.pay;
        MW.postApi("/api/miniweb/orders", v).then(function (r) {
          if (r && r.preview) { say("mwCoMsg", "co.preview_done"); return; }                    // koncept shopu: server objednavku jen zvaliduje a neulozi - kosik zustava
          items = []; MW.cart.write(items); wrap.textContent = ""; grid = null;
          wrap.appendChild(E("p", { class: "mw-msg", role: "status", text: MW.t("co.sent", { ref: r.reference || "" }) }));
        }).catch(function (e) { if (e && e.body && (e.body.error === "rules_changed" || e.body.error === "price_changed")) requestQuote(); say("mwCoMsg", errKey(e, "co.error")); });
      });
      return f;
    }
    function inquiryForm() {
      var sel = E("select", { name: "country", "aria-label": MW.t("co.country") }, cfg.countries.map(function (c) { return E("option", { value: c, text: MW.t("country." + c) }); }));
      var f = E("form", { class: "mw-form", id: "mwInquiry", novalidate: true }, [
        E("h2", { i18n: "inq.send" }),
        b2bNote(),
        field("name", "text", { ac: "name" }), field("email", "email", { ac: "email" }), field("phone", "tel", { ac: "tel", required: false }),
        field("company", "text", { ac: "organization", label: "inq.company" }), field("company_id", "text", { label: "inq.company_id" }), field("vat_id", "text", { required: false, label: "inq.vat_id" }),
        E("label", { class: "mw-field" }, [E("span", { class: "mw-label", i18n: "co.country" }), sel]),
        E("label", { class: "mw-field" }, [E("span", { class: "mw-label", i18n: "inq.message" }), E("textarea", { name: "message", rows: "3" })]),
        E("label", { class: "mw-opt mw-field" }, [E("input", { type: "checkbox", name: "b2b_confirm", required: true }), E("span", { i18n: "inq.b2b_confirm" })]),
        E("label", { class: "mw-opt mw-field" }, [E("input", { type: "checkbox", name: "consent", required: true }), E("span", { i18n: "inq.consent" })]),
        controllerNote(), honeypot(), E("button", { type: "submit", class: "mw-btn", i18n: "inq.send" }), E("p", { class: "mw-msg", id: "mwInqMsg", role: "status", "aria-live": "polite" })
      ]);
      var vatIn = f.querySelector("input[name=vat_id]");
      function syncVat() { vatIn.required = false; vatIn.setAttribute("aria-required", "false"); }   // DIC / IC DPH je nepovinne (pravidlo mini-shopu, server ho nevyzaduje)
      sel.addEventListener("change", syncVat); syncVat();
      var MISSING_KEY = { company: "err.company_required", company_id: "err.company_id_required", b2b_confirm: "err.b2b_confirm_required", consent: "err.consent_required" };
      f.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var bad = missing(f);
        if (bad.length) { say("mwInqMsg", MISSING_KEY[bad[0].name] || "co.fill_required"); bad[0].focus(); return; }
        if (demoOn()) { say("mwInqMsg", "inq.demo_done"); return; }
        var v = formValues(f); v.items = items.map(itemPayload);
        postInquiry(v).then(function (r) {
          if (r && r.preview) { say("mwInqMsg", "inq.preview_done"); return; }              // koncept shopu: server poptavku jen zvaliduje a neulozi
          items = []; MW.cart.write(items); wrap.textContent = ""; grid = null;
          wrap.appendChild(E("p", { class: "mw-msg", role: "status", i18n: "inq.sent" }));
        }).catch(function (e) { say("mwInqMsg", errKey(e, "inq.error")); });
      });
      return f;
    }
    requestQuote(); draw();
    document.title = MW.t(inquiry ? "inq.title" : "cart.title") + " – " + MW.t("brand.name");
    return Promise.resolve();
  };

  // ------------------------------------------------------------------ kontakt a pravni
  P.contact = function () {
    var m = mainEl(), c = MW.cfg.contact || {};
    m.appendChild(crumbs([{ href: MW.link("index.html"), text: MW.t("nav.home") }, { text: MW.t("nav.contact") }]));
    m.appendChild(E("h1", { i18n: "contact.title" }));
    m.appendChild(E("p", { class: "mw-lead", i18n: "contact.lead" }));
    var rows = [];                                           // e-mail se na webu nezobrazuje (jen formular); telefon/hodiny jen kdyz jsou zname, jinak nic ("Doplnime" na verejne strance nechceme)
    if (c.phone) rows.push(E("dt", { i18n: "contact.phone" }), E("dd", { text: c.phone }));
    if (c.hours) rows.push(E("dt", { i18n: "contact.hours" }), E("dd", { text: c.hours }));
    if (rows.length) m.appendChild(E("dl", { class: "mw-sum" }, rows));
    var sellerBox = E("dl", { class: "mw-sum mw-seller", hidden: true }); m.appendChild(sellerBox);
    api("/api/miniweb/legal").then(function (d) {                        // kontaktni udaje spolecnosti z jedineho zdroje na serveru (jmeno, adresa, ICO, DIC); e-mail se nezobrazuje
      var s = d && d.seller; if (!s || !s.name) return;
      var k = [[MW.t("legal.seller"), s.name], ["", s.address], [MW.t("legal.company_id"), s.id || s.company_id], [MW.t("legal.vat_id"), s.vat_id]].filter(function (x) { return x[1]; });
      k.forEach(function (x) { sellerBox.appendChild(E("dt", { text: x[0] })); sellerBox.appendChild(E("dd", { text: x[1] })); });
      sellerBox.hidden = !k.length;
    }).catch(function () { /* bez udaju se blok neukaze */ });
    var f = E("form", { class: "mw-form", novalidate: true }, [
      E("label", { class: "mw-field" }, [E("span", { class: "mw-label", i18n: "co.name" }), E("input", { type: "text", name: "name", required: true })]),
      E("label", { class: "mw-field" }, [E("span", { class: "mw-label", i18n: "co.email" }), E("input", { type: "email", name: "email", required: true })]),
      E("label", { class: "mw-field" }, [E("span", { class: "mw-label", i18n: "inq.company" }), E("input", { type: "text", name: "company", required: true, autocomplete: "organization" })]),      // jen firmam (Robert): firma a ICO i u kontaktu
      E("label", { class: "mw-field" }, [E("span", { class: "mw-label", i18n: "inq.company_id" }), E("input", { type: "text", name: "company_id", required: true })]),
      (MW.cfg.countries && MW.cfg.countries.length > 1 ? E("label", { class: "mw-field" }, [E("span", { class: "mw-label", i18n: "co.country" }), E("select", { name: "country" }, MW.cfg.countries.map(function (c) { return E("option", { value: c, text: MW.t("country." + c) }); }))]) : null),   // vice zemi dodani: server vyzaduje zemi
      E("label", { class: "mw-field" }, [E("span", { class: "mw-label", i18n: "contact.message" }), E("textarea", { name: "message", rows: "4", required: true })]),
      E("label", { class: "mw-opt mw-field" }, [E("input", { type: "checkbox", name: "b2b_confirm", required: true }), E("span", { i18n: "inq.b2b_confirm" })]),
      E("label", { class: "mw-opt mw-field" }, [E("input", { type: "checkbox", name: "consent", required: true }), E("span", { i18n: "inq.consent" })]),
      b2bNote(), controllerNote(), honeypot(), E("button", { type: "submit", class: "mw-btn", i18n: "contact.send" }), E("p", { class: "mw-msg", id: "mwContactMsg", role: "status", "aria-live": "polite" })]);
    f.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var msg = document.getElementById("mwContactMsg");
      var bad = Array.prototype.filter.call(f.querySelectorAll("input[required],textarea[required]"), function (i) { return i.type === "checkbox" ? !i.checked : !i.value.trim(); });
      var MK = { company: "err.company_required", company_id: "err.company_id_required", b2b_confirm: "err.b2b_confirm_required", consent: "err.consent_required" };
      if (bad.length) { msg.textContent = MW.t(MK[bad[0].name] || "co.fill_required"); bad[0].focus(); return; }
      if (demoOn()) { msg.textContent = MW.t("contact.demo"); return; }
      var v = {}; Array.prototype.forEach.call(f.querySelectorAll("input[name],textarea[name],select[name]"), function (i) { v[i.name] = i.type === "checkbox" ? i.checked : i.value.trim(); });
      postInquiry(v).then(function (r) { msg.textContent = MW.t(r && r.preview ? "inq.preview_done" : "contact.sent"); if (!(r && r.preview)) f.reset(); }).catch(function (e) { msg.textContent = MW.t(errKey(e, "contact.error")); });
    });
    m.appendChild(f);
    document.title = MW.t("contact.title") + " – " + MW.t("brand.name");
    return Promise.resolve();
  };
  P.legal = function () {
    var m = mainEl();
    m.appendChild(crumbs([{ href: MW.link("index.html"), text: MW.t("nav.home") }, { text: MW.t("nav.legal") }]));
    m.appendChild(E("h1", { i18n: "legal.title" }));
    // jen zakonne dokumenty, ktere vraci server (/api/miniweb/legal: documents [{kind, title, body}]; schvaluje je Robert); zadne zastupne sekce ani vraceni zbozi
    return api("/api/miniweb/legal").catch(function () { return { seller: null, documents: [] }; }).then(function (d) {
      var s = d && d.seller, docs = (d && Array.isArray(d.documents)) ? d.documents : [];
      if (s) m.appendChild(E("section", { class: "mw-section" }, [E("h2", { i18n: "legal.seller" }), E("p", { text: [s.name, s.address, (s.id || s.company_id) ? MW.t("legal.company_id") + ": " + (s.id || s.company_id) : "", s.vat_id ? MW.t("legal.vat_id") + ": " + s.vat_id : ""].filter(Boolean).join(", ") })]));
      docs.forEach(function (doc) {
        if (!doc || !doc.body) return;
        var title = doc.title || (Object.prototype.hasOwnProperty.call(MW.dict, "legal." + doc.kind) ? MW.t("legal." + doc.kind) : "");
        m.appendChild(E("section", { class: "mw-section" }, [title ? E("h2", { text: title }) : null, E("p", { class: "mw-pre", text: doc.body })]));
      });
      document.title = MW.t("legal.title") + " – " + MW.t("brand.name");
    });
  };
})(window);
