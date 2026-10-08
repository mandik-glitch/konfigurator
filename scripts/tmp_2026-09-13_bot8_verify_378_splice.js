// Overeni "skutecne kolize" pro splice opravu #378 - kriterium koordinatora:
// presah >2mm na VSECH 3 osach SOUCASNE mezi necim NOVYM (podelnik-*-horni,
// pricka-horni-*) a necim PUVODNIM (vse ostatni). nosnik/spojnice-vs-eurobox
// neni kolize (zapustena geometrie, zname a ocekavane).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");

const dryRunOut = require("child_process").execSync(
  "cd /opt/konfigurator && api/venv/bin/python3 scripts/tmp_2026-09-13_bot8_splice_378.py --dry-run", { encoding: "utf8" });
// dry-run netiskne cely JSON parts - radsi znovu sestavit stejnou logikou primo tady na zaklade DB.
const { execSync } = require("child_process");
execSync(`api/venv/bin/python3 -c "
import sys, json
sys.path.insert(0, 'scripts')
from _env import get_conn
conn = get_conn()
cur = conn.cursor()
cur.execute('SELECT data FROM product_assemblies WHERE id=378')
d = json.loads(cur.fetchone()['data'])
parts = d['parts']
split_roles = {'podelnik-celni-horni-0','podelnik-celni-horni-1','podelnik-zadni-horni-0','podelnik-zadni-horni-1'}
removed = [p for p in parts if p.get('role') in split_roles]
celni_q = next(p['quaternion'] for p in removed if p['role'].startswith('podelnik-celni'))
zadni_q = next(p['quaternion'] for p in removed if p['role'].startswith('podelnik-zadni'))
celni_x = next(p['position'][0] for p in removed if p['role'].startswith('podelnik-celni'))
zadni_x = next(p['position'][0] for p in removed if p['role'].startswith('podelnik-zadni'))
parts = [p for p in parts if p.get('role') not in split_roles]
svislice = sorted((p for p in parts if p.get('role')=='predni-svislice'), key=lambda p: p['position'][2])
z0 = svislice[0]['position'][2] + 15
z1 = svislice[-1]['position'][2] - 15
z_stred = (z0+z1)/2
delka = z1-z0
parts.append({'part_id':'Object_7','position':[celni_x,1205.0,z_stred],'quaternion':celni_q,'scale':[1,delka/1000,1],'role':'podelnik-celni-horni'})
parts.append({'part_id':'Object_7','position':[zadni_x,1205.0,z_stred],'quaternion':zadni_q,'scale':[1,delka/1000,1],'role':'podelnik-zadni-horni'})
for p in parts:
    if str(p.get('role','')).startswith('pricka-horni'):
        p['position'][1] = 1205.0
d['parts'] = parts
with open('/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/378_fixed_preview.json','w') as f:
    json.dump(d, f)
print('ok', len(parts), 'dilu')
"`, { encoding: "utf8", stdio: "inherit" });

const data = JSON.parse(fs.readFileSync(
  "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/378_fixed_preview.json", "utf8"));

const meshCache = new Map();
function meshFor(f) { if (!meshCache.has(f)) meshCache.set(f, parseGlbMesh(f)); return meshCache.get(f); }

const NEW_ROLES = new Set(["podelnik-celni-horni", "podelnik-zadni-horni", "pricka-horni-0", "pricka-horni-1", "pricka-horni-2"]);

const entries = [];
data.parts.forEach((p, idx) => {
  if (R.jeKaroserie(p.part_id)) return;
  const glb = R.glbPath(p.part_id);
  if (!glb) return;
  const mesh = meshFor(glb);
  const obj = new THREE.Mesh(mesh.geometry);
  obj.position.set(...p.position);
  obj.quaternion.set(...p.quaternion);
  if (p.scale) obj.scale.set(...p.scale); else obj.scale.set(1, 1, 1);
  obj.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(obj);
  entries.push({ idx, role: p.role || p.part_id, box, isNew: NEW_ROLES.has(p.role) });
});

const AXES = ["x", "y", "z"];
function overlap3mm(a, b) {
  return AXES.every(ax => {
    const lo = Math.max(a.min[ax], b.min[ax]);
    const hi = Math.min(a.max[ax], b.max[ax]);
    return (hi - lo) > 2; // >2mm presah na teto ose
  });
}

let realCollisions = 0;
const newEntries = entries.filter(e => e.isNew);
const oldEntries = entries.filter(e => !e.isNew);
newEntries.forEach(n => {
  oldEntries.forEach(o => {
    if (overlap3mm(n.box, o.box)) {
      realCollisions++;
      console.log(`KOLIZE: ${n.role}(idx${n.idx}) x ${o.role}(idx${o.idx})`);
    }
  });
});
console.log(`\nSkutecnych kolizi (presah >2mm na vsech 3 osach, novy vs puvodni): ${realCollisions}`);
console.log(`Celkem dilu: ${entries.length}, novych: ${newEntries.length}`);
