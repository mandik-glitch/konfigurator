// Zpracuje JEDNU sestavu (krok 3-6 + krok 7-overeni procedury
// shape_geometry_methods.id=11) - spousti se jako SAMOSTATNY proces per
// sestava (viz scripts/2026-09-12_wide_run_model.py), aby se pamet mezi
// sestavami uplne uvolnila (Robertovo "hlidej si RAM" na sdilenem VPS).
//
// Pouziti: node 2026-09-12_wide_process_one.js <assembly_id> <cfg.json> <outdir>
// cfg.json: { base, legZ:[...], notchLegIdx:[...], colPrefix }
// Vystup: <outdir>/<id>_parts_new.json, <outdir>/<id>_report.json
const fs = require("fs");
const THREE = require("three");
const { execSync } = require("child_process");
const { transformAssemblyGeneric, DELTA_Y } = require("/opt/konfigurator/scripts/2026-09-12_wide_transform_lib.js");
const { verifyAssembly, partMesh } = require("/opt/konfigurator/scripts/2026-09-12_wide_verify_lib.js");

const [, , idArg, cfgPath, outDir] = process.argv;
const id = Number(idArg);
const cfgRaw = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
const cfg = { legZ: cfgRaw.legZ, notchLegIdx: new Set(cfgRaw.notchLegIdx), colPrefix: cfgRaw.colPrefix };

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
cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (${id},))
row = cur.fetchone()
conn.close()
print(json.dumps(json.loads(row["data"])["parts"]))
`;
fs.writeFileSync(`/tmp/_wide_dump_${id}.py`, dumpPy);
const partsOrig = JSON.parse(execSync(`api/venv/bin/python3 /tmp/_wide_dump_${id}.py`, { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 80 }).toString());

// Pre-pass: pro kazdou vyrezovou nohu zjisti REALNYM GLB bbox dotykem
// (ne odhadem/pevnou Y-tolerance), ktere uhelnik-noha<N> kusy se FYZICKY
// dotykaji vyrezove trojice (sloupek-pred-podbehem/zadni-svislice-nad-
// zarezem/pricka-uzavreni-vyrezu) v PUVODNICH (pred-transform) datech -
// ty musi jit S seamem (deltaY), ostatni zustavaji beze zmeny. Presnejsi
// a univerzalnejsi nez pevna Y-offset konvence (ktera se mezi modely lisi
// - viz komentar v transform_lib.js u uhelnik-noha vetve).
const touchSet = new Set();
for (const legIdx of cfg.notchLegIdx) {
  const legZ = cfg.legZ[legIdx];
  const trioRoles = ["sloupek-pred-podbehem", "zadni-svislice-nad-zarezem", "pricka-uzavreni-vyrezu"];
  const trioParts = partsOrig.filter(p => trioRoles.includes(p.role) && Math.abs(p.position[2] - legZ) < 2);
  if (!trioParts.length) continue;
  // KAZDY dil trojice zvlast (ne union) - union by vytvoril jeden obalujici
  // box od podlahy po strop leg a "dotyk" by tak zjistil skoro kazdy
  // uhelnik na te noze, at je kdekoliv na Y.
  // tolerance = DELTA_Y + male rezervy: chceme zachytit i brackety, ktere
  // se PRED transformem jeste nedotykaji, ale po +10mm posunu seamu by uz
  // ANO (jinak by vznikla NOVA kolize zpusobena prave timhle transformem,
  // presne typ chyby, ktery krok 7c ma odhalit) - takove je spravnejsi
  // posunout SPOLU se seamem, nez nechat viset s mezerou, ktera se uzavre.
  const TOUCH_TOL = DELTA_Y + 2;
  const trioBoxes = trioParts.map(p => new THREE.Box3().setFromObject(partMesh(p)).expandByScalar(TOUCH_TOL));
  const uhelnikParts = partsOrig.filter(p => p.role === `uhelnik-noha${legIdx}`);
  for (const p of uhelnikParts) {
    const box = new THREE.Box3().setFromObject(partMesh(p));
    if (trioBoxes.some(tb => tb.intersectsBox(box))) {
      touchSet.add(`${p.position[0].toFixed(2)},${p.position[1].toFixed(2)},${p.position[2].toFixed(2)}`);
    }
  }
}
cfg.touchSet = touchSet;

const { parts: partsNew, log } = transformAssemblyGeneric(partsOrig, cfg);
console.log(`touchSet (uhelnik dilu fyzicky dotykajicich vyrezove trojice, geometricky zmereno): ${touchSet.size}`);

// notchChecks pro overeni kroku 7b (presna mezera + nevisi ve vzduchu)
const notchChecks = [...cfg.notchLegIdx].map(idx => {
  const cand = partsOrig.find(p => p.role === "zadni-svislice-nad-zarezem" && Math.abs(p.position[2] - cfg.legZ[idx]) < 2);
  const oldYnew = cand.position[1] - cand.scale[1] * 500;
  return { z: cfg.legZ[idx], oldYnew, deltaY: DELTA_Y };
});

const report = verifyAssembly({
  partsNew, partsOrig, carBodyBase: cfgRaw.base, notchChecks, label: `id=${id}`,
});
report.log = log;
report.unclassifiedCount = log.unclassified.length;
report.unclassifiedSample = log.unclassified.slice(0, 20);

fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(`${outDir}/${id}_parts_new.json`, JSON.stringify(partsNew));
fs.writeFileSync(`${outDir}/${id}_report.json`, JSON.stringify(report, null, 1));
console.log(`id=${id} OK=${report.OK} collisions=${report.collisions}/${report.testedParts} allSeamsOk=${report.allSeamsOk} newSelfCollisions=${report.newProblems.length} unclassified=${report.unclassifiedCount}`);
if (report.unclassifiedCount) console.log("  unclassified sample:", JSON.stringify(report.unclassifiedSample));
if (!report.OK) {
  console.log("  collidingList:", JSON.stringify(report.collidingList.slice(0, 10)));
  console.log("  seamChecks:", JSON.stringify(report.seamChecks));
  console.log("  newProblems:", JSON.stringify(report.newProblems.slice(0, 10)));
}
