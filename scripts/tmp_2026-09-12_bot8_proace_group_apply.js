// Aplikuje shape_geometry_methods.id=11 na VSECHNY sestavy JEDNE karoserie
// (skupiny) Proace rodiny, pres genericka lib tmp_2026-09-12_bot8_generic_
// kolizni_rezerva_lib.js. Zpracovava JEN jednu skupinu na jeden beh
// (RAM disciplina - spoustet po jednotlivych skupinach z shellu, ne vsechny
// najednou v jednom node procesu).
//
// Pouziti: node tmp_2026-09-12_bot8_proace_group_apply.js <KOD> [--write]
// Bez --write jen zmeri/transformuje/overi a vypise report (dry-run).
// S --write: pri VERDIKTU OK u VSECH sestav skupiny provede UPDATE (zadna
// z techto 43 sestav neni v chranenem seznamu, viz zadani).

const fs = require("fs");
const { execSync } = require("child_process");
const LIB = require("/opt/konfigurator/scripts/tmp_2026-09-12_bot8_generic_kolizni_rezerva_lib.js");

const GROUPS = {
  "K-160e": { ids: [101,139,140,161,162], base: "car_bodies/Peugeot_Partner_PE23_2021-" },
  "K-090e": { ids: [74,149,150,171], base: "car_bodies/Peugeot_Expert_PE25_2021-" },
  "K-296":  { ids: [136,157,158,179], base: "car_bodies/Opel_Vivaro_OP31_2020-" },
  "K-020":  { ids: [127,198,268], base: "car_bodies/Volkswagen_Caddy_VW32_2021-" },
  "K-091":  { ids: [66,235,305], base: "car_bodies/Peugeot_Expert_PE12_2007-2015" },
  "K-096":  { ids: [71,238,308], base: "car_bodies/Peugeot_Expert_PE17_2016-" },
  "K-120":  { ids: [181,217,287], base: "car_bodies/Citroën_Jumpy_CI13_2016-" },
  "K-158":  { ids: [97,229,299], base: "car_bodies/Peugeot_Partner_PE02_2008-2018" },
  "K-237":  { ids: [128,213,283], base: "car_bodies/Ford_Connect_FO12_2014-" },
  "K-247":  { ids: [110,201,271], base: "car_bodies/Ford_Custom_FO29_2012-2023" },
  "K-254e": { ids: [113,206,276], base: "car_bodies/Ford_Custom_FO39_2023-" },
  "K-287":  { ids: [120,253,323], base: "car_bodies/Volkswagen_Transporter_VW29_2024-" },
  "K-294":  { ids: [81,226,296], base: "car_bodies/Mercedes_Vito_MB25_2014-" },
};

const PROTECTED = new Set([79,82,83,116,117,134,135,151,152,173,182,189,209,219,224,250,251,279,289,294,320,321,332,333,334,335,336,337]);

const code = process.argv[2];
const doWrite = process.argv.includes("--write");
if (!GROUPS[code]) { console.error("Neznamy kod:", code, "znama:", Object.keys(GROUPS)); process.exit(2); }
const { ids, base } = GROUPS[code];
for (const id of ids) if (PROTECTED.has(id)) throw new Error(`id=${id} je v CHRANENEM seznamu - tenhle skript neumi INSERT vetev, STOP.`);

const T = 30, DELTA_Z = 8, DELTA_Y = 10;

const dumpPy = `
import json, pymysql
env = {}
with open("/opt/konfigurator/api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT",3306)), user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SELECT id, name, data, prepazka_rezerva_mm, podbeh_rezerva_mm, category_id FROM product_assemblies WHERE id IN (${ids.join(",")})")
out = {}
for r in cur.fetchall():
    out[r["id"]] = {"name": r["name"], "data": json.loads(r["data"]), "prepazka": r["prepazka_rezerva_mm"], "podbeh": r["podbeh_rezerva_mm"], "category_id": r["category_id"]}
conn.close()
print(json.dumps(out))
`;
fs.writeFileSync(`/tmp/_dump_group_${code}.py`, dumpPy);
const raw = execSync(`api/venv/bin/python3 /tmp/_dump_group_${code}.py`, { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 200 }).toString();
const DB = JSON.parse(raw);

console.log(`=== Skupina ${code} (${ids.length} sestav), karoserie ${base} ===`);
for (const id of ids) if (!DB[id]) throw new Error(`id=${id} nenalezeno v DB`);

