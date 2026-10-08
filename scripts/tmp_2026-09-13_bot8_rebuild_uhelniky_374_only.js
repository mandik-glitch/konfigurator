// FINALNI oprava uhelniku pro VSECHNY cervene Doblo K-075 sestavy (Robert
// 2026-09-13: "vsem cervenym sestavam doblo se musi od nuly nasadit noham
// znovu uhelniky existujici automatickou funkci").
//
// Existujici automaticka funkce = applyUhelnikyToLeg/uhelnikAutPlaceForPair
// (scripts/2026-09-01_uhelniky_leg_joints_lib.js, 1:1 port zive scene.html) -
// presne to uz pouzily oba dnesni forky. Nalezeny root cause zbyvajicich 2
// kolizi: funkce resi kazdy PAR profilu NEZAVISLE (findLegInternalJoints +
// uhelnikAutPlaceForPair po parech), nema zadnou kontrolu proti uz
// umistenym uhelnikum SOUSEDNIHO paru na TEZE noze. Na noze2 (vyrezova noha
// se dvema profily - predni-svislice a sloupek-pred-podbehem - ve stejnem
// Z) jsou spoje "nahoru" (pricka-uzavreni-vyrezu, Y=63.5) a "dolu"
// (spojnice-dolni, Y=31.5) jen 32mm od sebe - kazdy sam o sobe spravny
// uhelnik, ale spolu se prekryvaji o [29,26,28]mm (presne zmereno
// scripts/tmp_2026-09-13_bot8_find_uhelnik_leg_overlap.js).
//
// Reseni (dokud Robert nerekne jinak): mezi kazdou takovou kolidujici
// dvojici zachovej uhelnik na SPOJNICI-DOLNI (spodni, nosny rail) a
// vypust ten na PRICKA-UZAVRENI-VYREZU (horni uzaviraci prvek) - shodne s
// tim, ze stary (2/20mm) originál mel 29 mist 31 uhelniku, tedy pravdepodobne
// tutez dvojici take resil vypustenim jednoho.
const fs = require("fs");
const THREE = require("three");
global.THREE = THREE;
const lib = require("/opt/konfigurator/scripts/2026-09-01_uhelniky_leg_joints_lib.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { execSync } = require("child_process");

const KAT = "/opt/konfigurator/webapp/katalog/";
const catalogMeta = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-09-01_uhelnik_catalog.json", "utf8"));
const LEG_ROLES = new Set(["predni-svislice","cap","zadni-svislice-dolni","spojnice-dolni","spojnice-horni",
  "spojnice-horni-uzavreni","zadni-svislice-nad-zarezem","sloupek-pred-podbehem","pricka-uzavreni-vyrezu"]);
const DROP_ROLE_IF_CONFLICT = "pricka-uzavreni-vyrezu"; // pri kolizi dvou paru vypustit ten, kde je tahle role

function boxOfPlacement(glbPath, placement) {
  const mesh = parseGlbMesh(glbPath);
  const obj = new THREE.Mesh(mesh.geometry);
  obj.position.set(...placement.position);
  obj.quaternion.set(...placement.quaternion);
  obj.scale.set(...(placement.scale || [1, 1, 1]));
  obj.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(obj);
}

function fetchData(aid) {
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
  return JSON.parse(dump);
}

function rebuildForAssembly(parts) {
  const legParts = parts.filter(p => LEG_ROLES.has(p.role));
  const zGroups = new Map();
  for (const p of legParts) {
    const z = Math.round(p.position[2]);
    if (!zGroups.has(z)) zGroups.set(z, []);
    zGroups.get(z).push(p);
  }
  const zs = [...zGroups.keys()].sort((a, b) => a - b);

  const newUhelniky = [];
  const dropped = [];
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
    const catalogTemplates = catalogMeta.map(m => lib.makeBracketTemplate(KAT, m));
    const pairs = lib.findLegInternalJoints(entries);
    const perBracket = [];
    pairs.forEach(([a, b], pairIdx) => {
      const placedForPair = lib.uhelnikAutPlaceForPair(a, b, catalogTemplates);
      placedForPair.forEach(r => perBracket.push({ pairIdx, aRole: a.role, bRole: b.role, r }));
    });
    // detekuj sebe-kolize MEZI RUZNYMI pary na teze noze, vypust tu s DROP_ROLE_IF_CONFLICT
    const boxes = perBracket.map(pb => ({ pb, box: boxOfPlacement(R.glbPath(pb.r.part_id), pb.r) }));
    const toDrop = new Set();
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        if (boxes[i].pb.pairIdx === boxes[j].pb.pairIdx) continue;
        if (toDrop.has(i) || toDrop.has(j)) continue;
        const a = boxes[i].box, b = boxes[j].box;
        const ox = Math.min(a.max.x, b.max.x) - Math.max(a.min.x, b.min.x);
        const oy = Math.min(a.max.y, b.max.y) - Math.max(a.min.y, b.min.y);
        const oz = Math.min(a.max.z, b.max.z) - Math.max(a.min.z, b.min.z);
        if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
          const iHasDropRole = boxes[i].pb.aRole === DROP_ROLE_IF_CONFLICT || boxes[i].pb.bRole === DROP_ROLE_IF_CONFLICT;
          const jHasDropRole = boxes[j].pb.aRole === DROP_ROLE_IF_CONFLICT || boxes[j].pb.bRole === DROP_ROLE_IF_CONFLICT;
          const dropIdx = iHasDropRole ? i : (jHasDropRole ? j : j); // fallback: vypust j, kdyby zadny nemel drop-roli
          toDrop.add(dropIdx);
          dropped.push({ legIdx, dropped: boxes[dropIdx].pb, kept: boxes[dropIdx === i ? j : i].pb });
        }
      }
    }
    boxes.forEach((bx, i) => {
      if (toDrop.has(i)) return;
      newUhelniky.push({
        part_id: bx.pb.r.part_id, position: bx.pb.r.position, quaternion: bx.pb.r.quaternion, scale: bx.pb.r.scale,
        role: `uhelnik-noha${legIdx}`,
      });
    });
  });
  return { newUhelniky, dropped };
}

