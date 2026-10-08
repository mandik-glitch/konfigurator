const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { execSync } = require("child_process");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const IDS = [389,393,397,401,405,409,413,417,421,425,429,433,437,441,445,449,453,457,461,465,469];

function fetchAll(ids) {
  const py = `
import sys, json
sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn
conn = get_conn()
out = {}
with conn.cursor() as cur:
    for aid in ${JSON.stringify(ids)}:
        cur.execute("SELECT name, data FROM product_assemblies WHERE id=%s", (aid,))
        row = cur.fetchone()
        out[aid] = {"name": row["name"], "data": json.loads(row["data"])}
conn.close()
print(json.dumps(out))
`;
  fs.writeFileSync(`${SCRATCH}/_fetch_celo04_all.py`, py);
  return JSON.parse(execSync(`/opt/konfigurator/api/venv/bin/python3 ${SCRATCH}/_fetch_celo04_all.py`, { maxBuffer: 1024 * 1024 * 200 }).toString());
}

function box(p) {
  const glb = R.glbPath(p.part_id);
  if (!glb) return null;
  const m = parseGlbMesh(glb);
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}

const all = fetchAll(IDS);
let totalSuspicious = 0;
for (const aid of IDS) {
  const info = all[aid];
  const parts = info.data.parts;
  const targets = parts.filter(p => p.role === "vypln-celo-0-a" || p.role === "vypln-celo-0-b");
  const hits = [];
  for (const t of targets) {
    const tb = box(t);
    if (!tb) continue;
    for (const p of parts) {
      if (p === t) continue;
      if (R.jeKaroserie(p.part_id)) continue;
      const b = box(p);
      if (!b) continue;
      const ox = Math.min(tb.max.x, b.max.x) - Math.max(tb.min.x, b.min.x);
      const oy = Math.min(tb.max.y, b.max.y) - Math.max(tb.min.y, b.min.y);
      const oz = Math.min(tb.max.z, b.max.z) - Math.max(tb.min.z, b.min.z);
      if (ox > 0.5 && oy > 0.5 && oz > 0.5) hits.push({ t: t.role, s: p.role, overlap: [ox, oy, oz].map(v => +v.toFixed(1)) });
    }
  }
  // ocekavany vzor: jen zasun do drazky podelniku/pricky-police (~8x7mm
  // pruniku, X/Y male, Z = cela delka zkraceneho panelu). Cokoli s VETSIM
  // X/Y prunikem nez ~10mm je podezrele - skutecna kolize, ne zasun.
  const suspicious = hits.filter(h => h.overlap[0] > 10 || h.overlap[1] > 10);
  console.log(`id=${aid} ${info.name.slice(0, 55)} zasunu=${hits.length - suspicious.length} podezrelych=${suspicious.length}`);
  if (suspicious.length) { console.log("  ", JSON.stringify(suspicious)); totalSuspicious += suspicious.length; }
}
console.log("CELKEM PODEZRELYCH KOLIZI:", totalSuspicious);
