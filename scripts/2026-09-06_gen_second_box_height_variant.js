// Generuje DRUHOU variantu skladby vysek boxu pro karoserie, ktere maji
// zatim jen 1 (Robert 2026-09-06: "Vsude kde mas pouze 1 variantu musis
// pridat aspon 2", "varianty delame proto aby byl od sebe odlisne",
// "maimalne odlisne"). Reuzivá presne stejny overeny algoritmus jako
// scripts/tmp_2026-09-02_bot16_de_build.js (planColumn/measurePhysCeil) -
// jen zobecneny pro DVE ruzne rolove konvence nalezene v datech
// (nosnik-sloupecN-patroM vs nosnik-colN-pM) a pro cteni primo z DB dumpu
// (pa_data/pa_<id>.json), ne z hardcoded seznamu 5 vozidel. Vysledek
// (70/70 OK, id 192-261) + plny postup viz AGENTS_LOG.md 2026-09-06 22:45.
//
// ARCHIVNI KOPIE - skript ocekava scratch vstupy, ktere uz v repu nejsou
// (byly v /tmp scratchpadu tehdejsi session, ne verzovane):
//   glb_map.json    - {part_id: skutecny_glb_soubor} z `SELECT id, glb_file
//                      FROM shop_products WHERE glb_file IS NOT NULL`
//                      (part_id != nazev souboru u spousty dilu)
//   targets.json    - [{assembly_id, car_body, mix, car_body_base, ...}]
//                      pro kazdou karoserii s 1 variantou (viz artefakt
//                      "Skladby boxů" pro aktualni seznam)
//   pa_data/pa_<assembly_id>.json - {parts: [...]} dump product_assemblies.data
// Pro opakovani/rozsireni na dalsi karoserie znovu vygeneruj tyhle 3 vstupy
// stejnym zpusobem (viz AGENTS_LOG.md zaznam pro presne SQL dotazy).
const THREE = require("three");
const fs = require("fs");
const path = require("path");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const EUROBOX_PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
const PID_TO_H = {}; for (const [h, pid] of Object.entries(EUROBOX_PID)) PID_TO_H[pid] = +h;
// part_id != nazev GLB souboru pro spoustu dilu (napr. product_3045 ->
// product_2895.glb, viz AGENTS_LOG.md) - realna mapa ze shop_products.glb_file,
// predpocitana do souboru (viz prikaz vedle tohoto skriptu).
const GLB_MAP = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-konfigurator/cd1e4f98-59ca-4757-a63c-ad69ec4e8fb4/scratchpad/glb_map.json", "utf8"));
function glbFor(id) {
  if (id === "Object_7") return KAT + "Object_7.glb";
  if (GLB_MAP[id]) return KAT + GLB_MAP[id];
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

// Dve rolove konvence pozorovane v datech - detekujeme a pouzijeme STEJNOU
// konvenci, jakou uz ma dana sestava, aby nove sloupce vypadaly konzistentne.
const COL_RE = /^(nosnik|spojnice|eurobox)-(?:sloupec(\d+)-patro(\d+)|col(\d+)-p(\d+))$/;
function parseColRole(role) {
  const m = COL_RE.exec(role || "");
  if (!m) return null;
  const kind = m[1];
  const isLong = m[2] !== undefined;
  return { kind, col: +(isLong ? m[2] : m[4]), floor: +(isLong ? m[3] : m[5]), long: isLong };
}
function makeColRole(kind, col, floor, long) {
  return long ? `${kind}-sloupec${col}-patro${floor}` : `${kind}-col${col}-p${floor}`;
}

function analyzeColumn(parts, colIdx, long) {
  const roleAt = (kind, floor) => makeColRole(kind, colIdx, floor, long);
  const railTemplate = parts.filter(p => p.role === roleAt("nosnik", 0));
  const connTemplate = parts.filter(p => p.role === roleAt("spojnice", 0));
  const boxTemplate = parts.filter(p => p.role === roleAt("eurobox", 0));
  const floorY0 = railTemplate[0].position[1];

  const railBoxes = railTemplate.map(box3Of);
  const zMin = Math.min(...railBoxes.map(b => b.min.z));
  const zMax = Math.max(...railBoxes.map(b => b.max.z));
  // "noha" = cokoli neni sloupcovy dil (blacklist, ne whitelist - zachyti i
  // uhelnik-nohaN/zaslepka-*/pricka-*, cokoli specificke pro danou sestavu)
  const legParts = parts.filter(p => !parseColRole(p.role) && !(p.part_id || "").startsWith("car_body_"));
  const legsNear = z0 => legParts.filter(p => Math.abs(p.position[2] - z0) < 100);
  const legTopY = lp => {
    const rel = lp.filter(p => /zadni-svislice/.test(p.role || ""));
    if (!rel.length) return Infinity;
    return Math.max(...rel.map(p => box3Of(p).max.y));
  };
  const TOP_Y = Math.min(legTopY(legsNear(zMin)), legTopY(legsNear(zMax)));
  const MAXY = TOP_Y - 15;
  return { floorY0, railTemplate, connTemplate, boxTemplate, TOP_Y, MAXY, zMin, zMax };
}

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
  if (collisionY === null) return Infinity;
  return collisionY - 2;
}

