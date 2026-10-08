// Varianty D/E (jen vysky 120/170/220mm, BEZ 270mm) pro 5 nejnovejsich karoserii -
// bot16, 2026-09-02. Navazuje na jiz hotove A(zaklad)/B/C varianty (viz
// AGENTS_LOG.md "bot16 - 2026-09-01 - Vivaro OP31 od nuly + varianty B/C").
//
// METODA (na rozdil od B/C, ktere jen PRELABELOVALY box na UZ EXISTUJICI railY
// pozici): D/E POCITAJI railY POZICE PATER ZNOVU OD NULY (floor0 anchor beze
// zmeny, pak Y_rail_top(N+1)=Y_rail_top(N)+H_box(N)+60 vzorec, viz
// shape_geometry_methods.id=3 'pravidlo_vertikalni_patra_2026_08_31' - vzorec
// EMPIRICKY OVEREN 1:1 proti realnym datum vsech 5 variant A, diff=0.000mm),
// protoze cilem je vyuzit USPORU MISTA z mensich boxu (bez 270mm) k pripadnemu
// PRIDANI dalsich pater - presne to, co se stalo u FO31/VW25 B ("A vyuzila jen
// 2 ze 3 fyzicky moznych pater"). Nohy/X-Z pudorys/car_body 100% beze zmeny.
//
// D = maximalni DIVERZITA (pouzit vsechny 3 vysky 220/170/120, tall-to-short
//     zdola nahoru, pak doplnit zbyvajici budget 120mm patry navic).
// E = maximalni POCET KUSU (vsechna patra 120mm - zamerne, task explicitne
//     povoluje "mostly/all 120mm" pro E na rozdil od D).
//
// Kazde kandidatni NEJVYSSI patro overeno REALNOU kolizi (engine.collidesWithWalls)
// - box smi presahnout TOP_Y (viz box_muze_presahovat_zadni_profil_2026_08_31),
// nizsi patra jsou vzdy automaticky bezpecna (dukaz v AGENTS_LOG.md zaznamu).
const THREE = require("three");
const fs = require("fs");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
const PID_TO_H = {}; for (const [h, pid] of Object.entries(EUROBOX_PID)) PID_TO_H[pid] = +h;
function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (id === "product_3071") return KAT + "product_3071.glb";
  return KAT + id + ".glb";
}
function meshOf(p) {
  const m = parseGlbMesh(glbFor(p.part_id));
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}
function box3Of(p) { return new THREE.Box3().setFromObject(meshOf(p)); }
function isBoxPart(p) { return Object.values(EUROBOX_PID).includes(p.part_id); }
const legRoleRe = /^(predni-svislice|zadni-svislice-dolni|zadni-svislice-nad-zarezem|cap|spojnice-dolni|spojnice-horni|sloupek-pred-podbehem|spojnice-dolni-kratka|pricka-uzavreni-vyrezu|zaslepka.*)$/;

const SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad";
const VEHICLES = [
  { key: "PE25", id: 74, base: "Peugeot_Expert_PE25_2021-", baseName: "Peugeot e-Expert L1 PE25 (2021-)" },
  { key: "MB47", id: 83, base: "Mercedes_Vito_MB47_2014-", baseName: "Mercedes Vito MB47 (2014-)" },
  { key: "FO31", id: 111, base: "Ford_Custom_FO31_2023-", baseName: "Transit Custom L2 FO31" },
  { key: "VW25", id: 118, base: "Volkswagen_Transporter_VW25_2024-", baseName: "T7 VW25" },
  { key: "OP31", id: 136, base: "Opel_Vivaro_OP31_2020-", baseName: "Vivaro Electric L1 OP31" },
];

function newBoxPart(templateBox, hNew, railYCenter) {
  const railRole = templateBox.role;
  const origCenter = box3Of(templateBox).getCenter(new THREE.Vector3());
  const newPid = EUROBOX_PID[hNew];
  const probeMesh = parseGlbMesh(glbFor(newPid));
  probeMesh.position.set(0, 0, 0); probeMesh.quaternion.set(...templateBox.quaternion); probeMesh.scale.set(1, 1, 1);
  probeMesh.updateMatrixWorld(true);
  const probeBox = new THREE.Box3().setFromObject(probeMesh);
  const probeCenter = probeBox.getCenter(new THREE.Vector3());
  const targetYbottom = railYCenter + 15;
  const position = [
    origCenter.x - probeCenter.x,
    targetYbottom - probeBox.min.y - 12,
    origCenter.z - probeCenter.z,
  ];
  return { part_id: newPid, position, quaternion: templateBox.quaternion, scale: [1, 1, 1], role: railRole };
}
function cloneRailAt(templateParts, newY, newRoleSuffix, oldRoleSuffix) {
  return templateParts.map(p => ({
    part_id: p.part_id,
    position: [p.position[0], newY, p.position[2]],
    quaternion: p.quaternion, scale: p.scale,
    role: p.role.replace(oldRoleSuffix, newRoleSuffix),
  }));
}

