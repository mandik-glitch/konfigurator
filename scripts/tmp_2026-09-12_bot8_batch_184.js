// Prepocet kolizni rezervy (2/20mm -> 10/30mm) na product_assemblies.id=184
// (rodina K-118 = Citroen Jumpy Crew Cab L2, karoserie_kod K-118), podle
// procedury shape_geometry_methods.id=11
// "prepocet-kolizni-rezervy-existujici-sestavy".
//
// Vstupni fakta o nohach teto rodiny (dana zadanim, NEPROVADI se vlastni
// kolizni analyza): 2 fyzicke Z-pozice noh, identicke napric rodinou K-118
// (overeno 3x primo v DB - 184/215/285):
//   leg0 Z=-1170.5000534057617  (jen "plain": predni-svislice + zadni-svislice-dolni + cap + spojnice-dolni/horni)
//   leg1 Z=-308.5000534057617   (predni-svislice PLAIN + vyrezova trojice SOUCASNE na stejnem Z)
//   OLD_YNEW: leg1=291.0001220703125 (svar sloupek-pred-podbehem / zadni-svislice-nad-zarezem, gap=0mm - overeno primo v datech 184 nize)
//
// TRANSFORM PRAVIDLA: vychazeji z textu procedury KROK 3, ale u leg1 (kde se
// "plna" a "vyrez" noha prekryvaji na stejnem Z) jsou DOPLNENA/OPRAVENA podle
// EMPIRICKEHO overeni na uz hotovem a overenem paru K-075 279(pred,2/20mm) ->
// 340(po,10/30mm) - viz SELF-CHECK sekce nize, ktera tohle overuje bit-presne
// pred aplikaci na 184:
//   - na leg1 (sdilene Z) zustavaji predni-svislice/cap/spojnice-dolni/
//     spojnice-horni/zaslepka (vsechny, i ty "patrici" k vyrezove noze, napr.
//     zaslepka-zadni-svislice-nad-zarezem) BEZE ZMENY (ani Z, ani Y) - i kdyz
//     text procedury naznacuje, ze zaslepka-* vyrezove nohy ma +=deltaY. Text
//     procedury tohle explicitne neresi (leg1 = Z sdilena dvema typy nohou
//     je specialni pripad), realna overena data 340 ukazuji "beze zmeny" a
//     fyzikalne to sedi: zaslepka kryje KONEC dilu, ktery se u vyrezove nohy
//     NEHYBE (sloupek ma fixni SPODEK, svislice ma fixni VRCHOL - hybe se jen
//     stred/svar, kde zadna zaslepka neni).
//   - JEN samotna vyrezova trojice (sloupek-pred-podbehem/zadni-svislice-
//     nad-zarezem/pricka-uzavreni-vyrezu) dostava Y-posun podle vzorce id=6.
//   - sloupec (nosnik/spojnice/eurobox) mezi leg0..leg1: stred Z +=deltaZ/2,
//     nosnik/eurobox delka -deltaZ (jen nosnik ma scale zmenu, eurobox ne),
//     spojnice u leg0 dostava CELE deltaZ, spojnice u leg1 zadne. K-118 ma
//     navic (na rozdil od K-075 col0) TRETI "spojnice-sloupec0-patroN" v
//     polovine rozpeti (~1mm od stredu Z0..Z1) - ta neni u zadne nohy, takze
//     sleduje stred nosniku (+deltaZ/2), ne binarni "blizsi noze" pravidlo
//     (to by ji o par mm nesmyslne prirklo cele +8).
//   - dorovnani pater (KROK 5): POCITA SE, ale u 184 vychazi 0mm (spodni
//     hrana nejnizsiho patra uz ma 29mm rezervu nad starym Y_new, po +10mm
//     Y_new zbyva 19mm > 0 -> zadne "viseni ve vzduchu").

const fs = require("fs");
const THREE = require("three");
const { execSync } = require("child_process");

