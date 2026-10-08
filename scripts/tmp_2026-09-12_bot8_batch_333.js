// Prepocet kolizni rezervy (2/20mm -> 10/30mm) na product_assemblies.id=333
// (rodina K-075 = Fiat Doblo L1H1, karoserie_kod K-075), podle procedury
// shape_geometry_methods.id=11 "prepocet-kolizni-rezervy-existujici-sestavy"
// (verified_by robert).
//
// Vstupni fakta o nohach (dana zadanim, NEPROVADI se vlastni kolizni
// analyza - jen se ctou z JIZ ZJISTENYCH dat rodiny K-075):
//   leg0 Z=-1358.5025482177734  (jen "plain", predni-svislice + zadni-svislice-dolni,
//        cely sloupec kotveny k prepazce B -> hybe se v Z)
//   leg1 Z=-898.5025482177734   (predni-svislice PLAIN [nehybe se] + vyrezova
//        trojice nad podbehem [Y roste], wall_x=-706.5, old_y_new=101.50017929077148)
//   leg2 Z=-34.50254821777344   (totez jako leg1, old_y_new=53.500179290771484)
//
// DELTY jsou presne aritmeticke konstanty (krok 1 procedury):
//   deltaZ_predni_noha = +8mm (10-2), deltaY_vyrezova_noha = +10mm (30-20).
//
// TRANSFORM PRAVIDLA: zaklad prevzat a rozsireny ze sdilene, uz JEDNOU
// empiricky overene funkce transformAssembly()
// (scripts/tmp_2026-09-12_bot8_batch_334.js, self-check tamtez proti
// realnemu paru 279 [pred] -> 340 [po] na TEZE karoserii). Rozsireni oproti
// 334 verzi (334 tyhle role/situace nema, takze puvodni self-check je
// nemohl pokryt - overeno primo v DB, viz komentare u kazde vetve):
//   1) role "vypln-dno-0"/"vypln-dno-1" (MDF vyplnove desky dna) - 333 JE MA,
//      334 ne. Stejny Z-rozpon jako "podelnik-*-spodni-0/1" (0=leg0..leg1
//      span, kratitko; 1=leg1..leg2 span, oba konce fixni -> beze zmeny).
//   2) logo-ochrana par mountovany NA vyrezove noze (Z blizko leg1/leg2,
//      ne presne na nem - logo/vypln jsou plosky na CELE pricka-uzavreni-
//      vyrezu, ktera ma vlastni tloustku, proto Z-offset ~10-16mm od leg
//      Z misto X-offsetu jako u svislych dilu) - puvodni 334 verze tohle
//      vubec neresila (334 zadny takovy pripad nema, overeno v DB), 333 ANO
//      (logo-ochrana-vypln-3/logo-3, viz klasifikace v logu nize).
//
// Self-check (transform(279) === skutecny 340 bit-presne na vsech
// sdilenych rolich) BEZI I TADY, PRED aplikaci na 333 - obe rozsireni
// nemaji zadny dil v 279/340 na ktery by mohly dopadnout, takze self-check
// zustava validni test, ze jsem nic nerozbil/a.

const fs = require("fs");
const { execSync } = require("child_process");

const LEG_Z = { leg0: -1358.5025482177734, leg1: -898.5025482177734, leg2: -34.50254821777344 };
const OLD_YNEW = { leg1: 101.50017929077148, leg2: 53.500179290771484 };
const DELTA_Z = 8;     // 10mm - 2mm (prepazka)
const DELTA_Y = 10;    // 30mm - 20mm (podbeh)
const T = 30, HALF_T = 15;
const ZTOL = 0.5;
const LOGO_LEG_TOL = 25; // toleruje mount na pricka-uzavreni-vyrezu (offset ~10-16mm od leg Z)
const near = (a, b, eps) => Math.abs(a - b) < (eps == null ? 0.05 : eps);

