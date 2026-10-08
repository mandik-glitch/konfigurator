// Test: generator stolu na strankach kategorii (bot10, 2026-10-04) - ZIVA stranka autovestavby.logiman.cz (jen cteni, nic se nezapisuje):
//   311 "Robustni balici stul system 40" -> iframe /embed/stul.html?p=4954&theme=..., titulek "systém 40", v iframe cena podle systemu 40
//   206 "Lehky balici stul system 30"    -> iframe /embed/stul.html?theme=... (bez p), titulek "systém 30", v iframe cena karty 4934 (beze zmeny)
//   183 "Ergonomicke balici stoly SSE"   -> bez generatoru
// Spusteni: node scripts/2026-10-04_system40/test_kategorie_generator.js   (BASE=https://... pro jinou adresu)
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE || "https://autovestavby.logiman.cz";
let ok = 0; const fails = [];
function check(c, m) { if (c) ok++; else { fails.push(m); console.log("  CHYBA:", m); } }
(async () => {
  const b = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  async function otevri(slug, ceka) {
    const ctx = await b.newContext({ viewport: { width: 1300, height: 900 } });
    const p = await ctx.newPage(); const errs = [], resolve = [];
    p.on("pageerror", e => errs.push(e.message));
    p.on("request", r => { if (/\/api\/shop\/configurator\/resolve/.test(r.url())) resolve.push(r.postData() || ""); });
    const resp = await p.goto(`${BASE}/${slug}`, { waitUntil: "load" });
    if (ceka) await p.waitForTimeout(12000); else await p.waitForTimeout(2500);
    const out = { ctx, p, status: resp.status(), errs, resolve };
    return out;
  }
  // ---- 311: system 40
  let t = await otevri("robustni-balici-stul-system-40", true);
  check(t.status === 200, `311: HTTP ${t.status}`);
  let info = await t.p.evaluate(() => {
    const w = document.getElementById("catGenerator"), f = document.getElementById("catGeneratorFrame");
    return { h1: (document.querySelector("h1") || {}).textContent || "", visible: !!w && getComputedStyle(w).display !== "none", src: f && f.getAttribute("src"), title: f && f.getAttribute("title") };
  });
  check(/Robustní balicí stůl system 40/.test(info.h1), `311: nadpis '${info.h1.trim()}'`);
  check(info.visible, "311: generator je videt");
  check(/^\/embed\/stul\.html\?p=4954&theme=(dark|light)/.test(info.src || ""), `311: src iframe '${info.src}'`);
  check(info.title === "Generátor stolu – systém 40", `311: titulek iframe '${info.title}'`);
  const fr = t.p.frames().find(f => /\/embed\/stul\.html/.test(f.url()));
  check(!!fr, "311: iframe se nacetl");
  if (fr) {
    const txt = await fr.evaluate(() => document.body.innerText.replace(/\s+/g, " "));
    check(/CENA KONFIGURACE\s+[\d\s]+ Kč bez DPH/.test(txt), "311: v iframe je cena konfigurace");
    check(await fr.evaluate(() => !!document.querySelector("canvas")), "311: v iframe je 3D okno");
  }
  check(t.resolve.length > 0 && /"product_id":4954/.test(t.resolve[0]), `311: resolve jde na kartu 4954 (${(t.resolve[0] || "").slice(0, 40)})`);
  check(t.errs.length === 0, `311: chyby stranky: ${t.errs.slice(0, 2).join(" | ")}`);
  const cena40 = fr ? await fr.evaluate(() => ((document.body.innerText.replace(/\s+/g, " ")).match(/CENA KONFIGURACE ([\d ]+) Kč bez DPH/) || [])[1] || "") : "";
  await t.ctx.close();

  // ---- 206: system 30 beze zmeny
  t = await otevri("lehky-balici-stul-system-30", true);
  check(t.status === 200, `206: HTTP ${t.status}`);
  info = await t.p.evaluate(() => {
    const f = document.getElementById("catGeneratorFrame");
    return { src: f && f.getAttribute("src"), title: f && f.getAttribute("title") };
  });
  check(/^\/embed\/stul\.html\?theme=(dark|light)/.test(info.src || "") && !/p=/.test(info.src), `206: src iframe '${info.src}'`);
  check(info.title === "Generátor stolu – systém 30", `206: titulek iframe '${info.title}'`);
  const fr30 = t.p.frames().find(f => /\/embed\/stul\.html/.test(f.url()));
  check(!!fr30, "206: iframe se nacetl");
  const cena30 = fr30 ? await fr30.evaluate(() => ((document.body.innerText.replace(/\s+/g, " ")).match(/CENA KONFIGURACE ([\d ]+) Kč bez DPH/) || [])[1] || "") : "";
  check(!!cena30, "206: v iframe je cena konfigurace");
  check(t.resolve.length > 0 && /"product_id":4934/.test(t.resolve[0]), `206: resolve jde na kartu 4934 (${(t.resolve[0] || "").slice(0, 40)})`);
  check(t.errs.length === 0, `206: chyby stranky: ${t.errs.slice(0, 2).join(" | ")}`);
  await t.ctx.close();
  check(!!cena40 && !!cena30 && cena40 !== cena30, `ceny se lisi podle systemu (40: ${cena40} / 30: ${cena30})`);

  // ---- 183: bez generatoru
  t = await otevri("ergonomicke-balici-stoly-sse", false);
  check(t.status === 200, `183: HTTP ${t.status}`);
  info = await t.p.evaluate(() => { const w = document.getElementById("catGenerator"); return { visible: !!w && getComputedStyle(w).display !== "none" }; });
  check(!info.visible, "183: generator se neukazuje");
  check(t.errs.length === 0, `183: chyby stranky: ${t.errs.slice(0, 2).join(" | ")}`);
  await t.ctx.close();
  await b.close();
  console.log(`\n${ok} kontrol OK` + (fails.length ? `; SELHALO ${fails.length}` : ""));
  process.exit(fails.length ? 1 : 0);
})();
