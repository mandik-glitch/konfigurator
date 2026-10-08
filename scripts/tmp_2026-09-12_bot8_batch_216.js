// Prepocet kolizni rezervy (2/20mm -> 10/30mm) na product_assemblies.id=216
// (rodina K-119 = Citroen Jumpy Crew Cab L3, karoserie_kod K-119, verze B
// "boxy43-120x12"), podle procedury shape_geometry_methods.id=11
// "prepocet-kolizni-rezervy-existujici-sestavy".
//
// Vstupni fakta o nohach teto rodiny (DANA ZADANIM teto session, zadna
// vlastni kolizni re-analyza noh se nedelala):
//   leg0 (plain) Z=-1522.500114440918
//   leg1 (sdilena: plna "predni" cast + vyrezova trojice SOUCASNE na stejnem Z)
//        Z=-260.50011444091797, OLD_YNEW=141.00018310546875, wall_x=-736
//   (zdroj: predchozi krok teto session, overeno na vsech 3 sourozencich
//   rodiny K-119 - id=185/216/286 - na realne GLB geometrii)
//
// STRUKTURA id=216 OVERENA PRIMO V DATECH (76 dilu, precteno primo z DB):
//   role "predni-svislice" 2x (X=-440, na OBOU Z) - presne stejny "sdileny Z"
//   jev jako uz reseno u sourozenecke rodiny K-118 (id=184->348, tento skript
//   PREBIRA jeho jiz overenou genericku transformAssembly() 1:1, jen s jinymi
//   cfg hodnotami - viz scripts/tmp_2026-09-12_bot8_batch_184.js).
//   role "zadni-svislice-dolni" jen 1x (jen na leg0 - na leg1 ji nahrazuje
//   "zadni-svislice-nad-zarezem", vyrezova protejsi strana), "spojnice-dolni"/
//   "spojnice-horni"/"cap"/"zaslepka" po 2x (shodne s K-118 vzorem). Sloupec
//   ma jmeno "sloupec0" (4 patra: patro0..patro3), s "nosnik-sloupec0-patroN"
//   (2/patro, front X=-440 + back X=-736, Z=-891.500114440918 = presny
//   stred rozpeti leg0..leg1), "spojnice-sloupec0-patroN" (4/patro - 2
//   blizko konci (Z~30mm od nohy) + 2 "stredove" symetricky kolem stredu
//   rozpeti Z=-891.5 (na Z=-1092.5 a -691.5, +-200mm od stredu) - genericke
//   pravidlo "mid" v transformAssembly() zvladne LIBOVOLNY pocet stredovych
//   spojnic, netreba upravovat), "eurobox-sloupec0-patroN" (3/patro).
//   "uhelnik-noha0" 7x (VZDY cele deltaZ, presne jako K-118), "uhelnik-noha1"
//   12x - z toho presne 5 ma Y na starem svaru (~141.0/171.0mm, tj.
//   OLD_YNEW/OLD_YNEW+30) a dostava deltaY, zbylych 7 (Y~891/921/31, rohove
//   uhelniky nesouvisejici se svarem) zustava beze zmeny - stejny pomer
//   5/12 jako u K-118 (kde bylo 5/12 na Y=291/321).
//
// TRANSFORM PRAVIDLA: identicka s jiz overenym scripts/tmp_2026-09-12_
// bot8_batch_184.js (K-118, 184->348, zapsano bez chyb v teto session) -
// funkce transformAssembly() je sem zkopirovana BEZE ZMENY logiky (jen
// komentar upraven), aby byl tenhle soubor soběstačný/auditovatelny sam o
// sobe bez zavislosti na soubory sourozenecke session, ktera muze byt
// jeste ve zpracovani:
//   - na leg1 (sdilene Z) zustavaji predni-svislice/cap/spojnice-dolni/
//     spojnice-horni/zaslepka BEZE ZMENY (ani Z, ani Y).
//   - JEN samotna vyrezova trojice (sloupek-pred-podbehem/zadni-svislice-
//     nad-zarezem/pricka-uzavreni-vyrezu) dostava Y-posun podle vzorce id=6.
//   - sloupec (nosnik/spojnice/eurobox) mezi leg0..leg1: stred Z +=deltaZ/2,
//     nosnik delka -deltaZ (eurobox delku nemeni), spojnice u leg0 dostava
//     CELE deltaZ, spojnice u leg1 zadne, "stredove" spojnice sleduji stred
//     nosniku (+deltaZ/2), scale beze zmeny.
//   - dorovnani pater (KROK 5): POCITA SE runtime (viz nize) - u 216 vychazi
//     0mm (floorEdge patra0 ma po delte kolem 169mm rezervy nad novym
//     Y_new nohy1, mnohem vic nez K-118, dorovnani neni potreba).

const fs = require("fs");
const { execSync } = require("child_process");

const DELTA_Z = 8;   // 10mm - 2mm (prepazka)
const DELTA_Y = 10;  // 30mm - 20mm (podbeh)
const HALF_T = 15;   // polovina tloustky pricky-uzavreni-vyrezu profilu (30mm)
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

function makeDorovnaniFn(levels, dorovnaniOverride) {
  const N = levels.length;
  return function (levelKey) {
    if (dorovnaniOverride != null) return dorovnaniOverride;
    const i = levels.indexOf(levelKey);
    if (i < 0 || N <= 1) return 0;
    return DELTA_Y * (N - 1 - i) / (N - 1);
  };
}

