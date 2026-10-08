// Znovupostaveni vsech "uhelnik-noha*" na K-075 verze B (370,376,377,378,
// 379,380) od nuly pres shape_geometry_methods.id=7 (applyUhelnikyToLeg) -
// presna kopie postupu scripts/tmp_2026-09-13_bot8_rebuild_uhelniky_k122.js
// (K-122, tentyz den), jen jine ID sestav. Duvod: shape_geometry_methods.id=11
// v2 krok 8 - po prepoctu kolizni rezervy 10/30mm se uhelniky rigidne
// posunuly s nohou, ale nadale koliduji (kolize_pocet=2 u vsech, mereno
// automatickou kontrolou 2026-09-13 14:00).
const fs = require("fs");
const THREE = require("three");
global.THREE = THREE;
const lib = require("/opt/konfigurator/scripts/2026-09-01_uhelniky_leg_joints_lib.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const catalogMeta = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-09-01_uhelnik_catalog.json", "utf8"));

const LEG_ROLES = new Set(["predni-svislice","cap","zadni-svislice-dolni","spojnice-dolni","spojnice-horni",
  "spojnice-horni-uzavreni","zadni-svislice-nad-zarezem","sloupek-pred-podbehem","pricka-uzavreni-vyrezu"]);

function rebuildForAssembly(parts) {
  const legParts = parts.filter(p => LEG_ROLES.has(p.role));
  const zGroups = new Map();
  for (const p of legParts) {
    const z = Math.round(p.position[2]);
    if (!zGroups.has(z)) zGroups.set(z, []);
    zGroups.get(z).push(p);
  }
  const zs = [...zGroups.keys()].sort((a, b) => a - b);

  const newUhelniky = [];
  const report = [];
  zs.forEach((z, legIdx) => {
    const legPartsHere = zGroups.get(z);
    const entries = legPartsHere.map((p, idx) => {
      const glbPath = R.glbPath(p.part_id);
      return lib.makeProfileEntry(glbPath, {
        position: p.position, quaternion: p.quaternion, scale: p.scale,
        id: p.part_id, length_mm: 1000, cross_section_mm: [30, 30],
        role: p.role, idx,
      });
    });
    const { results, stats } = lib.applyUhelnikyToLeg(entries, catalogMeta, KAT);
    report.push({ z, legIdx, pairsMatched: stats.pairsMatched, placed: results.length });
    results.forEach(r => {
      newUhelniky.push({
        part_id: r.part_id, position: r.position, quaternion: r.quaternion, scale: r.scale,
        role: `uhelnik-noha${legIdx}`,
      });
    });
  });
  return { newUhelniky, report };
}

const IDS = process.argv.slice(2).map(Number);
const { execSync } = require("child_process");
const SCRATCH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad";
for (const aid of IDS) {
  const dump = execSync(`api/venv/bin/python3 -c "
import json
env={}
with open('api/.env') as f:
    for line in f:
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k,v=line.split('=',1); env[k.strip()]=v.strip()
import pymysql
conn=pymysql.connect(host=env['DB_HOST'],port=int(env.get('DB_PORT',3306)),user=env['DB_USER'],password=env['DB_PASSWORD'],database=env['DB_NAME'],cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute('SELECT data FROM product_assemblies WHERE id=${aid}')
    print(cur.fetchone()['data'])
conn.close()
"`, { maxBuffer: 1024 * 1024 * 20, cwd: "/opt/konfigurator" }).toString();
  const data = JSON.parse(dump);
  const oldCount = data.parts.filter(p => String(p.role||"").startsWith("uhelnik-")).length;
  const { newUhelniky, report } = rebuildForAssembly(data.parts);
  console.log(`\n=== id=${aid} ===`);
  console.log("stare uhelniky:", oldCount, "-> nove:", newUhelniky.length);
  console.log("report per noha:", JSON.stringify(report));
  data.parts = data.parts.filter(p => !String(p.role||"").startsWith("uhelnik-")).concat(newUhelniky);
  fs.writeFileSync(`${SCRATCH}/rebuilt_${aid}.json`, JSON.stringify(data));
}