const NEST_FOOT = 12;
function newBoxPart(templateBox, hNew, railYCenter, role) {
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
  return { part_id: newPid, position, quaternion: templateBox.quaternion, scale: [1, 1, 1], role };
}
function cloneRailAt(templateParts, newY, role) {
  return templateParts.map(p => ({ part_id: p.part_id, position: [p.position[0], newY, p.position[2]], quaternion: p.quaternion, scale: p.scale, role }));
}

function planColumn(colInfo, heightsFn, physCeil) {
  const { floorY0, MAXY } = colInfo;
  const railYs = [floorY0];
  let i = 0;
  while (true) {
    const H = heightsFn(i);
    const nextY = railYs[i] + (H - NEST_FOOT) + 60;
    if (nextY > MAXY) break;
    railYs.push(nextY);
    i++;
    if (i > 20) break;
  }
  let K = railYs.length;
  function boxTopAt(f) { return railYs[f] + 15 + (heightsFn(f) - NEST_FOOT); }
  while (K > 0 && boxTopAt(K - 1) > physCeil + 1e-6) K--;
  return { count: K, railYs: railYs.slice(0, K), heights: Array.from({ length: K }, (_, f) => heightsFn(f)) };
}

function buildColumnParts(colInfo, plan, colIdx, long) {
  const parts = [];
  for (let f = 0; f < plan.count; f++) {
    const y = plan.railYs[f], H = plan.heights[f];
    parts.push(...cloneRailAt(colInfo.railTemplate, y, makeColRole("nosnik", colIdx, f, long)));
    parts.push(...cloneRailAt(colInfo.connTemplate, y, makeColRole("spojnice", colIdx, f, long)));
    for (const bt of colInfo.boxTemplate) {
      parts.push(newBoxPart(bt, H, y, makeColRole("eurobox", colIdx, f, long)));
    }
  }
  return parts;
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
        const isRail = p => p.part_id === "Object_7" && parseColRole(p.role) && parseColRole(p.role).kind !== "eurobox";
        const levelOf = p => { const pc = parseColRole(p.role); return pc ? `${pc.col}|${pc.floor}` : (p.role || ""); };
        const sameLevel = (a, b) => levelOf(a) === levelOf(b);
        const boxOnOwnRail = (isBox(pi) && isRail(pj) && sameLevel(pi, pj)) || (isBox(pj) && isRail(pi) && sameLevel(pj, pi));
        // uhelnik (rohova spojka, montazni kovani) se dotyka/mirne prekryva
        // svuj nosny profil ZAMERNE (stejny duvod jako box-na-vlastnim-railu) -
        // overeno, ze presne tenhle typ prekryvu existuje uz i v NEZMENENYCH
        // datech puvodni varianty A (spojnice-dolni/uhelnik-nohaN), tedy neni
        // to nic, co by zavedla tahle generace noveho patra.
        // vypln-* (MDF vyplne horniho bloku) se montuji PRIMO na nohu
        // (predni-svislice) - stejny duvod jako uhelnik vyse, overeno
        // v NEZMENENYCH datech puvodni varianty A (K-122).
        const rolesOk = /zaslepka|cap|uhelnik|vypln/.test(pi.role || "") || /zaslepka|cap|uhelnik|vypln/.test(pj.role || "") || boxOnOwnRail;
        if (!rolesOk) { unexpected++; unexpectedPairs.push([pi.role, pj.role, pi.part_id, pj.part_id]); }
      }
    }
  }
  return { unexpected, unexpectedPairs };
}

function gen2dSanity(allParts) {
  const nonCarBody = allParts.filter(p => !(p.part_id || "").startsWith("car_body"));
  let gx = [1e9, -1e9], gy = [1e9, -1e9], gz = [1e9, -1e9];
  nonCarBody.forEach(p => {
    const b = box3Of(p);
    gx[0] = Math.min(gx[0], b.min.x); gx[1] = Math.max(gx[1], b.max.x);
    gy[0] = Math.min(gy[0], b.min.y); gy[1] = Math.max(gy[1], b.max.y);
    gz[0] = Math.min(gz[0], b.min.z); gz[1] = Math.max(gz[1], b.max.z);
  });
  const dims = { depthX: gx[1] - gx[0], heightY: gy[1] - gy[0], lengthZ: gz[1] - gz[0] };
  return { dims, okH: dims.heightY > 400 && dims.heightY < 1600, okD: dims.depthX > 200 && dims.depthX < 450 };
}

function mixString(colFinal) {
  // stejny format jako existujici nazvy: "boxy43-270x2-170x3-..." - secti
  // pocet boxu KAZDE vysky napric VSEMI sloupci, seradit sestupne dle vysky
  const counts = {};
  colFinal.forEach(c => c.heights.forEach(h => { counts[h] = (counts[h] || 0) + c.N; }));
  return Object.keys(counts).map(Number).sort((a, b) => b - a).map(h => `${h}x${counts[h]}`).join("-");
}

