"""Zapoji konfigurator do webapp/product.html (idempotentni, kazda kotva musi byt prave 1x).

  apply_product_hooks.py <cesta_k_product.html>
Zmeny jsou zamerne male: kontejner pro panel, lazy nacteni modulu js/product-configurator.js jen kdyz server vrati
product.configurator.available, ochrana ceny v renderPrice, rozsireni cartAdd o pole configuration (kontrakt kosiku bot5:
scripts/2026-10-02_konfigurace_kosik_testy/nasazeni/README.md), chybove kody kosiku, radky konfigurace v kosiku (made_to_order, souhrn, upozorneni).
Hashe souboru v URL (?v=) se pocitaji pri behu ze skutecnych souboru; po zmene modulu je treba je v product.html zmenit rucne.
"""
import sys

path = sys.argv[1]
s = open(path, encoding="utf-8").read()
if "pdInitConfigurator" in s:
    print("uz upraveno - preskakuji")
    sys.exit(0)


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, "kotva nalezena %d× (cekam 1): %r" % (n, old[:80])
    s = s.replace(old, new, 1)


# 1) kontejner pro panel voleb: prvni v pravem sloupci (nad cenou)
rep('            <div id="pdGrooveBadge" style="margin-bottom:6px;"></div>\n',
    '            <!-- Panel voleb konfiguratoru (bot16, 2026-10-02) - plni ho js/product-configurator.js, jen u produktu, ktere server\n'
    '                 oznaci product.configurator.available. Jinde zustava prazdny. -->\n'
    '            <div id="pdConfiguratorHost"></div>\n'
    '            <div id="pdGrooveBadge" style="margin-bottom:6px;"></div>\n')

# 2) funkce adapteru pred loadProduct()
ADAPTER = '''// ---------------------------------------------------------------------------
// Konfigurator sestav NE do auta (bot16, 2026-10-02; Robert pres bot3: "interaktivni zivou volbou komponent" - VEDOMA vyjimka z
// ochrany modelu 2026-09-06, jen pro sestavy, ktere server oznaci product.configurator.available; sestavy do aut zustavaji
// jen otocka). Stranka NIC neodvozuje z dat produktu, vsechno dela lazy-nacteny js/product-configurator.js nad API
// /api/shop/products/<id>/configurator + /api/shop/configurator/resolve. Kdyz priznak chybi nebo modul/API selze, chova se
// stranka PRESNE jako dosud. Verejna stranka nenacita scene.html ani katalog/*.glb - model je jen kratce platny odkaz z resolve.
let pdConfigurator = null;
let pdCfgPrice = null;
// Ceske texty a format ceny pro modul (modul sam ma jen anglicke vychozi, aby sel pouzit i v mini-shopu v jinem jazyce).
const PDC_LABELS_CS = {
  tabTurntable: "Otočka", tabConfigurator: "Konfigurátor", cta: "Upravit komponenty", title: "Vaše konfigurace",
  reset: "Zpět na výchozí", price: "Cena konfigurace", noVat: "bez DPH", withVat: "s DPH", pending: "Počítám…",
  code: "Kód konfigurace", summary: "Souhrn", unavailable: "Tuto možnost teď nelze zvolit.",
  turntableNote: "Otočka ukazuje základní provedení, vaše konfigurace je v tabulce Konfigurátor.",
  errLoad: "Konfigurátor se nepodařilo načíst. Zkuste to prosím znovu.", errNet: "Spojení selhalo, zkuste to prosím znovu.",
  retry: "Zkusit znovu", rateLimit: "Příliš mnoho změn najednou, chvilku počkejte…", rulesChanged: "Nabídka voleb se změnila, načítám novou.",
  modelPrep: "Připravuji model…", modelErr: "Model se nepodařilo načíst, cena platí.", noWebgl: "3D náhled tento prohlížeč nepodporuje, volby a cena fungují.",
  viewerErr: "3D náhled se nepodařilo načíst, volby a cena fungují.", lock: "Klepněte pro ovládání 3D", invalid: "Zvolte prosím platnou konfiguraci.",
  lockHint: "", yes: "ano", no: "ne",
  handleTitle: "Táhněte do stran – posune se celá střední osa", handleCap: "{mm} mm od levé nohy", handleAria: "Poloha střední nohy",
};
function pdcMoney(n) {
  const r = Math.round(Number(n) * 100) / 100;
  return (Number.isInteger(r) ? r.toLocaleString("cs-CZ") : r.toLocaleString("cs-CZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 })) + " Kč";
}
function pdCfgApplyPrice() {
  if (!pdCfgPrice) return false;
  const priceEl = document.getElementById("pdPrice");
  const wasEl = document.getElementById("pdPriceWas");
  const basisEl = document.getElementById("pdPriceBasis");
  const addBtn = document.getElementById("pdAddCartBtn");
  const link = document.getElementById("pdPriceOnRequestLink");
  if (priceEl) priceEl.textContent = `${pdCfgPrice.net.toLocaleString("cs-CZ", { maximumFractionDigits: 2 })} Kč`;
  if (wasEl) wasEl.style.display = "none";
  if (basisEl) basisEl.style.display = "none";
  if (addBtn) addBtn.style.display = "";
  if (link) link.style.display = "none";
  return true;
}
function pdInitConfigurator(p) {
  if (pdConfigurator) { try { pdConfigurator.destroy(); } catch (e) {} pdConfigurator = null; pdCfgPrice = null; }
  if (!p || !p.configurator || !p.configurator.available) return;
  const wrap = document.querySelector(".pd-tt-wrap");
  const panelHost = document.getElementById("pdConfiguratorHost");
  if (!wrap || !panelHost) return;
  const loadModule = window.PdConfigurator ? Promise.resolve() : new Promise((ok, no) => {
    const s = document.createElement("script");
    s.src = "/js/product-configurator.js?v=__JS_V__"; s.onload = ok; s.onerror = no;
    document.head.appendChild(s);
  });
  loadModule.then(() => window.PdConfigurator.init({
    product: p, labels: PDC_LABELS_CS, money: pdcMoney, lang: "cs",
    viewerOpts: (window.matchMedia && window.matchMedia("(max-width: 800px)").matches) ? { hudDock: "top" } : {},
    dom: { tabsBefore: wrap.firstChild, visual: [document.getElementById("pdAssemblyVariants"), wrap.querySelector(".pd-tt-visual")], stageHost: wrap, panelHost },
    page: {
      setPrice(price) { if (price && isFinite(price.net)) { pdCfgPrice = price; pdCfgApplyPrice(); } },
      setBuyState(ok, reason) { const b = document.getElementById("pdAddCartBtn"); if (b) { b.disabled = !ok || CART_ENABLED === false; b.title = ok ? "" : (reason || ""); } },
      toast(msg, type) { showToast(msg, type); },
      onActivate() {}, track() {},
    },
    assets: { cssNow: ["/css/product-configurator.css?v=__CSS_V__"], css: ["/css/v3d.css?v=__V3DCSS_V__"], viewer: "/js/v3d/viewer3d.js?v=__VIEWER_V__" },
  })).then(ctl => { pdConfigurator = ctl; }).catch(() => {});
}

function loadProduct() {
'''
rep('function loadProduct() {\n', ADAPTER)

