// ALTERNATIVNI ZACATEK POSTUPU UMISTOVANI (Robert, 2026-09-04).
//
// Zadani doslovne: "Podle puvodniho postupu nektere nohy skonci utopene
// prilis predni casti karoserie nebo naopak protoze jsou vysoke ty nohy
// zastavi se brzo nejblizsi horni lem karoserie. Proto zkusme alternativni
// zpusob zacatku postupu noha od stredu kdy prekroci podlahu nepujde smerem
// k predni prepazce ale bude hledat prvni kolizi v miste nejvyssiho podbehu.
// po kolizi se vrati o 10 mm a to je vychozi pozice pro normalni nohu v
// podelne ose ktera se zastavi prepazku jako v postupu predeslem se jiz
// pokracuje."
//
// PROC: puvodni krok 3 (car_body_placement_methods.id=1) krokoval nohu od
// stredu korby K PREPAZCE B. Protoze je noha vysoka, narazi cestou na horni
// lem karoserie a zastavi se predcasne - noha pak skonci "utopena" v predni
// casti misto nad podbehem, kam podle pravidla "clenita_noha" patri.
//
// NOVY KROK 3: kroky 1 a 2 beze zmeny (stred nakladoveho prostoru -> dolu na
// podlahu). Pak se noha NEPOSOUVA k prepazce, ale K PODBEHU: krokuje podel
// auta, dokud nenarazi na podbeh, a vrati se o 10 mm. Tahle pozice je KOTVA
// cele sestavy. Od ni se pak pokracuje NORMALNE podle puvodniho postupu
// (normalni noha v podelne ose az k prepazce atd.).
//
// READ-ONLY - nic nemeni, jen spocita a vypise kotvu pro zadane sestavy.
//
// Pouziti:
//   node scripts/2026-09-04_anchor_leg_at_arch.js <all_asm.json> <podbeh_all.json> <car_bodies.json> [--ids 57,124] [--out out.json]

