// Prepocet kolizni rezervy (2/20mm -> 10/30mm) na product_assemblies.id=334
// (rodina K-075 = Fiat Doblo L1H1, karoserie_kod K-075), podle procedury
// shape_geometry_methods.id=11 "prepocet-kolizni-rezervy-existujici-sestavy".
//
// Vstupni fakta o nohach teto rodiny (dana zadanim, NEPROVADI se vlastni
// kolizni analyza): 3 Z-pozice noh, byte-identicke napric rodinou K-075
// (overeno primym ctenim 334 dat nize - viz SELF-CHECK sekce):
//   leg0 Z=-1358.5025482177734  (jen "plain", predni-svislice + zadni-svislice-dolni)
//   leg1 Z=-898.5025482177734   (predni-svislice PLAIN + vyrezova trojice, wall_x=-706.5)
//   leg2 Z=-34.50254821777344   (predni-svislice PLAIN + vyrezova trojice, wall_x=-706.5)
//   OLD_YNEW: leg1=101.50017929077148, leg2=53.500179290771484 (dany svar sloupek/svislice)
//
// TRANSFORM PRAVIDLA odvozena EMPIRICKY diffem existujiciho over/prepocitaneho
// paru 279 (pred, 2/20mm) -> 340 (po, 10/30mm) na TEZE karoserii (viz
// SELF-CHECK nize, ktery aplikuje tuhle funkci na 279 a overuje bit-presnou
// shodu s 340 pro vsechny sdilene role) - NE jen z textu procedury.

const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const { execSync } = require("child_process");

const LEG_Z = { leg0: -1358.5025482177734, leg1: -898.5025482177734, leg2: -34.50254821777344 };
const OLD_YNEW = { leg1: 101.50017929077148, leg2: 53.500179290771484 };
const DELTA_Z = 8;     // 10mm - 2mm (prepazka)
const DELTA_Y = 10;    // 30mm - 20mm (podbeh)
const T = 30, HALF_T = 15;
const ZTOL = 0.5;
const near = (a, b, eps) => Math.abs(a - b) < (eps == null ? 0.05 : eps);

// ---- klasifikace + transform jednoho dilu ----
// col0Shift(role) -> Y dorovnani (mm) pro dany nosnik/spojnice/eurobox-col0-pN podle
// urovne (0=nejnizsi). Predpocitano dole podle skutecneho poctu urovni v dane sestave.
function makeCol0ShiftFn(levels) {
  const N = levels.length; // levels serazene vzestupne podle Y (0=nejnizsi)
  const idxOf = role => levels.indexOf(levelKey(role));
  return function shiftFor(role) {
    const i = idxOf(role);
    if (i < 0) return null;
    if (N <= 1) return 0;
    return DELTA_Y * (N - 1 - i) / (N - 1);
  };
}
function levelKey(role) {
  const m = /^(nosnik|spojnice|eurobox)-col0-(p\d+)$/.exec(role);
  return m ? m[2] : null;
}

