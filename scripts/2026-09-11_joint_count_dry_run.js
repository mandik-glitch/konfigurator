// Dry-run rekonstrukce poctu spoju pro cenu (bot10, zadani bot8
// 2026-09-11, rozhodnuti po prvnim kole 2026-09-11 vecer). Pouziva
// PRIMO stejnou flush-pair detekci jako 2026-08-19_bookkeeping_
// validator.js (realna .glb geometrie), driver okolo uz overene
// funkce, zadna nova touchReport logika.
//
// car_body_* dily (vizualni reference karoserie) VYNECHANY - nemaji
// glb a nejsou fyzicky spojovany sroubem s ramem.
//
// PRAVIDLA (rozhodnuti bot8, ne moje vlastni klasifikace topologie):
//  - profil<->profil, profil<->uhelnikova spojka: GEOMETRICKY pocet
//    flush dvojic (isFlush) - tady je pocet skutecne variabilni a
//    metoda funguje cist (overeno na id=279/333: 88+54=142).
//  - profil<->zaslepka: PRESNE 1 spoj na kus, BEZ OHLEDU na to, jestli
//    je nasazena zvenku (flush) nebo zapustena dovnitr (plna kontejnace
//    na vsech 3 osach) - "zaslepka zakryva konec JEDNOHO profilu,
//    nemuze byt pripojena ke dvema" (bot8). Levna pojistka: over, ze
//    kazda zaslepka sousedi (dotyk NEBO vnoreni) s PRAVE JEDNIM
//    profilem - 0 nebo 2+ je NALEZ, vypsat a NEPOCITAT jako 1.
//  - deska v drazce (is_board_material): 0, ZNAMA MEZERA (obchodni
//    otazka, ne geometricka - cekame na Roberta pres bot8), viditelne
//    vypsat pri kazdem vyskytu.
//  - vse ostatni (eurobox apod.): 0, potvrzeno bot8 (jen lezi v ramu,
//    nejsou sroubovane).
const fs = require("fs");
const path = require("path");
const THREE = require("three");
const { parseGlbMesh } = require("./2026-08-19_glb_real_geometry.js");

const KATALOG_DIR = "/opt/konfigurator/webapp/katalog";
const JOINT_PRICE_CZK = 110;
const ADJ_EPS = 0.5; // mm, tolerance pro "sousedi" (dotyk nebo vnoreni)

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
  const axes = ["x", "y", "z"];
  const f = axes.filter(ax => Math.abs(r[ax].overlap) <= eps);
  const o = axes.filter(ax => r[ax].overlap > eps);
  return f.length === 1 && o.length === 2;
}
// "sousedi" = dotyk (flush) NEBO vnoreni (plny obsah) - vsechny 3 osy
// maji overlap > -ADJ_EPS (zadna osa neni skutecne oddelena mezerou).
function isAdjacent(r) {
  return ["x", "y", "z"].every(ax => r[ax].overlap > -ADJ_EPS);
}

const dumpPath = process.argv[2];
if (!dumpPath) { console.error("Pouziti: node 2026-09-11_joint_count_dry_run.js <dump.json>"); process.exit(2); }
const dump = JSON.parse(fs.readFileSync(dumpPath, "utf8"));

