// Validátor ÚČETNICTVÍ spojů uložených `custom_shapes` sestav - Robert
// (2026-08-18/19): "z pohledu oka může být vše v pořádku, ale z pohledu
// matematiky obsazených ploch, počet spojů a tak dále může být chybný a
// tohle všechno musíme nějak pro kontrolovat." Geometrii (mezera/zanoření)
// ověřují nástroje výše (touchReport v 2026-08-18_scene_geometry_lib.js) -
// TENHLE nástroj ověřuje DATOVOU stránku: joint_count / lic_peers /
// used_conn vs. skutečné (geometricky změřené) doteky mezi díly.
//
// Invarianty (viz webapp/scene.html attachEntryToParent/registerJoint):
//  I1  lic_peers symetrie: když díl i uvádí j, musí j uvádět i.
//  I2  každá dvojice dílů ve SKUTEČNÉM flush doteku (box test: 1 osa
//      gap≈0/overlap≈0, 2 osy plný překryv) má být propojená v lic_peers.
//  I3  sum(joint_count) == počet skutečných flush dotyků (1 fyzický spoj =
//      1 šroub = jointCount+1 na "child" straně, viz scene.html komentář
//      "L tvar ukazoval 2 spoje misto 1").
//  I4  used_conn indexy ukazují na existující konektory dílu.
//
// Použití: `npm install` v ROOTU repa, pak:
//   node scripts/2026-08-19_bookkeeping_validator.js <dump.json>
// kde dump.json = {"shapes":[{id,name,parts:[...]}], "glb_map":{part_id:glb}}
// (vytáhne se z DB přes api/venv/bin/python3 + pymysql - viz
//  .claude/skills/3d-scena-spoje/SKILL.md, sekce "zápis do custom_shapes").
const fs = require("fs");
const path = require("path");
const THREE = require("three");
const { computeConnectorsLocal, isStampPart } = require("../webapp/js/scene-geometry-shared.js");
const { parseGlbMesh } = require("./2026-08-19_glb_real_geometry.js");

const KATALOG_DIR = "/opt/konfigurator/webapp/katalog";

function boxOf(obj) { return new THREE.Box3().setFromObject(obj); }
function touchReport(A, B) {
  const out = {};
  ["x", "y", "z"].forEach(ax => {
    out[ax] = {
      gap: Math.max(A.min[ax] - B.max[ax], B.min[ax] - A.max[ax]),
      overlap: Math.min(A.max[ax], B.max[ax]) - Math.max(A.min[ax], B.min[ax]),
    };
  });
  return out;
}
function isFlush(r, eps) {
  eps = eps == null ? 0.05 : eps;
  const f = ["x", "y", "z"].filter(ax => Math.abs(r[ax].overlap) <= eps);
  const o = ["x", "y", "z"].filter(ax => r[ax].overlap > eps);
  return f.length === 1 && o.length === 2;
}

