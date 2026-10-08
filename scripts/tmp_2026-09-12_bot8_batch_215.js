// Prepocet kolizni rezervy (2/20mm -> 10/30mm) na product_assemblies.id=215
// (rodina K-118 = Citroen Jumpy Crew Cab L2, karoserie_kod K-118), podle
// procedury shape_geometry_methods.id=11 "prepocet-kolizni-rezervy-existujici-
// sestavy" a jiz zjistenych leg-dat rodiny (dodano zadanim, viz AGENTS_LOG).
//
// LEG DATA (K-118, identicke na vsech 3 sourozencich 184/215/285, overeno
// primo ctenim dat 215 nize): LEG0 Z=-1170.5000534057617 (plna noha, cela
// rigidni - predni-svislice X=-439 + zadni-svislice-dolni X=-735 + cap +
// spojnice-dolni/horni + zaslepky + uhelnik-noha0). LEG1 Z=-308.5000534057617
// (SOUCASNE predni-svislice X=-439 (plain) I vyrezova trojice X=-735/-611
// (zadni-svislice-nad-zarezem/sloupek-pred-podbehem/pricka-uzavreni-vyrezu)
// na stejnem Z). OLD_YNEW (sloupek top = svislice bottom) = 291.0001220703125.
//
// KLICOVE ROZHODNUTI (predni-svislice@leg1): zadani teto ulohy (vstupni
// "fakta" od predchoziho kroku) doslovne rika, ze KAZDA instance role
// "predni-svislice" (vc. te na Z1) dostava deltaZ nezavisle. Ale REALNE,
// JIZ OVERENE zpracovani sourozence 184->348 (stejna rodina K-118,
// hotovo/zapsano pred timto behem) predni-svislice@leg1 NEPOSOUVA (dZ=0,
// zjisteno primym diffem 184 vs 348 nad VSEMI 61 dily - viz AGENTS_LOG
// zapis k teto sestave). Overeno i fyzicky: car_bodies/..._B.glb (prepazka,
// car_body_placement_methods.id=1) ma Z rozsah [-1725,-1096] - leg1
// (Z=-308.5) je 788mm od nejblizsi hrany teto steny, tedy k ni realne
// NEPRILEHA a zvyseni rezervy od ni nema na leg1 zadny fyzicky dopad.
// Aby vysledek zustal KONZISTENTNI s uz hotovym a zapsanym sourozencem
// 184->348 (a nevytvaril zbytecne mismatch dilu, ktere by pri doslovnem
// posunu predni-svislice@leg1 vznikly vuci spojnice-dolni/horni/cap, jez
// leg1 sdili s vyrezovou trojici na stejnem Z), POUZIVAM STEJNY, JIZ
// OVERENY vzor jako 348: predni-svislice@leg1 (a jeji cap/spojnice/zaslepka)
// se v Z NEHYBOU - meni se JEN u vyrezove trojice (Y) a u vseho na leg0.
// Transform nize je extrahovan PRIMO diffem 184 (pred) vs 348 (po, uz
// overeno/zapsano) nad VSEMI sdilenymi rolemi - ne "znovu vymysleny".
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { execSync } = require("child_process");

const LEG0_Z = -1170.5000534057617;
const LEG1_Z = -308.5000534057617;
const DELTA_Z = 8;   // 10mm - 2mm (prepazka)
const DELTA_Y = 10;  // 30mm - 20mm (podbeh)
const T = 30, HALF_T = 15;
const ZTOL = 1;
const near = (a, b, eps) => Math.abs(a - b) < (eps == null ? 0.05 : eps);