const results = [];
dump.shapes.forEach(shape => {
  const rawParts = shape.parts.filter(p => !String(p.part_id).startsWith("car_body_"));
  const skippedCarBody = shape.parts.length - rawParts.length;
  const entries = rawParts.map(p => {
    const glb = dump.glb_map[p.part_id];
    if (!glb) return { missing: p.part_id };
    const file = path.join(KATALOG_DIR, glb);
    if (!fs.existsSync(file)) return { missing: p.part_id, file };
    const obj = parseGlbMesh(file);
    obj.position.fromArray(p.position);
    obj.quaternion.fromArray(p.quaternion);
    obj.scale.fromArray(p.scale || [1, 1, 1]);
    obj.updateMatrixWorld(true);
    return {
      part: p, object3d: obj, box: boxOf(obj),
      isProfile: !!dump.is_profile[p.part_id],
      isBracket: !!dump.is_bracket[p.part_id],
      isEndcap: !!dump.is_endcap[p.part_id],
      isBoard: !!dump.is_board[p.part_id],
    };
  });
  const missing = entries.filter(e => e.missing);
  const ok = entries.filter(e => !e.missing);

  const findings = [];
  let jointCount = 0;
  let boardCount = 0;

  const profiles = ok.filter(e => e.isProfile);
  const brackets = ok.filter(e => e.isBracket);
  const boards = ok.filter(e => e.isBoard);
  boardCount = boards.length;
  if (boardCount) findings.push(`ZNAMA MEZERA: ${boardCount}x deska (is_board_material) - 0 spoju, obchodni rozhodnuti ceka na Roberta`);

  // profil<->profil a profil<->uhelnik: geometricky flush pocet
  const profileLike = ok.filter(e => e.isProfile || e.isBracket);
  for (let i = 0; i < profileLike.length; i++) {
    for (let j = i + 1; j < profileLike.length; j++) {
      const a = profileLike[i], b = profileLike[j];
      if (!(a.isProfile || b.isProfile)) continue; // spojka-spojka se nepocita, jen pres profil
      const r = touchReport(a.box, b.box);
      if (isFlush(r)) jointCount++;
    }
  }

  // profil<->zaslepka: presne 1 na kus, s pojistkou poctu sousedu
  const endcaps = ok.filter(e => e.isEndcap);
  endcaps.forEach((ec, i) => {
    const adjacentProfiles = profiles.filter(pr => isAdjacent(touchReport(ec.box, pr.box)));
    if (adjacentProfiles.length === 1) {
      jointCount += 1;
    } else {
      findings.push(`NALEZ: zaslepka #${i} (${ec.part.part_id}, pos=${ec.part.position.map(v=>Math.round(v)).join(",")}) sousedi s ${adjacentProfiles.length} profily (ocekavano presne 1) - NEPOCITANO`);
    }
  });

  const result = {
    id: shape.id, name: shape.name,
    parts_total: shape.parts.length, car_body_skipped: skippedCarBody, glb_missing: missing.length,
    profiles: profiles.length, brackets: brackets.length, endcaps: endcaps.length, boards: boardCount,
    jointCount, jointCzk: jointCount * JOINT_PRICE_CZK,
    findings,
  };
  results.push(result);

  console.log(`\n=== id=${shape.id} "${shape.name}" ===`);
  console.log(`  dilu: ${result.parts_total} (car_body vynechano ${skippedCarBody}, chybi glb ${missing.length}), profilu ${result.profiles}, spojek ${result.brackets}, zaslepek ${result.endcaps}, desek ${result.boards}`);
  console.log(`  JOINT_COUNT=${jointCount}  JOINT_CZK=${result.jointCzk}`);
  if (missing.length) console.log(`  CHYBI GLB: ${[...new Set(missing.map(m=>m.missing))].join(", ")}`);
  result.findings.forEach(f => console.log(`  ${f}`));
});

console.log(`\n\n=== SOUHRN (${results.length} sestav) ===`);
results.forEach(r => console.log(`  id=${r.id} dilu=${r.parts_total} joint=${r.jointCount} (${r.jointCzk} Kc)${r.findings.length ? "  <-- " + r.findings.length + " nalez(u)" : ""}`));
const jc = results.map(r => r.jointCount);
const avg = jc.reduce((a,b)=>a+b,0) / jc.length;
console.log(`\nprumer joint_count: ${avg.toFixed(1)}, min: ${Math.min(...jc)} (id=${results[jc.indexOf(Math.min(...jc))].id}), max: ${Math.max(...jc)} (id=${results[jc.indexOf(Math.max(...jc))].id})`);
const withFindings = results.filter(r => r.findings.length);
console.log(`sestav s nalezem: ${withFindings.length}/${results.length}`);

fs.writeFileSync("/tmp/joint_dry_run_results.json", JSON.stringify(results, null, 2));
console.log("\nplny vysledek: /tmp/joint_dry_run_results.json");