# 3) renderPrice: cena konfigurace ma prednost
rep('function renderPrice(p) {\n  const priceEl = document.getElementById("pdPrice");\n',
    'function renderPrice(p) {\n  if (pdConfigurator && pdConfigurator.active() && pdCfgApplyPrice()) return; // konfigurator (viz pdInitConfigurator)\n  const priceEl = document.getElementById("pdPrice");\n')

# 4) inicializace: po nacteni produktu i po prepnuti na sourozeny produkt
rep('      pdInitAssemblyVariants(p);   // provedeni v ramci teto karty (bot8 2026-09-10)\n',
    '      pdInitAssemblyVariants(p);   // provedeni v ramci teto karty (bot8 2026-09-10)\n      pdInitConfigurator(p);       // konfigurator sestav ne do auta (bot16 2026-10-02), jen kdyz server rekne\n')
rep('    pdInitAssemblyVariants(p);\n    pdUpdateOfferBox(p);\n    const url = p.slug',
    '    pdInitAssemblyVariants(p);\n    pdInitConfigurator(p);\n    pdUpdateOfferBox(p);\n    const url = p.slug')

# 5) kosik: configuration
rep('async function cartAdd(product_id, cutPieces, couponCode, wholeQty, assemblyOpts, supplierMontaz) {',
    'async function cartAdd(product_id, cutPieces, couponCode, wholeQty, assemblyOpts, supplierMontaz, configuration) {')
rep('  if (couponCode) body.coupon_code = couponCode;\n',
    '  if (couponCode) body.coupon_code = couponCode;\n'
    '  // Konfigurator (bot16 2026-10-02): server cenu pocita znovu z vyberu a hashe, klient cenu NEPOSILA.\n'
    '  if (configuration) body.configuration = configuration;\n')
rep('        const ok = await cartAdd(p.id, cuts.length ? cuts : null, appliedCouponCode, wholeQty, assemblyOpts, supplierMontazOpts);\n',
    '        // Konfigurovatelna sestava: do kosiku jde vybrana konfigurace (null = neplatna/pocita se, nepustit dal).\n'
    '        const cfgPayload = pdConfigurator && pdConfigurator.active() ? pdConfigurator.cartPayload() : undefined;\n'
    '        if (cfgPayload === null) { showToast("Zvolte prosím platnou konfiguraci.", "error"); return; }\n'
    '        const ok = await cartAdd(p.id, cuts.length ? cuts : null, appliedCouponCode, wholeQty, cfgPayload ? null : assemblyOpts, supplierMontazOpts, cfgPayload ? { selection: cfgPayload.configuration.selection, rules_version: cfgPayload.configuration.rules_version } : null);\n')

