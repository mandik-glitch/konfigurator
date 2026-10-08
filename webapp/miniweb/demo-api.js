/* DEMO odpovedi pro mini-shop (bot16, 2026-10-02): nahrazuje serverove API, dokud ho nepripravi bot5 (cena, kosik, objednavka) a bot10
 * (schema voleb, resolve, model). Zapina se jen s ?demo=1 nebo "demo": true v config.json. Tvar odpovedi je KONTRAKT, ktery skutecne API ma
 * dodrzet (viz the configurator and mini-shop data contracts): stranky se pak nemeni, jen se tenhle soubor prestane nacitat.
 * Texty (nazvy voleb, produktu) jsou DATA ze serveru - v demu se berou z i18n/<jazyk>.json (klice demo.*), skutecny server je preklada sam.
 * Demo modely: bot10 (kontrolni scena), jen pro prihlaseneho staffa. Ceny a doprava jsou vymyslene.
 */
(function (global) {
  "use strict";

  var MODELS = { a: "/katalog/vandr/v3d_nahled/stul_demo_a.glb", b: "/katalog/vandr/v3d_nahled/stul_demo_b.glb" };
  var RULES = "demo-1";
  var BASE = 1290;                                    // EUR bez DPH
  var started = {};                                   // hash -> cas prvni zadosti (simulace "model se pripravuje")

  var TOP = { birch: 0, white: 60, anthracite: 90, steel: 420 };
  var LEGS = { black: 0, white: 25, adjustable: 240 };
  var DEFAULTS = { width: "w0", top: "birch", legs: "black", shelf: false, light: false, service: false };

  function serverConfigurator() { return !!(MW.cfg && MW.cfg.configurator_source === "server"); }
  function t(key) { return (global.MW && MW.t) ? MW.t(key) : key; }

  function norm(sel) {
    var o = Object.assign({}, DEFAULTS, sel || {});
    if (o.width !== "w0" && o.width !== "w200") o.width = "w0";
    if (!(o.top in TOP)) o.top = DEFAULTS.top;
    if (!(o.legs in LEGS)) o.legs = DEFAULTS.legs;
    o.shelf = !!o.shelf; o.light = !!o.light; o.service = !!o.service;
    if (o.top === "steel" && o.legs === "adjustable") o.legs = "black";           // nedostupna kombinace se vrati na vychozi
    return o;
  }
  function net(sel) {
    var n = BASE + (sel.width === "w200" ? 180 : 0) + TOP[sel.top] + LEGS[sel.legs] + (sel.shelf ? 85 : 0) + (sel.light ? 120 : 0);
    return sel.service ? Math.round(n * 1.12) : n;
  }
  function hashOf(sel) {
    var s = JSON.stringify(Object.keys(sel).sort().map(function (k) { return [k, sel[k]]; })) + RULES, h = 5381;
    for (var i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
    return ("00000000" + (h >>> 0).toString(16)).slice(-8) + ("00000000" + ((h * 31) >>> 0).toString(16)).slice(-8);
  }
  function reason(slot, opt, sel) {
    if (slot === "legs" && opt === "adjustable" && sel.top === "steel") return t("demo.reason.steel_adjustable");
    if (slot === "top" && opt === "steel" && sel.legs === "adjustable") return t("demo.reason.steel_adjustable");
    return null;
  }
  var SLOTS = [
    { id: "width", group: "g_size", key: "width", type: "chips", options: ["w0", "w200"], g: 11 },
    { id: "top", group: "g_surface", key: "top", type: "swatch", options: ["birch", "white", "anthracite", "steel"], g: 12, sw: { birch: "#d9b98a", white: "#eeeeee", anthracite: "#3a3f46", steel: "#b8c0c8" } },
    { id: "legs", group: "g_frame", key: "legs", type: "chips", options: ["black", "white", "adjustable"], g: 13 },
    { id: "shelf", group: "g_frame", key: "shelf", type: "toggle", g: 14 },
    { id: "light", group: "g_extras", key: "light", type: "toggle" },
    { id: "service", group: "g_extras", key: "service", type: "toggle" }
  ];
  function schema() {
    return {
      rules_version: RULES,
      groups: ["g_size", "g_surface", "g_frame", "g_extras"].map(function (g) { return { id: g, label: t("demo.group." + g) }; }),
      slots: SLOTS.map(function (s) {
        var o = { id: s.id, group: s.group, label: t("demo.slot." + s.key), help: null, type: s.type };
        if (s.options) o.options = s.options.map(function (id) { var x = { id: id, label: t("demo.opt." + s.key + "." + id) }; if (s.sw) x.swatch = s.sw[id]; return x; });
        else o.options = [{ id: "on", label: t("demo.slot." + s.key) }];
        if (s.g != null) o.g = s.g;
        return o;
      }),
      default_selection: DEFAULTS
    };
  }
  function resolve(raw) {
    var sel = norm(raw), cur = net(sel), options = {};
    SLOTS.forEach(function (s) {
      options[s.id] = {};
      (s.options || ["on"]).forEach(function (id) {
        var alt = Object.assign({}, sel);
        if (s.type === "toggle") alt[s.key] = true; else alt[s.key] = id;
        var altN = norm(alt), why = reason(s.id, id, alt);
        options[s.id][id] = { price_delta: net(altN) - cur, disabled: !!why, reason: why };
      });
    });
    var hash = hashOf(sel), model;
    if (sel.top === "steel") {                                                  // ukazka "model se pripravuje"
      started[hash] = started[hash] || Date.now();
      model = Date.now() - started[hash] > 1400 ? { stav: "hotovo", url: sel.width === "w200" ? MODELS.b : MODELS.a, odhad_ms: 0 } : { stav: "pripravuje_se", url: null, odhad_ms: 700 };
    } else model = { stav: "hotovo", url: sel.width === "w200" ? MODELS.b : MODELS.a, odhad_ms: 0 };
    return { selection: sel, hash: hash, kod: "PS-" + hash.slice(0, 6).toUpperCase(), rules_version: RULES, valid: true, errors: [],
             price: { net: cur, vat_rate: 0, currency: (MW.cfg && MW.cfg.currency) || "EUR" }, options: options, model: model };
  }

  var stateByHash = {};                                                         // pro GET model/<hash>
  function categories() {                                                       // az pri zadosti, kdy uz je nacteny slovnik
    return [{ id: 1, parent_id: null, slug: "tables", name: t("demo.cat.tables"), count: 1 }, { id: 2, parent_id: 1, slug: "packing-stations", name: t("demo.cat.packing"), count: 1 }];
  }
  function product() {
    return { id: 9001, slug: "packing-station-ps120", sku: t("demo.product.sku"), category_id: 2, name: t("demo.product.name"), summary: t("demo.product.summary"),
             description: t("demo.product.description"), price_from: serverConfigurator() ? null : net(norm({})), currency: (MW.cfg && MW.cfg.currency) || "EUR",
             delivery: t("demo.product.delivery"), groove_family: "8", cross_section_label: "30\u00d730", profil_mm: 30, configurator: { available: true, default_view: "configurator", product_id: (MW.cfg && MW.cfg.configurator_product_id) || 9001 },
             specs: [{ name: t("demo.spec.dimensions"), value: t("demo.spec.dimensions_value") }, { name: t("demo.spec.material"), value: t("demo.spec.material_value") }, { name: t("demo.spec.load"), value: t("demo.spec.load_value") }] };
  }

  function quote(b) {                                                            // tvar jako POST /api/miniweb/quote (bot5): EUR, bez DPH, moznosti dopravy "po dohode" / osobni odber
    var lines = (b.items || []).map(function (it) {
      var unit = net(norm(it.configuration && it.configuration.selection)), qty = Math.max(1, Math.min(99, parseInt(it.qty, 10) || 1));
      return { product_id: it.product_id, name: t("demo.product.name"), qty: qty, net_unit: unit, net_total: unit * qty, configuration: { valid: true, changed: false, kod: "DEMO", summary: [], errors: [] } };
    });
    var goods = lines.reduce(function (s, l) { return s + l.net_total; }, 0);
    return { currency: (MW.cfg && MW.cfg.currency) || "EUR", prices_include_vat: false, lines: lines, subtotal: goods, total_goods: goods,
             shipping_options: [{ id: "quote", label: t("demo.ship.quote"), net: null }, { id: "pickup", label: t("demo.ship.pickup"), net: 0 }],
             vat: { applied: false, note: t("demo.vat.note") }, notes: [] };
  }
  function json(obj, status) { return new Response(JSON.stringify(obj), { status: status || 200, headers: { "Content-Type": "application/json" } }); }

  MW.demoInstall = function () {
    var real = global.fetch.bind(global);
    global.fetch = function (input, init) {
      var url = typeof input === "string" ? input : (input && input.url) || "";
      var path = url.replace(location.origin, "").split("?")[0];
      var method = ((init && init.method) || (input && input.method) || "GET").toUpperCase();
      var m;
      if (path === "/api/miniweb/config") {                                                         // demo bere konfiguraci ze statickeho souboru config.<jazyk>.json (jinak config.json)
        var cl = String((MW.params && MW.params.lang) || "en").replace(/[^a-z-]/gi, "");
        return real("/miniweb/config." + cl + ".json").then(function (r) { return r.ok ? r : real("/miniweb/config.json"); });
      }
      if (/^\/api\/shop\/(products\/\d+\/configurator|configurator\/)/.test(path) && serverConfigurator()) return real(input, init);   // skutecny configurator ze serveru (bot8), ne vymyslena data
      if (path === "/api/miniweb/quote" && method === "POST") {                                     // fáze 3 (nahled): cena, doprava a DPH ze serveru, tady z vymyslenych pravidel
        var qb = {}; try { qb = JSON.parse(init.body); } catch (e) { /* prazdne */ }
        return Promise.resolve(json(quote(qb)));
      }
      if (path === "/api/miniweb/categories") return Promise.resolve(json({ categories: categories() }));
      if (path === "/api/miniweb/products" && method === "GET") return Promise.resolve(json({ products: [product()], total: 1 }));
      if ((m = path.match(/^\/api\/miniweb\/products\/(\d+)$/))) return Promise.resolve(Number(m[1]) === 9001 ? json({ product: product() }) : json({ error: "not_found" }, 404));
      if (path === "/api/miniweb/legal") return Promise.resolve(json({ seller: null }));
      if (path === "/api/shop/products/9001/configurator") return Promise.resolve(json(schema()));
      if (path === "/api/shop/configurator/resolve" && method === "POST") {
        var body = {}; try { body = JSON.parse(init.body); } catch (e) { /* prazdne */ }
        var r = resolve(body.selection); stateByHash[r.hash] = body.selection;
        return Promise.resolve(json(r));
      }
      if ((m = path.match(/^\/api\/shop\/configurator\/model\/([0-9a-f]+)$/))) {
        var s = stateByHash[m[1]]; return Promise.resolve(s ? json({ model: resolve(s).model }) : json({ error: "not_found" }, 404));
      }
      return real(input, init);
    };
  };
})(window);