const DELTA_Z = 8;   // 10mm - 2mm (prepazka)
const DELTA_Y = 10;  // 30mm - 20mm (podbeh)
const T = 30, HALF_T = 15;
const near = (a, b, eps) => Math.abs(a - b) < (eps == null ? 0.05 : eps);

// ---- id=6 vzorec pro Y-posun vyrezove nohy ----
function shiftVyrezPart(p, role, oldYnew, deltaY) {
  const [x, y, z] = p.position;
  const newYnew = oldYnew + deltaY;
  if (role === "sloupek-pred-podbehem") {
    const oldH = p.scale[1] * 1000, floorY = y - oldH / 2, newH = newYnew - floorY;
    return { ...p, position: [x, floorY + newH / 2, z], scale: [p.scale[0], newH / 1000, p.scale[2]] };
  }
  if (role === "zadni-svislice-nad-zarezem") {
    const oldH = p.scale[1] * 1000, topY = y + oldH / 2, newH = topY - newYnew;
    return { ...p, position: [x, newYnew + newH / 2, z], scale: [p.scale[0], newH / 1000, p.scale[2]] };
  }
  if (role === "pricka-uzavreni-vyrezu") {
    return { ...p, position: [x, newYnew + HALF_T, z] };
  }
  throw new Error("neznama vyrez role: " + role);
}

// levels: pole nazvu urovni (napr. ["p0","p1","p2"] nebo ["patro0","patro1","patro2"]),
// serazenych vzestupne podle Y (0=nejnizsi) - dorovnani[i] = deltaY*(N-1-i)/(N-1)
function makeDorovnaniFn(levels, dorovnaniOverride) {
  const N = levels.length;
  return function (levelKey) {
    if (dorovnaniOverride != null) return dorovnaniOverride; // force 0 kdyz krok 4 rekl "neni potreba"
    const i = levels.indexOf(levelKey);
    if (i < 0 || N <= 1) return 0;
    return DELTA_Y * (N - 1 - i) / (N - 1);
  };
}

