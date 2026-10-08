// Primy sanity-check NAD ZIVYMI (jiz zapsanymi) daty: existuje v aktualnim
// stavu DB nejaky uhelnik-noha<N> kus, ktery se REALNE (GLB bbox) prekryva
// s vyrezovou trojici na stejne noze o vic nez par mm? Nezavisle na tom,
// jakou heuristikou byl posun spocitan - kontroluje VYSLEDEK, ne postup.
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { execSync } = require("child_process");
const fs = require("fs");

function partMesh(p) {
  const glbPath = R.glbPath(p.part_id);
  if (!glbPath) throw new Error("chybi glb pro " + p.part_id);
  const m = parseGlbMesh(glbPath);
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

const ids = process.argv.slice(2).map(Number);
const dumpPy = `
import json, pymysql
env = {}
with open("api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT",3306)), user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SELECT id, data FROM product_assemblies WHERE id IN (${ids.join(",")})")
out = {}
for r in cur.fetchall(): out[r["id"]] = json.loads(r["data"])["parts"]
conn.close()
print(json.dumps(out))
`;
fs.writeFileSync("/tmp/_recheck_dump.py", dumpPy);
const DB = JSON.parse(execSync("api/venv/bin/python3 /tmp/_recheck_dump.py", { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 80 }).toString());

const trioRoles = ["sloupek-pred-podbehem", "zadni-svislice-nad-zarezem", "pricka-uzavreni-vyrezu"];
for (const id of ids) {
  const parts = DB[id];
  const trio = parts.filter(p => trioRoles.includes(p.role));
  if (!trio.length) { console.log(`id=${id}: bez vyrezove trojice, preskoceno`); continue; }
  // seskup podle Z (leg)
  const legZs = [...new Set(trio.map(p => Math.round(p.position[2] * 10) / 10))];
  let anyBad = false;
  for (const lz of legZs) {
    const trioAtLeg = trio.filter(p => Math.abs(p.position[2] - lz) < 2);
    const trioBoxes = trioAtLeg.map(p => ({ p, box: new THREE.Box3().setFromObject(partMesh(p)) }));
    const uhel = parts.filter(p => /^uhelnik-noha\d+$/.test(p.role || "") && Math.abs(p.position[2] - lz) < 40);
    for (const u of uhel) {
      const ub = new THREE.Box3().setFromObject(partMesh(u));
      for (const tb of trioBoxes) {
        if (!ub.intersectsBox(tb.box)) continue;
        const ix = Math.min(ub.max.x, tb.box.max.x) - Math.max(ub.min.x, tb.box.min.x);
        const iy = Math.min(ub.max.y, tb.box.max.y) - Math.max(ub.min.y, tb.box.min.y);
        const iz = Math.min(ub.max.z, tb.box.max.z) - Math.max(ub.min.z, tb.box.min.z);
        const vol = Math.max(0, ix) * Math.max(0, iy) * Math.max(0, iz);
        if (vol > 500) {
          console.log(`id=${id} leg Z=${lz}: PREKRYV ${u.role}@${JSON.stringify(u.position.map(v=>+v.toFixed(1)))} x ${tb.p.role}@${JSON.stringify(tb.p.position.map(v=>+v.toFixed(1)))} vol=${vol.toFixed(0)} overlap=[${ix.toFixed(1)},${iy.toFixed(1)},${iz.toFixed(1)}]`);
          anyBad = true;
        }
      }
    }
  }
  if (!anyBad) console.log(`id=${id}: OK, zadny uhelnik-vyrez prekryv nenalezen (${legZs.length} vyrezovych noh zkontrolovano)`);
}
