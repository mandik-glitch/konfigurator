// Z vystupu sweepu udela VYPIS K POSOUZENI (markdown) - Robert 2026-09-11
// k nalezum mimo odsouhlasenou skupinu rekl: „Napred mi je ukazat."
// Nemaze nic, necte DB (krome metadat sestav, ktera dostane na vstupu).
//
// Pouziti:
//   node scripts/2026-09-11_report_kolizni_uhelniky.cjs <nalezy.json> <sestavy_meta.json> <out.md>
//
// `sestavy_meta.json` = {"<id>": {"name": ..., "kod_sestavy": ...}, ...}
//
// === JAK VZNIKA POSOUZENI VE SLOUPCI "co s tim" ===
// Neni to nazor, je to prevod dvou ZMERENYCH veci na vetu:
//  1. Zmizi to samo? Kdyz vsichni kolizni partneri toho kusu jsou dily
//     STARYCH HORNICH BLOKU a sestava je na seznamu k uklidu
//     (scripts/2026-09-11_smazat_stare_horni_bloky.py), kolize po uklidu
//     zanikne bez zasahu.
//  2. Slo by to posunout? Sweep zkousi posuny do 40mm a hlida, jestli
//     uhelniku zustanou aspon dva dosedy. Kdyz takova poloha existuje,
//     vada vypada na rozhozenou pozici; kdyz ne, uhelnik nema kam ustoupit.
const fs = require("fs");

const CILE_UKLIDU = [134, 135, 182, 189, 209, 219, 279, 289];
const jeDilBloku = (r) => {
  r = r || "";
  // Stejny predikat jako mazaci skript. `pricka-uzavreni-vyrezu` je soucast
  // NOHY, ne bloku - siroke startsWith("pricka") by ji sem spatne zaradilo.
  return r.startsWith("podelnik") || r.startsWith("vypln-")
    || r.startsWith("pricka-horni") || r.startsWith("pricka-police") || r.startsWith("pricka-spodni");
};

const popisRole = (r) => (r || "").replace(/^vypln-dno-(\d+)$/, "dno bloku $1")
  .replace(/^pricka-spodni-prepazka$/, "spodní příčka přepážky");

const nalezy = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const meta = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const out = process.argv[4];

for (const x of nalezy) {
  const partneri = [x.doCeho, ...x.dalsi.map(d => d.role)];
  x._zmiziSBlokem = partneri.every(jeDilBloku) && CILE_UKLIDU.includes(x.asm);
}

function posouzeni(x) {
  if (x._zmiziSBlokem) return "zmizí s úklidem bloků";
  if (x.posun) return `**posun ${x.posun.smer}${x.posun.o} mm po ${x.posun.osa} to řeší**`;
  return "**nemá kam ustoupit**";
}

// seskupit kusy se stejnym podpisem vady (tataz poloha, tyz partner, tyz odsun)
const skupiny = new Map();
for (const x of nalezy) {
  const k = [x.role, x.poz.join("|"), x.doCeho, x.odsun, x._zmiziSBlokem].join("::");
  if (!skupiny.has(k)) skupiny.set(k, []);
  skupiny.get(k).push(x);
}
const vsechny = [...skupiny.values()].sort((a, b) => (a[0]._zmiziSBlokem - b[0]._zmiziSBlokem)
  || (a[0].asm - b[0].asm));
const otevrene = vsechny.filter(v => !v[0]._zmiziSBlokem);
const zmizi = vsechny.filter(v => v[0]._zmiziSBlokem);
const pocet = (g) => g.reduce((s, v) => s + v.length, 0);

const jmeno = (id) => ((meta[String(id)] || {}).name || "").trim();
const L = [];
L.push("# Kolizní úhelníky — výpis k posouzení");
L.push("");
L.push(`Kritérium: **průnik hmoty** (pravidlo v3, Robert 2026-09-11 — pozice ani výška `
  + `kritérium nejsou). Verdikt dává skutečná GLB geometrie, ne \`Box3\`.`);