// Genericka transformace jedne "rodiny" (parametrizovano nazvy roli), pouzitelna
// jak pro self-check (K-075 col0/pN) tak pro realnou aplikaci (K-118 sloupec0/patroN).
function transformAssembly(parts, cfg) {
  // cfg: { legZ0 (Z ciste plna noha), sharedLegs:[{z, uhelnikRole, oldYnew}, ...]
  //        (Z sdilene plnou i vyrezovou nohou soucasne), colPrefix (napr. "col0"/"sloupec0"),
  //        dorovnaniOverride (cislo nebo null - kdyz null, pocita se z poctu urovni) }
  const { legZ0, sharedLegs, colPrefix, dorovnaniOverride } = cfg;
  const ZTOL = 1;
  const log = { leg0Rigid: 0, sharedLegUnaffected: 0, sharedLegVyrezShift: 0, uhelnikNoha0: 0,
    uhelnikSharedShift: 0, uhelnikSharedUnaffected: 0, colSpanBeam: 0, colSpanEnd: 0, colSpanMid: 0,
    carBody: 0, unaffected: 0 };
  const out = [];
  const allLegZ = [legZ0, ...sharedLegs.map(l => l.z)];

  const nosnikLevelRe = new RegExp(`^nosnik-${colPrefix}-(\\w+)$`);
  const spojniceLevelRe = new RegExp(`^spojnice-${colPrefix}-(\\w+)$`);
  const euroboxLevelRe = new RegExp(`^eurobox-${colPrefix}-(\\w+)$`);
  function levelKeyOf(role) {
    let m = nosnikLevelRe.exec(role) || spojniceLevelRe.exec(role) || euroboxLevelRe.exec(role);
    return m ? m[1] : null;
  }
  const nosnikParts = parts.filter(p => nosnikLevelRe.test(p.role || ""));
  const levelSet = [...new Set(nosnikParts.map(p => levelKeyOf(p.role)))];
  levelSet.sort((a, b) => {
    const ya = Math.min(...nosnikParts.filter(p => levelKeyOf(p.role) === a).map(p => p.position[1]));
    const yb = Math.min(...nosnikParts.filter(p => levelKeyOf(p.role) === b).map(p => p.position[1]));
    return ya - yb;
  });
  const dorovnaniFn = makeDorovnaniFn(levelSet, dorovnaniOverride);

  for (const orig of parts) {
    const p = JSON.parse(JSON.stringify(orig));
    const role = p.role || "";
    const [x, y, z] = p.position;

    if (String(p.part_id || "").startsWith("car_body_")) { out.push(p); log.carBody++; continue; }

    // -- uhelnik-noha0: VZDY cele deltaZ (bez ohledu na presny Z-offset od leg0) --
    if (role === "uhelnik-noha0") {
      out.push({ ...p, position: [x, y, z + DELTA_Z] }); log.uhelnikNoha0++; continue;
    }
    // -- uhelnik-noha<N> patrici sdilene noze: deltaY JEN kdyz Y sedi na starem svaru nebo +30 odsazeni --
    const sharedByUhelnik = sharedLegs.find(l => l.uhelnikRole === role);
    if (sharedByUhelnik) {
      if (near(y, sharedByUhelnik.oldYnew, 3) || near(y, sharedByUhelnik.oldYnew + 30, 3)) {
        out.push({ ...p, position: [x, y + DELTA_Y, z] }); log.uhelnikSharedShift++; continue;
      }
      out.push(p); log.uhelnikSharedUnaffected++; continue;
    }

    // -- vyrezova trojice na sdilene noze: Y-posun podle id=6 formule, Z beze zmeny --
    if (role === "sloupek-pred-podbehem" || role === "zadni-svislice-nad-zarezem" || role === "pricka-uzavreni-vyrezu") {
      const leg = sharedLegs.find(l => near(z, l.z, ZTOL));
      if (leg) {
        out.push(shiftVyrezPart(p, role, leg.oldYnew, DELTA_Y)); log.sharedLegVyrezShift++; continue;
      }
    }

    // -- roli plna noha (predni-svislice/cap/spojnice-dolni/spojnice-horni/
    //    zadni-svislice-dolni/zaslepka): na PRESNE legZ0 -> cele deltaZ,
    //    na sdilene noze -> beze zmeny (overeno empiricky na 279->340) --
    const LEG_FRAME_ROLES = new Set(["predni-svislice", "cap", "spojnice-dolni", "spojnice-horni",
      "zadni-svislice-dolni", "zaslepka"]);
    if (LEG_FRAME_ROLES.has(role)) {
      if (near(z, legZ0, ZTOL)) {
        out.push({ ...p, position: [x, y, z + DELTA_Z] }); log.leg0Rigid++; continue;
      }
      if (sharedLegs.some(l => near(z, l.z, ZTOL))) {
        out.push(p); log.sharedLegUnaffected++; continue;
      }
      // na zadne zname noze - nemelo by nastat, ponech beze zmeny a oznac
      out.push(p); log.unaffected++; continue;
    }

    // -- sloupec: nosnik/eurobox (rozpeti legZ0..nejblizsi sdilena noha, stred +deltaZ/2) --
    if (nosnikLevelRe.test(role) || euroboxLevelRe.test(role)) {
      const lvl = levelKeyOf(role);
      const dy = dorovnaniFn(lvl);
      const isNosnik = nosnikLevelRe.test(role);
      const newPos = [x, y + dy, z + DELTA_Z / 2];
      const newScale = isNosnik ? [p.scale[0], p.scale[1] - DELTA_Z / 1000, p.scale[2]] : p.scale;
      out.push({ ...p, position: newPos, scale: newScale }); log.colSpanBeam++; continue;
    }

    // -- sloupec: spojnice (3 varianty - blizko legZ0 / blizko sdilene nohy / uprostred rozpeti) --
    if (spojniceLevelRe.test(role)) {
      const lvl = levelKeyOf(role);
      const dy = dorovnaniFn(lvl);
      const distLeg0 = Math.abs(z - legZ0);
      const NEAR_LEG_TOL = 60; // empiricky: koncove spojnice jsou ~30mm od nohy, stredova je ~1mm od stredu rozpeti
      const nearestSharedDist = Math.min(...allLegZ.slice(1).map(lz => Math.abs(z - lz)));
      if (distLeg0 < NEAR_LEG_TOL) {
        out.push({ ...p, position: [x, y + dy, z + DELTA_Z], scale: p.scale }); log.colSpanEnd++; continue;
      }
      if (nearestSharedDist < NEAR_LEG_TOL) {
        out.push({ ...p, position: [x, y + dy, z], scale: p.scale }); log.colSpanEnd++; continue;
      }
      // uprostred rozpeti - sleduje stred nosniku (+deltaZ/2), scale beze zmeny (neroztahuje se)
      out.push({ ...p, position: [x, y + dy, z + DELTA_Z / 2], scale: p.scale }); log.colSpanMid++; continue;
    }

    out.push(p); log.unaffected++;
  }
  return { parts: out, log };
}