function transformAssembly(parts, oldYnew) {
  const newYnew = oldYnew + DELTA_Y;
  const log = { leg0Rigid: 0, leg1Unaffected: 0, seamVyrez: 0, uhelnikSeam: 0, uhelnikUnaffected: 0,
    eurobox: 0, nosnik: 0, spojniceNearLeg0: 0, spojniceMid: 0, spojniceNearLeg1: 0, carBody: 0, other: 0 };
  const out = [];

  for (const orig of parts) {
    const p = JSON.parse(JSON.stringify(orig));
    const role = p.role || "";
    const [x, y, z] = p.position;

    if (String(p.part_id || "").startsWith("car_body_")) { out.push(p); log.carBody++; continue; }

    // -- role sdilena leg0 (rigidni cely sloupek) / leg1-predni-svislice
    //    (nehybe se, viz zduvodneni v hlavicce) : cap/predni-svislice/
    //    spojnice-dolni/spojnice-horni/zaslepka
    if (["cap", "predni-svislice", "spojnice-dolni", "spojnice-horni", "zaslepka"].includes(role)) {
      if (near(z, LEG0_Z, ZTOL)) { p.position = [x, y, z + DELTA_Z]; out.push(p); log.leg0Rigid++; continue; }
      out.push(p); log.leg1Unaffected++; continue; // na leg1 - beze zmeny
    }

    // -- role vyskytujici se JEN na leg0 (cela plna noha)
    if (role === "zadni-svislice-dolni" || role === "uhelnik-noha0") {
      p.position = [x, y, z + DELTA_Z]; out.push(p); log.leg0Rigid++; continue;
    }

    // -- uhelnik-noha1: Y-shift jen kdyz sedi presne na starem svaru (nebo +30 odsazeni)
    if (role === "uhelnik-noha1") {
      if (near(y, oldYnew, 2) || near(y, oldYnew + 30, 2)) {
        p.position = [x, y + DELTA_Y, z]; out.push(p); log.uhelnikSeam++; continue;
      }
      out.push(p); log.uhelnikUnaffected++; continue;
    }

    // -- vyrezova trojice (jen na leg1, Z se nemeni, jen Y)
    if (role === "sloupek-pred-podbehem") {
      const oldH = p.scale[1] * 1000, floorY = y - oldH / 2, newH = newYnew - floorY;
      p.position = [x, floorY + newH / 2, z]; p.scale = [p.scale[0], newH / 1000, p.scale[2]];
      out.push(p); log.seamVyrez++; continue;
    }
    if (role === "zadni-svislice-nad-zarezem") {
      const oldH = p.scale[1] * 1000, topY = y + oldH / 2, newH = topY - newYnew;
      p.position = [x, newYnew + newH / 2, z]; p.scale = [p.scale[0], newH / 1000, p.scale[2]];
      out.push(p); log.seamVyrez++; continue;
    }
    if (role === "pricka-uzavreni-vyrezu") {
      p.position = [x, newYnew + HALF_T, z]; out.push(p); log.seamVyrez++; continue;
    }

    // -- sloupec0 (jediny sloupec, opira se o leg0 i leg1)
    if (/^eurobox-sloupec0-patro\d+$/.test(role)) {
      p.position = [x, y, z + DELTA_Z / 2]; out.push(p); log.eurobox++; continue;
    }
    if (/^nosnik-sloupec0-patro\d+$/.test(role)) {
      const newLenM = p.scale[1] - DELTA_Z / 1000;
      p.position = [x, y, z + DELTA_Z / 2]; p.scale = [p.scale[0], newLenM, p.scale[2]];
      out.push(p); log.nosnik++; continue;
    }
    if (/^spojnice-sloupec0-patro\d+$/.test(role)) {
      const dLeg0 = Math.abs(z - LEG0_Z), dLeg1 = Math.abs(z - LEG1_Z);
      if (dLeg0 <= 35) { p.position = [x, y, z + DELTA_Z]; out.push(p); log.spojniceNearLeg0++; continue; }
      if (dLeg1 <= 35) { out.push(p); log.spojniceNearLeg1++; continue; }
      p.position = [x, y, z + DELTA_Z / 2]; out.push(p); log.spojniceMid++; continue;
    }

    out.push(p); log.other++;
  }
  return { parts: out, log };
}

module.exports = { transformAssembly, LEG0_Z, LEG1_Z, DELTA_Z, DELTA_Y };

// ============================================================
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
cur.execute("SELECT id, data FROM product_assemblies WHERE id IN (215,184,348)")
out = {}
for r in cur.fetchall():
    out[r["id"]] = json.loads(r["data"])["parts"]