L.push("");
L.push(`**Celkem ${nalezy.length} úhelníků v ${new Set(nalezy.map(x => x.asm)).size} sestavách, `
  + `${vsechny.length} různých vad.** Nic není smazáno.`);
L.push("");
L.push(`- **${pocet(otevrene)} kusů** (${otevrene.length} vad) — čeká na rozhodnutí`);
L.push(`- **${pocet(zmizi)} kusů** (${zmizi.length} vad) — zmizí samo s úklidem starých horních bloků`);
L.push("");
L.push("Sloupec **o kolik** je nejmenší posun, po kterém se díly přestanou překrývat "
  + "(měřeno na skutečné síti). Sloupec **obálka** je, co by na témže místě hlásil `Box3` — "
  + "je vedle pro srovnání, protože se liší až čtyřnásobně.");
L.push("");
L.push("Poslední sloupec je převod měření na větu:");
L.push("");
L.push("- **nemá kam ustoupit** — žádný posun do 40 mm kolizi neodstraní, aniž by úhelník "
  + "přišel o dosed. Buď se smaže, nebo se musí hnout dílem, do kterého proniká.");
L.push("- **posun … to řeší** — existuje poloha, kde nekoliduje a dosedy si udrží. "
  + "Vypadá to na rozhozenou pozici, ne na zbytečný kus.");
L.push("- **zmizí s úklidem bloků** — koliduje výhradně s díly starého horního bloku, "
  + "který je na seznamu ke smazání. Samostatné rozhodnutí nepotřebuje.");

function tabulka(nadpis, skup) {
  if (!skup.length) return;
  L.push("");
  L.push(`## ${nadpis}`);
  L.push("");
  L.push("| ks | sestavy | úhelník na pozici `X\\|Y\\|Z` | kde sedí | proniká do | o kolik | obálka | co s tím |");
  L.push("|---|---|---|---|---|---|---|---|");
  for (const v of skup) {
    const x = v[0];
    const sest = v.map(y => `#${y.asm}`).join(" ");
    const dalsi = x.dalsi.length ? ` + ${x.dalsi.map(d => popisRole(d.role)).join(", ")}` : "";
    L.push(`| ${v.length}× | ${sest} | \`${x.role}\` \`${x.poz.join("|")}\` | ${x.kde} | ${x.doCehoPopis}${dalsi} `
      + `| **${x.odsun} mm** | ${x.prunikBox} mm | ${posouzeni(x)} |`);
  }
  L.push("");
  L.push("Názvy sestav:");
  L.push("");
  const ids = [...new Set(skup.flatMap(v => v.map(y => y.asm)))].sort((a, b) => a - b);
  for (const id of ids) L.push(`- **#${id}** — ${jmeno(id)}`);
}

tabulka("Čeká na rozhodnutí", otevrene);
tabulka("Zmizí s úklidem starých horních bloků (jen pro úplnost)", zmizi);

L.push("");
L.push("## Rozměry společné hmoty (doklad, že jde o tutéž vadu)");
L.push("");
L.push("První rozměr je vždy ~6,3 mm — to je **tloušťka plechu úhelníku**, ne hloubka zaboření. "
  + "Proto se hloubka neměří jako nejmenší rozměr překryvu.");
L.push("");
L.push("| sestavy | úhelník | pozice `X\\|Y\\|Z` | společná hmota `dx×dy×dz` mm |");
L.push("|---|---|---|---|");
for (const v of vsechny) {
  const x = v[0];
  L.push(`| ${v.map(y => "#" + y.asm).join(" ")} | \`${x.role}\` | \`${x.poz.join("|")}\` | ${x.oblast.join(" × ")} |`);
}
L.push("");

fs.writeFileSync(out, L.join("\n"));
console.log(`nalezu ${nalezy.length}, vad ${vsechny.length} -> ${out}`);
console.log(`  ceka na rozhodnuti: ${pocet(otevrene)} kusu / ${otevrene.length} vad`);
console.log(`  zmizi s uklidem bloku: ${pocet(zmizi)} kusu / ${zmizi.length} vad`);
