/* Mini-shop - spolecne jadro (bot16, 2026-10-02; zadani Robert pres bot3: prvni anglicky mini-shop na stoly, bez znacky, vse pres preklady).
 *
 * Zadne texty tu nejsou napevno: vse jde z i18n/<jazyk>.json pres MW.t(klic). Jazyk, mena, format cisel, DPH a zeme jsou v config.json
 * (pozdeji z tabulky storefrontu podle hosta - stranky se kvuli tomu nemeni). Nahled je jen pro staff (brana pres /api/auth/me), stranky
 * jsou noindex. Soubor je schvalne BEZ jmena znacky (TEXT_FILTR pravidlo 5, QA static_page_brand_leak); pravni udaje prodejce prijdou
 * ze serveru, ne ze statickeho souboru.
 *
 * Vyber obchodu/jazyka na IP/spolecne domene: ?shop=<kod>&lang=<kod>&demo=1 (drzi se v sessionStorage a pridava do odkazu, MW.link);
 * na vlastni domene pozdeji urci vse host a parametry odpadnou.
 */
(function (global) {
  "use strict";

  var MW = global.MW = {};
  try { document.documentElement.setAttribute("data-theme", localStorage.getItem("shopTheme") === "light" ? "light" : "dark"); } catch (e) { document.documentElement.setAttribute("data-theme", "dark"); }   // motiv jako hlavni web (vychozi tmavy)
  var STAFF_ROLES = ["admin", "manager", "skladnik", "ucetni", "monter", "sklad"];
  var KEEP = ["shop", "lang", "demo", "drafts"];

  // ------------------------------------------------------------------ parametry (drzi se mezi strankami)
  var q = new URLSearchParams(location.search);
  MW.params = {};
  KEEP.forEach(function (k) {
    var v = q.get(k);
    try { if (v !== null) sessionStorage.setItem("mw_" + k, v); else v = sessionStorage.getItem("mw_" + k); } catch (e) { /* bez ulozeni */ }
    if (v !== null && v !== undefined) MW.params[k] = v;
  });
  // Hezke adresy (/produkt/<slug>, /kategoria/<slug>, /kontakt ...): zapina je jen server (api/miniweb_seo.py vlozi window.MW_BOOT.pretty + cesty podle jazyka);
  // bez nej (staticky shell, ukazkovy nahled) zustavaji adresy /miniweb/<stranka>.html?...
  var BOOT = window.MW_BOOT || null;
  MW.link = function (page, extra) {
    var p = new URLSearchParams(), e = {}, path = null;
    KEEP.forEach(function (k) { if (MW.params[k] !== undefined) p.set(k, MW.params[k]); });
    if (extra) for (var k in extra) if (extra[k] != null) e[k] = extra[k];
    if (BOOT && BOOT.pretty && BOOT.paths) {
      var B = BOOT.paths;
      if (page === "index.html") path = "/";
      else if (page === "category.html") { path = e.cat ? B.category + e.cat : B.shop; delete e.cat; }
      else if (page === "product.html" && e.slug) { path = B.product + e.slug; delete e.id; }
      else if (page === "contact.html") path = B.contact;
      else if (page === "legal.html") path = B.legal;
      else if (page === "cart.html") path = B.cart;
    }
    delete e.slug;
    for (var q2 in e) p.set(q2, e[q2]);
    var s = p.toString();
    return (path || "/miniweb/" + page) + (s ? "?" + s : "");
  };

  // ------------------------------------------------------------------ pomocne
  MW.el = function (tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (!Object.prototype.hasOwnProperty.call(attrs, k) || attrs[k] == null || attrs[k] === false) continue;
      if (k === "text") n.textContent = attrs[k];
      else if (k === "class") n.className = attrs[k];
      else if (k === "i18n") { n.setAttribute("data-i18n", attrs[k]); n.textContent = MW.t(attrs[k]); }
      else n.setAttribute(k, attrs[k] === true ? "" : String(attrs[k]));
    }
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  };
  // Nazev zeme bez prekladoveho klice (country.<ISO>): z prohlizece v jazyce shopu (Intl.DisplayNames), takze dalsi shop (napr. HU) nepotrebuje preklad kazde zeme (bot16, 2026-10-07)
  function countryName(code) {
    try { return new Intl.DisplayNames([(MW.cfg && MW.cfg.lang) || "en"], { type: "region", fallback: "none" }).of(code) || ""; } catch (e) { return ""; }
  }
  MW.t = function (key, vars) {
    var s = MW.dict && Object.prototype.hasOwnProperty.call(MW.dict, key) ? MW.dict[key] : (/^country\.[A-Z]{2}$/.test(key) ? countryName(key.slice(8)) || key : key);   // chybejici klic je videt jako klic
    if (vars) s = s.replace(/\{(\w+)\}/g, function (_, k) { return vars[k] != null ? vars[k] : "{" + k + "}"; });
    return s;
  };
  MW.money = function (n) {
    var c = MW.cfg || {};
    var o = { style: "currency", currency: c.currency || "EUR" };
    if (typeof c.fraction_digits === "number") { o.minimumFractionDigits = c.fraction_digits; o.maximumFractionDigits = c.fraction_digits; }     // cs: cele koruny
    try { return new Intl.NumberFormat(c.locale || "en", o).format(Number(n)); }
    catch (e) { return String(n); }
  };
  MW.num = function (n, digits) {
    var c = MW.cfg || {};
    return new Intl.NumberFormat(c.locale || "en", { maximumFractionDigits: digits == null ? 2 : digits }).format(Number(n));
  };
  function getJSON(url) {
    return fetch(url, { credentials: "same-origin", headers: { "Accept": "application/json" } }).then(function (r) {
      if (!r.ok) { var e = new Error("HTTP " + r.status); e.status = r.status; throw e; }
      return r.json();
    });
  }
  MW.getJSON = getJSON;
  // dotaz na /api/miniweb/*: na spolecne (IP) domene staff vybira shop/jazyk parametry, na domene shopu je shop dany hostem
  MW.api = function (path, extra) {
    var p = new URLSearchParams();
    ["shop", "lang", "drafts"].forEach(function (k) { if (MW.params[k] !== undefined) p.set(k, MW.params[k]); });
    if (extra) for (var k in extra) if (extra[k] != null) p.set(k, extra[k]);
    var q = p.toString();
    return getJSON(path + (q ? (path.indexOf("?") < 0 ? "?" : "&") + q : ""));
  };
  // POST na /api/miniweb/* s parametry shop/lang/drafts (na spolecne domene staff vybira shop; na domene shopu je dany hostem) - stejne jako MW.api pro GET
  MW.postApi = function (path, body) {
    var q = new URLSearchParams();
    ["shop", "lang", "drafts"].forEach(function (k) { if (MW.params[k] !== undefined) q.set(k, MW.params[k]); });
    var t = q.toString();
    return MW.postJSON(path + (t ? (path.indexOf("?") < 0 ? "?" : "&") + t : ""), body);
  };
  // JSON POST s cookie prihlaseneho; chyba nese .status a .body (server vraci {error, ...})
  MW.postJSON = function (url, body) {
    return fetch(url, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "Accept": "application/json" }, body: JSON.stringify(body) }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) { var e = new Error("HTTP " + r.status); e.status = r.status; e.body = j; throw e; }
        return j;
      });
    });
  };
  // rezimy shopu urcuje server (config): price_mode "shown"|"hidden" (karta ukaze "Price on request"), checkout_mode "order"|"inquiry" (kosik je objednavka nebo poptavka)
  MW.mode = function () {
    var c = MW.cfg || {};
    return { price: c.price_mode === "hidden" ? "hidden" : "shown", checkout: (c.checkout_mode ? c.checkout_mode === "inquiry" : c.inquiry_only === true) ? "inquiry" : "order" };   // checkout_mode (je-li) rozhoduje sam; inquiry_only jen jako zaloha pro stary config
  };

  // ------------------------------------------------------------------ prelozit prvky s data-i18n / data-i18n-attr
  MW.translateDom = function (root) {
    (root || document).querySelectorAll("[data-i18n]").forEach(function (n) { n.textContent = MW.t(n.getAttribute("data-i18n")); });
    (root || document).querySelectorAll("[data-i18n-attr]").forEach(function (n) {
      n.getAttribute("data-i18n-attr").split(";").forEach(function (pair) {
        var kv = pair.split(":"); if (kv.length === 2) n.setAttribute(kv[0].trim(), MW.t(kv[1].trim()));
      });
    });
  };

  // ------------------------------------------------------------------ kosik (mistni ulozeni; skutecne API doplni bot5, kontrakt viz the mini-shop data contract)
  MW.cart = {
    key: function () { return "mw_cart_" + (MW.params.shop || "default"); },
    // poskozena nebo cizi hodnota v sessionStorage (null, objekt, seznam s null...) nesmi shodit start stranky: neplatne polozky se vyradi, mnozstvi se omezi na 1-99
    read: function () {
      var a;
      try { a = JSON.parse(sessionStorage.getItem(MW.cart.key()) || "[]"); } catch (e) { return []; }
      if (!Array.isArray(a)) return [];
      return a.filter(function (i) { return i && typeof i === "object" && !Array.isArray(i); }).map(function (i) {
        var q = Math.floor(Number(i.qty));
        return { product_id: i.product_id, name: typeof i.name === "string" ? i.name : "", sku: typeof i.sku === "string" ? i.sku : "", kod: typeof i.kod === "string" ? i.kod : undefined,
                 qty: isFinite(q) ? Math.max(1, Math.min(99, q)) : 1, montaz: i.montaz === true ? true : undefined, configuration: i.configuration && typeof i.configuration === "object" ? i.configuration : undefined, summary: Array.isArray(i.summary) ? i.summary : [] };
      });
    },
    write: function (items) { try { sessionStorage.setItem(MW.cart.key(), JSON.stringify(items)); } catch (e) { /* ticho */ } MW.updateCartBadge(); },
    count: function () { return MW.cart.read().reduce(function (s, i) { return s + (i.qty || 0); }, 0); }
  };
  // Konfigurace v kosiku se po zavreni prohlizece NEUCHOVAVA (Robert 2026-10-05): kosik drzi jen relace (sessionStorage); drivejsi kosiky v localStorage se smazou
  try { for (var li = localStorage.length - 1; li >= 0; li--) { var lk = localStorage.key(li); if (lk && lk.indexOf("mw_cart_") === 0) localStorage.removeItem(lk); } } catch (e) { /* nic */ }
  MW.updateCartBadge = function () {
    var b = document.getElementById("mwCartCount"); if (!b) return;
    var n = MW.cart.count(); b.textContent = String(n); b.hidden = n === 0;
  };

  // ------------------------------------------------------------------ hlavicka a patka
  function renderChrome(active) {
    var head = document.getElementById("mwHeader"), foot = document.getElementById("mwFooter");
    if (head) {
      head.textContent = "";
      var nav = MW.el("nav", { class: "mw-nav", "aria-label": MW.t("nav.main") }, [
        MW.el("a", { class: "mw-brand", href: MW.link("index.html") }, [MW.el("span", { class: "mw-mark", "aria-hidden": "true" }), MW.el("span", { text: MW.t("brand.name") })]),
        MW.el("div", { class: "mw-links" }, [
          MW.el("a", { href: MW.link("category.html"), "aria-current": active === "shop" ? "page" : null, text: MW.t("nav.shop") }),
          MW.el("a", { href: MW.link("contact.html"), "aria-current": active === "contact" ? "page" : null, text: MW.t("nav.contact") })
        ]),
        MW.el("a", { class: "mw-cart", href: MW.link("cart.html"), "aria-label": MW.t(MW.mode().checkout === "inquiry" ? "nav.inquiry" : "nav.cart") }, [
          MW.el("span", { text: MW.t(MW.mode().checkout === "inquiry" ? "nav.inquiry" : "nav.cart") }), MW.el("span", { class: "mw-count", id: "mwCartCount", hidden: true, text: "0" })
        ])
      ]);
      if (MW.cfg && MW.cfg.preview) head.appendChild(MW.el("div", { class: "mw-staffbar", role: "note", text: MW.t("staff.banner") }));
      head.appendChild(nav);
    }
    if (foot) {
      foot.textContent = "";
      foot.appendChild(MW.el("div", { class: "mw-foot" }, [
        MW.el("div", {}, [MW.el("strong", { text: MW.t("brand.name") }), MW.el("p", { text: MW.t("footer.tagline") })]),
        MW.el("div", {}, [
          MW.el("a", { href: MW.link("category.html"), text: MW.t("nav.shop") }),
          MW.el("a", { href: MW.link("contact.html"), text: MW.t("nav.contact") }),
          MW.el("a", { href: MW.link("legal.html"), text: MW.t("nav.legal") })
        ]),
        MW.el("div", {}, [MW.el("p", { class: "mw-fine", text: MW.params.demo === "1" ? MW.t("footer.demo") : "" })])
      ]));
    }
    MW.updateCartBadge();
  }

  function gate(msgKey, withLogin) {
    document.body.classList.add("mw-gated");
    var main = document.getElementById("mwMain") || document.body;
    main.textContent = "";
    var box = MW.el("section", { class: "mw-gate", role: "alert" }, [MW.el("h1", { text: MW.t("gate.title") }), MW.el("p", { text: MW.t(msgKey) })]);
    if (withLogin) box.appendChild(MW.el("a", { class: "mw-btn", href: "/login.html?next=" + encodeURIComponent(location.pathname + location.search), text: MW.t("gate.signin") }));
    main.appendChild(box);
  }

  // ------------------------------------------------------------------ start: konfigurace ze serveru, preklad, brana
  // Skutecny shop (GET /api/miniweb/config): host urcuje shop a jazyk, brana (koncept = jen staff) je NA SERVERU; zivy shop je verejny a JS nic nebrani.
  // Kdyz server shop nevydal (koncept pro nepovolaneho = 404), nebo je zapnute demo (?demo=1, vymyslena data), pustime dal jen prihlaseneho staffa.
  // MW.start(page) -> Promise<{cfg, user}> (nesplni se, kdyz stranku nema videt: zustane jen hlaska)
  MW.start = function (page) {
    // meta robots resi shell (noindex) a server (api/miniweb_seo.py: index jen u live shopu) - JS uz noindex nepridava (prebil by index z serveru)
    var base = "/miniweb/", demo = MW.params.demo === "1";
    // demo-api.js (vymyslene odpovedi) se nacita JEN s ?demo=1 - verejne stranky ho vubec neobsahuji
    var demoP = !demo ? Promise.resolve() : (typeof MW.demoInstall === "function" ? Promise.resolve() : new Promise(function (ok) {
      var sc = document.createElement("script"); sc.src = base + "demo-api.js"; sc.onload = ok; sc.onerror = ok; document.head.appendChild(sc);
    })).then(function () { if (typeof MW.demoInstall === "function") MW.demoInstall(); });
    var meP = null, cfgFail = null;
    function loadMe() { return meP || (meP = getJSON("/api/auth/me").catch(function () { return { user: null }; })); }
    return demoP.then(function () { return MW.api("/api/miniweb/config"); }).catch(function (e) { cfgFail = e || {}; return null; }).then(function (cfg) {
      MW.cfg = cfg || { lang: MW.params.lang || "en", countries: [] };
      var lang = String(MW.cfg.lang || "en").replace(/[^a-z-]/gi, "") || "en", loadedLang = lang;
      return getJSON(base + "i18n/" + encodeURIComponent(lang) + ".json").catch(function () { loadedLang = "en"; return getJSON(base + "i18n/en.json"); }).then(function (dict) {
        MW.dict = dict; document.documentElement.lang = loadedLang;
        if (demo) {                                                                           // ukazkove texty (demo katalog, vymyslena data) jsou ve zvlastnim souboru jen pro ?demo=1
          return getJSON(base + "i18n/demo." + encodeURIComponent(loadedLang) + ".json").catch(function () { return getJSON(base + "i18n/demo.en.json"); }).catch(function () { return {}; })
            .then(function (dd) { Object.keys(dd).forEach(function (k) { MW.dict[k] = dd[k]; }); return loadMe(); });
        }
        return (demo || cfgFail || MW.cfg.preview === true) ? loadMe() : { user: null };     // prihlaseny uzivatel se zjistuje jen kdyz ho nahled/brana potrebuje (verejny shop se na nej neptá)
      });
    }).then(function (me) {
      var u = me && me.user, staff = !!u && STAFF_ROLES.indexOf(u.role) >= 0;
      MW.user = u || null;
      if (cfgFail) {
        if (cfgFail.status === 404) { if (!u) gate("gate.login", true); else gate(staff ? "gate.shop_missing" : "gate.staff", false); }
        else gate("gate.error", false);
        return new Promise(function () {});
      }
      var needStaff = demo || MW.cfg.preview === true;
      if (needStaff && !u) { renderChromeSafe(page); gate("gate.login", true); return new Promise(function () {}); }
      if (needStaff && !staff) { renderChromeSafe(page); gate("gate.staff", false); return new Promise(function () {}); }
      document.documentElement.setAttribute("data-shop", MW.cfg.shop || "");
      document.documentElement.setAttribute("data-price-mode", MW.mode().price);
      document.documentElement.setAttribute("data-checkout-mode", MW.mode().checkout);
      if (MW.cfg.accent && /^#[0-9a-fA-F]{6}$/.test(MW.cfg.accent)) document.documentElement.style.setProperty("--accent", MW.cfg.accent);
      (MW.cfg.alternates || []).forEach(function (a) {                                     // hreflang sourozencu (jazykove verze shopu)
        if (!a.lang || !a.href) return;
        var l = document.createElement("link"); l.rel = "alternate"; l.hreflang = a.lang; l.href = a.href; document.head.appendChild(l);
      });
      renderChrome(page); MW.translateDom();
      return { cfg: MW.cfg, user: u };
    });
  };
  function renderChromeSafe(page) { try { renderChrome(page); MW.translateDom(); } catch (e) { /* hlavicka je jen kosmetika, hlaska brany se zobrazi tak jako tak */ } }
})(window);
