const fs = require("fs");
const THREE = require("three");
const { execSync } = require("child_process");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { verifyAssembly } = require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const ZASUN = 7, TOP_CLEAR = 11, SIDE_ZASUN = 8;

function worldBox(p) {
  const glb = R.glbPath(p.part_id); if (!glb) return null;
  const mesh = parseGlbMesh(glb);
  mesh.position.set(...p.position); mesh.quaternion.set(...p.quaternion); mesh.scale.set(...p.scale);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}
function addDorazovaDeska(parts) {
  const pricka = parts.find(p => p.role === "pricka-spodni-0");
  const z = pricka.position[2];
  const atZ = parts.filter(p => Math.abs(p.position[2] - z) < 1 && !R.jeKaroserie(p.part_id));
  const predni = atZ.find(p => p.role === "predni-svislice");
  const cap = atZ.find(p => p.role === "cap");
  const zaslepky = atZ.filter(p => String(p.role || "").startsWith("zaslepka")).map(p => ({ p, box: worldBox(p) })).sort((a, b) => b.box.max.y - a.box.max.y).slice(0, 2);
  const prickaBox = worldBox(pricka);
  const zaslepkaMinY = Math.min(...zaslepky.map(zz => zz.box.min.y));
  const bottomY = prickaBox.max.y - ZASUN, topY = zaslepkaMinY - TOP_CLEAR;
  const xMid = (predni.position[0] + cap.position[0]) / 2;
  const width = Math.abs(cap.position[0] - predni.position[0]) - 2 * SIDE_ZASUN;
  return { role: "vypln-bok-prepazka", part_id: "product_3939", position: [xMid, (bottomY + topY) / 2, z],
    quaternion: [0, 0, 0, 1], scale: [width / 1000, (topY - bottomY) / 1000, 1] };
}
const RAMOVE = /^(podelnik|pricka|cap|predni-svislice)/;
function jeZamernyZasun(roleA, roleB, dims) {
  const a1 = roleA.startsWith("vypln"), b1 = roleB.startsWith("vypln");
  if (a1 === b1) return false;
  const profil = a1 ? roleB : roleA;
  if (!RAMOVE.test(profil)) return false;
  const h = dims.filter(v => v > 0.5).sort((m, n) => m - n);
  return h.length > 0 && h[0] <= ZASUN + 0.5;
}

const VARIANTY = {
  "01": { flags: ["--jedno-pasmo"], dorazova: true, odeberRoli: null },
  "02": { flags: ["--bez-hornich-pricek", "--police-bez-podelniku", "--bez-vyplni"], dorazova: true, odeberRoli: "pricka-police-0" },
  "03": { flags: ["--bez-police", "--horni-pricka-jen-prepazka"], dorazova: false, odeberRoli: null },
};

const AID = process.argv[2];
const VOZ = process.argv[3];
const srcPath = `${SCRATCH}/hb_src_${AID}.json`;
const src = { data: JSON.parse(fs.readFileSync(srcPath, "utf8")) };
const out = {};
for (const [label, cfg] of Object.entries(VARIANTY)) {
  const raw = execSync(`node /opt/konfigurator/scripts/2026-09-05_horni_ram.js "${srcPath}" --vozidlo="${VOZ}" ${cfg.flags.join(" ")} --json`, { maxBuffer: 1024 * 1024 * 80 }).toString();
  const res = JSON.parse(raw);
  let parts = res.upraveneParts;
  if (cfg.odeberRoli) parts = parts.filter(p => p.role !== cfg.odeberRoli);
  if (cfg.dorazova) parts = parts.concat([addDorazovaDeska(parts)]);
  const orig = src.data.parts;
  const report = verifyAssembly({ partsNew: parts, partsOrig: orig, carBodyBase: VOZ, notchChecks: [], label: `${AID}-${label}` });
  const novyProblem = report.newProblems.filter(p => !jeZamernyZasun(p.a, p.b, p.overlap_mm));
  const ok = report.collisions === 0 && novyProblem.length === 0 && res.kolize.length === 0 && res.kolizeKaroserie.length === 0;
  console.log(`${label}: dilu=${parts.length} wall=${report.collisions} self-nove=${novyProblem.length} script-kolize=${res.kolize.length} OK=${ok}`);
  out[label] = { parts, ok };
}
fs.writeFileSync(`${SCRATCH}/hb_build_${AID}.json`, JSON.stringify(out));
console.log("CELKEM OK:", Object.values(out).filter(v => v.ok).length, "/4");
