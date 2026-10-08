// Slouci transformovany "realParts" vystup (newparts_<id>.json, jen dily BEZ
// car_body_*/kontrolni-pomucka) zpatky do PUVODNI, PLNE sekvence dilu - nektere
// stare sestavy (car_model_id IS NULL) jeste maji vlozene car_body_* dily v datech
// (WORKFLOW.md bod 25 - jeste neodstraneny, protoze by se ztratila napojenost na
// vozidlo bez predchoziho dopoctu car_model_id). Tenhle ukol se NEMA dotykat
// odstranovani car_body_ dilu (mimo rozsah) - zachovava je 1:1 beze zmeny na
// puvodni pozici v poli.
const fs = require("fs");
const { execSync } = require("child_process");

const IDS = [95,137,138,159,160, 111,153,154,175,176, 92,193,263, 124,196,266,
             69,233,303, 68,237,307, 183,221,291, 102,260,330, 133,258,328,
             115,212,282, 78,227,297];

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad";

function dbFetchData(id) {
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
cur.execute("SELECT data FROM product_assemblies WHERE id=${id}")
print(cur.fetchone()["data"])
`;
  const tmpf = `/tmp/_merge_dump_${id}.py`;
  fs.writeFileSync(tmpf, py);
  return JSON.parse(execSync(`api/venv/bin/python3 ${tmpf}`, { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 50 }).toString());
}

function isExcluded(p) {
  return String(p.part_id || "").startsWith("car_body_") || String(p.role || "").startsWith("kontrolni-pomucka");
}

let totalOk = 0;
for (const id of IDS) {
  const npf = `${SCRATCH}/newparts_${id}.json`;
  if (!fs.existsSync(npf)) { console.log(`id=${id}: SKIP (no newparts file)`); continue; }
  const transformedReal = JSON.parse(fs.readFileSync(npf, "utf8"));
  const data = dbFetchData(id);
  const orig = data.parts;

  let ti = 0;
  const merged = orig.map(p => {
    if (isExcluded(p)) return p;
    const t = transformedReal[ti++];
    if (!t) throw new Error(`id=${id}: nedostatek transformovanych dilu (ti=${ti})`);
    return t;
  });
  if (ti !== transformedReal.length) throw new Error(`id=${id}: pocet nesedi po slouceni (pouzito ${ti}, mel ${transformedReal.length})`);
  if (merged.length !== orig.length) throw new Error(`id=${id}: delka pole se zmenila (${orig.length} -> ${merged.length})`);

  fs.writeFileSync(npf, JSON.stringify(merged));
  const nExcluded = orig.length - transformedReal.length;
  console.log(`id=${id}: merged OK (${orig.length} celkem, ${transformedReal.length} transformovano, ${nExcluded} zachovano beze zmeny [car_body_/kontrolni-pomucka])`);
  totalOk++;
}
console.log(`\nHotovo: ${totalOk}/${IDS.length} slouceno.`);