module.exports = { transformAssembly, DELTA_Z, DELTA_Y };

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
cur.execute("SELECT id, data FROM product_assemblies WHERE id IN (184,279,340)")
out = {}
for r in cur.fetchall():
    out[r["id"]] = json.loads(r["data"])["parts"]
conn.close()
print(json.dumps(out))
`;
  fs.writeFileSync("/tmp/_dump_184batch.py", dumpPy);
  const raw = execSync("api/venv/bin/python3 /tmp/_dump_184batch.py", { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 80 }).toString();
  const DB = JSON.parse(raw);

  // ---- A) SELF-CHECK: transform(279, col0/pN params) vs skutecny 340 ----
  console.log("=== SELF-CHECK: genericka transformAssembly(279, col0) vs skutecny 340 ===");
  const p279 = DB[279], p340 = DB[340].filter(p => !(p.role || "").startsWith("kontrolni-pomucka"));
  const cfg279 = {
    legZ0: -1358.5025482177734,
    sharedLegs: [
      { z: -898.5025482177734, uhelnikRole: "uhelnik-noha1", oldYnew: 101.50017929077148 },
      { z: -34.50254821777344, uhelnikRole: "uhelnik-noha2", oldYnew: 53.500179290771484 },
    ],
    colPrefix: "col0",
    dorovnaniOverride: null,
  };
  // K-075 leg1 ma "spojnice-horni-uzavreni" misto "spojnice-horni" - doplnime do LEG_FRAME_ROLES
  // pro tenhle self-check pres male opicani (monkeypatch) neni potreba, staci parts predfiltrovat:
  // spojnice-horni-uzavreni bereme jako additional LEG_FRAME rovnocenna - upravime kopii funkce
  // jednoduseji: pretypujeme roli jen pro ucely testu (nemeni vstupni data 279).
  const p279ForTest = p279.map(p => (p.role === "spojnice-horni-uzavreni") ? { ...p, role: "spojnice-horni" } : p);
  const p340ForTest = p340.map(p => (p.role === "spojnice-horni-uzavreni") ? { ...p, role: "spojnice-horni" } : p);
  // K-075 zaslepka je jmenovana zaslepka-<co>, K-118 jen "zaslepka" - sjednotime pro test tak,
  // aby odpovidalo LEG_FRAME_ROLES ("zaslepka") - vsechny 4 varianty maji byt na leg0 rigid / leg1 unaffected.
  const p279b = p279ForTest.map(p => /^zaslepka-/.test(p.role || "") ? { ...p, role: "zaslepka" } : p);
  const p340b = p340ForTest.map(p => /^zaslepka-/.test(p.role || "") ? { ...p, role: "zaslepka" } : p);
  // logo-ochrana-* v K-075 na leg0 dostava taky cele deltaZ (patri do "plna noha" skupiny) -
  // v generickem transformAssembly nejsou LEG_FRAME_ROLES zahrnuty (K-118 zadne logo nema),
  // takze je pro tenhle self-check filtrujeme pryc (netestujeme je, K-118 se to netyka).
  // col1 (span leg1..leg2) netestujeme - K-118 ma jen jeden sloupec (col0/sloupec0)
  const irrelevant = p => /^logo-ochrana-/.test(p.role || "") || /-col1-/.test(p.role || "");
  const p279c = p279b.filter(p => !irrelevant(p));
  const p340c = p340b.filter(p => !irrelevant(p));

  const { parts: myResult, log: log279 } = transformAssembly(p279c, cfg279);
  console.log("log (279):", JSON.stringify(log279));

  function byRoleSorted(parts) {
    const m = {};
    for (const p of parts) { const r = p.role || "(none)"; (m[r] = m[r] || []).push(p); }
    for (const r in m) m[r].sort((a, b) => a.position[2] - b.position[2] || a.position[0] - b.position[0] || a.position[1] - b.position[1]);
    return m;
  }
  const mMine = byRoleSorted(myResult.filter(p => !String(p.part_id || "").startsWith("car_body_")));
  const mRef = byRoleSorted(p340c.filter(p => !String(p.part_id || "").startsWith("car_body_")));
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
  console.log(mismatches === 0 ? "SELF-CHECK OK: presna shoda s 340 na vsech sdilenych/testovanych rolich (col0,leg0,leg1,uhelnik)." : `SELF-CHECK SELHAL: ${mismatches} nesrovnalosti.`);
  if (mismatches > 0) { console.log("STOP - nepokracuji na 184, dokud self-check neprojde."); process.exit(1); }

  // ---- B) aplikuj na 184 ----
  console.log("\n=== APLIKACE na 184 (K-118, sloupec0/patroN) ===");
  const p184 = DB[184];
  const LEG_Z_184 = { leg0: -1170.5000534057617, leg1: -308.5000534057617 };
  const OLD_YNEW_184 = 291.0001220703125;

  // krok 4: over jestli je potreba dorovnani (nejnizsi patro sloupce vs Y_new nohy1)
  const nosnikPatro0 = p184.filter(p => p.role === "nosnik-sloupec0-patro0");
  const floorEdge = Math.min(...nosnikPatro0.map(p => p.position[1])) - 15; // poloviny tloustky profilu (30mm)
  const newYnewLeg1 = OLD_YNEW_184 + DELTA_Y;
  console.log(`krok4: floorEdge patro0 = ${floorEdge}, newYnewLeg1 = ${newYnewLeg1}, visi_ve_vzduchu=${floorEdge < newYnewLeg1}`);
  const dorovnaniOverride = (floorEdge < newYnewLeg1) ? null : 0; // 0 = zadne dorovnani potreba

  const cfg184 = {
    legZ0: LEG_Z_184.leg0,
    sharedLegs: [{ z: LEG_Z_184.leg1, uhelnikRole: "uhelnik-noha1", oldYnew: OLD_YNEW_184 }],
    colPrefix: "sloupec0",
    dorovnaniOverride,
  };

  console.log("leg0 pritomen?", p184.some(p => p.role === "predni-svislice" && near(p.position[2], LEG_Z_184.leg0, 1)));
  console.log("leg1 plna pritomna?", p184.some(p => p.role === "predni-svislice" && near(p.position[2], LEG_Z_184.leg1, 1)));
  console.log("leg1 vyrez pritomen?", p184.some(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], LEG_Z_184.leg1, 1)));

  const { parts: result184, log: log184 } = transformAssembly(p184, cfg184);
  console.log("log (184):", JSON.stringify(log184));
  console.log("celkem dilu:", p184.length, "-> vystup:", result184.length);

  fs.writeFileSync(__dirname + "/tmp_2026-09-12_184_parts_new.json", JSON.stringify(result184));
  console.log("\nUlozeno: tmp_2026-09-12_184_parts_new.json");
}
