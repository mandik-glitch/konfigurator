// JEDNORAZOVY orchestrator orientace karoserii (bot22 2026-09-05).
// Robert: "proc se neudela script ktery jednou provzdy poresi" - misto
// rucnich davek 180-flip po jednom aute.
//
// Co dela:
//  1. Audit orientace VSECH karoserii (B_midZ z realne GLB geometrie,
//     stejne kriterium jako 2026-08-31_car_body_orientation_audit.js:
//     B_midZ > +50 = NEEDS_FLIP, < -50 = OK).
//  2. Pro kazdou NEEDS_FLIP: zaloha 3 GLB (L/R_D/B) + baked 180Y flip
//     (POSITION+NORMAL (x,y,z)->(-x,y,-z), overena technika z
//     flip_expert_vito_180.js). Dedup podle realpath (sdileny/hardlink
//     soubor se flipne max jednou - ochrana proti dvojflipu).
//  3. Vypise flipnute car_body IDs -> /tmp/flipped_cb_ids.json
//     (navazuje python skript, ktery prepocita regaly v sestavach:
//     car_body party zustavaji na identite, ostatni se flipnou).
//  4. Re-audit -> overi 0 zbylych NEEDS_FLIP.
//
// Rezimy: --dry-run (jen report) | --only <substr> (jedna karoserie) | --all
const fs = require("fs");
const path = require("path");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const BACKUP_DIR = "/opt/konfigurator/backups/2026-09-05_mass_orientation_flip";
const AUDIT = "/tmp/orient_audit_fresh.jsonl";

const arg = process.argv.slice(2);
const DRY = arg.includes("--dry-run");
const ALL = arg.includes("--all");
const onlyIdx = arg.indexOf("--only");
const ONLY = onlyIdx >= 0 ? arg[onlyIdx + 1] : null;
if (!DRY && !ALL && !ONLY) { console.error("Rezim: --dry-run | --only <substr> | --all"); process.exit(1); }

function bMidZ(glbRel) {
  const p = KAT + glbRel;
  if (!fs.existsSync(p)) return null;
  const mesh = parseGlbMesh(p);
  mesh.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(mesh);
  return (box.min.z + box.max.z) / 2;
}
function verdictFor(mid) { return mid == null ? "MISSING" : mid > 50 ? "NEEDS_FLIP" : mid < -50 ? "OK" : "UNCERTAIN"; }

function flipGlb180Y(p) {
  const buf = fs.readFileSync(p);
  if (buf.readUInt32LE(0) !== 0x46546c67) throw new Error(`${p}: not a glb`);
  const version = buf.readUInt32LE(4);
  let offset = 12, json = null, binChunk = null;
  while (offset < buf.length) {
    const chunkLen = buf.readUInt32LE(offset), chunkType = buf.readUInt32LE(offset + 4);
    const chunkData = buf.slice(offset + 8, offset + 8 + chunkLen);
    if (chunkType === 0x4e4f534a) json = JSON.parse(chunkData.toString("utf8"));
    else if (chunkType === 0x004e4942) binChunk = Buffer.from(chunkData);
    offset += 8 + chunkLen;
  }
  if (!json || !binChunk) throw new Error(`${p}: missing chunk`);
  for (const mesh of json.meshes) for (const prim of mesh.primitives) {
    ["POSITION", "NORMAL"].forEach(attrName => {
      const accIdx = prim.attributes[attrName];
      if (accIdx == null) return;
      const acc = json.accessors[accIdx], bv = json.bufferViews[acc.bufferView];
      const byteOffset = (bv.byteOffset || 0) + (acc.byteOffset || 0);
      const arr = new Float32Array(binChunk.buffer, binChunk.byteOffset + byteOffset, acc.count * 3);
      for (let i = 0; i < arr.length; i += 3) { arr[i] = -arr[i]; arr[i + 2] = -arr[i + 2]; }
      if (acc.min && acc.max) {
        const nMinX = -acc.max[0], nMaxX = -acc.min[0], nMinZ = -acc.max[2], nMaxZ = -acc.min[2];
        acc.min = [nMinX, acc.min[1], nMinZ]; acc.max = [nMaxX, acc.max[1], nMaxZ];
      }
    });
  }
  let newJsonBuf = Buffer.from(JSON.stringify(json), "utf8");
  const pad = (4 - (newJsonBuf.length % 4)) % 4;
  if (pad) newJsonBuf = Buffer.concat([newJsonBuf, Buffer.alloc(pad, 0x20)]);
  const header = Buffer.alloc(12); header.writeUInt32LE(0x46546c67, 0); header.writeUInt32LE(version, 4);
  const jH = Buffer.alloc(8); jH.writeUInt32LE(newJsonBuf.length, 0); jH.writeUInt32LE(0x4e4f534a, 4);
  const bH = Buffer.alloc(8); bH.writeUInt32LE(binChunk.length, 0); bH.writeUInt32LE(0x004e4942, 4);
  header.writeUInt32LE(12 + 8 + newJsonBuf.length + 8 + binChunk.length, 8);
  fs.writeFileSync(p, Buffer.concat([header, jH, newJsonBuf, bH, binChunk]));
}

