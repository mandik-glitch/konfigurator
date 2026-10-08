// Nezavisle overeni "zanoreni" - tentokrat SEBE-kolize dilu UVNITR
// kazde sestavy (ne vuci karoserii - to uz vyslo 0, viz sesterky skript).
// Pouziva dnesni scripts/2026-09-11_mesh_kolize_lib.js (mesh-presny test,
// SAT + volumetricky, nema slepa mista Box3/hranoveho raycastu).
const THREE = require("three");
const fs = require("fs");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const lib = require("/opt/konfigurator/scripts/2026-09-11_mesh_kolize_lib.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const data = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));

// Omezeno na NOHU/RAM (leg-builder), ne na generickou sloupec/patro
// box-skladbu (ta je sdilena napric VSEMI rodinami a dukladne regresne
// testovana jinde - kdyby tam byl bug, projevi se u vic nez 2 rodin).
// "dve sablony rodin" z zadani ukazuje presne na tenhle sdileny, PER-
// KAROSERII kod (proace_leg_builder.js a analogicky pro e-Expert),
// stejne nazvy roli jako u drivejsiho TO14/15/16 vyrez/pricka bugu.
// "zaslepka-*" (product_3071, zatky/plug do dutych konců profilů) VYNECHÁNY
// zámerně - zjistil jsem profilovanim, ze tenhle jeden GLB ma 2950
// trojuhelniku (proti 50 u profilu/188 u uhelniku), takze SAT fallback
// (protinajiSeSteny, O(tri_A*tri_B)) na par takovych dilu je radove
// pomalejsi a byl skutecnou pricinou toho, proc test na 1 sestavu trval
// minuty. Zatky navic sedi PEVNE nasazene v dutem konci sveho
// hostitelskeho profilu (predni-svislice/cap/zadni-svislice) - to je
// UCEL spoje (tesne vlozeny plast), ne pozice, kterou by mel leg-builder
// per-karoserii pocitat, takze tam bug rodiny stejne nehledam.
const LEG_ROLES = new Set([
  "predni-svislice", "spojnice-horni", "spojnice-dolni", "spojnice-dolni-kratka",
  "cap", "sloupek-pred-podbehem", "zadni-svislice-nad-zarezem",
  "zadni-svislice-dolni", "pricka-uzavreni-vyrezu",
  "uhelnik-noha0", "uhelnik-noha1", "uhelnik-noha2",
]);

const results = [];
const chybyPrimitiv = {};
let hotovo = 0;
for (const a of data) {
  const dily = [];
  for (const p of a.parts) {
    if (!LEG_ROLES.has(p.role)) continue;
    try {
      const D = lib.dilVeSvete(KAT + p.glb, p, parseGlbMesh);
      dily.push({ p, D });
    } catch (e) {
      chybyPrimitiv[p.glb] = (chybyPrimitiv[p.glb] || 0) + 1;
    }
  }
  // Faze 1: HRUBY broad-phase prah zvednuty z lib.TOL_MM (0,05mm) na 1,5mm.
  // Duvod zjisten empiricky (prvnich par sestav trvalo minuty): presne
  // dosedajici (flush) spoje maji box-prekryv v radu desetin mm kvuli
  // zaokrouhlenim v datech - to preleze 0,05mm test skoro vzdy a spustí
  // nejdrazsi cast kolize() (protinajiSeSteny, O(trojuhelniku^2) SAT),
  // ktera pak pro KAZDY takovy nekolidujici flush spoj dobehne naprazdno.
  // 1,5mm je porad hluboko pod nejmensi realnou kolizi, jakou tahle
  // knihovna dokumentuje (6mm plech uhelniku, viz hlavicka souboru) -
  // neztraci se tim citlivost na skutecnou kolizi, jen se prestane platit
  // za analyzu spoju, ktere jsou navrzene se dotykat.
  const BROAD_TOL = 1.5;
  const kandidati = [];
  for (let i = 0; i < dily.length; i++) {
    for (let j = i + 1; j < dily.length; j++) {
      const ov = lib.prekryvBoxu(dily[i].D.box, dily[j].D.box);
      if (Math.min(ov[0], ov[1], ov[2]) <= BROAD_TOL) continue; // broad phase
      const r = lib.kolize(dily[i].D, dily[j].D, lib.TOL_MM, true);
      if (r.koliduje) kandidati.push([i, j]);
    }
  }
  // Faze 2: presne domereni JEN nalezenych dvojic.
  const nalezy = [];
  for (const [i, j] of kandidati) {
    const r = lib.kolize(dily[i].D, dily[j].D, lib.TOL_MM, false);
    if (r.koliduje) {
      nalezy.push({
        a: { role: dily[i].p.role, part_id: dily[i].p.part_id },
        b: { role: dily[j].p.role, part_id: dily[j].p.part_id },
        odsun: r.odsun, oblast: r.oblast, typ: r.typ,
      });
    }
  }
  if (nalezy.length) {
    results.push({ id: a.id, name: a.name, pocet_dilu: a.parts.length, nalezy });
  }
  hotovo++;
  process.stderr.write(`\r${hotovo}/${data.length} sestav (${dily.length} leg-dilu v posledni)`);
}
process.stderr.write("\n");

console.log(`Zkontrolovano ${data.length} sestav (sebe-kolize dilu uvnitr sestavy).`);
console.log(`${results.length} sestav ma alespon jeden kolidujici par dilu.`);
for (const r of results) {
  console.log(`\n#${r.id} ${r.name} (${r.pocet_dilu} dilu):`);
  for (const n of r.nalezy) {
    console.log(`  ${n.a.role} (${n.a.part_id})  <->  ${n.b.role} (${n.b.part_id})`
      + `   odsun=${n.odsun}mm  oblast=[${n.oblast.map(x => x.toFixed(1))}]mm  typ=${n.typ}`);
  }
}
if (Object.keys(chybyPrimitiv).length) {
  console.log("\nGLB, ktere neslo zmerit touhle knihovnou (vic nez 1 primitiv/mesh):");
  for (const [glb, n] of Object.entries(chybyPrimitiv)) console.log(`  ${glb}  (${n}x vyskyt)`);
}
fs.writeFileSync("/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/sebekolize_vysledky.json",
  JSON.stringify(results, null, 1));