function analyzeColumn(parts, col) {
  const floorIdx = new Set();
  for (const p of parts) {
    const m = new RegExp(`^nosnik-${col}-patro(\\d+)$`).exec(p.role || "");
    if (m) floorIdx.add(+m[1]);
  }
  const floors = [...floorIdx].sort((a, b) => a - b);
  const f0 = floors[0];
  const railTemplate = parts.filter(p => p.role === `nosnik-${col}-patro${f0}`);
  const connTemplate = parts.filter(p => p.role === `spojnice-${col}-patro${f0}`);
  const boxTemplate = parts.filter(p => p.role === `eurobox-${col}-patro${f0}`);
  const floorY0 = railTemplate[0].position[1];

  const railBoxes = railTemplate.map(box3Of);
  const zMin = Math.min(...railBoxes.map(b => b.min.z));
  const zMax = Math.max(...railBoxes.map(b => b.max.z));
  const legParts = parts.filter(p => legRoleRe.test(p.role || ""));
  const legsNear = z0 => legParts.filter(p => Math.abs(p.position[2] - z0) < 100);
  const legTopY = lp => {
    const rel = lp.filter(p => /^zadni-svislice/.test(p.role));
    if (!rel.length) return Infinity;
    return Math.max(...rel.map(p => box3Of(p).max.y));
  };
  const TOP_Y = Math.min(legTopY(legsNear(zMin)), legTopY(legsNear(zMax)));
  const MAXY = TOP_Y - 15;
  return { floorY0, railTemplate, connTemplate, boxTemplate, TOP_Y, MAXY, origFloorCount: floors.length, zMin, zMax };
}

// Fyzicky strop (physCeil) - stejna technika jako tmp_2026-08-31_batch_pipeline.js step7:
// tenka horizontalni "sonda" (slab) siroka jako CELY pudorys boxu (ne synteticky box mesh
// samotny - edge-crossing collidesWithWalls dava FALSE NEGATIVE, kdyz je box UZ CELY nad
// strechou, protoze pak zadna hrana nekrizi stenu), postupne posouvana nahoru po 1mm,
// dokud nezkoliduje - pak -2mm rezerva. Nezavisle na vysce boxu (ciste geometricky strop).
function measurePhysCeil(engine, colInfo) {
  const allBoxParts = colInfo.boxTemplate;
  let xMin = Infinity, xMax = -Infinity;
  allBoxParts.forEach(p => { const b = box3Of(p); xMin = Math.min(xMin, b.min.x); xMax = Math.max(xMax, b.max.x); });
  const zMin = colInfo.zMin, zMax = colInfo.zMax;
  const D = xMax - xMin, Zspan = zMax - zMin;
  const cx = (xMin + xMax) / 2, cz = (zMin + zMax) / 2;
  function slab(y) {
    const geo = new THREE.BoxGeometry(D, 10, Zspan);
    const mesh = new THREE.Mesh(geo);
    mesh.position.set(cx, y, cz);
    mesh.updateMatrixWorld(true);
    return mesh;
  }
  let y = Math.max(colInfo.TOP_Y - 50, 700), s = 0, collisionY = null;
  while (s < 800) {
    y += 1; s++;
    if (engine.collidesWithWalls(slab(y))) { collisionY = y; break; }
  }
  if (collisionY === null) return Infinity; // zadna kolize nalezena v rozumnem rozsahu
  const safeY = collisionY - 2;
  return safeY;
}