function validateShape(shape, glbMap, meshCache) {
  const problems = [];
  const entries = shape.parts.map((p, idx) => {
    // Ochranne razitko (logo + vypln drazky) se do ucetnictvi spoju NESMI -
    // a je to tu kritictejsi nez u kusovniku. Logo s profilem ZAMERNE LICUJE,
    // cimz presne splnuje kriterium I2/I3 "flush dotyk" (1 osa gap~0, 2 osy
    // plny prekryv). Bez tohohle filtru by kazde razitko vyrobilo hlaseni
    // "dotyk neni v lic_peers" + rozjezd sum(joint_count) - tedy falesne
    // nalezy na sestavach, ktere jsou ve skutecnosti v poradku.
    // (Razitka jsou v datech sestavy od 2026-09-11, driv jen v renderu.)
    //
    // POZOR, vraci se ZNACKA, ne `null`: `null` znamena "chybi geometrie" a
    // o par radek niz kvuli nemu PRESKOCI CELA SESTAVA. Razitko by tim
    // validator na kazde orazitkovane sestave tise vyplo - tedy "0 nalezu"
    // ve vyznamu "nezmereno", ne "cisto" (viz skill 3d-scena-spoje).
    // A index se MUSI zachovat: lic_peers odkazuje na poradi v `parts`,
    // takze vyfiltrovat razitka uz tady by cela cisla posunulo.
    if (isStampPart(p)) return { idx, part: p, razitko: true };
    const glb = glbMap[p.part_id];
    if (!glb) return null;
    const file = path.join(KATALOG_DIR, glb);
    if (!fs.existsSync(file)) return null;
    // mesh cache: stejny glb = stejna geometrie, klonovat neni potreba -
    // parseGlbMesh vytvari novy Mesh, ale pozici/rotaci/scale nastavime per dil
    const obj = parseGlbMesh(file);
    obj.position.fromArray(p.position);
    obj.quaternion.fromArray(p.quaternion);
    obj.scale.fromArray(p.scale || [1, 1, 1]);
    obj.updateMatrixWorld(true);
    return { idx, part: p, object3d: obj, connectorsLocal: computeConnectorsLocal(obj) };
  });
  if (entries.some(e => e === null)) {
    return { skipped: true, reason: "chybi realna .glb geometrie pro nektery dil" };
  }

  // I4: used_conn indexy platne
  entries.forEach(e => {
    if (e.razitko) return;
    (e.part.used_conn || []).forEach(ci => {
      if (ci < 0 || ci >= e.connectorsLocal.length) {
        problems.push(`I4: dil #${e.idx} (${e.part.part_id}) used_conn index ${ci} mimo rozsah (dil ma ${e.connectorsLocal.length} konektoru)`);
      }
    });
  });

  // skutecne flush dotyky (geometrie)
  const boxes = entries.map(e => (e.razitko ? null : boxOf(e.object3d)));
  const flushPairs = new Set();
  for (let i = 0; i < entries.length; i++) {
    if (entries[i].razitko) continue;
    for (let j = i + 1; j < entries.length; j++) {
      if (entries[j].razitko) continue;
      const r = touchReport(boxes[i], boxes[j]);
      if (isFlush(r)) flushPairs.add(`${i}-${j}`);
    }
  }

  // lic_peers (indexy do parts pole, viz serializeToCustomShapeParts)
  const licSets = entries.map(e => new Set(e.part.lic_peers || []));

  // I1: symetrie
  licSets.forEach((s, i) => {
    s.forEach(j => {
      if (j < 0 || j >= entries.length) {
        problems.push(`I1: dil #${i} lic_peers odkazuje na neexistujici index ${j}`);
      } else if (!licSets[j].has(i)) {
        problems.push(`I1: lic_peers nesymetricke - dil #${i} uvadi #${j}, ale #${j} neuvadi #${i}`);
      }
    });
  });

  // I2: kazdy flush dotyk registrovan v lic_peers
  flushPairs.forEach(key => {
    const [i, j] = key.split("-").map(Number);
    if (!licSets[i].has(j) && !licSets[j].has(i)) {
      problems.push(`I2: dily #${i} a #${j} se GEOMETRICKY dotykaji flush, ale lic_peers je nepropojuje (spoj chybi v datech)`);
    }
  });
  // I2b (opacny smer, informativne): lic_peers dvojice bez flush dotyku
  const reported = new Set();
  licSets.forEach((s, i) => {
    s.forEach(j => {
      const key = i < j ? `${i}-${j}` : `${j}-${i}`;
      if (reported.has(key)) return;
      reported.add(key);
      if (!flushPairs.has(key)) {
        problems.push(`I2b: lic_peers propojuje dily #${Math.min(i,j)} a #${Math.max(i,j)}, ale geometricky flush dotyk mezi nimi NENI`);
      }
    });
  });

  // I3: soucet joint_count vs pocet flush dotyku
  const totalJointCount = entries.reduce((s, e) => s + (e.razitko ? 0 : (e.part.joint_count || 0)), 0);
  if (totalJointCount !== flushPairs.size) {
    problems.push(`I3: sum(joint_count)=${totalJointCount}, ale skutecnych flush dotyku=${flushPairs.size}`);
  }

  const razitek = entries.filter(e => e.razitko).length;
  return { skipped: false, problems, flushCount: flushPairs.size, totalJointCount,
           partCount: entries.length - razitek, razitek };
}

// ---- main ----
const dumpPath = process.argv[2];
if (!dumpPath) {
  console.error("Pouziti: node 2026-08-19_bookkeeping_validator.js <dump.json>");
  process.exit(2);
}
const dump = JSON.parse(fs.readFileSync(dumpPath, "utf8"));
let anyProblem = false;
dump.shapes.forEach(shape => {
  const res = validateShape(shape, dump.glb_map, {});
  console.log(`\n=== id=${shape.id} "${shape.name}" (${shape.parts.length} dilu) ===`);
  if (res.skipped) { console.log(`  PRESKOCENO: ${res.reason}`); return; }
  console.log(`  flush dotyku: ${res.flushCount}, sum(joint_count): ${res.totalJointCount}`
    + (res.razitek ? `, vynechano razitkovych dilu: ${res.razitek}` : ""));
  if (!res.problems.length) {
    console.log("  OK - vsechny invarianty (I1-I4) sedi");
  } else {
    anyProblem = true;
    res.problems.forEach(p => console.log(`  PROBLEM ${p}`));
  }
});
console.log(`\n${anyProblem ? "NALEZENY PROBLEMY (viz vyse)" : "VSECHNY SESTAVY OK"}`);
process.exit(anyProblem ? 1 : 0);
