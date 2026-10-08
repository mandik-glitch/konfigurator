// Test vyberu TYPU nove sestavy ve scene (webapp/scene.html, panel Produktove sestavy) - bot8, 2026-10-02.
// Pilotni stul musi jit ulozit jako sestava typu STUL_SKLAD. Backend: POST /api/product-assemblies
// {sestava_typ}, GET /api/product-assemblies/typy (api/product_assemblies.py, test_ulozeni_typu.py).
//
// Bez prohlizece: z scene.html vyrizne PRESNY text bloku (znacky nize) a spusti ho v Node vm proti atrape
// DOM. Hlida: (1) bez typu z backendu (starsi backend / 404) se NIC nemeni - telo POST bez `sestava_typ`,
// vyber skryty; (2) s typy se zobrazi vyber, zvoleny typ jde do tela; (3) zmena vyberu aktualizuje radek;
// (4) typ, ktery z backendu zmizel, se vrati na vychozi; (5) zdroj: ulozeni posila extras, ukladani overuje
// odpoved, nacitani vola /typy.
//
// Spusteni: node scripts/2026-10-02_sestava_typ_testy/test_scena_vyber_typu.js
//   (kandidat: SCENE_HTML=/cesta/scene.html)  ->  "N testu proslo" / "FAIL - ..." + exit 1.
const vm = require("vm"), fs = require("fs"), assert = require("assert"), path = require("path");
const sceneFile = process.env.SCENE_HTML || path.join(__dirname, "..", "..", "webapp", "scene.html");
const src = fs.readFileSync(sceneFile, "utf8");
function between(a, b) {
  const i = src.indexOf(a); if (i < 0) throw new Error("znacka A: " + a);
  const j = src.indexOf(b, i + a.length); if (j < 0) throw new Error("znacka B: " + b);
  return src.slice(i, j);
}
const block = between("let PA_TYPY = [];", "function paFindCategoryName(id)");

function makeEnv() {
  const els = {
    paTypLine: { style: { display: "none" } },
    paTypSelect: { innerHTML: "", children: [], value: "", appendChild(o) { this.children.push(o); },
                   set innerHTMLReset(_) {} },
    paActiveCategoryLine: { textContent: "" },
  };
  // innerHTML = "" maze potomky (jako prohlizec)
  Object.defineProperty(els.paTypSelect, "innerHTML", { get() { return ""; }, set(v) { this.children.length = 0; } });
  const ctx = vm.createContext({
    document: { getElementById: id => els[id] || null, createElement: () => ({ value: "", textContent: "" }) },
    PRODUCT_ASSEMBLY_CATEGORIES: [], console, Array, Object, Set, JSON,
  });
  vm.runInContext(`
    function paFindCategoryName(id) { return id == null ? "Nezařazené" : "Kat" + id; }
    let activeAssemblyCategoryId = null;
    ${block}
  `, ctx);
  return { els, run: code => vm.runInContext(code, ctx) };
}

const TYPY = { typy: [{ kod: "AUTO", nazev: "Vestavby do vozidel" }, { kod: "STUL_SKLAD", nazev: "Stolové a skladové sestavy" }], vychozi: "AUTO" };
let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log("  ok  -", name); }
  catch (e) { console.log("FAIL  -", name, "\n       ", e.message); process.exitCode = 1; }
}

test("T1 bez typu z backendu: telo POST beze zmeny (zadny sestava_typ), vyber skryty", () => {
  const { els, run } = makeEnv();
  assert.deepStrictEqual(JSON.parse(run(`JSON.stringify(paNewAssemblyBodyExtras())`)), {});
  run(`paSetTypy(null); paRenderTypSelect(); paUpdateActiveLine();`);
  assert.strictEqual(els.paTypLine.style.display, "none");
  assert.ok(!els.paActiveCategoryLine.textContent.includes("typ:"), els.paActiveCategoryLine.textContent);
  assert.deepStrictEqual(JSON.parse(run(`JSON.stringify(paNewAssemblyBodyExtras())`)), {});
});

test("T2 se dvema typy: vyber viditelny, 2 volby, vychozi AUTO, telo nese sestava_typ", () => {
  const { els, run } = makeEnv();
  run(`paSetTypy(${JSON.stringify(TYPY)}); paRenderTypSelect(); paUpdateActiveLine();`);
  assert.strictEqual(els.paTypLine.style.display, "flex");
  assert.deepStrictEqual(els.paTypSelect.children.map(o => o.value), ["AUTO", "STUL_SKLAD"]);
  assert.strictEqual(els.paTypSelect.children[1].textContent, "Stolové a skladové sestavy");
  assert.strictEqual(els.paTypSelect.value, "AUTO");
  assert.deepStrictEqual(JSON.parse(run(`JSON.stringify(paNewAssemblyBodyExtras())`)), { sestava_typ: "AUTO" });
  assert.ok(els.paActiveCategoryLine.textContent.endsWith("typ: Vestavby do vozidel"), els.paActiveCategoryLine.textContent);
});

