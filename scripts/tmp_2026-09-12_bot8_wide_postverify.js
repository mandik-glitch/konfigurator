// Nezavisle overeni PO zapisu - cte data PRIMO Z DB (ne z mezivysledku v pameti),
// pro kazdou ze 37 aktualizovanych sestav spousti WC.verifyAssembly (SAT + self-kolize)
// a navic presnou kontrolu sevu na kazde vyrezove noze (sloupek top vs svislice bottom).
const fs = require("fs");
const { execSync } = require("child_process");
const L = require("/opt/konfigurator/scripts/tmp_2026-09-12_bot8_wide_v2_lib.js");

const MODELS = [
  { kod: "K-007e", base: "Citroën_Berlingo_CI22_2021-", ids: [95,137,138,159,160] },
  { kod: "K-251", base: "Ford_Custom_FO31_2023-", ids: [111,153,154,175,176] },
  { kod: "K-008", base: "Citro_n_Berlingo_CI04_2008-2018", ids: [92,193,263] },
  { kod: "K-018", base: "Volkswagen_Caddy_VW21_2021-", ids: [124,196,266] },
  { kod: "K-088", base: "Peugeot_Expert_PE15_2016-", ids: [69,233,303] },
  { kod: "K-094", base: "Peugeot_Expert_PE14_2007-2015", ids: [68,237,307] },
  { kod: "K-124", base: "Citroën_Jumpy_CI15_2016-", ids: [183,221,291] },
  { kod: "K-163e", base: "Peugeot_Partner_PE24_2021-", ids: [102,260,330] },
  { kod: "K-242", base: "Ford_Connect_FO46_2024-", ids: [133,258,328] },
  { kod: "K-252e", base: "Ford_Custom_FO48_2023-", ids: [115,212,282] },
  { kod: "K-292", base: "Mercedes_Vito_MB18_2014-", ids: [78,227,297] },
];

function dbFetch(ids) {
  const py = `
import json, pymysql
env = {}
with open("api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT",3306)), user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SELECT id, prepazka_rezerva_mm, podbeh_rezerva_mm, data FROM product_assemblies WHERE id IN (${ids.join(",")})")
out = {}
for r in cur.fetchall():
    r["data"] = json.loads(r["data"])
    out[r["id"]] = r
conn.close()
print(json.dumps(out))
`;
  fs.writeFileSync("/tmp/_postverify_dump.py", py);
  return JSON.parse(execSync("api/venv/bin/python3 /tmp/_postverify_dump.py", { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 200 }).toString());
}

let totalChecked = 0, totalFail = 0;
for (const m of MODELS) {
  const rows = dbFetch(m.ids);
  for (const id of m.ids) {
    const row = rows[id];
    const parts = row.data.parts;
    const real = L.realParts(parts);
    const legs = L.analyzeLegs(real);
    const columns = L.analyzeColumns(real, legs.map(l => l.z));
    const seamProblems = L.seamAndShelfCheck(real, legs, columns);
    const v = L.verifyAssembly(real, m.base);
    const ok = row.prepazka_rezerva_mm === 10 && row.podbeh_rezerva_mm === 30 &&
      seamProblems.length === 0 && v.satCollisions === 0 && v.skipped === 0 && v.selfSusp === 0;
    totalChecked++;
    if (!ok) {
      totalFail++;
      console.log(`FAIL id=${id} (${m.kod}): prepazka=${row.prepazka_rezerva_mm} podbeh=${row.podbeh_rezerva_mm} seam=${JSON.stringify(seamProblems)} sat=${v.satCollisions} skipped=${v.skipped} self=${v.selfSusp}`);
    } else {
      console.log(`OK id=${id} (${m.kod}): sat=0 self=0 seam=clean checked=${v.checked}`);
    }
  }
}
console.log(`\nCELKEM: ${totalChecked} overeno, ${totalFail} SELHALO.`);
