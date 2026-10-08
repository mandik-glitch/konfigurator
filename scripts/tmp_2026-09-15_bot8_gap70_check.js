// Robert 2026-09-15: "pokud vychazi u sestavy a varianty 04 ze mezera
// mezi prickami/profily horniho bloku je mensi nez 70mm, tato varianta
// se nebude renderovat ani zobrazovat na eshopu". Pocita PRESNE stejnou
// "mezera mezi profily" logiku jako novy kotovaci kod ve scene.html
// (XZ-prekryv + nejblizsi Y-sousedi mezi "lezicimi" profily), aplikovano
// primo na ulozena data (ne live scenu).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");

function realBox(p) {
  const glb = R.glbPath(p.part_id); if (!glb) return null;
  const m = parseGlbMesh(glb);
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}

function najdiMezery(parts) {
  const horiz = [];
  for (const p of parts) {
    if (R.jeKaroserie(p.part_id)) continue;
    const role = p.role || "";
    if (!/^(podelnik|pricka)/.test(role)) continue; // jen ramove profily horniho bloku
    const b = realBox(p);
    if (!b) continue;
    if (b.max.y - b.min.y > 60) continue; // jen "lezici" (pricka/podelnik), ne nohy
    horiz.push({ role, box: b });
  }
  const mezery = [];
  for (let i = 0; i < horiz.length; i++) {
    for (let j = i + 1; j < horiz.length; j++) {
      const A = horiz[i], B = horiz[j];
      const ox = Math.min(A.box.max.x, B.box.max.x) - Math.max(A.box.min.x, B.box.min.x);
      const oz = Math.min(A.box.max.z, B.box.max.z) - Math.max(A.box.min.z, B.box.min.z);
      if (ox < 10 || oz < 10) continue;
      const lower = A.box.max.y <= B.box.min.y ? A : B;
      const upper = lower === A ? B : A;
      const gap = upper.box.min.y - lower.box.max.y;
      if (gap <= 2 || gap > 400) continue;
      const blocked = horiz.some(C => {
        if (C === A || C === B) return false;
        const cox = Math.min(C.box.max.x, A.box.max.x, B.box.max.x) - Math.max(C.box.min.x, A.box.min.x, B.box.min.x);
        const coz = Math.min(C.box.max.z, A.box.max.z, B.box.max.z) - Math.max(C.box.min.z, A.box.min.z, B.box.min.z);
        if (cox < 10 || coz < 10) return false;
        return C.box.min.y > lower.box.max.y - 2 && C.box.max.y < upper.box.min.y + 2;
      });
      if (blocked) continue;
      mezery.push({ a: lower.role, b: upper.role, gap: +gap.toFixed(1) });
    }
  }
  return mezery;
}

const { execSync } = require("child_process");
const IDS = [389,393,397,401,405,409,413,417,421,425,429,433,437,441,445,449,453,457,461,465,469];
const py = `
import sys, json
sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn
conn = get_conn()
out = {}
with conn.cursor() as cur:
    for aid in [${IDS.join(",")}]:
        cur.execute("SELECT name, data FROM product_assemblies WHERE id=%s", (aid,))
        row = cur.fetchone()
        out[aid] = {"name": row["name"], "data": json.loads(row["data"])}
conn.close()
print(json.dumps(out))
`;
const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
fs.writeFileSync(`${SCRATCH}/_fetch_gap70.py`, py);
const D = JSON.parse(execSync(`/opt/konfigurator/api/venv/bin/python3 ${SCRATCH}/_fetch_gap70.py`, { maxBuffer: 1024 * 1024 * 80 }).toString());

const podLimit = [];
for (const id of IDS) {
  const info = D[id];
  const mezery = najdiMezery(info.data.parts);
  const minGap = mezery.length ? Math.min(...mezery.map(m => m.gap)) : null;
  const spatne = minGap != null && minGap < 70;
  console.log(`${id} ${info.name.slice(0,55).padEnd(56)} min=${minGap} ${spatne ? "POD LIMITEM" : ""}`);
  mezery.forEach(m => console.log(`     ${m.a} <-> ${m.b}: ${m.gap}mm`));
  if (spatne) podLimit.push(id);
}
console.log("\nPOD 70mm:", podLimit);
