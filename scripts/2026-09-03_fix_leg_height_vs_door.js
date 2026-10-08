// Oprava vysky noh podle oficialni vysky otvoru zadnich dveri
// (shape_geometry_methods.id=8, "prizpusobeni-vysky-nohy-vysce-dveri").
//
// MERICI ROVINA = KONEC PROFILU (Robert, 2026-09-03, pres bot3, doslovne:
// "merit ke konci profilu, ne k celu zaslepky (zaslepka je jen kosmeticka,
// nenosna)"). Cil: horni konec profilu presne na H_cil = dvere - 30mm.
// Zaslepka (product_3071) se posouva S profilem a drzi si svuj puvodni
// 3mm presah - do limitu se NEPOCITA.
//
// Nahrazuje drivejsi Python verzi (bot16, napsana ale nikdy nespustena),
// ktera mela tri vady:
//   1. merila vrchol jako cap.position.y (tj. celo zaslepky) -> hlasila
//      74/120 poruseni, z toho 73 falesnych;
//   2. zkracovala jen dily do 10mm od vrcholu sloupce - druha noha teze
//      Z-skupiny mohla zustat nad limitem;
//   3. nijak nehlidala, ze pod novym koncem profilu zustanou vsechna
//      patra/nosniky (tvrdila to jen v komentari).
//
// READ-ONLY dokud se nezavola s --out (ten jen ULOZI navrh do JSON).
//
// Pouziti:
//   node scripts/2026-09-03_fix_leg_height_vs_door.js <all_asm.json> <car_bodies.json> <door_heights.json> [--out navrh.json]

