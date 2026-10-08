// Siroka aplikace shape_geometry_methods.id=11 na model K-088 (car_bodies base
// "Peugeot_Expert_PE15_2016-", car_models.id=232) - sestavy: 69,233,303.
// Pouziva sdilenou knihovnu tmp_2026-09-12_bot8_wide_v2_lib.js (kalibrovana self-checkem
// 184->348, 0 nesrovnalosti - viz AGENTS_LOG zapis k teto davce). Jen transform+overeni,
// zadny zapis do DB (ten dela az samostatny python krok po precteni JSON reportu odsud).
const fs = require("fs");
const { execSync } = require("child_process");
const L = require("/opt/konfigurator/scripts/tmp_2026-09-12_bot8_wide_v2_lib.js");

const KOD = "K-088";
const BASE = "Peugeot_Expert_PE15_2016-";
const IDS = [69, 233, 303];

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
cur.execute("SELECT id, name, kod_sestavy, category_id, car_model_id, technicky_ok, prepazka_rezerva_mm, podbeh_rezerva_mm, data FROM product_assemblies WHERE id IN (${ids.join(",")})")
out = {}
for r in cur.fetchall():
    r["data"] = json.loads(r["data"])
    out[r["id"]] = r
conn.close()
print(json.dumps(out))
`;
  const tmpf = "/tmp/_dump_wide_K_088.py";
  fs.writeFileSync(tmpf, py);
  const raw = execSync(`api/venv/bin/python3 ${tmpf}`, { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 200 }).toString();
  return JSON.parse(raw);
}

const rows = dbFetch(IDS);
const report = { kod: KOD, base: BASE, assemblies: {} };

// wallLegZ - zjisti jednou na prvni (nejvetsi) sestave, pouzij shodne pro vsechny varianty
// (stejna karoserie/rám v cele rodine) - overeno i per-assembly pro jistotu shody.
let sharedWallInfo = null;
for (const id of IDS) {
  const row = rows[id];
  if (!row) { report.assemblies[id] = { ok: false, reason: "DB radek nenalezen" }; continue; }
  const parts = L.realParts(row.data.parts);
  const wi = L.findWallLegZ(parts, BASE);
  if (!sharedWallInfo) sharedWallInfo = wi;
  else if (Math.abs((wi.wallLegZ||0) - (sharedWallInfo.wallLegZ||0)) > 2 || (wi.wallLegZ==null) !== (sharedWallInfo.wallLegZ==null)) {
    console.log(`VAROVANI: id=${id} ma jiny wallLegZ (${JSON.stringify(wi)}) nez sdileny (${JSON.stringify(sharedWallInfo)})`);
  }
  const res = L.runAssembly(row.data.parts, BASE, wi.wallLegZ);
  report.assemblies[id] = {
    name: row.name, technicky_ok: row.technicky_ok, category_id: row.category_id,
    prepazka_before: row.prepazka_rezerva_mm, podbeh_before: row.podbeh_rezerva_mm,
    ok: res.ok, reason: res.reason, log: res.log, wallInfo: wi,
    legsSummary: (res.legs||[]).map(l => ({ z: +l.z.toFixed(1), isVyrez: l.isVyrez, hasSloupek: l.hasSloupek, oldYnew: l.oldYnew==null?null:+l.oldYnew.toFixed(2) })),
    problems: res.problems, afterVerify: res.after ? { satCollisions: res.after.satCollisions, selfSusp: res.after.selfSusp, skipped: res.after.skipped, checked: res.after.checked } : null,
    baselineVerify: res.baseline ? { satCollisions: res.baseline.satCollisions, selfSusp: res.baseline.selfSusp } : null,
  };
  if (res.ok) {
    const outFile = `/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/newparts_${id}.json`;
    fs.writeFileSync(outFile, JSON.stringify(res.newParts));
    // ulozime i plnou puvodni data pro pripadny backup (o par radek niz z DB primo v pythonu)
  }
  console.log(`id=${id} ok=${res.ok}` + (res.ok ? "" : ` reason=${res.reason}`));
}

fs.writeFileSync(`/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/report_${KOD.replace(/[^A-Za-z0-9]/g,"_")}.json`, JSON.stringify(report, null, 2));
console.log("Report ulozen pro", KOD);
