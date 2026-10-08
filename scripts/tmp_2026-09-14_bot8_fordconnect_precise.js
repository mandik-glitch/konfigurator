// Presne "1mm krok, 2mm zpet" kolizni krokovani (car_body_placement_methods
// id=1) pro Ford Connect K-237(FO12)/K-239(FO13), pomoci JIZ OVERENE
// knihovny scripts/2026-09-12_wide_verify_lib.js (collidesWithWallsReal =
// hranovy raycast VSECH triuhelniku dilu proti realne GLB stene, ne jen
// stred-bodovy odhad).
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { verifyAssembly, loadWalls, partMesh } = require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");
const { execSync } = require("child_process");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const IDS = [128, 213, 283, 129, 214, 284];
const WALL_BASE = { 128: "Ford_Connect_FO12_2014-", 213: "Ford_Connect_FO12_2014-", 283: "Ford_Connect_FO12_2014-",
                     129: "Ford_Connect_FO13_2014-", 214: "Ford_Connect_FO13_2014-", 284: "Ford_Connect_FO13_2014-" };
// priblizny odhad z drivejsiho hrubeho vypoctu (raycast od stredu nohy) -
// pouzije se jako BEZPECNY vychozi bod (o kus DAL od steny nez odhad), od
// ktereho se pak kroky 1mm poctivě přibližují a testuji REALNOU kolizi.
const APPROX = { 128: -411.74, 213: -411.74, 283: -411.74, 129: -389.70, 214: -389.70, 284: -389.70 };
const SAFETY_START_BACKOFF = 60; // mm - o tolik min agresivni nez odhad, jistota ze start je bez kolize

function fetchAll(ids) {
  const py = `
import json, sys
sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn
conn = get_conn()
out = {}
with conn.cursor() as cur:
    for aid in [${ids.join(",")}]:
        cur.execute("SELECT name, data FROM product_assemblies WHERE id=%s", (aid,))
        row = cur.fetchone()
        out[aid] = {"name": row["name"], "data": json.loads(row["data"])}
conn.close()
print(json.dumps(out))
`;
  fs.writeFileSync(`${SCRATCH}/_fetch_fc2.py`, py);
  return JSON.parse(execSync(`/opt/konfigurator/api/venv/bin/python3 ${SCRATCH}/_fetch_fc2.py`, { maxBuffer: 1024 * 1024 * 80 }).toString());
}

const D = fetchAll(IDS);

function shiftParts(parts, dx) {
  return parts.map(p => R.jeKaroserie(p.part_id) ? p : { ...p, position: [p.position[0] + dx, p.position[1], p.position[2]] });
}
function anyRealWallCollision(parts, base) {
  const walls = loadWalls(base);
  function collidesWithWallsReal(mesh) {
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
  const testable = parts.filter(p => !R.jeKaroserie(p.part_id) && !(p.role || "").startsWith("kontrolni-pomucka"));
  for (const p of testable) {
    if (collidesWithWallsReal(partMesh(p))) return { hit: true, role: p.role };
  }
  return { hit: false };
}

const finalResults = {};
for (const id of [128, 129]) { // spocitej jen 1x na REPREZENTANTA kazde karoserie (A/B/C sdileji stejne nohy/X)
  const base = WALL_BASE[id];
  const orig = D[id].data.parts;
  const approxDx = APPROX[id];
  const dirSign = approxDx < 0 ? -1 : 1;
  let dx = approxDx + dirSign * -SAFETY_START_BACKOFF; // o 60mm blize k puvodni (bezpecnejsi) pozici
  console.log(`\n=== karoserie pro id=${id} (${base}) === start dx=${dx.toFixed(1)} (odhad byl ${approxDx.toFixed(1)})`);

  // over, ze START je bez kolize (jinak by 1mm-krok bisekci-podobne minul tenkou stenu) -
  // pokud koliduje, USTOUPIT po 10mm, dokud neni cisty (nikdy nezacinat kroky z kolizniho bodu)
  let test = anyRealWallCollision(shiftParts(orig, dx), base);
  let retreat = 0;
  while (test.hit && retreat < 100) {
    dx -= dirSign * 10;
    retreat += 10;
    test = anyRealWallCollision(shiftParts(orig, dx), base);
  }
  if (retreat > 0) console.log(`  start kolidoval (${test.hit ? "porad" : "opraveno po " + retreat + "mm ustupu"}), novy start dx=${dx.toFixed(1)}`);

  let lastGood = dx;
  const stepDir = dirSign; // krokujeme SMEREM KE STENE, tedy stejne znamenko jako approxDx
  let steps = 0;
  while (steps < 400) {
    const candidate = dx + stepDir * 1;
    const hit = anyRealWallCollision(shiftParts(orig, candidate), base);
    if (hit.hit) {
      console.log(`  kolize nalezena na dx=${candidate.toFixed(1)} (dil ${hit.role}) po ${steps} krocich - vracim 2mm zpet`);
      break;
    }
    dx = candidate; lastGood = candidate;
    steps++;
  }
  const finalDx = lastGood - stepDir * 2; // 2mm zpet od posledni bezkolizni
  const finalCheck = anyRealWallCollision(shiftParts(orig, finalDx), base);
  console.log(`  FINALNI dx=${finalDx.toFixed(1)}mm, over bez kolize: ${!finalCheck.hit}`);
  finalResults[id] = finalDx;
}

fs.writeFileSync(`${SCRATCH}/fordconnect_precise_dx.json`, JSON.stringify(finalResults));
console.log("\n", finalResults);