const fs = require("fs");
const THREE = require("/opt/konfigurator/node_modules/three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { makeCollisionModule } = require("/opt/konfigurator/scripts/2026-09-01_collision_module_factory.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const T = 30;
const BASE_UNIT = 1000;
const MARGIN = 30;    // bezpecnostni rezerva pod vyskou otvoru dveri
const EPS = 1.0;

const [asmPath, cbPath, doorPath] = process.argv.slice(2, 5);
const outIdx = process.argv.indexOf("--out");
const outPath = outIdx > 0 ? process.argv[outIdx + 1] : null;

const input = JSON.parse(fs.readFileSync(asmPath, "utf8"));
const carBodies = JSON.parse(fs.readFileSync(cbPath, "utf8"));
const doorH = JSON.parse(fs.readFileSync(doorPath, "utf8"));
const modelNames = input.m2n || {};   // car_models.id -> name (obsahuje vendor kod)

const meshCache = {};
function boxOf(part) {
  const pid = part.part_id;
  if (!(pid in meshCache)) {
    const f = KAT + pid + ".glb";
    meshCache[pid] = fs.existsSync(f) ? parseGlbMesh(f) : null;
  }
  const m = meshCache[pid];
  if (!m) return null;
  m.position.set(part.position[0], part.position[1], part.position[2]);
  const q = part.quaternion || [0, 0, 0, 1];
  m.quaternion.set(q[0], q[1], q[2], q[3]);
  const s = part.scale || [1, 1, 1];
  m.scale.set(s[0], s[1], s[2]);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}
function ov(a, b) {
  const o = {};
  for (const ax of ["x", "y", "z"]) o[ax] = Math.min(a.max[ax], b.max[ax]) - Math.max(a.min[ax], b.min[ax]);
  return o;
}
const isEmbedded = (o) => o.x > EPS && o.y > EPS && o.z > EPS;

// je to SVISLY nosny profil (Object_7 delkou podel Y)?
function isVertical(part, b) {
  if (part.part_id !== "Object_7") return false;
  return (b.max.y - b.min.y) > (b.max.x - b.min.x) + 1 && (b.max.y - b.min.y) > (b.max.z - b.min.z) + 1;
}

// POZOR: kod vendoru NENI v car_bodies.name (tam je jen napr.
// "FO30_L (leva stena, samostatne)"), ale az v car_models.name - proto
// cesta car_body_<id> -> car_bodies.model_id -> car_models.name.
// (Prvni verze hledala kod primo v car_bodies.name a nasla proto 0 radku.)
function codeOf(row) {
  for (const p of row.parts) {
    const m = /^car_body_(\d+)$/.exec(p.part_id || "");
    if (!m) continue;
    const modelId = (carBodies[m[1]] || {}).model_id;
    const modelName = modelId != null ? (modelNames[String(modelId)] || "") : "";
    const cm = /\[([A-Z]{2}\d{2})\]/.exec(modelName);
    if (cm) return cm[1];
  }
  return null;
}
function bodyBaseFor(row) {
  for (const p of row.parts) {
    const m = /^car_body_(\d+)$/.exec(p.part_id || "");
    if (!m) continue;
    const rec = carBodies[m[1]];
    if (rec && rec.glb) return KAT + rec.glb.replace(/_(L|R_D|B)\.glb$/, "").replace(/\.glb$/, "");
  }
  return null;
}
const colCache = {};
function collisionFor(base) {
  if (!(base in colCache)) {
    try { colCache[base] = makeCollisionModule(base); } catch (e) { colCache[base] = { error: e.message }; }
  }
  return colCache[base];
}

const results = [];
const patched = {};

for (const row of input.rows) {
  const code = codeOf(row);
  if (!code || !(code in doorH)) continue;
  const limit = doorH[code] - MARGIN;

  // vsechny svisle nosne profily nad limitem
  const boxes = new Map();
  for (const p of row.parts) {
    if (!p.position || !p.role) continue;
    const b = boxOf(p);
    if (b) boxes.set(p, b);
  }
  const nadLimit = [];
  for (const [p, b] of boxes) if (isVertical(p, b) && b.max.y > limit + 0.5) nadLimit.push({ p, b });
  if (!nadLimit.length) continue;

  const rec = { id: row.id, name: row.name, code, door: doorH[code], limit, zmeny: [], stav: null, kontroly: {} };

  // Novy konec profilu nesmi klesnout pod NEJVYSSI DIL, KTERY PROFIL NESE
  // (nosniky, spojnice, pricky) - jinak by patro viselo nad zkracenou nohou.
  // EUROBOXY se sem ZAMERNE nepocitaji: jsou to naklad lezici na polici, ne
  // konstrukce - horni box bezne precnehuje nad konec nohy (u id=91 sahá do
  // 1192mm, zatimco nejvyssi nosnik je na 1019mm) a nakladá/vyklada se
  // jednotlive, takze vysku RAMU pro pruchod dvermi neomezuje.
  // Zaslepky se posouvaji s profilem, karoserie neni soucast sestavy.
  let maxJine = -Infinity, maxJineRole = null;
  for (const [p, b] of boxes) {
    if (nadLimit.some((e) => e.p === p)) continue;
    if (p.part_id === "product_3071") continue;
    if (/^car_body_/.test(p.part_id || "")) continue;
    if (/^eurobox/.test(p.role || "")) continue;
    if (b.max.y > maxJine) { maxJine = b.max.y; maxJineRole = p.role; }
  }
  if (maxJine > limit) {
    rec.stav = "BLOKOVANO - profil nese dil nad limitem (" + maxJineRole + " Y=" + maxJine.toFixed(0) + " > limit " + limit + ")";
    results.push(rec); continue;
  }

  // navrh: zkratit KAZDY svisly profil nad limitem na svuj vlastni presah
  const novéParts = row.parts.map((p) => JSON.parse(JSON.stringify(p)));
  const idxOf = new Map(); row.parts.forEach((p, i) => idxOf.set(p, i));
  for (const { p, b } of nadLimit) {
    const shift = b.max.y - limit;
    const np = novéParts[idxOf.get(p)];
    const sc = (p.scale || [1, 1, 1]).slice();
    // delka profilu je podel lokalni Y (Object_7 = 30 x 1000 x 30, centrovany)
    sc[1] = +(sc[1] - shift / BASE_UNIT).toFixed(6);
    np.scale = sc;
    np.position = [p.position[0], +(p.position[1] - shift / 2).toFixed(4), p.position[2]];
    rec.zmeny.push({ role: p.role, z: Math.round(p.position[2]), top_pred: +b.max.y.toFixed(1), top_po: limit, zkraceno: +shift.toFixed(1) });
    // zaslepka TOHOTO profilu = shodne X i Z, sedici na jeho puvodnim konci
    for (const [q, qb] of boxes) {
      if (q.part_id !== "product_3071") continue;
      if (Math.abs(q.position[0] - p.position[0]) > 1 || Math.abs(q.position[2] - p.position[2]) > 1) continue;
      if (Math.abs(qb.max.y - (b.max.y + 3)) > 4) continue;   // 3mm limecek nad koncem profilu
      const nq = novéParts[idxOf.get(q)];
      nq.position = [q.position[0], +(q.position[1] - shift).toFixed(4), q.position[2]];
    }
  }

  // ---- OVERENI: POROVNANI PRED/PO, hlasi se jen NOVE kolize ----
  // Sestavy obsahuji zamerne "zanoreni", ktera Box3 nerozezna od skutecne
  // kolize (skill 3d-scena-spoje, metodika bod 8): zaslepka zastrcena 6mm do
  // profilu a eurobox s 12mm nozkou zapadajici do luzka nosniku - to druhe je
  // Robertem potvrzena finalni pozice. Absolutni test by je hlasil jako vadu.
  // Rozhoduje proto DELTA: kolize, ktera v datech byla uz pred upravou, neni
  // nas nalez; blokuje jen kolize, kterou by uprava NOVE zavedla.
  const embedSet = (parts) => {
    const bs = parts.filter((p) => p.position && p.role && !/^car_body_/.test(p.part_id || ""))
      .map((p) => ({ p, b: boxOf(p) })).filter((e) => e.b);
    const out = new Set();
    for (let i = 0; i < bs.length; i++) {
      for (let j = i + 1; j < bs.length; j++) {
        if (isEmbedded(ov(bs[i].b, bs[j].b))) {
          out.add([bs[i].p.role, Math.round(bs[i].p.position[2]), bs[j].p.role, Math.round(bs[j].p.position[2])].join("|"));
        }
      }
    }
    return out;
  };
  const pred = embedSet(row.parts), po = embedSet(novéParts);
  const nove = [...po].filter((k) => !pred.has(k));
  rec.kontroly.self_kolize = nove.length ? "SELHALO (nove: " + nove[0] + ")" : "OK (nove kolize 0, existujicich beze zmeny " + pred.size + ")";

  const base = bodyBaseFor(row);
  if (!base) rec.kontroly.karoserie = "NELZE";
  else {
    const mod = collisionFor(base);
    if (mod.error) rec.kontroly.karoserie = "NELZE - " + mod.error;
    else {
      // zkraceni jde smerem DOLU - kolize muze jen ubyt, presto overit
      let hit = null;
      for (const { p } of nadLimit) {
        const np = novéParts[idxOf.get(p)];
        if (mod.collidesWithWalls(mod.buildLegObject([np]))) { hit = np.role; break; }
      }
      rec.kontroly.karoserie = hit ? "KOLIZE (" + hit + ")" : "OK";
    }
  }
  // vsechny profily skutecne na/pod limitem?
  const zbyva = novéParts.filter((p) => p.position && p.role && !/^car_body_/.test(p.part_id || ""))
    .map((p) => ({ p, b: boxOf(p) })).filter((e) => e.b)
    .filter((e) => isVertical(e.p, e.b) && e.b.max.y > limit + 0.5).length;
  rec.kontroly.pod_limitem = zbyva === 0 ? "OK" : "SELHALO (" + zbyva + " profilu porad nad limitem)";

  const ok = rec.kontroly.self_kolize.startsWith("OK") && rec.kontroly.karoserie === "OK" && rec.kontroly.pod_limitem === "OK";
  rec.stav = ok ? "OPRAVENO" : "BLOKOVANO";
  if (ok) patched[row.id] = { id: row.id, name: row.name, parts: novéParts };
  results.push(rec);
}

console.log("=== NAVRH UPRAVY VYSKY NOH (merici rovina = konec profilu) ===\n");
for (const r of results) {
  console.log("id=" + r.id + "  " + r.code + "  " + String(r.name).slice(0, 46));
  console.log("   dvere=" + r.door + "mm  limit=" + r.limit + "mm   stav: " + r.stav);
  if (Object.keys(r.kontroly).length) console.log("   kontroly: " + JSON.stringify(r.kontroly));
  for (const z of r.zmeny) console.log("      " + z.role.padEnd(28) + " z=" + String(z.z).padStart(7) + "  top " + z.top_pred + " -> " + z.top_po + " (zkraceno o " + z.zkraceno + "mm)");
}
console.log("\n=== SOUHRN ===");
console.log("radku nad limitem: " + results.length +
  "  | opraveno: " + results.filter((r) => r.stav === "OPRAVENO").length +
  "  | blokovano: " + results.filter((r) => /BLOKOVANO/.test(r.stav)).length);
if (outPath) { fs.writeFileSync(outPath, JSON.stringify(patched, null, 1)); console.log("navrh -> " + outPath + "  (DO DB SE NIC NEZAPSALO)"); }