const fs = require("fs");
const THREE = require("/opt/konfigurator/node_modules/three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { makeCollisionModule } = require("/opt/konfigurator/scripts/2026-09-01_collision_module_factory.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const REBOUND = 10;   // mm - Robert 2026-09-04: "po kolizi se vrati o 10 mm"
const STEP = 1;       // mm - krokovani jako jinde v metode
const COARSE = 10;    // mm - hrube hledani, pak dojezd po 1mm

const [asmPath, audPath, cbPath] = process.argv.slice(2, 5);
const idsIdx = process.argv.indexOf("--ids");
const onlyIds = idsIdx > 0 ? process.argv[idsIdx + 1].split(",").map(Number) : null;
const outIdx = process.argv.indexOf("--out");
const outPath = outIdx > 0 ? process.argv[outIdx + 1] : null;

const input = JSON.parse(fs.readFileSync(asmPath, "utf8"));
const audit = new Map(JSON.parse(fs.readFileSync(audPath, "utf8")).map((r) => [r.id, r]));
const carBodies = JSON.parse(fs.readFileSync(cbPath, "utf8"));

const meshCache = {};
function boxOf(part) {
  const pid = part.part_id;
  if (!(pid in meshCache)) {
    const f = KAT + pid + ".glb";
    meshCache[pid] = fs.existsSync(f) ? parseGlbMesh(f) : null;
  }
  const m = meshCache[pid];
  if (!m) return null;
  m.position.set(part.position[0], part.position[1], part.position[2]);
  const q = part.quaternion || [0, 0, 0, 1];
  m.quaternion.set(q[0], q[1], q[2], q[3]);
  const s = part.scale || [1, 1, 1];
  m.scale.set(s[0], s[1], s[2]);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}
const colCache = {};
function collisionFor(base) {
  if (!(base in colCache)) {
    try { colCache[base] = makeCollisionModule(KAT + "car_bodies/" + base); }
    catch (e) { colCache[base] = { error: e.message }; }
  }
  return colCache[base];
}

const results = [];
for (const row of input.rows) {
  if (onlyIds && !onlyIds.includes(row.id)) continue;
  const a = audit.get(row.id);
  if (!a) continue;
  const arch = a.arch || {};
  if (arch.startZ === null || arch.startZ === undefined) continue;

  // dily VYREZOVE nohy (ta, ktera se s podbehem potkava)
  const vyrezZs = [...new Set(row.parts.filter((p) => p.position && /sloupek-pred-podbehem/.test(p.role || ""))
    .map((p) => Math.round(p.position[2])))];
  if (!vyrezZs.length) continue;
  const legZ = vyrezZs[0];
  const legParts = row.parts.filter((p) => p.position && p.role &&
    Math.abs(Math.round(p.position[2]) - legZ) <= 60 && !/^car_body_|^eurobox|^nosnik/.test(p.part_id + "|" + p.role) &&
    !/^spojnice-(sloupec|col)\d/.test(p.role));
  if (!legParts.length) continue;

  const mod = collisionFor(a.base);
  const rec = { id: row.id, code: (a.official || {}).code, name: row.name, base: a.base,
                arch: { startZ: arch.startZ, endZ: arch.endZ, peak: arch.peak }, soucasna_z: legZ };
  if (mod.error) { rec.chyba = mod.error; results.push(rec); continue; }

  // stred NAKLADOVEHO prostoru (krok 1): lic prepazky B .. zadni hranice korby
  const b = a.body || {};
  const cargoFront = b.bulkheadMeshZ !== undefined && b.bulkheadMeshZ !== null ? b.bulkheadMeshZ : b.lFrontZ;
  const cargoRear = b.endZ;
  const stredKorby = (cargoFront + cargoRear) / 2;
  rec.stred_korby = +stredKorby.toFixed(0);
  rec.rearSign = a.rearSign;

  // posun nohy tak, aby jeji Z stred byl ve stredu korby (kroky 1-2 hotove:
  // noha uz je z existujici sestavy dosednuta na podlahu)
  const boxes = legParts.map((p) => boxOf(p)).filter(Boolean);
  const legCz = (Math.min(...boxes.map((x) => x.min.z)) + Math.max(...boxes.map((x) => x.max.z))) / 2;
  const posunNaStred = stredKorby - legCz;

  function legAt(dz) {
    return legParts.map((p) => ({ ...p, position: [p.position[0], p.position[1], p.position[2] + posunNaStred + dz] }));
  }
  // ROZLISENI DVOU PREKAZEK (klicove, zmereno 2026-09-04):
  // Ve stredu korby koliduji u vetsiny vozidel POUZE HORNI dily nohy (zaslepky
  // ve vysce 836-1193mm) - to je "horni lem karoserie", presne to, na co
  // Robert upozornil ("protoze jsou vysoke ty nohy, zastavi se brzo o nejblizsi
  // horni lem"). Spodek nohy je pritom volny. Kotva se proto hleda podle
  // kolize se SPODNI prekazkou (podbeh); horni lem se reportuje zvlast, aby
  // se nezamenil s podbehem a nezastavil hledani predcasne.
  const hranice = (arch.peak || 300) + 100;   // mm nad podlahou - co jeste muze potkat podbeh
  const dolni = legParts.filter((p) => { const b = boxOf(p); return b && b.min.y < hranice; });
  const horni = legParts.filter((p) => !dolni.includes(p));
  function kolidujeDole(dz) {
    const parts = legAt(dz).filter((_, i) => dolni.includes(legParts[i]));
    return parts.length ? mod.collidesWithWalls(mod.buildLegObject(parts)) : false;
  }
  function kolidujeNahore(dz) {
    const parts = legAt(dz).filter((_, i) => horni.includes(legParts[i]));
    return parts.length ? mod.collidesWithWalls(mod.buildLegObject(parts)) : false;
  }
  const koliduje = kolidujeDole;

  // KROK 3 (novy): krokovat od stredu K PODBEHU, dokud nenarazi
  const dir = a.rearSign >= 0 ? +1 : -1;   // podbeh lezi smerem dozadu
  rec.dilu_dole = dolni.length; rec.dilu_nahore = horni.length;
  rec.start_koliduje = kolidujeDole(0);
  rec.start_koliduje_nahore = kolidujeNahore(0);
  let hit = null;
  if (!rec.start_koliduje) {
    // hrube po COARSE, pak dojezd po 1mm
    let d = 0;
    const maxD = 4000;
    while (d < maxD && !koliduje(dir * (d + COARSE))) d += COARSE;
    if (d < maxD) {
      let f = d;
      while (f < d + COARSE && !koliduje(dir * (f + STEP))) f += STEP;
      hit = f + STEP;
    }
  }
  if (hit === null) {
    rec.stav = rec.start_koliduje ? "STRED KORBY UZ KOLIDUJE S PODBEHEM" : "ZADNA KOLIZE S PODBEHEM SMEREM DOZADU";
    results.push(rec); continue;
  }
  const kotvaDz = dir * (hit - REBOUND);
  const kotvaZ = legZ + posunNaStred + kotvaDz;
  rec.kolize_po_mm = hit;
  rec.kotva_z = +kotvaZ.toFixed(0);
  rec.posun_proti_dnesku = +(kotvaZ - legZ).toFixed(0);
  rec.kotva_koliduje = kolidujeDole(kotvaDz);
  rec.kotva_horni_lem = kolidujeNahore(kotvaDz);
  rec.stav = rec.kotva_koliduje ? "CHYBA - kotva porad koliduje s podbehem"
           : (rec.kotva_horni_lem ? "KOTVA OK, ale HORNI LEM koliduje (noha je tam prilis vysoka)" : "OK");
  results.push(rec);
  console.log((rec.code || "?").padEnd(6) + String(row.id).padEnd(5) + String(row.name).slice(0, 34).padEnd(35) +
    " podbeh[" + arch.startZ + ".." + arch.endZ + "] stred=" + rec.stred_korby +
    "  kotva=" + rec.kotva_z + "  (dnes " + legZ + ", posun " + (rec.posun_proti_dnesku > 0 ? "+" : "") + rec.posun_proti_dnesku + ")  " + rec.stav);
}

if (outPath) { fs.writeFileSync(outPath, JSON.stringify(results, null, 1)); console.log("\nJSON -> " + outPath); }