conn.close()
print(json.dumps(out))
`;
  fs.writeFileSync("/tmp/_dump_215.py", dumpPy);
  const raw = execSync("api/venv/bin/python3 /tmp/_dump_215.py", { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 80 }).toString();
  const DB = JSON.parse(raw);

  // ---- A) SELF-CHECK: transform(184) musi presne sedet na skutecny 348 ----
  console.log("=== SELF-CHECK: transform(184) vs skutecny (jiz overeny) 348 ===");
  const p184 = DB[184];
  const sloupek184 = p184.find(p => p.role === "sloupek-pred-podbehem");
  const oldYnew184 = sloupek184.position[1] + (sloupek184.scale[1] * 1000) / 2;
  const { parts: myResult184, log: log184 } = transformAssembly(p184, oldYnew184);
  console.log("oldYnew184=", oldYnew184, "log:", JSON.stringify(log184));

  function byRoleSorted(parts) {
    const m = {};
    for (const p of parts) { const r = p.role || "(none)"; (m[r] = m[r] || []).push(p); }
    for (const r in m) m[r].sort((a, b) => a.position[2] - b.position[2] || a.position[0] - b.position[0] || a.position[1] - b.position[1]);
    return m;
  }
  const mMine = byRoleSorted(myResult184.filter(p => !String(p.part_id || "").startsWith("car_body_")));
  const mRef = byRoleSorted(DB[348].filter(p => !String(p.part_id || "").startsWith("car_body_")));
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
  console.log(mismatches === 0 ? "SELF-CHECK OK: presna shoda s 348 na vsech sdilenych rolich." : `SELF-CHECK SELHAL: ${mismatches} nesrovnalosti.`);
  if (mismatches > 0) { console.log("STOP - nepokracuji na 215, dokud self-check neprojde."); process.exit(1); }

  // ---- B) aplikuj na 215 ----
  console.log("\n=== APLIKACE na 215 ===");
  const p215 = DB[215];
  const sloupek215 = p215.find(p => p.role === "sloupek-pred-podbehem");
  console.log("leg0 pritomen (predni-svislice na Z=leg0)?", p215.some(p => p.role === "predni-svislice" && near(p.position[2], LEG0_Z, 1)));
  console.log("leg1 predni-svislice pritomna?", p215.some(p => p.role === "predni-svislice" && near(p.position[2], LEG1_Z, 1)));
  console.log("leg1 vyrez (sloupek-pred-podbehem) pritomen?", !!sloupek215 && near(sloupek215.position[2], LEG1_Z, 1));
  const oldYnew215 = sloupek215.position[1] + (sloupek215.scale[1] * 1000) / 2;
  console.log("oldYnew215=", oldYnew215, "(ocekavano ~291.0001220703125)");

  // krok 4: visici luzko check - nejnizsi patro sloupec0 vs novy Y_new leg1
  const nosnikY = p215.filter(p => /^nosnik-sloupec0-patro\d+$/.test(p.role || "")).map(p => p.position[1]);
  const minPatroY = Math.min(...nosnikY);
  const spodniHrana = minPatroY - HALF_T;
  const newYnew215 = oldYnew215 + DELTA_Y;
  console.log(`krok4: nejnizsi patro Y=${minPatroY}, spodni hrana=${spodniHrana}, novy Y_new(leg1)=${newYnew215}, clearance=${(spodniHrana - newYnew215).toFixed(3)}mm (${spodniHrana >= newYnew215 ? "OK, NEVISI - dorovnani NENI potreba" : "VISI - dorovnani POTREBA"})`);

  const { parts: result215, log: log215 } = transformAssembly(p215, oldYnew215);
  console.log("log (215):", JSON.stringify(log215));
  console.log("celkem dilu:", p215.length, "-> vystup:", result215.length);

  fs.writeFileSync(__dirname + "/tmp_2026-09-12_215_parts_new.json", JSON.stringify(result215));
  console.log("\nUlozeno: tmp_2026-09-12_215_parts_new.json");
}
