const fs = require("fs");
const src = fs.readFileSync("/opt/konfigurator/webapp/product.html", "utf8");

// vytahni SKUTECNE funkce ze souboru (ne kopii)
const a = src.indexOf("function pdAssemblyLabel");
const b = src.indexOf("\nfunction pdInitVariantSwitcher");
let kod = src.slice(a, b);
// pdVariantSlider vola pdAssemblyLabel + pdOcistiVerejnyPopisek; ty jsou pred nim
const c = src.indexOf("function pdOcistiVerejnyPopisek");
kod = src.slice(c, b);

// --- minimalni DOM stub ---
const handlers = {};
function mkEl() {
  return {
    style: {}, dataset: {}, children: [], className: "", textContent: "", title: "", tabIndex: 0,
    classList: { add() {}, remove() {}, contains() { return false; } },
    setAttribute(k, v) { this[k] = v; },
    appendChild(x) { this.children.push(x); return x; },
    append(...xs) { this.children.push(...xs); },
    addEventListener(ev, fn) { handlers[ev] = fn; },
    focus() {}, setPointerCapture() {}, releasePointerCapture() {},
    getBoundingClientRect() { return { top: 0, height: 300 }; },
  };
}
global.document = { createElement: mkEl, createDocumentFragment: mkEl, getElementById: () => null };
global.pdActiveAssemblyId = null;

eval(kod);

// --- data presne jako z API karty 3943 ---
const vse = [
  { id: 346, name: "K-075-EB-30-C-0063-0-0 - boxy43-220x3-170x3-120x2 [10/30mm od kolize]", has_turntable: false, is_master: false, price_czk: 11822 },
  { id: 342, name: "K-075-EB-30-C-0063-1-0 - jedno pásmo, jen rám [10/30mm od kolize]", has_turntable: false, is_master: false, price_czk: 13234 },
  { id: 344, name: "K-075-EB-30-C-0063-2-0 - jedno pásmo, rám + dna [ZÁKLAD]", has_turntable: false, is_master: false, price_czk: 13643 },
  { id: 341, name: "K-075-EB-30-C-0063-3-0 - dvě pásma, jen rám, bez police [10/30mm od kolize]", has_turntable: false, is_master: false, price_czk: 14521 },
  { id: 343, name: "K-075-EB-30-C-0063-4-0 - dvě pásma, police jen příčky [10/30mm od kolize]", has_turntable: true, is_master: true, price_czk: null },
  { id: 345, name: "K-075-EB-30-C-0063-5-0 - dvě pásma, plné výplně, bez police [10/30mm od kolize]", has_turntable: false, is_master: false, price_czk: 15499 },
  { id: 347, name: "K-075-EB-30-C-0063-6-0 - dvě pásma, plné výplně, s policí [10/30mm od kolize]", has_turntable: false, is_master: false, price_czk: 17250 },
];

const zmeny = [];
pdVariantSlider(vse, (id, opts) => zmeny.push({ id, user: !!(opts && opts.userInitiated) }));

console.log("vychozi poloha po sestaveni:", JSON.stringify(zmeny[0]));

// projed posuvnik klavesnici odspoda nahoru
const key = handlers["keydown"];
const stisk = k => key({ key: k, preventDefault() {} });
stisk("Home");
for (let i = 0; i < 8; i++) stisk("ArrowUp");

const navstivene = [...new Set(zmeny.filter(z => z.user).map(z => z.id))];
console.log("\nprovedeni dosazitelna klavesnici:", navstivene.length, "/", vse.length);
console.log("  ->", navstivene.join(", "));
const chybi = vse.map(v => v.id).filter(id => !navstivene.includes(id));
console.log(chybi.length ? "  CHYBI: " + chybi.join(", ") : "  vsechna dosazitelna");
console.log("\nzmen ceny (userInitiated=true):", zmeny.filter(z => z.user).length);
console.log("vychozi NEmeni cenu:", zmeny[0].user === false ? "ANO (spravne)" : "NE - PROBLEM");
