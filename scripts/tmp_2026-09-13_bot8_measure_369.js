const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const fs = require("fs");

const env = {};
fs.readFileSync("/opt/konfigurator/api/.env", "utf8").split("\n").forEach(l => {
  l = l.trim(); if (!l || l.startsWith("#") || !l.includes("=")) return;
  const i = l.indexOf("="); env[l.slice(0,i).trim()] = l.slice(i+1).trim();
});

const { execSync } = require("child_process");
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
    cur.execute('SELECT data FROM product_assemblies WHERE id=369')
    print(cur.fetchone()['data'])
conn.close()
"`, { maxBuffer: 1024*1024*20, cwd: "/opt/konfigurator" }).toString();
const data = JSON.parse(dump);

function partMesh(p) {
  const gp = R.glbPath(p.part_id);
  if (!gp) return null;
  const m = parseGlbMesh(gp);
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}
function box(p) {
  const m = partMesh(p);
  if (!m) return null;
  return new THREE.Box3().setFromObject(m);
}

let legTop = -Infinity;
for (const p of data.parts) {
  if (p.role === "cap" || p.role === "predni-svislice") {
    const b = box(p);
    if (b) legTop = Math.max(legTop, b.max.y);
  }
}
let boxTop = -Infinity;
for (const p of data.parts) {
  if (String(p.role||"").startsWith("eurobox")) {
    const b = box(p);
    if (b) boxTop = Math.max(boxTop, b.max.y);
  }
}
console.log("Y_leg_top =", legTop.toFixed(1));
console.log("Y_box_top =", boxTop.toFixed(1));
console.log("volna vyska po 30mm mezere =", (legTop - boxTop - 30).toFixed(1));
