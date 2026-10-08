const fs = require("fs");
const src = fs.readFileSync("/opt/konfigurator/webapp/product.html", "utf8");

// --- pocitadla toho, co zpusobuje blikani ---
let mountu = 0, vyprazdneni = 0, fetchu = 0, vymenSrc = 0;

const handlers = {};
function mkImg() {
  return { _src: "", _srcset: "", decode: () => Promise.resolve(),
    set src(v) { this._src = v; vymenSrc++; }, get src() { return this._src; },
    set srcset(v) { this._srcset = v; }, get srcset() { return this._srcset; },
    getAttribute(k) { return k === "src" ? this._src : null; },
    setAttribute() {}, dataset: {}, style: {}, classList: { add(){}, remove(){} } };
}
function mkEl(tag) {
  const el = {
    tag, style: {}, dataset: {}, children: [], className: "", textContent: "", title: "", tabIndex: 0,
    classList: { add() {}, remove() {}, contains() { return false } },
    setAttribute(k, v) { this[k] = v }, removeAttribute() {},
    appendChild(x) { this.children.push(x); return x },
    append(...xs) { this.children.push(...xs) },
    addEventListener(ev, fn) { handlers[ev] = fn },
    focus() {}, setPointerCapture() {}, releasePointerCapture() {},
    getBoundingClientRect() { return { top: 0, left: 0, height: 26, width: 700 } },
    querySelector(sel) { return sel.includes("img") ? this._img : null },
    set innerHTML(v) { if (v === "") vyprazdneni++; this.children = []; },
    get innerHTML() { return ""; },
  };
  if (tag === "img") return mkImg();
  return el;
}
const holder = mkEl("div");
holder._img = mkImg();

global.document = {
  createElement: mkEl, createDocumentFragment: () => mkEl("frag"),
  getElementById: (id) => (id === "pdTurntable" ? holder : null),
};
global.Image = mkImg;
global.window = { Turntable: { mount: () => { mountu++; return { destroy() {}, ready: Promise.resolve() }; } },
                  requestIdleCallback: null, location: { href: "http://x/" } };
global.requestIdleCallback = null;
global.setTimeout = (fn) => { /* prefetch neresime */ };
global.Turntable = global.window.Turntable;
global.pdActiveTurntable = null;
global.pdActiveAssemblyId = null;
global.pdTurntableMaxVh = () => 600;
global.console = console;

// meta pro 7 provedeni - fetch se pocita
const META = {};
[346,342,344,341,343,345,347].forEach((id,i) => {
  META[id] = { available: true, default_elevation: 0, default_azimuth: 90,
    rings: [{ elevation: 0, frames: [{ azimuth: 90, urls: { "1024": `/f/${id}/1024.jpg`, "2048": `/f/${id}/2048.jpg` } }] }],
    canonical: { hero: "/sdileny.jpg" } };
});
global.fetch = (url) => {
  fetchu++;
  const m = url.match(/assembly=(\d+)/);
  return Promise.resolve({ ok: true, json: () => Promise.resolve(META[m ? m[1] : 346]) });
};

// vytahni skutecny kod ze souboru
const a = src.indexOf("function pdHeroZPrstence");
const b = src.indexOf("\nfunction pdInitVariantSwitcher");
eval(src.slice(a, b));

const vse = [346,342,344,341,343,345,347].map(id => ({ id, name: `K-x-${id} - provedeni`, has_turntable: true, is_master: id === 343, price_czk: 1000 }));
const p = { id: 3943, name: "Regál" };

// sestav posuvnik se STEJNYM callbackem jako v pdInitAssemblyVariants
let volani = { tazeni: 0, konec: 0 };
const frag = pdVariantSlider(vse, (id, opts) => {
  if (opts && opts.behemTazeni) volani.tazeni++; else volani.konec++;
  pdSwapTurntable(p, id, { behemTazeni: !!(opts && opts.behemTazeni) });
});

const poInit = { mountu, vyprazdneni, fetchu };

// --- simuluj TAZENI pres celou trat ---
mountu = 0; vyprazdneni = 0; fetchu = 0; vymenSrc = 0;
// REALISTICKE tazeni: mezi pohyby se necha dobehnout mikrotask fronta,
// jako kdyz prst putuje po displeji desitky ms. Bez toho vystreli vsech 85
// pohybu v jedne smycce, vsechno se zaradi a vyhraje jen posledni - coz
// neodpovida nicemu, co zakaznik udela.
const tik = () => new Promise(r => setImmediate(r));
(async () => {
  handlers["pointerdown"]({ clientX: 12, pointerId: 1, preventDefault() {} });
  await tik(); await tik();
  for (let x = 12; x <= 688; x += 8) { handlers["pointermove"]({ clientX: x, pointerId: 1 }); await tik(); await tik(); }
  handlers["pointerup"]({ pointerId: 1 });
  await tik(); await tik(); await tik();
  {
  console.log("=== TAZENI pres vsech 7 provedeni (85 kroku pointermove) ===");
  console.log(`   vyprazdneni obrazku (innerHTML=""):  ${vyprazdneni}   <- zdroj blikani`);
  console.log(`   plnych prestaveni widgetu (mount):   ${mountu}`);
  console.log(`   sitovych dotazu (fetch):             ${fetchu}`);
  console.log(`   vymen src uz vykresleneho obrazku:   ${vymenSrc}`);
  console.log(`   callback: behemTazeni=${volani.tazeni}x, konec=${volani.konec}x`);
  console.log(`   holder._img nalezen querySelectorem: ${holder.querySelector("img[data-tt-hero]") ? "ano" : "NE"}`);
  }
})();