// heightsFn(i) -> nominal height (mm) for floor i (0-indexed), for i>=3 repeats last
// physCeil: realny fyzicky strop (viz measurePhysCeil) - JEN nejvyssi patro smi svym
// box-top tuhle hranici vyuzit (box_muze_presahovat_zadni_profil_2026_08_31), nizsi
// patra jsou vzdy <=TOP_Y-60 automaticky (dukaz v AGENTS_LOG.md).
// OPRAVA (bug #1, +12mm mezera - viz tmp_2026-08-31_batch_pipeline.js): eurobox
// ma 12mm "nozku" (nesting foot), ktera zapada 12mm POD rail top (railYs zde
// drzi railYCenter, railTop=railYCenter+15). Viditelna vyska boxu nad rail top
// je H_box-12, ne plna deklarovana H_box - puvodni "+60"/"+15+H" pouzivalo
// plne H bez odectu nozky, davalo kazde mezere +12mm navic (viz
// KOMPONENTY_EUROBOXY.md "Univerzalni +12mm chyba"). Spravne: dalsi railYCenter
// = soucasny + (H-12) + 30(mezera) + T(30, rail) = soucasny + H + 48.
const NEST_FOOT = 12;
function planColumn(colInfo, heightsFn, physCeil) {
  const { floorY0, railTemplate, connTemplate, boxTemplate, MAXY } = colInfo;
  const railYs = [floorY0];
  let i = 0;
  while (true) {
    const H = heightsFn(i);
    const nextY = railYs[i] + (H - NEST_FOOT) + 60;
    if (nextY > MAXY) break;
    railYs.push(nextY);
    i++;
    if (i > 20) break; // safety
  }
  let K = railYs.length;
  function boxTopAt(f) { return railYs[f] + 15 + (heightsFn(f) - NEST_FOOT); }
  // Osekej K, dokud posledni (nejvyssi) patro nesplni realny fyzicky strop.
  while (K > 0 && boxTopAt(K - 1) > physCeil + 1e-6) K--;
  function buildFloors(count) {
    const newParts = [];
    for (let f = 0; f < count; f++) {
      const H = heightsFn(f);
      const y = railYs[f];
      newParts.push(...cloneRailAt(railTemplate, y, `patro${f}`, /patro\d+$/));
      newParts.push(...cloneRailAt(connTemplate, y, `patro${f}`, /patro\d+$/));
      for (const bt of boxTemplate) {
        newParts.push(newBoxPart({ ...bt, role: bt.role.replace(/patro\d+$/, `patro${f}`) }, H, y));
      }
    }
    return newParts;
  }
  if (K === 0) return { count: 0, parts: [], railYs: [], heights: [] };
  return { count: K, parts: buildFloors(K), railYs: railYs.slice(0, K), heights: Array.from({ length: K }, (_, f) => heightsFn(f)) };
}

function selfCollisionCheck(nonCarBody) {
  const meshes = nonCarBody.map(meshOf);
  const boxes3 = meshes.map(m => new THREE.Box3().setFromObject(m));
  let unexpected = 0; const unexpectedPairs = [];
  for (let i = 0; i < boxes3.length; i++) {
    for (let j = i + 1; j < boxes3.length; j++) {
      const A = boxes3[i], B = boxes3[j];
      const ox = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
      const oy = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
      const oz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
      if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
        const pi = nonCarBody[i], pj = nonCarBody[j];
        const isBox = p => isBoxPart(p);
        const isRail = p => p.part_id === "Object_7" && /^(nosnik|spojnice)-sloupec\d+-patro\d+$/.test(p.role || "");
        const levelSuffix = role => (role || "").replace(/^(eurobox|nosnik|spojnice)-/, "");
        const sameLevel = (a, b) => levelSuffix(a.role) === levelSuffix(b.role);
        const boxOnOwnRail = (isBox(pi) && isRail(pj) && sameLevel(pi, pj)) || (isBox(pj) && isRail(pi) && sameLevel(pj, pi));
        const rolesOk = /zaslepka|cap/.test(pi.role || "") || /zaslepka|cap/.test(pj.role || "") || boxOnOwnRail;
        if (!rolesOk) { unexpected++; unexpectedPairs.push([pi.role, pj.role, pi.part_id, pj.part_id]); }
      }
    }
  }
  return { unexpected, unexpectedPairs };
}

function gen2d(allParts) {
  const nonCarBody = allParts.filter(p => !p.part_id.startsWith("car_body"));
  const boxes = nonCarBody.map(p => { const b = box3Of(p); return { min: [b.min.x, b.min.y, b.min.z], max: [b.max.x, b.max.y, b.max.z] }; });
  let gx = [1e9, -1e9], gy = [1e9, -1e9], gz = [1e9, -1e9];
  boxes.forEach(b => {
    gx[0] = Math.min(gx[0], b.min[0]); gx[1] = Math.max(gx[1], b.max[0]);
    gy[0] = Math.min(gy[0], b.min[1]); gy[1] = Math.max(gy[1], b.max[1]);
    gz[0] = Math.min(gz[0], b.min[2]); gz[1] = Math.max(gz[1], b.max[2]);
  });
  const dims = { depthX: gx[1] - gx[0], heightY: gy[1] - gy[0], lengthZ: gz[1] - gz[0] };
  const okH = dims.heightY > 900 && dims.heightY < 1500;
  const okD = dims.depthX > 250 && dims.depthX < 420;
  return { dims, okH, okD };
}