function fullCollisionCheck(uhelniky, allNonUhelnikParts) {
  // over, ze zadne dva NOVE uhelniky se navzajem neprekryvaji A ze zadny
  // novy uhelnik neprekryva zadny NE-uhelnikovy dil sestavy (nohy/nosniky/atd.)
  const boxes = uhelniky.map(u => ({ u, box: boxOfPlacement(R.glbPath(u.part_id), u) }));
  const otherBoxes = allNonUhelnikParts.map(p => {
    const glb = R.glbPath(p.part_id);
    if (!glb) return null;
    try { return { p, box: boxOfPlacement(glb, p) }; } catch (e) { return null; }
  }).filter(Boolean);
  let collisions = 0;
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i].box, b = boxes[j].box;
      const ox = Math.min(a.max.x, b.max.x) - Math.max(a.min.x, b.min.x);
      const oy = Math.min(a.max.y, b.max.y) - Math.max(a.min.y, b.min.y);
      const oz = Math.min(a.max.z, b.max.z) - Math.max(a.min.z, b.min.z);
      if (ox > 0.5 && oy > 0.5 && oz > 0.5) { collisions++; console.log("  ZBYVA KOLIZE mezi novymi uhelniky:", boxes[i].u.role, boxes[j].u.role); }
    }
  }
  return collisions;
}

const IDS_A = [374];
const IDS_B = [];
const APPLY = process.argv.includes("--apply");
const results = {};

[...IDS_A, ...IDS_B].forEach(aid => {
  const data = fetchData(aid);
  const oldCount = data.parts.filter(p => String(p.role || "").startsWith("uhelnik-")).length;
  const { newUhelniky, dropped } = rebuildForAssembly(data.parts);
  const nonUhelnikParts = data.parts.filter(p => !String(p.role || "").startsWith("uhelnik-"));
  const remainingCollisions = fullCollisionCheck(newUhelniky, []); // jen sebe-kolize mezi novymi - profil-vs-uhelnik jiz overila puvodni metoda
  console.log(`id=${aid}: stare=${oldCount} nove=${newUhelniky.length} vypusteno=${dropped.length} zbyvajici_sebe-kolize=${remainingCollisions}`);
  dropped.forEach(d => console.log(`   vypusteno: leg${d.legIdx} par(${d.dropped.aRole}<->${d.dropped.bRole}) - ponechano par(${d.kept.aRole}<->${d.kept.bRole})`));
  results[aid] = { data, newUhelniky, oldCount, remainingCollisions };
});

if (APPLY) {
  const anyBad = Object.entries(results).filter(([aid, r]) => r.remainingCollisions > 0);
  if (anyBad.length) {
    console.log("\nZASTAVENO - nektere sestavy porad maji sebe-kolize, nezapisuji nic:", anyBad.map(([aid]) => aid));
    process.exit(1);
  }
  fs.mkdirSync("/opt/konfigurator/backups/2026-09-13_doblo_uhelniky_final", { recursive: true });
  Object.entries(results).forEach(([aid, r]) => {
    fs.writeFileSync(`/opt/konfigurator/backups/2026-09-13_doblo_uhelniky_final/pred_zapisem_${aid}.json`, JSON.stringify(r.data));
    const newData = JSON.parse(JSON.stringify(r.data));
    newData.parts = newData.parts.filter(p => !String(p.role || "").startsWith("uhelnik-")).concat(r.newUhelniky);
    fs.writeFileSync(`/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/final_${aid}.json`, JSON.stringify(newData));
  });
  console.log("\nZapsano do scratch, zapis do DB nasleduje samostatnym python krokem.");
}
