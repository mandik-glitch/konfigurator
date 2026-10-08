// Najde, KTERE dva konkretni uhelniky na stejne noze se navzajem prekryvaji
// (self-kolize v ramci "existujici automaticke funkce" applyUhelnikyToLeg) -
// Robert 2026-09-13: "vsem cervenym sestavam doblo se musi od nuly nasadit
// noham znovu uhelniky existujici automatickou funkci". Zjisteni: funkce
// (uhelnikAutPlaceForPair) resi kazdy PAR profilu nezavisle, nema zadnou
// kontrolu proti UZ ULOZENYM uhelnikum ze SOUSEDNIHO paru na stejne noze -
// u dvou blizkych spoju (62mm) tak vyjdou dva jednotlive spravne, ale spolu
// prekryvajici se uhelniky.
const fs = require("fs");
const THREE = require("three");
global.THREE = THREE;
const lib = require("/opt/konfigurator/scripts/2026-09-01_uhelniky_leg_joints_lib.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { execSync } = require("child_process");

const KAT = "/opt/konfigurator/webapp/katalog/";
const catalogMeta = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-09-01_uhelnik_catalog.json", "utf8"));
const LEG_ROLES = new Set(["predni-svislice","cap","zadni-svislice-dolni","spojnice-dolni","spojnice-horni",
  "spojnice-horni-uzavreni","zadni-svislice-nad-zarezem","sloupek-pred-podbehem","pricka-uzavreni-vyrezu"]);

const aid = Number(process.argv[2]);
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
    cur.execute('SELECT data FROM product_assemblies WHERE id=${aid}')
    print(cur.fetchone()['data'])
conn.close()
"`, { maxBuffer: 1024 * 1024 * 20, cwd: "/opt/konfigurator" }).toString();
const data = JSON.parse(dump);
const legParts = data.parts.filter(p => LEG_ROLES.has(p.role));
const zGroups = new Map();
for (const p of legParts) {
  const z = Math.round(p.position[2]);
  if (!zGroups.has(z)) zGroups.set(z, []);
  zGroups.get(z).push(p);
}
const zs = [...zGroups.keys()].sort((a, b) => a - b);

function boxOfPlacement(glbPath, placement) {
  const mesh = parseGlbMesh(glbPath);
  const obj = new THREE.Mesh(mesh.geometry);
  obj.position.set(...placement.position);
  obj.quaternion.set(...placement.quaternion);
  obj.scale.set(...(placement.scale || [1, 1, 1]));
  obj.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(obj);
}

zs.forEach((z, legIdx) => {
  const legPartsHere = zGroups.get(z);
  const entries = legPartsHere.map((p, idx) => {
    const glbPath = R.glbPath(p.part_id);
    return lib.makeProfileEntry(glbPath, {
      position: p.position, quaternion: p.quaternion, scale: p.scale,
      id: p.part_id, length_mm: 1000, cross_section_mm: [30, 30],
      role: p.role, idx,
    });
  });
  const pairs = lib.findLegInternalJoints(entries);
  const perBracket = []; // {pairIdx, aRole, bRole, result}
  pairs.forEach(([a, b], pairIdx) => {
    const placedForPair = lib.uhelnikAutPlaceForPair(a, b, catalogMeta.map(m => lib.makeBracketTemplate(KAT, m)));
    placedForPair.forEach(r => perBracket.push({ pairIdx, aRole: a.role, bRole: b.role, r }));
  });
  // pocitej box kazdeho umistenehoi uhelniku, hledej prekryvy MEZI RUZNYMI pary
  const boxes = perBracket.map(pb => ({ pb, box: boxOfPlacement(R.glbPath(pb.r.part_id), pb.r) }));
  console.log(`\n--- leg${legIdx} (z=${z}), ${perBracket.length} uhelniku ---`);
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      if (boxes[i].pb.pairIdx === boxes[j].pb.pairIdx) continue; // stejny par - nepocita se
      const a = boxes[i].box, b = boxes[j].box;
      const ox = Math.min(a.max.x, b.max.x) - Math.max(a.min.x, b.min.x);
      const oy = Math.min(a.max.y, b.max.y) - Math.max(a.min.y, b.min.y);
      const oz = Math.min(a.max.z, b.max.z) - Math.max(a.min.z, b.min.z);
      if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
        console.log(`  KOLIZE: par#${boxes[i].pb.pairIdx} (${boxes[i].pb.aRole}<->${boxes[i].pb.bRole}) uhelnik@${JSON.stringify(boxes[i].pb.r.position.map(v=>+v.toFixed(1)))}`,
          `  vs  par#${boxes[j].pb.pairIdx} (${boxes[j].pb.aRole}<->${boxes[j].pb.bRole}) uhelnik@${JSON.stringify(boxes[j].pb.r.position.map(v=>+v.toFixed(1)))}`,
          `  overlap=[${ox.toFixed(1)},${oy.toFixed(1)},${oz.toFixed(1)}]`);
      }
    }
  }
});
