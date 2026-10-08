const fs = require("fs");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { verifyAssembly } = require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");
const { execSync } = require("child_process");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const SHIFT = { 128: -74, 213: -74, 283: -74, 129: -52, 214: -52, 284: -52 };
const WALL_BASE = { 128: "Ford_Connect_FO12_2014-", 213: "Ford_Connect_FO12_2014-", 283: "Ford_Connect_FO12_2014-",
                     129: "Ford_Connect_FO13_2014-", 214: "Ford_Connect_FO13_2014-", 284: "Ford_Connect_FO13_2014-" };
const IDS = [128, 213, 283, 129, 214, 284];

function fetchAll(ids) {
  const py = `
import json, sys
sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn
conn = get_conn()
out = {}
with conn.cursor() as cur:
    for aid in [${ids.join(",")}]:
        cur.execute("SELECT name, data FROM product_assemblies WHERE id=%s", (aid,))
        row = cur.fetchone()
        out[aid] = {"name": row["name"], "data": json.loads(row["data"])}
conn.close()
print(json.dumps(out))
`;
  fs.writeFileSync(`${SCRATCH}/_fetch_fc4.py`, py);
  return JSON.parse(execSync(`/opt/konfigurator/api/venv/bin/python3 ${SCRATCH}/_fetch_fc4.py`, { maxBuffer: 1024 * 1024 * 80 }).toString());
}
const D = fetchAll(IDS);

const results = {};
for (const id of IDS) {
  const orig = D[id].data.parts;
  const dx = SHIFT[id];
  const after = orig.map(p => R.jeKaroserie(p.part_id) ? p : { ...p, position: [p.position[0] + dx, p.position[1], p.position[2]] });
  const report = verifyAssembly({ partsNew: after, partsOrig: orig, carBodyBase: WALL_BASE[id], notchChecks: [], label: `id=${id}` });
  console.log(`\nid=${id} ${D[id].name.slice(0,50)} dx=${dx}mm`);
  console.log(`  wall-kolize: ${report.collisions} (${report.collidingList.map(c=>c.role).join(",")})`);
  console.log(`  self-kolize baseline=${report.baselineSelfSusp} po=${report.afterSelfSusp} nove=${report.newProblems.length}`);
  console.log(`  OK: ${report.OK}`);
  results[id] = { name: D[id].name, parts: after, ok: report.OK, expectCount: orig.length, dx };
}
fs.writeFileSync(`${SCRATCH}/fordconnect_APPLY_final.json`, JSON.stringify(results));
console.log("\nCELKEM OK:", Object.values(results).filter(r=>r.ok).length, "/", IDS.length);