function buildVariant(engine, struct, heightsFn) {
  const allParts = [...struct.carBodyParts, ...struct.legParts];
  const colFinal = [];
  for (const c of struct.columns) {
    const physCeil = measurePhysCeil(engine, c.info);
    let plan = planColumn(c.info, heightsFn, physCeil);
    // Backoff proti FIXNIM dilum navic (napr. podelnik horniho bloku u K-122),
    // ktere nejsou soucasti nohy/car_body a planColumn/measurePhysCeil o nich
    // neví - stejny princip jako wall-collision backoff v tmp_2026-09-01_
    // bc_build.js, jen misto steny testujeme proti struct.legParts.
    while (plan.count > 0) {
      const colParts = buildColumnParts(c.info, plan, c.colIdx, c.long);
      const self = selfCollisionCheck([...struct.legParts, ...colParts]);
      if (self.unexpected === 0) { plan._parts = colParts; break; }
      plan = { count: plan.count - 1, railYs: plan.railYs.slice(0, -1), heights: plan.heights.slice(0, -1) };
    }
    if (plan.count === 0) return null;
    allParts.push(...(plan._parts || buildColumnParts(c.info, plan, c.colIdx, c.long)));
    colFinal.push({ colIdx: c.colIdx, N: c.info.connTemplate.length - 1, heights: plan.heights });
  }
  const nonCarBody = allParts.filter(p => !(p.part_id || "").startsWith("car_body"));
  const g = new THREE.Group();
  nonCarBody.forEach(p => g.add(meshOf(p)));
  g.updateMatrixWorld(true);
  const collidesWalls = engine.collidesWithWalls(g);
  const self = selfCollisionCheck(nonCarBody);
  const g2 = gen2dSanity(allParts);
  const mix = mixString(colFinal);
  const ok = !collidesWalls && self.unexpected === 0 && g2.okH && g2.okD;
  return { allParts, colFinal, mix, collidesWalls, unexpectedSelf: self.unexpected, unexpectedPairs: self.unexpectedPairs, dims: g2.dims, ok };
}

function extractStructure(parts) {
  const carBodyParts = parts.filter(p => (p.part_id || "").startsWith("car_body_"));
  const legParts = parts.filter(p => !parseColRole(p.role) && !(p.part_id || "").startsWith("car_body_"));
  const colMap = new Map();
  parts.forEach(p => { const pc = parseColRole(p.role); if (pc) colMap.set(pc.col, pc.long); });
  const columns = [...colMap.entries()].sort((a, b) => a[0] - b[0]).map(([colIdx, long]) => ({
    colIdx, long, info: analyzeColumn(parts, colIdx, long),
  }));
  return { carBodyParts, legParts, columns };
}

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/cd1e4f98-59ca-4757-a63c-ad69ec4e8fb4/scratchpad";
const targets = JSON.parse(fs.readFileSync(`${SCRATCH}/targets.json`, "utf8"));

fs.mkdirSync(`${SCRATCH}/variant_parts`, { recursive: true });
const results = [];
for (const t of targets) {
  const label = `${t.assembly_id} ${t.car_body}`;
  try {
    const data = JSON.parse(fs.readFileSync(`${SCRATCH}/pa_data/pa_${t.assembly_id}.json`, "utf8"));
    const struct = extractStructure(data.parts);
    const engine = createEngine(t.car_body_base);
    // Strategie pro DRUHOU variantu: E (vse 120mm, max pocet beden) je
    // preferovana - jednoduchá, komercne uzitecna, skoro vzdy validni a
    // skoro vzdy odlisna od varianty A. Kdyz selze/neni odlisna, zkus D
    // (max diverzita bez 270mm).
    const candidates = [
      { tag: "E", fn: () => 120 },
      { tag: "D", fn: (i) => [220, 170, 120][Math.min(i, 2)] },
    ];
    let chosen = null;
    for (const cand of candidates) {
      const built = buildVariant(engine, struct, cand.fn);
      if (built && built.ok && built.mix !== t.mix) { chosen = { tag: cand.tag, ...built }; break; }
    }
    if (!chosen) {
      results.push({ ...t, status: "FAIL", reason: "zadna kandidatni vyska-strategie neprosla/neni odlisna" });
      console.log(`${label}: FAIL (no valid distinct candidate)`);
      continue;
    }
    fs.writeFileSync(`${SCRATCH}/variant_parts/${t.assembly_id}_${chosen.tag}.json`, JSON.stringify(chosen.allParts));
    results.push({ ...t, status: "OK", tag: chosen.tag, new_mix: chosen.mix, dims: chosen.dims });
    console.log(`${label}: OK tag=${chosen.tag} mix=${chosen.mix}`);
  } catch (e) {
    results.push({ ...t, status: "ERROR", reason: e.message });
    console.log(`${label}: ERROR ${e.message}`);
  }
}
fs.writeFileSync(`${SCRATCH}/gen_results.json`, JSON.stringify(results, null, 1));
const okCount = results.filter(r => r.status === "OK").length;
console.log(`\nHOTOVO: ${okCount}/${results.length} OK`);