// Genericka transformace (prevzata 1:1 z scripts/tmp_2026-09-12_bot8_batch_184.js,
// jiz overena na K-075 279->340 self-checku a naostro pouzita na K-118 184->348).
function transformAssembly(parts, cfg) {
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

    if (role === "uhelnik-noha0") {
      out.push({ ...p, position: [x, y, z + DELTA_Z] }); log.uhelnikNoha0++; continue;
    }
    const sharedByUhelnik = sharedLegs.find(l => l.uhelnikRole === role);
    if (sharedByUhelnik) {
      if (near(y, sharedByUhelnik.oldYnew, 3) || near(y, sharedByUhelnik.oldYnew + 30, 3)) {
        out.push({ ...p, position: [x, y + DELTA_Y, z] }); log.uhelnikSharedShift++; continue;
      }
      out.push(p); log.uhelnikSharedUnaffected++; continue;
    }

    if (role === "sloupek-pred-podbehem" || role === "zadni-svislice-nad-zarezem" || role === "pricka-uzavreni-vyrezu") {
      const leg = sharedLegs.find(l => near(z, l.z, ZTOL));
      if (leg) {
        out.push(shiftVyrezPart(p, role, leg.oldYnew, DELTA_Y)); log.sharedLegVyrezShift++; continue;
      }
    }

    const LEG_FRAME_ROLES = new Set(["predni-svislice", "cap", "spojnice-dolni", "spojnice-horni",
      "zadni-svislice-dolni", "zaslepka"]);
    if (LEG_FRAME_ROLES.has(role)) {
      if (near(z, legZ0, ZTOL)) {
        out.push({ ...p, position: [x, y, z + DELTA_Z] }); log.leg0Rigid++; continue;
      }
      if (sharedLegs.some(l => near(z, l.z, ZTOL))) {
        out.push(p); log.sharedLegUnaffected++; continue;
      }
      out.push(p); log.unaffected++; continue;
    }

    if (nosnikLevelRe.test(role) || euroboxLevelRe.test(role)) {
      const lvl = levelKeyOf(role);
      const dy = dorovnaniFn(lvl);
      const isNosnik = nosnikLevelRe.test(role);
      const newPos = [x, y + dy, z + DELTA_Z / 2];
      const newScale = isNosnik ? [p.scale[0], p.scale[1] - DELTA_Z / 1000, p.scale[2]] : p.scale;
      out.push({ ...p, position: newPos, scale: newScale }); log.colSpanBeam++; continue;
    }

    if (spojniceLevelRe.test(role)) {
      const lvl = levelKeyOf(role);
      const dy = dorovnaniFn(lvl);
      const distLeg0 = Math.abs(z - legZ0);
      const NEAR_LEG_TOL = 60;
      const nearestSharedDist = Math.min(...allLegZ.slice(1).map(lz => Math.abs(z - lz)));
      if (distLeg0 < NEAR_LEG_TOL) {
        out.push({ ...p, position: [x, y + dy, z + DELTA_Z], scale: p.scale }); log.colSpanEnd++; continue;
      }
      if (nearestSharedDist < NEAR_LEG_TOL) {
        out.push({ ...p, position: [x, y + dy, z], scale: p.scale }); log.colSpanEnd++; continue;
      }
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
cur.execute("SELECT data FROM product_assemblies WHERE id=216")
print(json.dumps(json.loads(cur.fetchone()["data"])["parts"]))
conn.close()
`;
  fs.writeFileSync("/tmp/_dump_216batch.py", dumpPy);
  const raw = execSync("api/venv/bin/python3 /tmp/_dump_216batch.py", { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 40 }).toString();
  const p216 = JSON.parse(raw);

  const LEG_Z = { leg0: -1522.500114440918, leg1: -260.50011444091797 };
  const OLD_YNEW = 141.00018310546875;

  // krok 2: over ktere nohy z rodinnych dat se v teto konkretni sestave vyskytuji
  const has = (role, z) => p216.some(p => p.role === role && near(p.position[2], z, 1));
  console.log("leg0 (plain) pritomna?", has("predni-svislice", LEG_Z.leg0) && has("zadni-svislice-dolni", LEG_Z.leg0));
  console.log("leg1 plna (predni) cast pritomna?", has("predni-svislice", LEG_Z.leg1));
  console.log("leg1 vyrez trojice pritomna?", has("sloupek-pred-podbehem", LEG_Z.leg1) && has("zadni-svislice-nad-zarezem", LEG_Z.leg1) && has("pricka-uzavreni-vyrezu", LEG_Z.leg1));

  // krok 4: over jestli je potreba dorovnani (nejnizsi patro sloupce vs Y_new nohy1)
  const nosnikPatro0 = p216.filter(p => p.role === "nosnik-sloupec0-patro0");
  const floorEdge = Math.min(...nosnikPatro0.map(p => p.position[1])) - 15; // polovina tloustky profilu (30mm)
  const newYnewLeg1 = OLD_YNEW + DELTA_Y;
  console.log(`krok4: floorEdge patro0 = ${floorEdge}, newYnewLeg1 = ${newYnewLeg1}, visi_ve_vzduchu=${floorEdge < newYnewLeg1}`);
  const dorovnaniOverride = (floorEdge < newYnewLeg1) ? null : 0;

  const cfg216 = {
    legZ0: LEG_Z.leg0,
    sharedLegs: [{ z: LEG_Z.leg1, uhelnikRole: "uhelnik-noha1", oldYnew: OLD_YNEW }],
    colPrefix: "sloupec0",
    dorovnaniOverride,
  };

  const { parts: result216, log: log216 } = transformAssembly(p216, cfg216);
  console.log("log (216):", JSON.stringify(log216));
  console.log("celkem dilu:", p216.length, "-> vystup:", result216.length);

  fs.writeFileSync(__dirname + "/tmp_2026-09-12_216_parts_new.json", JSON.stringify(result216));
  console.log("\nUlozeno: tmp_2026-09-12_216_parts_new.json");
}