function makeCol0ShiftFn(levels) {
  const N = levels.length;
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

function transformAssembly(parts) {
  const log = { frontRigid: 0, frontSpanCol0: 0, frontSpanFull: 0, col0Box: 0, col0LogoRamp: 0,
    col0Dorovnani: 0, leg1Seam: 0, leg2Seam: 0, leg1LogoSeam: 0, leg2LogoSeam: 0,
    unaffected: 0, carBody: 0 };
  const out = [];
  const touched = [];

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

    // -- logo-ochrana --
    const logoM = /^logo-ochrana-(?:vypln|logo)-\d+$/.test(role);
    if (logoM) {
      if (z <= LEG_Z.leg0 + 1) {
        p.position = [x, y, z + DELTA_Z]; out.push(p); log.frontRigid++;
        touched.push({ role, class: "logo-leg0-rigid", dz: DELTA_Z, dy: 0 }); continue;
      }
      if (z > LEG_Z.leg0 + 1 && z < LEG_Z.leg1 - 1) {
        const frac = (z - LEG_Z.leg1) / (LEG_Z.leg0 - LEG_Z.leg1);
        const newLeg0Z = LEG_Z.leg0 + DELTA_Z;
        const newZ = LEG_Z.leg1 + frac * (newLeg0Z - LEG_Z.leg1);
        p.position = [x, y, newZ]; out.push(p); log.col0LogoRamp++;
        touched.push({ role, class: "logo-col0-ramp", dz: +(newZ - z).toFixed(3), dy: 0 }); continue;
      }
      // NOVE (333 rozsireni): mount na vyrezove noze (leg1/leg2) - pozna se
      // podle blizkosti Z k leg1/leg2 (do LOGO_LEG_TOL, kryje offset dane
      // tloustkou pricka-uzavreni-vyrezu), NE presnou shodou. MUSI navic byt
      // na zadni/vyrezove strane (X < -450, tj. strana zadni-svislice-nad-
      // zarezem/sloupek/pricka-uzavreni-vyrezu, X in {-706.5,-572.5,-547}) -
      // svar 279->340 ukazal, ze logo se stejnym Z-offsetem ALE na PREDNI
      // strane (X=-387.5, predni-svislice, ktera se u leg1/leg2 nehybe)
      // zustava beze zmeny (logo-3 v 279/340: X=-387.5, Z blizko leg2,
      // presto se NEHYBE - self-check by bez teto podminky selhal).
      const d1 = Math.abs(z - LEG_Z.leg1), d2 = Math.abs(z - LEG_Z.leg2);
      if (x < -450 && (d1 <= LOGO_LEG_TOL || d2 <= LOGO_LEG_TOL)) {
        const onLeg1 = d1 <= d2;
        p.position = [x, y + DELTA_Y, z]; out.push(p);
        (onLeg1 ? log.leg1LogoSeam++ : log.leg2LogoSeam++);
        touched.push({ role, class: onLeg1 ? "logo-leg1-vyrez" : "logo-leg2-vyrez", dz: 0, dy: DELTA_Y }); continue;
      }
      out.push(p); log.unaffected++;
      touched.push({ role, class: "logo-unaffected", dz: 0, dy: 0 }); continue;
    }

    // -- role primo na leg0 (plna noha + jeji vlastni dily) --
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

    if (/^eurobox-col0-p\d+$/.test(role)) {
      const dy = col0Shift(role) || 0;
      p.position = [x, y + dy, z + DELTA_Z / 2]; out.push(p); log.col0Box++; log.col0Dorovnani += dy ? 1 : 0; continue;
    }
    if (/^eurobox-col1-p\d+$/.test(role)) { out.push(p); log.unaffected++; continue; }

    if (/^nosnik-col0-p\d+$/.test(role)) {
      const dy = col0Shift(role) || 0;
      const newLenM = p.scale[1] - DELTA_Z / 1000;
      p.position = [x, y + dy, z + DELTA_Z / 2];
      p.scale = [p.scale[0], newLenM, p.scale[2]];
      out.push(p); log.frontSpanCol0++; log.col0Dorovnani += dy ? 1 : 0; continue;
    }
    if (/^nosnik-col1-p\d+$/.test(role)) { out.push(p); log.unaffected++; continue; }

    if (/^spojnice-col0-p\d+$/.test(role)) {
      const distLeg0 = Math.abs(z - LEG_Z.leg0), distLeg1 = Math.abs(z - LEG_Z.leg1);
      const dy = col0Shift(role) || 0;
      if (distLeg0 < distLeg1) { p.position = [x, y + dy, z + DELTA_Z]; }
      else { p.position = [x, y + dy, z]; }
      out.push(p); log.frontSpanCol0++; log.col0Dorovnani += dy ? 1 : 0; continue;
    }
    if (/^spojnice-col1-p\d+$/.test(role)) { out.push(p); log.unaffected++; continue; }

    // podelnik-* (horni ztuzujici pasnice pres col0/col1, Y~981, BEZ ucasti
    // na patro-dorovnani - neni to cislovane patro)
    if (/^podelnik-.*-spodni-1$/.test(role)) { out.push(p); log.unaffected++; continue; }
    if (/^podelnik-.*-(horni|spodni-0)$/.test(role)) {
      const newLenM = p.scale[1] - DELTA_Z / 1000;
      p.position = [x, y, z + DELTA_Z / 2];
      p.scale = [p.scale[0], newLenM, p.scale[2]];
      out.push(p); log.frontSpanFull++; continue;
    }

    // NOVE (333 rozsireni): vypln-dno-N (MDF vyplnova deska dna, stejny
    // Z-rozpon jako podelnik-*-spodni-N pro totez N - viz hlavicka souboru).
    if (role === "vypln-dno-1") { out.push(p); log.unaffected++; continue; }
    if (role === "vypln-dno-0") {
      const newLenM = p.scale[1] - DELTA_Z / 1000;
      p.position = [x, y, z + DELTA_Z / 2];
      p.scale = [p.scale[0], newLenM, p.scale[2]];
      out.push(p); log.frontSpanFull++; continue;
    }

    if (/^pricka-(horni|spodni)-\d+$/.test(role)) { out.push(p); log.unaffected++; continue; }

    if (role === "uhelnik-noha1" || role === "uhelnik-noha2") {
      const oldYnew = role === "uhelnik-noha1" ? OLD_YNEW.leg1 : OLD_YNEW.leg2;
      if (near(y, oldYnew, 3) || near(y, oldYnew + 30, 3)) {
        p.position = [x, y + DELTA_Y, z]; out.push(p);
        (role === "uhelnik-noha1" ? log.leg1Seam++ : log.leg2Seam++); continue;
      }
      out.push(p); log.unaffected++; continue;
    }

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
  return { parts: out, log, touched };
}

module.exports = { transformAssembly, LEG_Z, OLD_YNEW, DELTA_Z, DELTA_Y };

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
cur.execute("SELECT id, data FROM product_assemblies WHERE id IN (333,279,340)")
out = {}
for r in cur.fetchall():
    out[r["id"]] = json.loads(r["data"])["parts"]
conn.close()
print(json.dumps(out))
`;
  fs.writeFileSync("/tmp/_dump_333.py", dumpPy);
  const raw = execSync("api/venv/bin/python3 /tmp/_dump_333.py", { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 80 }).toString();
  const DB = JSON.parse(raw);

  // ---- A) SELF-CHECK 279 -> 340 (rozsireni nesmi nic rozbit) ----
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
  if (mismatches > 0) { console.log("STOP - nepokracuji na 333, dokud self-check neprojde."); process.exit(1); }

  // ---- B) over ktere leg-pozice se v 333 vyskytuji (krok 2 procedury) ----
  console.log("\n=== KROK 2: over leg-pozice v 333 ===");
  const p333 = DB[333];
  console.log("celkem dilu v 333:", p333.length);
  console.log("leg0 (predni-svislice na Z=leg0)?", p333.some(p => p.role === "predni-svislice" && near(p.position[2], LEG_Z.leg0, 1)));
  console.log("leg0 (zadni-svislice-dolni na Z=leg0)?", p333.some(p => p.role === "zadni-svislice-dolni" && near(p.position[2], LEG_Z.leg0, 1)));
  console.log("leg1 plain (predni-svislice na Z=leg1)?", p333.some(p => p.role === "predni-svislice" && near(p.position[2], LEG_Z.leg1, 1)));
  console.log("leg1 vyrez (sloupek-pred-podbehem na Z=leg1)?", p333.some(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], LEG_Z.leg1, 1)));
  console.log("leg2 plain (predni-svislice na Z=leg2)?", p333.some(p => p.role === "predni-svislice" && near(p.position[2], LEG_Z.leg2, 1)));
  console.log("leg2 vyrez (sloupek-pred-podbehem na Z=leg2)?", p333.some(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], LEG_Z.leg2, 1)));

  // svar presnost PRED zmenou (krok 6b prekurzor - over ze 0mm gap plati uz ted)
  for (const leg of ["leg1", "leg2"]) {
    const z = LEG_Z[leg];
    const sloupek = p333.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], z, 1));
    const svislice = p333.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], z, 1));
    const top = sloupek.position[1] + sloupek.scale[1] * 1000 / 2;
    const bottom = svislice.position[1] - svislice.scale[1] * 1000 / 2;
    console.log(`  ${leg}: sloupek top=${top}, svislice bottom=${bottom}, gap=${(bottom - top).toFixed(6)}mm (ocekavano ~0), OLD_YNEW konstanta=${OLD_YNEW[leg]}`);
  }

  // ---- C) aplikuj transform ----
  console.log("\n=== KROK 3-5: aplikace transformu na 333 ===");
  const { parts: result333, log: log333, touched } = transformAssembly(p333);
  console.log("log:", JSON.stringify(log333, null, 1));
  console.log("celkem dilu:", p333.length, "-> vystup:", result333.length);
  if (result333.length !== p333.length) throw new Error("Pocet dilu se zmenil - STOP.");

  console.log("\nlogo-ochrana klasifikace (11 paru x2):");
  for (const t of touched) console.log(" ", JSON.stringify(t));

  // ---- D) explicitni dorovnani sanity check (krok 4) pro col0 A col1 ----
  console.log("\n=== KROK 4: dorovnani sanity check (explicitni, nad JIZ transformovanymi daty) ===");
  function bottomEdgeAndLimit(colPrefix, legsToCheck) {
    const nosnikP0 = result333.filter(p => new RegExp(`^nosnik-${colPrefix}-p\\d+$`).test(p.role))
      .reduce((min, p) => (min === null || p.position[1] < min.position[1]) ? p : min, null);
    if (!nosnikP0) return null;
    const bottomEdge = nosnikP0.position[1] - HALF_T;
    const limit = Math.max(...legsToCheck.map(l => OLD_YNEW[l] + DELTA_Y));
    return { role: nosnikP0.role, bottomEdge, limit, ok: bottomEdge >= limit - 1e-6 };
  }
  const c0 = bottomEdgeAndLimit("col0", ["leg1"]);
  console.log("col0:", JSON.stringify(c0));
  if (c0 && !c0.ok) throw new Error("col0 nejnizsi patro VISI VE VZDUCHU po transformu - dorovnani neni spravne!");
  const c1 = bottomEdgeAndLimit("col1", ["leg1", "leg2"]);
  console.log("col1:", JSON.stringify(c1));
  if (c1 && !c1.ok) throw new Error("col1 nejnizsi patro VISI VE VZDUCHU po transformu - potreba dorovnani, skript to nema!");

  fs.writeFileSync(__dirname + "/tmp_2026-09-12_333_parts_new.json", JSON.stringify(result333));
  console.log("\nUlozeno: scripts/tmp_2026-09-12_333_parts_new.json");
}
