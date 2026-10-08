// QA: kazda polozka katalogu ve Scene (dlazdice obrazkoveho katalogu i radek seznamu) MA mazaci ikonu (bot8, 2026-10-03; Robert: "chybi mazaci ikona u polozky z obrazku -
// udelej script, ktery pohlida, aby se udelala mazaci ikona u kazde nove polozky").
// 1) STATICKA kontrola webapp/js/scene/catalog-panels.js: mazaci ikonu vyrabi JEDINA funkce attachCatalogRemoveButton; makePartButton a makeCatalogImgBtn ji volaji;
//    obe vykreslovaci funkce volaji hlidac ensureCatalogRemoveButtons; hlidac je nainstalovan (MutationObserver).
// 2) BEHOVA kontrola v Chromiu (Playwright, bez prihlaseni a bez serveru): vytazene funkce se pustí nad umelym katalogem (produkt i dil z cfg_dily) - ikona se doplni sama,
//    u produktu vypne "Pro scenu" (PUT), u cfg_dily smaze (DELETE), neadmin ikonu nedostane.
// Pouziti: node scripts/qa/catalog_delete_icons.js [--json]     Exit: 0 ok, 2 chyba (kontrakt scripts/qa/README.md)
const fs = require("fs"), path = require("path");
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const SRC = process.env.CATALOG_PANELS_SRC || path.join(__dirname, "..", "..", "webapp", "js", "scene", "catalog-panels.js");   // CATALOG_PANELS_SRC = kopie pro mutacni zkousku
const wantJson = process.argv.includes("--json");
const findings = [], t0 = Date.now();
let ok = 0;
const check = (cond, code, title, detail) => { if (cond) ok++; else findings.push({ severity: "critical", code, title, detail: detail || "", where: "webapp/js/scene/catalog-panels.js", fix_hint: "Mazaci ikonu vyrabi jen attachCatalogRemoveButton; kazdy novy typ dlazdice/radku katalogu ji musi volat (nebo ho doplni ensureCatalogRemoveButtons)." }); };

function funcBody(src, name) {
  const i = src.indexOf("function " + name + "(");
  if (i < 0) return null;
  let d = 0, k = src.indexOf("{", i);
  for (let j = k; j < src.length; j++) { if (src[j] === "{") d++; else if (src[j] === "}") { d--; if (d === 0) return src.slice(i, j + 1); } }
  return null;
}