// ---- nacti audit, vyber cile ----
let rows = fs.readFileSync(AUDIT, "utf8").split("\n").filter(l => l.trim().startsWith("{")).map(l => JSON.parse(l));
let targets = rows.filter(r => String(r.verdict).startsWith("NEEDS_FLIP"));
if (ONLY) targets = targets.filter(r => (r.base || "").includes(ONLY));
console.log(`NEEDS_FLIP celkem v auditu: ${rows.filter(r => String(r.verdict).startsWith("NEEDS_FLIP")).length}, k zpracovani teď: ${targets.length}${ONLY ? " (filtr --only " + ONLY + ")" : ""}`);

if (DRY) {
  console.log("--- DRY RUN (nic se nemeni) ---");
  targets.slice(0, 30).forEach(r => console.log(`  ${r.base.split("/").pop()}  B_midZ=${Math.round(r.B_midZ)}  ids=${r.ids}`));
  if (targets.length > 30) console.log(`  ... a dalsich ${targets.length - 30}`);
  process.exit(0);
}

if (!fs.existsSync(BACKUP_DIR)) fs.mkdirSync(BACKUP_DIR, { recursive: true });
const flippedRealpaths = new Set();
const flippedCbIds = [];
let fileCount = 0, modelCount = 0, errors = [];
// bot8 2026-09-05 OPRAVA: "_B_wall.glb" tu CHYBELA. Model FO30 (Transit Custom
// L1 23-) ma prepazku jako `FO30_B_wall.glb`, ne `FO30_B.glb` - bez tehle
// pripony by se mu flipla jen leva a prava stena a prepazka by zustala
// otocena opacne, tedy rozbita karoserie. (Vyjimka je dokumentovana uz
// v KAROSERIE_UMISTENI.md: "jeden model ma `_B_wall` misto `_B`".)
const SUFFIXES = ["_L.glb", "_R_D.glb", "_B.glb", "_B_wall.glb"];

for (const r of targets) {
  const base = r.base; // "car_bodies/Xxx"
  let modelFlippedAny = false;
  for (const suf of SUFFIXES) {
    const rel = base + suf, abs = KAT + rel;
    if (!fs.existsSync(abs)) { continue; }
    const real = fs.realpathSync(abs);
    if (flippedRealpaths.has(real)) { continue; } // dedup: uz flipnuto pres jiny nazev
    try {
      // zaloha (zachovej strukturu podadresaru)
      const bpath = path.join(BACKUP_DIR, rel);
      fs.mkdirSync(path.dirname(bpath), { recursive: true });
      if (!fs.existsSync(bpath)) fs.copyFileSync(abs, bpath);
      flipGlb180Y(abs);
      flippedRealpaths.add(real);
      fileCount++; modelFlippedAny = true;
    } catch (e) { errors.push(`${rel}: ${e.message}`); }
  }
  if (modelFlippedAny) {
    modelCount++;
    String(r.ids || "").split("/").map(s => parseInt(s.trim(), 10)).filter(n => Number.isFinite(n)).forEach(id => flippedCbIds.push(id));
  }
}
fs.writeFileSync("/tmp/flipped_cb_ids.json", JSON.stringify([...new Set(flippedCbIds)], null, 1));
console.log(`\nFLIP HOTOVO: ${modelCount} modelu, ${fileCount} GLB souboru, ${flippedCbIds.length} car_body IDs. Zalohy: ${BACKUP_DIR}`);
if (errors.length) { console.log(`CHYBY (${errors.length}):`); errors.slice(0, 10).forEach(e => console.log("  " + e)); }

// ---- re-audit flipnutych ----
console.log("\n--- RE-AUDIT flipnutych (B_midZ ma byt < -50) ---");
// bot8 2026-09-05 OPRAVA: drive se merilo natvrdo `r.base + "_B.glb"`. U modelu
// s prepazkou `_B_wall.glb` (FO30) ten soubor NEEXISTUJE -> bMidZ vratilo null
// -> verdikt "MISSING" -> NEZAPOCITALO se do stillBad a re-audit TICHE hlasil
// uspech, i kdyby byla karoserie rozbita. Nemereny model je ted taky problem.
let stillBad = 0, notMeasured = 0;
for (const r of targets) {
  let mid = bMidZ(r.base + "_B.glb");
  if (mid == null) mid = bMidZ(r.base + "_B_wall.glb");
  const v = verdictFor(mid);
  if (mid == null) {
    notMeasured++;
    if (notMeasured <= 10) console.log(`  NEZMERENO (chybi _B/_B_wall): ${r.base.split("/").pop()}`);
  } else if (v === "NEEDS_FLIP") {
    stillBad++;
    if (stillBad <= 10) console.log(`  STALE SPATNE: ${r.base.split("/").pop()} B_midZ=${Math.round(mid)}`);
  }
}
console.log((stillBad === 0 && notMeasured === 0)
  ? "  OK - vsechny flipnute karoserie maji spravnou orientaci (B_midZ<0)"
  : `  POZOR: ${stillBad} stale NEEDS_FLIP, ${notMeasured} nezmereno`);
