// Cilena krizova kontrola: VYREZ-souvisejici noha (sloupek-pred-podbehem,
// pricka-uzavreni-vyrezu, zadni-svislice-nad-zarezem, zadni-svislice-dolni)
// vs box/kolejnicka/patro dily (eurobox-*, nosnik-*, spojnice-sloupecN-*).
// Presne tenhle typ (noha vs sloupec0) uz mel v teto rodine precedens
// (TO23 sloupec0, AGENTS_LOG 2026-09-01: 7/18 dilu kolidovalo) - box
// layout se LISI mezi A/B/C/D/E variantami, takze se kontroluji VSECH
// 60 sestav, ne jen 19 unikatnich karoserii (na rozdil od leg-self-testu).
const fs = require("fs");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const lib = require("/opt/konfigurator/scripts/2026-09-11_mesh_kolize_lib.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const data = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));

const VYREZ_ROLES = new Set([
  "sloupek-pred-podbehem", "pricka-uzavreni-vyrezu",
  "zadni-svislice-nad-zarezem", "zadni-svislice-dolni",
  "predni-svislice", "spojnice-horni", "spojnice-dolni", "spojnice-dolni-kratka",
  "cap", "uhelnik-noha0", "uhelnik-noha1", "uhelnik-noha2",
]);
function jeBoxDil(role) {
  return role.startsWith("eurobox-") || role.startsWith("nosnik-") || role.startsWith("spojnice-sloupec");
}

const BROAD_TOL = 1.5;
const results = [];
let hotovo = 0;
for (const a of data) {
  const leve = [], prave = [];
  for (const p of a.parts) {
    if (VYREZ_ROLES.has(p.role)) {
      leve.push({ p, D: lib.dilVeSvete(KAT + p.glb, p, parseGlbMesh) });
    } else if (jeBoxDil(p.role)) {
      prave.push({ p, D: lib.dilVeSvete(KAT + p.glb, p, parseGlbMesh) });
    }
  }
  const nalezy = [];
  for (const L of leve) {
    for (const R of prave) {
      const ov = lib.prekryvBoxu(L.D.box, R.D.box);
      if (Math.min(ov[0], ov[1], ov[2]) <= BROAD_TOL) continue;
      const rr = lib.kolize(L.D, R.D, lib.TOL_MM, true);
      if (!rr.koliduje) continue;
      const presne = lib.kolize(L.D, R.D, lib.TOL_MM, false);
      if (presne.koliduje) {
        nalezy.push({ noha: { role: L.p.role, part_id: L.p.part_id, position: L.p.position },
                      box: { role: R.p.role, part_id: R.p.part_id, position: R.p.position },
                      odsun: presne.odsun, oblast: presne.oblast, typ: presne.typ });
      }
    }
  }
  if (nalezy.length) results.push({ id: a.id, name: a.name, nalezy });
  hotovo++;
  process.stderr.write(`\r${hotovo}/${data.length} (leve=${leve.length} prave=${prave.length})`);
}
process.stderr.write("\n");
console.log(`Zkontrolovano ${data.length} sestav, ${results.length} ma kolizi vyrez-noha vs box/kolejnicka.`);
for (const r of results) {
  console.log(`\n#${r.id} ${r.name}:`);
  for (const n of r.nalezy) {
    console.log(`  ${n.noha.role} (${n.noha.part_id})  <->  ${n.box.role} (${n.box.part_id})`
      + `   odsun=${n.odsun}mm oblast=[${n.oblast.map(x=>x.toFixed(1))}]mm typ=${n.typ}`);
  }
}
fs.writeFileSync("/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/kriz_kolize_vysledky.json",
  JSON.stringify(results, null, 1));