(async () => {
  const src = fs.readFileSync(SRC, "utf8");
  // ---- 1) staticka kontrola
  const attach = funcBody(src, "attachCatalogRemoveButton"), ensure = funcBody(src, "ensureCatalogRemoveButtons");
  check(!!attach && !!ensure, "ICON_FUNC_MISSING", "attachCatalogRemoveButton / ensureCatalogRemoveButtons v catalog-panels.js chybi");
  const tile = funcBody(src, "makeCatalogImgBtn"), row = funcBody(src, "makePartButton");
  check(tile && /attachCatalogRemoveButton\(btn, p, "catalog-img-btn-remove"\)/.test(tile), "ICON_TILE_NOT_USING_ATTACH", "makeCatalogImgBtn nevola attachCatalogRemoveButton (dlazdice by nemela mazaci ikonu)");
  check(row && /attachCatalogRemoveButton\(btn, p, "part-btn-remove"\)/.test(row), "ICON_ROW_NOT_USING_ATTACH", "makePartButton nevola attachCatalogRemoveButton (radek seznamu by nemel mazaci ikonu)");
  const sansAttach = src.replace(attach || "", "");
  check(!/createElement\("span"\)[\s\S]{0,200}-remove"/.test(sansAttach) && !/removeBtn\s*=\s*document\.createElement/.test(sansAttach), "ICON_DUPLICATE_IMPL", "mazaci ikona se vyrabi i mimo attachCatalogRemoveButton (druha implementace se muze rozejit)");
  const render = funcBody(src, "renderCatalogImagePanel"), build = funcBody(src, "buildCatalogList");
  check(render && /ensureCatalogRemoveButtons\(\)/.test(render), "GUARD_NOT_IN_RENDER", "renderCatalogImagePanel nevola ensureCatalogRemoveButtons");
  check(build && /ensureCatalogRemoveButtons\(\)/.test(build), "GUARD_NOT_IN_BUILD", "buildCatalogList nevola ensureCatalogRemoveButtons");
  check(/new MutationObserver\(scheduleCatalogRemoveGuard\)/.test(src) && /installCatalogRemoveGuard\(\)/.test(src), "GUARD_NOT_INSTALLED", "hlidac (MutationObserver) neni nainstalovan");

  // ---- 2) behova kontrola
  if (attach && ensure) {
    const guardSrc = src.slice(src.indexOf("function attachCatalogRemoveButton"), src.indexOf("function makePartButton"));
    const browser = await chromium.launch();
    try {
      const page = await browser.newPage();
      await page.setContent('<div id="catalogList"></div><div id="catalogImgPanelBody"></div><div id="viewport"></div>');
      const res = await page.evaluate(async (code) => {
        const calls = [];
        window.CURRENT_USER = { role: "admin" };
        window.CATALOG = [
          { id: "product_1", source: "product", shop_product_id: 1, name: "Produkt A" },
          { id: "test_dil", source: "profil", name: "Testovaci dil (kontrola)" },
          { id: "dil_b", source: "profil", name: "Dil B" },
        ];
        window.confirm = () => true; window.alert = (m) => calls.push("alert:" + m);
        window.fetch = async (url, opt) => { calls.push((opt && opt.method || "GET") + " " + url + (opt && opt.body ? " " + opt.body : "")); return { ok: true, json: async () => ({}) }; };
        window.buildCatalogList = () => calls.push("buildCatalogList"); window.renderCatalogImagePanel = () => calls.push("renderCatalogImagePanel");
        (0, eval)(code.replace(/let catalogRemoveGuardTimer/, "var catalogRemoveGuardTimer") + "\nwindow.__t = { attachCatalogRemoveButton, ensureCatalogRemoveButtons, installCatalogRemoveGuard };");
        const mk = (host, cls, id) => { const b = document.createElement("button"); b.className = cls; b.dataset.partId = id; b.textContent = id; document.getElementById(host).appendChild(b); return b; };
        window.__t.installCatalogRemoveGuard();
        const tiles = [mk("catalogImgPanelBody", "catalog-img-btn", "product_1"), mk("catalogImgPanelBody", "catalog-img-btn", "test_dil"), mk("catalogList", "part-btn", "dil_b")];
        const out = {};
        await new Promise(r => setTimeout(r, 120));                  // hlidac (MutationObserver + rAF) doplni ikony sam
        out.iconsAfterGuard = tiles.map(b => b.querySelector("[data-catalog-remove]") ? b.querySelector("[data-catalog-remove]").dataset.catalogRemove : null);
        out.classes = tiles.map(b => (b.querySelector("[data-catalog-remove]") || {}).className || null);
        out.dup = tiles.map(b => b.querySelectorAll("[data-catalog-remove]").length);
        // plovouci dlazdice v #viewport
        const fl = mk("viewport", "catalog-img-btn catalog-img-btn-floating", "dil_b");
        await new Promise(r => setTimeout(r, 120));
        out.floating = !!fl.querySelector("[data-catalog-remove]");
        // klik: produkt -> PUT visible_in_scene false; cfg_dily -> DELETE /api/admin/profily/<id>
        tiles[0].querySelector("[data-catalog-remove]").click(); await new Promise(r => setTimeout(r, 50));
        tiles[1].querySelector("[data-catalog-remove]").click(); await new Promise(r => setTimeout(r, 50));
        out.calls = calls.slice();
        out.catalogAfter = window.CATALOG.map(x => x.id);
        // neadmin: zadna ikona
        window.CURRENT_USER = { role: "editor" };
        const x = mk("catalogImgPanelBody", "catalog-img-btn", "dil_b");
        await new Promise(r => setTimeout(r, 120));
        const dir = window.__t.attachCatalogRemoveButton(document.createElement("button"), { id: "dil_b", source: "profil", name: "Dil B" }, "part-btn-remove");
        out.nonAdmin = !!x.querySelector("[data-catalog-remove]") || !!dir;      // ani hlidac, ani primo volana attach neadminovi ikonu nedaji
        return out;
      }, guardSrc);
      check(JSON.stringify(res.iconsAfterGuard) === JSON.stringify(["hide", "delete", "delete"]), "ICON_GUARD_FAILED", "hlidac nedoplnil ikony u vsech novych dlazdic/radku", JSON.stringify(res.iconsAfterGuard));
      check(res.classes[0] === "catalog-img-btn-remove" && res.classes[2] === "part-btn-remove", "ICON_CLASS_WRONG", "ikona ma spatnou CSS tridu (dlazdice catalog-img-btn-remove, radek part-btn-remove)", JSON.stringify(res.classes));
      check(res.dup.every(n => n === 1), "ICON_DUPLICATED", "nektera polozka ma vic nez jednu mazaci ikonu", JSON.stringify(res.dup));
      check(res.floating, "ICON_FLOATING_MISSING", "plovouci dlazdice (vytazena do #viewport) nema mazaci ikonu");
      check(res.calls.some(c => c.startsWith("PUT /api/shop/products/1 ") && c.includes('"visible_in_scene":false')), "ICON_PRODUCT_ACTION", "klik na ikonu produktu nevypnul 'Pro scenu' (PUT)", JSON.stringify(res.calls));
      check(res.calls.some(c => c.startsWith("DELETE /api/admin/profily/test_dil")), "ICON_CFG_ACTION", "klik na ikonu dilu z cfg_dily nesmazal dil (DELETE /api/admin/profily/<id>)", JSON.stringify(res.calls));
      check(!res.catalogAfter.includes("product_1") && !res.catalogAfter.includes("test_dil") && res.catalogAfter.includes("dil_b"), "ICON_CATALOG_STATE", "po smazani zustala polozka v CATALOG", JSON.stringify(res.catalogAfter));
      check(res.nonAdmin === false, "ICON_NON_ADMIN", "neadmin dostal mazaci ikonu");
    } finally { await browser.close(); }
  }
  const status = findings.length ? "fail" : "ok";
  if (wantJson) console.log(JSON.stringify({ suite: "catalog_delete_icons", ran_at: new Date().toISOString(), duration_s: (Date.now() - t0) / 1000, status, findings, stats: { checks_ok: ok } }));
  else { findings.forEach(f => console.log("CHYBA", f.code, "-", f.title, f.detail || "")); console.log(findings.length ? `${findings.length} CHYB, ${ok} kontrol OK` : `${ok} kontrol OK`); }
  process.exit(findings.length ? 2 : 0);
})().catch(e => { console.log("CHYBA testu:", e); process.exit(3); });
