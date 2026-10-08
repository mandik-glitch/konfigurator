// Robert: "odmitas prochazet ty sestavy jednu za druhou?" - kompletni
// pruchod vsech 72 novych horni-blok sestav (386-457) v JEJICH AKTUALNIM
// stavu v DB (po razitkovani), hleda REALNE problemy: kolize se stenou
// karoserie (edge-raycasting) + self-kolize (Box3, vsechny dvojice roli,
// isKnownNesting filtr) + navic zvlast oznaceny "znama kod6/04" par a
// "zamerny zasun" pary z 2026-09-05_horni_ram.js pro uplnost.
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { loadWalls, partMesh, selfCollide } = require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const D = JSON.parse(fs.readFileSync(`${SCRATCH}/all72_current.json`, "utf8"));
const VOZ = JSON.parse(fs.readFileSync(`${SCRATCH}/voz_map72.json`, "utf8"));

function collidesWithWallsReal(mesh, walls) {
  const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const maxEdges = 300;
  const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  const raycaster = new THREE.Raycaster();
  for (let t = 0; t < triCount; t += step) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); } else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    for (const [p0, p1] of [[vA, vB], [vB, vC], [vC, vA]]) {
      const dir = p1.clone().sub(p0), dist = dir.length();
      if (dist < 1e-6) continue;
      dir.normalize();
      raycaster.set(p0, dir); raycaster.far = dist;
      if (raycaster.intersectObjects(walls, false).length) return true;
    }
  }
  return false;
}

const RAMOVE = /^(podelnik|pricka|cap|predni-svislice)/;
function jeZamernyZasun(roleA, roleB, dims) {
  const a1 = roleA.startsWith("vypln"), b1 = roleB.startsWith("vypln");
  if (a1 === b1) return false;
  const profil = a1 ? roleB : roleA;
  if (!RAMOVE.test(profil)) return false;
  const h = dims.filter(v => v > 0.5).sort((m, n) => m - n);
  return h.length > 0 && h[0] <= 7.5;
}
function jeZnamaKod6Kolize(role, otherRole, dims) {
  const set = new Set([role, otherRole]);
  const d = [...dims].sort((a, b) => a - b);
  return [...set].some(r => r.startsWith("vypln-bok-prepazka")) && [...set].some(r => r.startsWith("pricka-"))
    && Math.abs(d[0] - 8) < 1 && Math.abs(d[1] - 18) < 1;
}
function jeRazitkoVDrazce(role, otherRole, dims) {
  const set = new Set([role, otherRole]);
  const isRaz = r => /^(logo-ochrana|signature)/.test(r);
  if (![...set].some(isRaz)) return false;
  const d = [...dims].sort((a, b) => a - b);
  return d[0] >= 7 && d[0] <= 11 && d[1] >= 7 && d[1] <= 11;
}
function jeProfilVlastniZaslepka(role, otherRole, dims) {
  const a = role.startsWith("zaslepka"), b = otherRole.startsWith("zaslepka");
  if (!a && !b) return false;
  const d = [...dims].sort((a2, b2) => a2 - b2);
  return d[0] >= 4.5 && d[0] <= 8.5;
}

const wallsCache = {};
const results = [];
let totalWall = 0, totalSelf = 0;

for (const [aid, info] of Object.entries(D)) {
  const base = VOZ[aid];
  if (!wallsCache[base]) wallsCache[base] = loadWalls(base);
  const walls = wallsCache[base];
  const parts = info.data.parts;

  const testable = parts.filter(p => !R.jeKaroserie(p.part_id) && !(p.role || "").startsWith("kontrolni-pomucka"));
  const wallHits = [];
  for (const p of testable) {
    if (collidesWithWallsReal(partMesh(p), walls)) wallHits.push(p.role);
  }

  const self = selfCollide(parts);
  const realProblems = self.list.filter(x =>
    !jeZamernyZasun(x.a, x.b, x.overlap_mm) &&
    !jeZnamaKod6Kolize(x.a, x.b, x.overlap_mm) &&
    !jeRazitkoVDrazce(x.a, x.b, x.overlap_mm) &&
    !jeProfilVlastniZaslepka(x.a, x.b, x.overlap_mm));

  totalWall += wallHits.length;
  totalSelf += realProblems.length;
  if (wallHits.length || realProblems.length) {
    results.push({ id: aid, name: info.name, wallHits, realProblems });
    console.log(`id=${aid} ${info.name.slice(0,60)}`);
    if (wallHits.length) console.log("  KOLIZE S KAROSERII:", wallHits);
    if (realProblems.length) console.log("  NEZNAMA SELF-KOLIZE:", JSON.stringify(realProblems));
  }
}
console.log(`\n=== CELKEM: ${Object.keys(D).length} sestav, wall-kolize=${totalWall}, nezname self-kolize=${totalSelf} ===`);
fs.writeFileSync(`${SCRATCH}/full_sweep72_result.json`, JSON.stringify(results));