// reprezentativni = nejvic dilu
const repId = ids.slice().sort((a, b) => DB[b].data.parts.length - DB[a].data.parts.length)[0];
console.log(`Reprezentativni sestava: id=${repId} (${DB[repId].data.parts.length} dilu) - "${DB[repId].name}"`);

const topo = LIB.detectTopology(DB[repId].data.parts, T);
console.log("Nohy:", topo.legs.map(l => `idx${l.idx} Z=${l.z.toFixed(1)} type=${l.type}${l.type === "vyrez" ? " old_y_new=" + l.oldYnew.toFixed(2) : ""}${l.isNearWall ? " [U PREPAZKY]" : ""}`).join(" | "));
console.log("Sloupce:", topo.columns.map(c => `${c.prefix}: noha${c.legAIdx}<->noha${c.legBIdx}`).join(" | "));

// konzistence topologie napric sourozenci (stejne Z noh, tolerance 3mm)
for (const id of ids) {
  const psz = DB[id].data.parts.filter(p => p.role === "predni-svislice").map(p => p.position[2]).sort((a, b) => a - b);
  const legZUniq = [];
  for (const z of psz) if (!legZUniq.length || Math.abs(z - legZUniq[legZUniq.length - 1]) > 5) legZUniq.push(z);
  if (legZUniq.length !== topo.legs.length) throw new Error(`id=${id}: ${legZUniq.length} noh, ocekavano ${topo.legs.length} (jina topologie nez reprezentant ${repId}) - STOP, over rucne.`);
  for (let i = 0; i < legZUniq.length; i++) {
    if (Math.abs(legZUniq[i] - topo.legs[i].z) > 3) throw new Error(`id=${id}: noha idx${i} Z=${legZUniq[i].toFixed(1)} nesedi s reprezentantem Z=${topo.legs[i].z.toFixed(1)} - STOP.`);
  }
}
console.log("Topologie konzistentni napric vsemi", ids.length, "sestavami skupiny (Z noh sedi na 3mm).");

const wallsShared = LIB.wallMeshes(base); // postaveno JEDNOU pro celou skupinu (BVH je drahy)

const results = [];
for (const id of ids) {
  const parts = DB[id].data.parts;
  const { parts: transformed, log } = LIB.transformAssembly(parts, topo, DELTA_Z, DELTA_Y, T);
  const verify = LIB.verifyAssembly(transformed, base, topo, DELTA_Y, T, wallsShared);
  console.log(`  id=${id}: dilu=${parts.length} transformLog=${JSON.stringify(log)} verify=${verify.verdict} (SAT=${verify.satCollisions} seamFail=${verify.seamFail} self=${verify.selfCollisions})`);
  if (verify.verdict !== "OK") {
    console.log(`    satHits=${JSON.stringify(verify.satHits).slice(0,500)}`);
    console.log(`    seamReport=${JSON.stringify(verify.seamReport)}`);
    console.log(`    selfHits=${JSON.stringify(verify.selfHits).slice(0,500)}`);
  }
  results.push({ id, transformed, verify, log, oldPrepazka: DB[id].prepazka, oldPodbeh: DB[id].podbeh, name: DB[id].name, data: DB[id].data });
}

const allOk = results.every(r => r.verify.verdict === "OK");
console.log(`\nCelkovy vysledek skupiny ${code}: ${allOk ? "VSECHNY OK" : "NEKTERE SELHALY"}`);

if (allOk && doWrite) {
  const writes = results.map(r => {
    const newData = { ...r.data, parts: r.transformed };
    return { id: r.id, data: newData };
  });
  fs.writeFileSync(`/tmp/_write_group_${code}.json`, JSON.stringify(writes));
  const writePy = `
import json, pymysql
env = {}
with open("/opt/konfigurator/api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT",3306)), user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
writes = json.load(open("/tmp/_write_group_${code}.json"))
for w in writes:
    cur.execute("UPDATE product_assemblies SET data=%s, prepazka_rezerva_mm=10, podbeh_rezerva_mm=30 WHERE id=%s", [json.dumps(w["data"], ensure_ascii=False), w["id"]])
conn.commit()
print("Zapsano UPDATE pro", [w["id"] for w in writes])
conn.close()
`;
  fs.writeFileSync(`/tmp/_write_group_${code}.py`, writePy);
  const out = execSync(`api/venv/bin/python3 /tmp/_write_group_${code}.py`, { cwd: "/opt/konfigurator" }).toString();
  console.log(out);
} else if (!doWrite) {
  console.log("(dry-run, --write nebyl predan - nic se nezapsalo)");
} else {
  console.log("NEZAPISUJI - ne vsechny sestavy skupiny presly overenim.");
}
