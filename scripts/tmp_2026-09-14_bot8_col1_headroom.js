// Zmeri SKUTECNOU volnou vysku nad nejvyssim boxem 2. sloupce (col1) pro
// varianty 01-05 (A i B) - najde realny Box3 kazdeho dilu (ne ulozenou
// position.y, ktera u tohohle rotovaneho eurobxu neodpovida stredu),
// a pro kazdou sestavu spocita mezeru mezi vrskem nejvyssiho eurobxu
// v col1 a nejblizsi prekazkou nad nim (cokoli se Z-rozsahem prekryvajicim
// box, VCETNE karoserie = skutecny strop).
const fs = require("fs");
const THREE = require("three");
const { execSync } = require("child_process");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const IDS = [369, 370, 381, 378, 382, 379, 383, 380, 384, 385];
const raw = execSync(
  `api/venv/bin/python3 -c "` +
  `import sys, json; sys.path.insert(0,'scripts'); from _env import get_conn; ` +
  `conn=get_conn(); cur=conn.cursor(); cur.execute('SELECT id, name, data FROM product_assemblies WHERE id IN (${IDS.join(",")})'); ` +
  `out={r['id']:{'name':r['name'],'data':json.loads(r['data'])} for r in cur.fetchall()}; ` +
  `print(json.dumps(out))"`,
  { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 50 }
).toString();
const D = JSON.parse(raw);

function worldBox(p) {
  const glb = R.glbPath(p.part_id);
  if (!glb) return null; // karoserie ma vlastni cestu, viz nize
  const mesh = parseGlbMesh(glb);
  mesh.position.set(p.position[0], p.position[1], p.position[2]);
  mesh.quaternion.set(p.quaternion[0], p.quaternion[1], p.quaternion[2], p.quaternion[3]);
  mesh.scale.set(p.scale[0], p.scale[1], p.scale[2]);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}
function karoserieBox3(partId) {
  const map = { car_body_15: "Fiat_Doblo_FI14_2010-2022_L", car_body_16: "Fiat_Doblo_FI14_2010-2022_R_D", car_body_17: "Fiat_Doblo_FI14_2010-2022_B" };
  const f = map[partId];
  if (!f) return null;
  const mesh = parseGlbMesh(`/opt/konfigurator/webapp/katalog/car_bodies/${f}.glb`);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}

for (const id of IDS) {
  const { name, data } = D[id];
  const parts = data.parts;
  const boxes = parts.map(p => ({ p, box: R.jeKaroserie(p.part_id) ? karoserieBox3(p.part_id) : worldBox(p) })).filter(x => x.box);

  // najdi VSECHNY instance eurobox-col1-p* (nejvyssi podle REALNEHO stredu)
  const col1Boxes = boxes.filter(x => (x.p.role || "").startsWith("eurobox-col1"));
  if (!col1Boxes.length) { console.log(`id=${id} (${name}): zadny eurobox-col1 - preskakuji`); continue; }
  col1Boxes.sort((a, b) => b.box.max.y - a.box.max.y);
  const top = col1Boxes[0];
  const zLo = top.box.min.z - 0.5, zHi = top.box.max.z + 0.5; // vlastni Z rozsah boxu (bez toleranci navic)
  const xLo = top.box.min.x - 0.5, xHi = top.box.max.x + 0.5;

  let ceiling = Infinity, ceilingPart = null;
  for (const { p, box } of boxes) {
    if (p === top.p) continue;
    if (box.min.y < top.box.max.y - 0.5) continue; // musi byt NAD boxem, ne pod/vedle
    const zOverlap = Math.min(box.max.z, zHi) - Math.max(box.min.z, zLo);
    const xOverlap = Math.min(box.max.x, xHi) - Math.max(box.min.x, xLo);
    if (zOverlap <= 0 || xOverlap <= 0) continue; // nepretina se pudorysne s boxem vubec
    if (box.min.y < ceiling) { ceiling = box.min.y; ceilingPart = p; }
  }
  const volno = ceiling - top.box.max.y;
  console.log(`id=${id} (${name.slice(0, 60)})`);
  console.log(`  top box: role=${top.p.role} part_id=${top.p.part_id} realny Y=[${top.box.min.y.toFixed(1)},${top.box.max.y.toFixed(1)}] vyska=${(top.box.max.y - top.box.min.y).toFixed(1)}mm`);
  console.log(`  strop: ${ceilingPart ? ceilingPart.role + "(" + ceilingPart.part_id + ")" : "NENALEZEN"} Y_min=${ceiling === Infinity ? "-" : ceiling.toFixed(1)}  VOLNO NAD BOXEM = ${volno === Infinity ? "?" : volno.toFixed(1)}mm`);
}
