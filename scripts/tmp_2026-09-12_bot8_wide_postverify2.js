// OPRAVENE nezavisle overeni PO zapisu (predchozi postverify.js melo 2 chyby -
// viz AGENTS_LOG zapis: 1) porovnavalo absolutni selfSusp misto delty proti baseline,
// 2) znovu aplikovalo DELTA_Y na uz transformovana data pri seam-check). Tahle verze
// kontroluje PRIMO aktualni (jiz zapsany) stav bez re-aplikace delty, a self-kolize
// porovnava proti zaloze (backups/2026-09-12_kolizni_rezerva_wide_bot8/<id>_before.json).
const fs = require("fs");
const path = require("path");
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
const BACKUP_DIR = "/opt/konfigurator/backups/2026-09-12_kolizni_rezerva_wide_bot8";

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
  fs.writeFileSync("/tmp/_postverify2_dump.py", py);
  return JSON.parse(execSync("api/venv/bin/python3 /tmp/_postverify2_dump.py", { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 200 }).toString());
}

// Primo kontroluje AKTUALNI stav (uz transformovana data) bez re-aplikace DELTA_Y.
function checkCurrentState(parts) {
  const problems = [];
  const legZs = [...new Set(parts.filter(p => p.role === "predni-svislice").map(p => p.position[2]))].sort((a,b)=>a-b);
  for (const z of legZs) {
    const sloupek = parts.find(p => p.role === "sloupek-pred-podbehem" && Math.abs(p.position[2]-z)<2);
    const svisl = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && Math.abs(p.position[2]-z)<2);
    if (sloupek && svisl) {
      const topSloupek = sloupek.position[1] + sloupek.scale[1]*500;
      const botSvisl = svisl.position[1] - svisl.scale[1]*500;
      const gap = botSvisl - topSloupek;
      if (Math.abs(gap) > 0.02) problems.push(`leg z=${z.toFixed(1)}: seam gap=${gap.toFixed(4)}mm`);
    }
  }
  // sloupcove kontroly: pro kazdy sloupec (nosnik-<col>-<level>) najdi nejnizsi patro a over
  // proti "svym" hranicnim nohám - pokud je hranicni noha vyrezova, jeji AKTUALNI (uz hotovy) seam
  // Y (sloupek top / nebo jen svisl bottom kdyz sloupek chybi) MUSI byt <= floorEdge nejnizsiho patra.
  const colZ = {};
  for (const p of parts) {
    const m = /^nosnik-([\w]+)-([\w]+)$/.exec(p.role || "");
    if (!m) continue;
    (colZ[m[1]] = colZ[m[1]] || []).push(p.position[2]);
  }
  for (const col in colZ) {
    const zMin = Math.min(...colZ[col]), zMax = Math.max(...colZ[col]);
    const zLow = Math.max(...legZs.filter(lz => lz <= zMin + 5));
    const zHigh = Math.min(...legZs.filter(lz => lz >= zMax - 5));
    const limits = [];
    for (const legZ of [zLow, zHigh]) {
      const sloupek = parts.find(p => p.role === "sloupek-pred-podbehem" && Math.abs(p.position[2]-legZ)<2);
      const svisl = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && Math.abs(p.position[2]-legZ)<2);
      if (svisl) {
        const seamY = sloupek ? (sloupek.position[1]+sloupek.scale[1]*500) : (svisl.position[1]-svisl.scale[1]*500);
        limits.push(seamY);
      }
    }
    if (!limits.length) continue;
    const limitY = Math.max(...limits);
    const levels = L.columnLevels(parts, col);
    if (!levels.length) continue;
    const rx0 = new RegExp(`^nosnik-${col}-${levels[0]}$`);
    const level0Parts = parts.filter(p => rx0.test(p.role||""));
    const floorEdge = Math.min(...level0Parts.map(p=>p.position[1])) - 15;
    const gap = floorEdge - limitY;
    if (gap < -0.02) problems.push(`col ${col}: nejnizsi patro (${floorEdge.toFixed(2)}) je ${(-gap).toFixed(3)}mm POD limitem seamu (${limitY.toFixed(2)})`);
  }
  return problems;
}

let totalChecked = 0, totalFail = 0;
for (const m of MODELS) {
  const rows = dbFetch(m.ids);
  for (const id of m.ids) {
    const row = rows[id];
    const real = L.realParts(row.data.parts);
    const problems = checkCurrentState(real);
    const after = L.verifyAssembly(real, m.base);

    const beforePath = `${BACKUP_DIR}/${id}_before.json`;
    const beforeData = JSON.parse(fs.readFileSync(beforePath, "utf8"));
    const beforeReal = L.realParts(beforeData.parts);
    const before = L.verifyAssembly(beforeReal, m.base);
    const newSelf = Math.max(0, after.selfSusp - before.selfSusp);

    const ok = row.prepazka_rezerva_mm === 10 && row.podbeh_rezerva_mm === 30 &&
      problems.length === 0 && after.satCollisions === 0 && after.skipped === 0 && newSelf === 0;
    totalChecked++;
    if (!ok) {
      totalFail++;
      console.log(`FAIL id=${id} (${m.kod}): problems=${JSON.stringify(problems)} sat=${after.satCollisions} skipped=${after.skipped} selfBefore=${before.selfSusp} selfAfter=${after.selfSusp} newSelf=${newSelf}`);
    } else {
      console.log(`OK id=${id} (${m.kod}): sat=0 seam-clean newSelf=0 (baseline self=${before.selfSusp}, after=${after.selfSusp}) checked=${after.checked}`);
    }
  }
}
console.log(`\nCELKEM: ${totalChecked} overeno, ${totalFail} SELHALO.`);
