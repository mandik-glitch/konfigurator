// Uhelniky na spoje noh (shape_geometry_methods.id=7) pro sestavu regalu K-020 A.
// Vstup: JSON data sestavy (argv[2]), vystup: data s uhelniky (argv[3]) + report.
// Role noh ve stavbe k020_build.js maji priponu "-noha<N>"; uhelniky dostanou role "uhelnik-noha<N>".
const fs = require("fs");
const THREE = require("three");
global.THREE = THREE;
const lib = require("/opt/konfigurator/scripts/2026-09-01_uhelniky_leg_joints_lib.js");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const catalogMeta = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-09-01_uhelnik_catalog.json", "utf8"));
const LEG_ROLES = ["predni-svislice", "cap", "zadni-svislice-dolni", "spojnice-dolni", "spojnice-horni",
  "zadni-svislice-nad-zarezem", "sloupek-pred-podbehem", "pricka-uzavreni-vyrezu"];

const data = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const bezUhelniku = data.parts.filter(p => !String(p.role || "").startsWith("uhelnik-"));
const nohy = new Map();
for (const p of bezUhelniku) {
  const m = /^(.*)-noha(\d+)$/.exec(p.role || "");
  if (!m || !LEG_ROLES.includes(m[1]) || p.part_id !== "Object_7") continue;
  if (!nohy.has(+m[2])) nohy.set(+m[2], []);
  nohy.get(+m[2]).push({ ...p, zakladniRole: m[1] });
}
const engine = createEngine("Volkswagen_Caddy_VW32_2021-");
const nove = [], report = [];
[...nohy.keys()].sort((a, b) => a - b).forEach(n => {
  const dily = nohy.get(n);
  const entries = dily.map((p, idx) => lib.makeProfileEntry(KAT + "Object_7.glb", {
    position: p.position, quaternion: p.quaternion, scale: p.scale,
    id: p.part_id, length_mm: 1000, cross_section_mm: [30, 30], role: p.zakladniRole, idx,
  }));
  const { results, stats } = lib.applyUhelnikyToLeg(entries, catalogMeta, KAT);
  let kolizeSteny = 0;
  results.forEach(r => {
    const g = new THREE.Group(); g.add(r.object3d); g.updateMatrixWorld(true);
    if (engine.collidesWithWalls(g)) kolizeSteny++;
    nove.push({ part_id: r.part_id, position: r.position, quaternion: r.quaternion, scale: r.scale, role: `uhelnik-noha${n}` });
  });
  report.push({ noha: n, profilu: dily.length, paruProvereno: stats.pairsChecked, spoju: stats.pairsMatched, uhelniku: results.length, kolizeSeStenami: kolizeSteny,
    spoje: stats.perPair.map(x => `${x.a}+${x.b}:${x.count}`) });
});
data.parts = bezUhelniku.concat(nove);
fs.writeFileSync(process.argv[3], JSON.stringify(data));
console.log(JSON.stringify(report, null, 1));
console.log("uhelniku celkem", nove.length, "| dilu sestavy po", data.parts.length);