test("T3 zmena vyberu na STUL_SKLAD: radek i telo POST se prepnou, strom se neprekresluje", () => {
  const { els, run } = makeEnv();
  run(`paSetTypy(${JSON.stringify(TYPY)}); paRenderTypSelect();`);
  els.paTypSelect.value = "STUL_SKLAD"; els.paTypSelect.onchange();
  assert.strictEqual(run(`activeAssemblyTypKod`), "STUL_SKLAD");
  assert.ok(els.paActiveCategoryLine.textContent.endsWith("typ: Stolové a skladové sestavy"), els.paActiveCategoryLine.textContent);
  assert.deepStrictEqual(JSON.parse(run(`JSON.stringify(paNewAssemblyBodyExtras())`)), { sestava_typ: "STUL_SKLAD" });
});

test("T4 znovunacteni: zvoleny typ zustane, kdyz existuje; kdyz zmizel (neaktivni), vrati se vychozi", () => {
  const { els, run } = makeEnv();
  run(`paSetTypy(${JSON.stringify(TYPY)}); paRenderTypSelect();`);
  els.paTypSelect.value = "STUL_SKLAD"; els.paTypSelect.onchange();
  run(`paSetTypy(${JSON.stringify(TYPY)}); paRenderTypSelect();`);
  assert.strictEqual(run(`activeAssemblyTypKod`), "STUL_SKLAD");
  assert.strictEqual(els.paTypSelect.value, "STUL_SKLAD");
  run(`paSetTypy(${JSON.stringify({ typy: [TYPY.typy[0], { kod: "JINY", nazev: "Jiný" }], vychozi: "AUTO" })}); paRenderTypSelect();`);
  assert.strictEqual(run(`activeAssemblyTypKod`), "AUTO");
});

test("T5 jediny typ: vyber skryty (neni z ceho vybirat), ale typ se v tele posila explicitne", () => {
  const { els, run } = makeEnv();
  run(`paSetTypy(${JSON.stringify({ typy: [TYPY.typy[0]], vychozi: "AUTO" })}); paRenderTypSelect(); paUpdateActiveLine();`);
  assert.strictEqual(els.paTypLine.style.display, "none");
  assert.ok(!els.paActiveCategoryLine.textContent.includes("typ:"));
  assert.deepStrictEqual(JSON.parse(run(`JSON.stringify(paNewAssemblyBodyExtras())`)), { sestava_typ: "AUTO" });
});

test("T6 vadna odpoved backendu (typy neni pole, polozka bez kodu) se bere jako 'typy nejsou'", () => {
  const { run } = makeEnv();
  run(`paSetTypy({ typy: "x" })`);
  assert.strictEqual(run(`PA_TYPY.length`), 0);
  run(`paSetTypy({ typy: [null, {}, { kod: "AUTO", nazev: "A" }] })`);
  assert.strictEqual(run(`PA_TYPY.length`), 1);
});

test("T7 zdroj: ulozeni sestavy posila extras, over odpoved, toast nese typ; nacitani vola /typy", () => {
  const save = between("function saveSelectionAsProductAssembly() {", "// bot8 2026-09-15 (Robert:");
  assert.ok(save.includes("Object.assign({ name, category_id: activeAssemblyCategoryId") && save.includes("paNewAssemblyBodyExtras()"),
    "telo POST musi obsahovat paNewAssemblyBodyExtras()");
  assert.ok(save.includes("data.sestava_typ !== activeAssemblyTypKod"), "ulozeni musi overit typ vraceny serverem");
  assert.ok(save.includes("typ: \" + paTypNazev(data.sestava_typ)"), "toast ma nest typ");
  const reload = between("function paReloadCategoriesAndShapes() {", "// ==================== Fronta ke schvalovani");
  assert.ok(reload.includes('fetch("/api/product-assemblies/typy")') && reload.includes("paSetTypy(typData)"),
    "nacitani musi volat /typy a predat paSetTypy");
  assert.ok(reload.includes(".catch(() => null)"), "chyba /typy nesmi shodit nacteni sestav (Promise.all)");
});

console.log(passed + " testu proslo" + (process.exitCode ? " - NEKTERE SELHALY" : ""));