# 6) chybove kody kosiku pro konfiguraci (bot5): rules_changed -> pravidla se zmenila, invalid_configuration (+errors), rate_limited, not_configurable
rep('    if (!r.ok) { showToast(data.error || "Produkt se nepodařilo přidat do košíku.", "error"); return false; }\n',
    '    if (!r.ok) {\n'
    '      let msg = data.error || "Produkt se nepodařilo přidat do košíku.";\n'
    '      if (data.code === "rules_changed") { msg = "Nabídka voleb se mezitím změnila. Zkontrolujte konfiguraci a přidejte ji znovu."; if (pdConfigurator && pdConfigurator.refresh) pdConfigurator.refresh(); }\n'
    '      else if (data.code === "invalid_configuration") msg = (data.errors && data.errors[0] && data.errors[0].message) || "Konfigurace není platná, upravte ji prosím.";\n'
    '      else if (data.code === "rate_limited") msg = "Příliš mnoho přidání najednou, zkuste to za chvíli.";\n'
    '      else if (data.code === "not_configurable") msg = "Tuhle položku už nelze konfigurovat.";\n'
    '      showToast(msg, "error"); return false;\n'
    '    }\n')

# 7) radky konfigurace v kosiku: vyroba na zakazku (stock_qty null), kod + souhrn voleb, upozorneni pri neplatne/zmenene konfiguraci
rep('    let availHtml;\n    if (!i.active || i.is_archived) {',
    '    let availHtml;\n'
    '    const cfg = i.configuration && typeof i.configuration === "object" ? i.configuration : null;\n'
    '    if (i.made_to_order) {\n'
    '      availHtml = \'<span class="avail-badge ok">výroba na zakázku</span>\';       // konfigurace: bez skladu, nepsat "skladem null" (bot5)\n'
    '    } else if (!i.active || i.is_archived) {')
rep('            <div class="ci-meta">${escapeHtmlCart(i.sku)}</div>\n',
    '            <div class="ci-meta">${escapeHtmlCart(cfg && cfg.kod ? "Kód konfigurace: " + cfg.kod : i.sku)}</div>\n'
    '            ${cfg && Array.isArray(cfg.summary) && cfg.summary.length ? `<div class="ci-cut-info">${cfg.summary.map(x => `${escapeHtmlCart(x.label)}: ${escapeHtmlCart(x.value)}`).join(" · ")}</div>` : ""}\n'
    '            ${i.montaz_zvolena && i.montaz_czk ? `<div class="ci-cut-info">Montáž: +${fmtCzk2(i.montaz_czk)}</div>` : ""}\n'
    '            ${cfg && (cfg.valid === false || cfg.changed) ? `<div class="ci-cut-info" style="color:var(--error,#f07a7a);">${cfg.valid === false ? "Tahle konfigurace už neplatí" : "Pravidla konfigurace se změnila"} - otevřete konfiguraci znovu a přidejte ji do košíku. Objednávku s touto položkou nelze odeslat.</div>` : ""}\n')

# 8) doprava Toptrans u konfigurace (bot5): dokud v katalogu chybi hmotnosti dilu, shipping-price-preview vraci 409 weight_incomplete -> zprava misto ceny
rep('let cartShipPriceTimer = null;\n', 'let cartShipPriceTimer = null;\nlet cartShipNote = "";     // 409 weight_incomplete (konfigurace bez hmotnosti): vysvetleni misto ceny dopravy\n')
rep('    cartLiveShipPrice = r.ok ? data.shipping_price_czk : null;\n    cartLiveShipBasis = r.ok ? data.basis : null;\n',
    '    cartLiveShipPrice = r.ok ? data.shipping_price_czk : null;\n    cartLiveShipBasis = r.ok ? data.basis : null;\n'
    '    cartShipNote = (!r.ok && data && data.code === "weight_incomplete") ? (data.error || "U této konfigurace zatím nejde spočítat dopravu Toptrans - zvolte osobní odběr, nebo nás kontaktujte.") : "";\n')
rep('  const shipM = shipId ? shippingMethodsCache.find(m => String(m.id) === shipId) : null;\n  if (!shipM || shipM.pricing_mode !== "zip_weight") {\n    cartLiveShipPrice = null; cartLiveShipBasis = null;',
    '  const shipM = shipId ? shippingMethodsCache.find(m => String(m.id) === shipId) : null;\n  cartShipNote = "";\n  if (!shipM || shipM.pricing_mode !== "zip_weight") {\n    cartLiveShipPrice = null; cartLiveShipBasis = null;')
rep('  if (shipM.pricing_mode === "zip_weight") {\n    el.textContent = cartLiveShipPrice != null',
    '  if (shipM.pricing_mode === "zip_weight" && cartShipNote) { el.textContent = cartShipNote; return; }\n  if (shipM.pricing_mode === "zip_weight") {\n    el.textContent = cartLiveShipPrice != null')


import hashlib, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/webapp"


def _h(rel):
    return hashlib.sha256(open(os.path.join(ROOT, rel), "rb").read()).hexdigest()[:10]


for _k, _rel in (("__JS_V__", "js/product-configurator.js"), ("__CSS_V__", "css/product-configurator.css"), ("__V3DCSS_V__", "css/v3d.css"), ("__VIEWER_V__", "js/v3d/viewer3d.js")):
    s = s.replace(_k, _h(_rel))


open(path, "w", encoding="utf-8").write(s)
print("upraveno:", path)
