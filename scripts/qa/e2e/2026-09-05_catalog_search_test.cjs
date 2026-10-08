// Test SKUTECNEHO kodu hledani (vyriznuty ze shipovaneho catalog-panels.js)
// nad REALNYMI nazvy z DB. bot8 2026-09-05.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const fs = require("fs");
const SP = "/tmp/claude-0/-opt-konfigurator/cd1e4f98-59ca-4757-a63c-ad69ec4e8fb4/scratchpad";
const fx = JSON.parse(fs.readFileSync(SP + "/fixture.json", "utf8"));

// --- vyrizni PRODUKCNI kod hledani z catalog-panels.js ---
const src = fs.readFileSync("/opt/konfigurator/webapp/js/scene/catalog-panels.js", "utf8");
const start = src.indexOf("// Slozeni diakritiky");
const endMark = "if (document.readyState === \"loading\")";
const end = src.indexOf(endMark);
if (start < 0 || end < 0) { console.error("NELZE vyriznout kod hledani"); process.exit(3); }
const searchCode = src.slice(start, end);

// --- vyrizni PRODUKCNI CSS ze scene.html ---
const html = fs.readFileSync("/opt/konfigurator/webapp/scene.html", "utf8");
const cssStart = html.indexOf("#catalogSearchWrap {");
const cssEnd = html.indexOf(".cs-tree.is-searching .cs-cat-children.search-hit { display:block; }");
if (cssStart < 0 || cssEnd < 0) { console.error("NELZE vyriznout CSS"); process.exit(3); }
const css = ".cat-children.is-collapsed{display:none;}.cs-cat-children{display:none;}.cs-cat-children.expanded{display:block;}\n"
  + html.slice(cssStart, cssEnd + 70);

const esc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const partBtns = fx.bodies.map(n => `<button class="part-btn">${esc(n)}<small>auto</small></button>`).join("");
const prodBtns = fx.products.map(n => `<button class="part-btn">${esc(n)}</button>`).join("");
const shapeBtns = fx.shapes.map(n => `<div class="custom-shape-btn-wrap"><button class="custom-shape-btn">${esc(n)}</button></div>`).join("");

const page_html = `<!doctype html><meta charset="utf-8"><style>${css}</style>
<div id="catalogSearchWrap">
  <input type="search" id="catalogSearchInput"><button id="catalogSearchClear">x</button>
</div>
<div id="catalogSearchCount"></div>
<div id="catalogList">
  <h2>Profily</h2>
  <div class="cat-group-title is-collapsed"><span class="cat-arrow">&#9662;</span>auto</div>
  <div class="cat-children is-collapsed">${partBtns}</div>
  <h2>Produkty</h2>
  <div class="cat-group-title is-collapsed"><span class="cat-arrow">&#9662;</span>Produkty</div>
  <div class="cat-children is-collapsed">${prodBtns}</div>
</div>
<div id="customShapesTree" class="cs-tree">
  <div class="cs-cat-node"><div class="cs-cat-row">Karoserie</div>
    <div class="cs-cat-children">${shapeBtns}</div></div>
</div>
<div id="productAssembliesTree" class="cs-tree"></div>
<script>${searchCode}</script>`;

fs.writeFileSync(SP + "/harness.html", page_html);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errs = [];
  page.on("pageerror", e => errs.push("pageerror: " + e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console.error: " + m.text()); });
  await page.goto("file://" + SP + "/harness.html");

  const visible = async sel => page.$$eval(sel, els => els.filter(e => e.offsetParent !== null).length);
  const run = async q => { await page.evaluate(v => { document.getElementById("catalogSearchInput").value = v; applyCatalogSearch(v); }, q); };

  let fail = 0;
  const check = (name, got, want) => {
    const ok = typeof want === "function" ? want(got) : got === want;
    console.log(`  ${ok ? "OK  " : "FAIL"}  ${name}  -> ${JSON.stringify(got)}`);
    if (!ok) fail++;
  };

  console.log("=== vychozi stav (sbaleno, nic se nehleda) ===");
  check("viditelnych .part-btn", await visible("#catalogList .part-btn"), 0);
  check("viditelnych tvaru", await visible("#customShapesTree .custom-shape-btn-wrap"), 0);

  console.log("\n=== hledani karoserie VCELKU: 'scudo' ===");
  await run("scudo");
  check("tvaru (ocekavano 11 Scudo)", await visible("#customShapesTree .custom-shape-btn-wrap"), 11);
  check("pocitadlo neprazdne", await page.textContent("#catalogSearchCount"), t => /položek/.test(t));

  console.log("\n=== diakritika: 'citroen' musi najit 'Citroën' ===");
  await run("citroen");
  const cit = await visible("#catalogList .part-btn");
  check("sten Citroen > 0", cit, v => v > 0);

  console.log("\n=== vic slov (AND): 'jumpy l3' ===");
  await run("jumpy l3");
  const j = await visible("#catalogList .part-btn");
  check("sten Jumpy L3 > 0", j, v => v > 0);
  check("uzsi nez samotne 'jumpy'", j, v => v < cit);

  console.log("\n=== kod karoserie: 'CI18' ===");
  await run("CI18");
  check("sten CI18 = 3 (L+R_D+B)", await visible("#catalogList .part-btn"), 3);
  check("tvar CI18 vcelku = 1", await visible("#customShapesTree .custom-shape-btn-wrap"), 1);

  console.log("\n=== nic nenalezeno ===");
  await run("xyzxyz-neexistuje");
  check("zadna polozka", await visible("#catalogList .part-btn"), 0);
  check("hlaska", await page.textContent("#catalogSearchCount"), "Nic nenalezeno");

  console.log("\n=== ZRUSENI hledani musi vratit PUVODNI sbaleny stav ===");
  await run("");
  check("viditelnych .part-btn zpet", await visible("#catalogList .part-btn"), 0);
  check("viditelnych tvaru zpet", await visible("#customShapesTree .custom-shape-btn-wrap"), 0);
  check("is-collapsed nedotcena", await page.$$eval("#catalogList .cat-children",
    els => els.every(e => e.classList.contains("is-collapsed"))), true);
  check("zadna zbytkova search-* trida", await page.$$eval("*",
    els => els.filter(e => e.classList && (e.classList.contains("search-hit") || e.classList.contains("search-miss"))).length), 0);
  check("pocitadlo prazdne", await page.textContent("#catalogSearchCount"), "");

  console.log("\n=== chyby v konzoli ===");
  check("zadny pageerror/console.error", errs, a => a.length === 0);
  if (errs.length) errs.forEach(e => console.log("   " + e));

  await browser.close();
  console.log("\n" + (fail ? `${fail} TESTU SELHALO` : "VSECHNY TESTY OK"));
  process.exit(fail ? 1 : 0);
})();