const results = {};
for (const v of VEHICLES) {
  console.log(`\n\n===== ${v.key} =====`);
  const dataA = JSON.parse(fs.readFileSync(`${SCRATCH}/pa_${v.id}.json`, "utf8"));
  const parts = dataA.parts;
  const engine = createEngine(v.base);
  const carBody = parts.filter(p => p.part_id.startsWith("car_body"));
  const legsAndCaps = parts.filter(p => legRoleRe.test(p.role || ""));

  const colSet = new Set();
  for (const p of parts) {
    const m = /^(?:eurobox|nosnik|spojnice)-(sloupec\d+)-patro(\d+)$/.exec(p.role || "");
    if (m) colSet.add(m[1]);
  }
  const cols = [...colSet].sort();
  results[v.key] = { legsAndCapsCount: legsAndCaps.length, columns: {} };

  const colPlans = {};
  for (const col of cols) {
    const colInfo = analyzeColumn(parts, col);
    const physCeil = measurePhysCeil(engine, colInfo);
    console.log(`  ${col}: floorY0=${colInfo.floorY0.toFixed(2)} TOP_Y=${colInfo.TOP_Y.toFixed(2)} MAXY=${colInfo.MAXY.toFixed(2)} physCeil=${physCeil.toFixed(2)} origFloors=${colInfo.origFloorCount}`);
    const planE = planColumn(colInfo, () => 120, physCeil);
    console.log(`    E: floors=${planE.count} heights=${JSON.stringify(planE.heights)} topBox=${planE.count ? (planE.railYs[planE.count - 1] + 15 + planE.heights[planE.count - 1]).toFixed(1) : "-"}`);
    const dSeq = [220, 170, 120];
    const planD = planColumn(colInfo, (i) => dSeq[Math.min(i, 2)], physCeil);
    console.log(`    D: floors=${planD.count} heights=${JSON.stringify(planD.heights)} topBox=${planD.count ? (planD.railYs[planD.count - 1] + 15 + planD.heights[planD.count - 1]).toFixed(1) : "-"}`);
    colPlans[col] = { planD, planE, TOP_Y: colInfo.TOP_Y, MAXY: colInfo.MAXY, physCeil, origFloorCount: colInfo.origFloorCount };
    results[v.key].columns[col] = { TOP_Y: colInfo.TOP_Y, MAXY: colInfo.MAXY, physCeil, origFloorCount: colInfo.origFloorCount, D: { count: planD.count, heights: planD.heights }, E: { count: planE.count, heights: planE.heights } };
  }

  for (const tag of ["D", "E"]) {
    const key = tag === "D" ? "planD" : "planE";
    const columnParts = cols.flatMap(c => colPlans[c][key].parts);
    const allParts = [...carBody, ...legsAndCaps, ...columnParts];
    const nonCarBody = allParts.filter(p => !p.part_id.startsWith("car_body"));
    const collidesWalls = engine.collidesWithWalls((() => { const g = new THREE.Group(); nonCarBody.forEach(p => g.add(meshOf(p))); g.updateMatrixWorld(true); return g; })());
    const self = selfCollisionCheck(nonCarBody);
    const g2 = gen2d(allParts);
    const totalBoxes = columnParts.filter(isBoxPart).length;
    const byHeight = {};
    columnParts.filter(isBoxPart).forEach(p => { const h = PID_TO_H[p.part_id]; byHeight[h] = (byHeight[h] || 0) + 1; });
    const ok = !collidesWalls && self.unexpected === 0 && g2.okH && g2.okD;
    console.log(`  === ${v.key} ${tag}: totalBoxes=${totalBoxes} byHeight=${JSON.stringify(byHeight)} collidesWalls=${collidesWalls} unexpectedSelf=${self.unexpected} dims=${JSON.stringify(g2.dims)} okH=${g2.okH} okD=${g2.okD} => OK=${ok}`);
    if (self.unexpected) console.log("    unexpectedPairs:", self.unexpectedPairs);
    fs.writeFileSync(`${SCRATCH}/de_parts_${v.key}_${tag}.json`, JSON.stringify(allParts, null, 1));
    results[v.key][tag] = { totalBoxes, byHeight, collidesWalls, unexpectedSelf: self.unexpected, dims: g2.dims, ok };
  }
}

fs.writeFileSync(`${SCRATCH}/de_plan_summary.json`, JSON.stringify(results, null, 1));
console.log("\nHOTOVO - plan+verifikace ulozeny do de_plan_summary.json");