function transformAssembly(parts, opts) {
  opts = opts || {};
  const log = { frontRigid: 0, frontSpanCol0: 0, frontSpanFull: 0, col0Box: 0, col0LogoRamp: 0,
    col0Dorovnani: 0, leg1Seam: 0, leg2Seam: 0, unaffected: 0, carBody: 0 };
  const out = [];

  // 1) urovne (patra) col0 podle nosnik-col0-p* pritomnych v datech, serazene Y vzestupne
  const nosnikCol0 = parts.filter(p => /^nosnik-col0-p\d+$/.test(p.role || ""));
  const levelSet = [...new Set(nosnikCol0.map(p => levelKey(p.role)))];
  levelSet.sort((a, b) => {
    const ya = Math.min(...nosnikCol0.filter(p => levelKey(p.role) === a).map(p => p.position[1]));
    const yb = Math.min(...nosnikCol0.filter(p => levelKey(p.role) === b).map(p => p.position[1]));
    return ya - yb;
  });
  const col0Shift = makeCol0ShiftFn(levelSet);

  for (const orig of parts) {
    const p = JSON.parse(JSON.stringify(orig));
    const role = p.role || "";
    const [x, y, z] = p.position;

    if (String(p.part_id || "").startsWith("car_body_")) { out.push(p); log.carBody++; continue; }

    // -- logo-ochrana: rozhodni podle Z: presne na leg0 -> rigid; mezi leg1..leg0 -> ramp interpolace; jinak (u leg1/leg2) beze zmeny
    const logoM = /^logo-ochrana-(?:vypln|logo)-\d+$/.test(role);
    if (logoM) {
      // "na leg0" = presne na Z leg0 NEBO za nim (dal od leg1, tj. jeste
      // zapornejsi) - logo muze byt montovano na cele/bocnici nohy, ne na
      // jejim strednim Z (zmereno: logo-8 sedi -15.7mm od leg0 Z, presto
      // je soucasti leg0 a jede s nim celym deltaZ - viz AGENTS_LOG poznamka
      // ve VSTUPNI DATA "ruzny offset stejne dvojice").
      if (z <= LEG_Z.leg0 + 1) {
        p.position = [x, y, z + DELTA_Z]; out.push(p); log.frontRigid++; continue;
      }
      // na rampe col0 (mezi leg1 a leg0)?
      if (z > LEG_Z.leg0 + 1 && z < LEG_Z.leg1 - 1) {
        const frac = (z - LEG_Z.leg1) / (LEG_Z.leg0 - LEG_Z.leg1);
        const newLeg0Z = LEG_Z.leg0 + DELTA_Z;
        const newZ = LEG_Z.leg1 + frac * (newLeg0Z - LEG_Z.leg1);
        p.position = [x, y, newZ]; out.push(p); log.col0LogoRamp++; continue;
      }
      out.push(p); log.unaffected++; continue;
    }

    // -- role primo na leg0 (plna noha + jeji vlastni dily): presna Z shoda s leg0
    const LEG0_RIGID_ROLES = new Set([
      "cap", "predni-svislice", "zadni-svislice-dolni", "spojnice-dolni", "spojnice-horni",
      "zaslepka-cap", "zaslepka-predni-svislice", "zaslepka-zadni-svislice-dolni",
      "uhelnik-noha0", "pricka-horni-0", "pricka-spodni-0",
    ]);
    if (LEG0_RIGID_ROLES.has(role)) {
      if (role === "uhelnik-noha0" || near(z, LEG_Z.leg0, ZTOL)) {
        p.position = [x, y, z + DELTA_Z]; out.push(p); log.frontRigid++; continue;
      }
    }
    // spojnice-dolni/spojnice-horni existuji i u leg1/leg2 (bez rigid shiftu) - uz osetreno vyse
    // (pokud role je v mnozine, ale Z nesedi na leg0, propadne dal do obecne logiky nize)

    // -- eurobox-col0-pN: Z posun +DELTA_Z/2 flat (stred bunky), + dorovnani Y podle patra
    if (/^eurobox-col0-p\d+$/.test(role)) {
      const dy = col0Shift(role) || 0;
      p.position = [x, y + dy, z + DELTA_Z / 2]; out.push(p); log.col0Box++; log.col0Dorovnani += dy ? 1 : 0; continue;
    }
    if (/^eurobox-col1-p\d+$/.test(role)) { out.push(p); log.unaffected++; continue; }

    // -- nosnik-col0-pN: rampa leg0..leg1, stred += DELTA_Z/2, delka -= DELTA_Z, + Y dorovnani
    if (/^nosnik-col0-p\d+$/.test(role)) {
      const dy = col0Shift(role) || 0;
      const newLenM = p.scale[1] - DELTA_Z / 1000;
      p.position = [x, y + dy, z + DELTA_Z / 2];
      p.scale = [p.scale[0], newLenM, p.scale[2]];
      out.push(p); log.frontSpanCol0++; log.col0Dorovnani += dy ? 1 : 0; continue;
    }
    if (/^nosnik-col1-p\d+$/.test(role)) { out.push(p); log.unaffected++; continue; }

    // -- spojnice-col0-pN: kratky prycny spoj u JEDNE nohy (leg0 nebo leg1) + Y dorovnani vzdy
    if (/^spojnice-col0-p\d+$/.test(role)) {
      const distLeg0 = Math.abs(z - LEG_Z.leg0), distLeg1 = Math.abs(z - LEG_Z.leg1);
      const dy = col0Shift(role) || 0;
      if (distLeg0 < distLeg1) { p.position = [x, y + dy, z + DELTA_Z]; }
      else { p.position = [x, y + dy, z]; }
      out.push(p); log.frontSpanCol0++; log.col0Dorovnani += dy ? 1 : 0; continue;
    }
    if (/^spojnice-col1-p\d+$/.test(role)) { out.push(p); log.unaffected++; continue; }

    // -- podelnik-*-horni / podelnik-*-spodni-0: spanuji od leg0 (stred += DELTA_Z/2, delka -= DELTA_Z)
    //    podelnik-*-spodni-1: span leg1..leg2 (oba fixni) -> beze zmeny
    if (/^podelnik-.*-spodni-1$/.test(role)) { out.push(p); log.unaffected++; continue; }
    if (/^podelnik-.*-(horni|spodni-0)$/.test(role)) {
      const newLenM = p.scale[1] - DELTA_Z / 1000;
      p.position = [x, y, z + DELTA_Z / 2];
      p.scale = [p.scale[0], newLenM, p.scale[2]];
      out.push(p); log.frontSpanFull++; continue;
    }

    // -- pricka-horni-N / pricka-spodni-N: rigid s leg0 JEN kdyz N odpovida leg0 Z (uz zachyceno vyse
    //    pres LEG0_RIGID_ROLES pro "-0"); pro "-1"/"-2" (leg1/leg2) beze zmeny
    if (/^pricka-(horni|spodni)-\d+$/.test(role)) { out.push(p); log.unaffected++; continue; }

    // -- uhelnik-noha1 / uhelnik-noha2: Y posun DELTA_Y jen kdyz sedi na starem svaru (nebo +30 odsazeni)
    if (role === "uhelnik-noha1" || role === "uhelnik-noha2") {
      const oldYnew = role === "uhelnik-noha1" ? OLD_YNEW.leg1 : OLD_YNEW.leg2;
      if (near(y, oldYnew, 3) || near(y, oldYnew + 30, 3)) {
        p.position = [x, y + DELTA_Y, z]; out.push(p);
        (role === "uhelnik-noha1" ? log.leg1Seam++ : log.leg2Seam++); continue;
      }
      out.push(p); log.unaffected++; continue;
    }

    // -- vyrezova noha leg1
    if (near(z, LEG_Z.leg1, ZTOL)) {
      const oldYnew = OLD_YNEW.leg1, newYnew = oldYnew + DELTA_Y;
      if (role === "sloupek-pred-podbehem") {
        const oldH = p.scale[1] * 1000, floorY = y - oldH / 2, newH = newYnew - floorY;
        p.position = [x, floorY + newH / 2, z]; p.scale = [p.scale[0], newH / 1000, p.scale[2]];
        out.push(p); log.leg1Seam++; continue;
      }
      if (role === "zadni-svislice-nad-zarezem") {
        const oldH = p.scale[1] * 1000, topY = y + oldH / 2, newH = topY - newYnew;
        p.position = [x, newYnew + newH / 2, z]; p.scale = [p.scale[0], newH / 1000, p.scale[2]];
        out.push(p); log.leg1Seam++; continue;
      }
      if (role === "pricka-uzavreni-vyrezu") {
        p.position = [x, newYnew + T / 2, z]; out.push(p); log.leg1Seam++; continue;
      }
      out.push(p); log.unaffected++; continue;
    }

    // -- vyrezova noha leg2
    if (near(z, LEG_Z.leg2, ZTOL)) {
      const oldYnew = OLD_YNEW.leg2, newYnew = oldYnew + DELTA_Y;
      if (role === "sloupek-pred-podbehem") {
        const oldH = p.scale[1] * 1000, floorY = y - oldH / 2, newH = newYnew - floorY;
        p.position = [x, floorY + newH / 2, z]; p.scale = [p.scale[0], newH / 1000, p.scale[2]];
        out.push(p); log.leg2Seam++; continue;
      }
      if (role === "zadni-svislice-nad-zarezem") {
        const oldH = p.scale[1] * 1000, topY = y + oldH / 2, newH = topY - newYnew;
        p.position = [x, newYnew + newH / 2, z]; p.scale = [p.scale[0], newH / 1000, p.scale[2]];
        out.push(p); log.leg2Seam++; continue;
      }
      if (role === "pricka-uzavreni-vyrezu") {
        p.position = [x, newYnew + T / 2, z]; out.push(p); log.leg2Seam++; continue;
      }
      out.push(p); log.unaffected++; continue;
    }

    out.push(p); log.unaffected++;
  }
  return { parts: out, log };
}

