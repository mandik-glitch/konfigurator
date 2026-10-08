// SDILENY resolver `part_id -> cesta ke GLB`. Pouzij ho misto toho, abys
// nazev souboru odvozoval z part_id nebo psal vlastni malou mapu.
//
// === PROC EXISTUJE ===
// `part_id` NENI nazev GLB souboru. Vetsina dilu se sice renderuje z
// `product_<id>.glb`, ale nektere ne (stav 2026-09-11: 4 produkty). Kdo si
// nazev odvodi, u tech dilu nenajde soubor, `parseGlbMesh` vrati null, dil
// se z mereni TISE vypadne a vysledek vypada cistsi, nez je.
//
// Tahle trida chyby napachala skodu TRIKRAT po sobe (viz AGENTS_LOG.md
// 2026-09-05 a 2026-09-11), pokazde u teze kolizni kontroly uhelniku:
//   1. mereno `product_3045.glb`, ktery neexistuje -> "0 kolizi" bylo
//      falesne, do produkce se zapsalo 33 realnych kolizi
//   2. po oprave mapovani se zase zamerne preskakovaly profily vlastni nohy
//      -> preskoceno 44 ze 44 skutecnych pruniku
//   3. mapa mela natvrdo JEDINY zaznam, takze MDF desky (`product_3939`)
//      se do kolizi nezapocitavaly vubec
// Zapsane pravidlo "mapuj pres shop_products.glb_file" existovalo uz po (1)
// a stejne se to stalo znovu. Proto tenhle modul: aby to slo udelat spravne
// jednim require, ne aby si to kazdy psal znovu.
//
// === KOLIK DILU JDE O ===
// Zmereno 2026-09-11 nad vsemi 269 sestavami (22 721 dilu, 252 ruznych
// part_id): naivni odvozeni `<part_id>.glb` NENAJDE soubor u 5 257 dilu,
// ktere ho mit maji - z toho 5 164 jsou SAME UHELNIKY (`product_3045`) a
// 93 MDF desky (`product_3939`). Kontrola uhelniku postavena na naivnim
// odvozeni je tedy slepa prave k tomu, co ma kontrolovat.
// Dalsich 243 part_id (6 064 dilu) jsou `car_body_*` - ty katalogovy GLB
// nemaji ZAMERNE (vlastni tvary, jina cesta nacteni; podle WORKFLOW.md
// bodu 25 v sestave vubec nemaji byt). Proto je `jeKaroserie()` odlisuje:
// "sem nepatri" NENI totez co "neslo zmerit".
//
// === POUZITI ===
//   const R = require("./2026-09-11_glb_resolver.js");
//   const cesta = R.glbPath(p.part_id);     // null = nenalezeno
//   if (R.jeKaroserie(p.part_id)) continue; // zamerne vyloucene
//
// Mapu generuje scripts/2026-09-11_dump_glb_mapping.py z shop_products.
// Kdyz chybi, tenhle modul SELZE pri nacteni - zamerne. Merit s neuplnou
// mapou je horsi nez nemerit vubec, protoze to vyrobi falesne cisty
// vysledek.
const fs = require("fs");
const path = require("path");

const KAT = "/opt/konfigurator/webapp/katalog/";
const MAPA_PATH = path.join(__dirname, "2026-09-11_glb_mapping.json");

if (!fs.existsSync(MAPA_PATH)) {
  throw new Error(
    `Chybi mapa GLB ${MAPA_PATH}. Vygeneruj ji:\n` +
    `  api/venv/bin/python3 scripts/2026-09-11_dump_glb_mapping.py\n` +
    "Bez ni by se cast dilu tise nemerila a kontrola by hlasila falesne cisto."
  );
}
const MAPA = JSON.parse(fs.readFileSync(MAPA_PATH, "utf8")).mapa;

// Karoserie: vlastni tvar, ne katalogovy dil. Nema GLB v webapp/katalog a
// ani ho mit nema - viz hlavicka.
function jeKaroserie(partId) {
  return String(partId || "").startsWith("car_body_");
}

// Vraci absolutni cestu ke GLB, nebo null kdyz soubor neexistuje.
// Volajici si sam rozhodne, jestli je null chyba (u katalogoveho dilu ANO)
// nebo ocekavany stav (u karoserie).
function glbPath(partId) {
  const zaklad = MAPA[partId] || partId;
  const f = KAT + zaklad + ".glb";
  return fs.existsSync(f) ? f : null;
}

// Kolik zaznamu ma mapa - pro vypis "kontrola opravdu bezela nad necim".
function velikostMapy() {
  return Object.keys(MAPA).length;
}

module.exports = { KAT, MAPA, glbPath, jeKaroserie, velikostMapy };