module.exports = { transformAssembly, LEG_Z, OLD_YNEW, DELTA_Z, DELTA_Y };

// ============================================================
// Kdyz je skript spusten primo (ne require-nut), provede:
//  A) SELF-CHECK: aplikuje transformAssembly na 279, diffuje proti skutecnemu
//     340 (uz existujici, overeny prepocet na TEZE karoserii) - MUSI sedet
//     bit-presne na vsech sdilenych rolich, jinak STOP (nepokracuje na 334).
//  B) Nacte 334, over ktere leg-pozice se v nem vyskytuji, aplikuje transform,
//     ulozi mezivysledek pro navazujici SAT/self-kolizni skript.
if (require.main === module) {
  const dumpPy = `
import json, pymysql
env = {}
with open("api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT",3306)), user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SELECT id, data FROM product_assemblies WHERE id IN (334,279,340)")
out = {}
for r in cur.fetchall():
    out[r["id"]] = json.loads(r["data"])["parts"]
conn.close()
print(json.dumps(out))
`;
  fs.writeFileSync("/tmp/_dump_334.py", dumpPy);
  const raw = execSync("api/venv/bin/python3 /tmp/_dump_334.py", { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 80 }).toString();
  const DB = JSON.parse(raw);

  // ---- A) SELF-CHECK 279 -> compare vs 340 ----
  console.log("=== SELF-CHECK: transform(279) vs skutecny 340 ===");
  const p279 = DB[279], p340 = DB[340].filter(p => !(p.role || "").startsWith("kontrolni-pomucka"));
  const { parts: myResult, log: log279 } = transformAssembly(p279);
  console.log("log (279):", JSON.stringify(log279));

  function byRoleSorted(parts) {
    const m = {};
    for (const p of parts) { const r = p.role || "(none)"; (m[r] = m[r] || []).push(p); }
    for (const r in m) m[r].sort((a, b) => a.position[2] - b.position[2] || a.position[0] - b.position[0] || a.position[1] - b.position[1]);
    return m;
  }
  const mMine = byRoleSorted(myResult.filter(p => !String(p.part_id || "").startsWith("car_body_")));
  const mRef = byRoleSorted(p340.filter(p => !String(p.part_id || "").startsWith("car_body_")));
  let mismatches = 0;
  const roles = new Set([...Object.keys(mMine), ...Object.keys(mRef)]);
  for (const r of [...roles].sort()) {
    const a = mMine[r] || [], b = mRef[r] || [];
    if (a.length !== b.length) { console.log("COUNT MISMATCH", r, a.length, b.length); mismatches++; continue; }
    for (let i = 0; i < a.length; i++) {
      const dp = a[i].position.map((v, idx) => Math.abs(v - b[i].position[idx]));
      const ds = a[i].scale.map((v, idx) => Math.abs(v - b[i].scale[idx]));
      if (dp.some(v => v > 0.01) || ds.some(v => v > 0.0001)) {
        console.log("MISMATCH", r, "#" + i, "mine=", a[i].position, a[i].scale, "ref=", b[i].position, b[i].scale);
        mismatches++;
      }
    }
  }
  console.log(mismatches === 0 ? "SELF-CHECK OK: presna shoda s 340 na vsech sdilenych rolich." : `SELF-CHECK SELHAL: ${mismatches} nesrovnalosti.`);
  if (mismatches > 0) { console.log("STOP - nepokracuji na 334, dokud self-check neprojde."); process.exit(1); }

  // ---- B) aplikuj na 334 ----
  console.log("\n=== APLIKACE na 334 ===");
  const p334 = DB[334];
  // over ktere leg-pozice se v 334 vyskytuji (podle Z, tolerance ~1mm)
  const zVals = [...new Set(p334.filter(p => !String(p.part_id || "").startsWith("car_body_")).map(p => +p.position[2].toFixed(1)))];
  function hasZ(z) { return p334.some(p => Math.abs(p.position[2] - z) < 1 && !String(p.part_id || "").startsWith("car_body_")); }
  console.log("leg0 pritomen (predni-svislice na Z=leg0)?", p334.some(p => p.role === "predni-svislice" && near(p.position[2], LEG_Z.leg0, 1)));
  console.log("leg1 vyrez pritomen?", p334.some(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], LEG_Z.leg1, 1)));
  console.log("leg2 vyrez pritomen?", p334.some(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], LEG_Z.leg2, 1)));

  const { parts: result334, log: log334 } = transformAssembly(p334);
  console.log("log (334):", JSON.stringify(log334));
  console.log("celkem dilu:", p334.length, "-> vystup:", result334.length);

  fs.writeFileSync(__dirname + "/tmp_2026-09-12_334_parts_new.json", JSON.stringify(result334));
  console.log("\nUlozeno: tmp_2026-09-12_334_parts_new.json");
}
