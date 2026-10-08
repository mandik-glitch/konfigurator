// Oprava vyrezovych ("clenitych") noh eurobox regalu, kterym chybi vnitrni
// pricky (bot22, 2026-09-03, zadal Robert: "nekde stale chybi pricky v
// nohach" + "2. noha od prepazky u nekterych sestav je spatne ve spodni
// casti u podlahy").
//
// CO SE OPRAVUJE (2 tridy vady, obe nalezene
// scripts/2026-09-03_audit_leg_structure.js):
//   (A) chybi "pricka-uzavreni-vyrezu" - noha neni UZAVRENA struktura.
//       "sloupek-pred-podbehem" a "zadni-svislice-nad-zarezem" na sebe
//       navazuji stejnou vyskou, ale RUZNYM X (uskok pred podbehem kola),
//       takze se podle Robertovy definice spoje nemuzou dotknout primo -
//       spojuje je az polozena pricka (KOMPONENTY_EUROBOXY.md r. 78-80,
//       shape_geometry_methods.id=4 'dokonceni-nohy-zaslepky-a-uzavreni').
//   (B) chybi NAVIC i "spojnice-dolni" - pak "sloupek-pred-podbehem" u
//       podlahy nedrzi VUBEC NIC (volne stojici pahyl).
//
// KONSTRUKCE (zamerne se nic nepocita "od nuly" - kopiruje se uz overeny
// dil TEZE nohy, aby nova geometrie nemohla zavest jinou konvenci):
//   pricka-uzavreni-vyrezu = KLON "spojnice-horni" teze nohy (ma presne
//     stejny X rozsah: od vnitrni plochy zadni svislice k vnitrni plose
//     predni svislice, overeno na kompletnich nohach id=57/83), posunuty
//     na Y = horni celo sloupku (lezi na nem shora, cap-styl).
//   spojnice-dolni = KLON "spojnice-horni" zkraceny na rozsah od vnitrni
//     plochy SLOUPKU k vnitrni plose predni svislice, na Y = spodni celo
//     sloupku (u podlahy).
//
// DEGENEROVANY PRIPAD: pri Y_new <= T (30mm) by se oba dily vertikalne
// srazily - podle shape_geometry_methods.id=6 / KOMPONENTY_EUROBOXY.md
// r. 349 se v takovem pripade OBA vynechavaji. Takova noha se preskoci.
//
// OVERENI kazde opravene nohy (vse na REALNE GLB geometrii, ne z
// position/scale cisel - skill 3d-scena-spoje, metodika bod 1 a 3):
//   1. kazdy novy dil ma s kazdym sousedem "flush" dotyk = presne 1 osa
//      gap/overlap ~0 a PLNY prekryv na zbylych dvou
//   2. zadna self-kolize (kladny prekryv na vsech 3 osach) v ramci nohy
//   3. zadna kolize s REALNOU karoserii (collidesWithWalls, tentyz modul
//      jako produkce)
// Noha, ktera neprojde vsemi 3 body, se NEOPRAVI (zustane v reportu jako
// blokovana) - radeji neuplna noha nez spatna geometrie.
//
// READ-ONLY dokud se nezavola s --out (ten jen ULOZI navrh do JSON, do DB
// nezapisuje nic).
//
// Pouziti:
//   node scripts/2026-09-03_fix_leg_missing_crossbars.js <all_asm.json> <car_bodies.json> [--out navrh.json]

const fs = require("fs");
const THREE = require("/opt/konfigurator/node_modules/three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { makeCollisionModule } = require("/opt/konfigurator/scripts/2026-09-01_collision_module_factory.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const T = 30;            // prurez profilu Object_7 (zmereno z GLB: 30 x 1000 x 30)
const BASE_UNIT = 1000;  // delka Object_7 pri scale=1
const EPS = 1.0;         // mm tolerance pro "flush" dotyk

const asmPath = process.argv[2];
const cbPath = process.argv[3];
const outIdx = process.argv.indexOf("--out");
const outPath = outIdx > 0 ? process.argv[outIdx + 1] : null;

const input = JSON.parse(fs.readFileSync(asmPath, "utf8"));
const carBodies = JSON.parse(fs.readFileSync(cbPath, "utf8"));

const meshCache = {};
function meshFor(partId) {
  if (!(partId in meshCache)) {
    const f = KAT + partId + ".glb";
    meshCache[partId] = fs.existsSync(f) ? parseGlbMesh(f) : null;
  }
  return meshCache[partId];
}
function boxOf(part) {
  const m = meshFor(part.part_id);
  if (!m) return null;
  m.position.set(part.position[0], part.position[1], part.position[2]);
  const q = part.quaternion || [0, 0, 0, 1];
  m.quaternion.set(q[0], q[1], q[2], q[3]);
  const s = part.scale || [1, 1, 1];
  m.scale.set(s[0], s[1], s[2]);
  m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}
function ov(a, b) {
  const o = {};
  for (const ax of ["x", "y", "z"]) o[ax] = Math.min(a.max[ax], b.max[ax]) - Math.max(a.min[ax], b.min[ax]);
  return o;
}
function isFlush(o) {
  const near = [], pos = [];
  for (const ax of ["x", "y", "z"]) {
    if (Math.abs(o[ax]) <= EPS) near.push(ax); else if (o[ax] > EPS) pos.push(ax);
  }
  return near.length === 1 && pos.length === 2;
}
function isEmbedded(o) { return o.x > EPS && o.y > EPS && o.z > EPS; }

// zaklad cesty ke GLB karoserie: "car_bodies/X_L.glb" -> KAT + "car_bodies/X"
function bodyBaseFor(row) {
  for (const p of row.parts) {
    const m = /^car_body_(\d+)$/.exec(p.part_id || "");
    if (!m) continue;
    const rec = carBodies[m[1]];
    if (!rec || !rec.glb) continue;
    const base = rec.glb.replace(/_(L|R_D|B)\.glb$/, "").replace(/\.glb$/, "");
    return KAT + base;
  }
  return null;
}
const colCache = {};
function collisionFor(base) {
  if (!(base in colCache)) {
    try { colCache[base] = makeCollisionModule(base); }
    catch (e) { colCache[base] = { error: e.message }; }
  }
  return colCache[base];
}

const results = [];
const patched = {};

for (const row of input.rows) {
  const legParts = row.parts.filter((p) => p.position && p.role);
  const zsAll = [...new Set(legParts.filter((p) => /sloupek-pred-podbehem/.test(p.role)).map((p) => Math.round(p.position[2])))];
  if (!zsAll.length) continue;

  // poradi noh od prepazky (rostouci Z) - kvuli hlaseni "2. noha od prepazky"
  const legZs = [...new Set(row.parts.filter((p) => p.position && /svislice|sloupek/.test(p.role || "")).map((p) => Math.round(p.position[2])))].sort((a, b) => a - b);
  const legOrder = [];
  for (const z of legZs) {
    const last = legOrder[legOrder.length - 1];
    if (last && z - last[last.length - 1] <= 60) last.push(z); else legOrder.push([z]);
  }
  const orderOf = (z) => legOrder.findIndex((g) => g.some((v) => Math.abs(v - z) <= 60)) + 1;

  for (const z of zsAll) {
    const inLeg = (p) => p.position && Math.abs(Math.round(p.position[2]) - z) <= 60;
    const byRole = (r) => row.parts.find((p) => inLeg(p) && p.role === r);
    const sloupek = byRole("sloupek-pred-podbehem");
    const predni = byRole("predni-svislice");
    const zadni = byRole("zadni-svislice-nad-zarezem");
    const horni = byRole("spojnice-horni");
    const hasPricka = !!byRole("pricka-uzavreni-vyrezu");
    const hasDolni = !!(byRole("spojnice-dolni") || byRole("spojnice-dolni-kratka"));
    if (hasPricka && hasDolni) continue; // kompletni noha

    const rec = { id: row.id, name: row.name, z, poradi: orderOf(z), pridano: [], stav: null, kontroly: {} };

    // Sablona slouzi UZ JEN pro orientaci profilu (quaternion/part_id/Z),
    // rozsah obou novych dilu se pocita explicitne z vnitrnich ploch svislic.
    // Nohy typu "U" (Caddy/Doblo 30x30) horni spojnici vubec nemaji - viz
    // KOMPONENTY_EUROBOXY.md r. 367 - proto fallback na spojnice-dolni.
    const sablona = horni || byRole("spojnice-dolni") || byRole("spojnice-dolni-kratka");
    if (!sloupek || !predni || !zadni || !sablona) {
      rec.stav = "PRESKOCENO - chybi referencni dil (" +
        [["sloupek", sloupek], ["predni-svislice", predni], ["zadni-svislice-nad-zarezem", zadni], ["vodorovna sablona", sablona]]
          .filter((e) => !e[1]).map((e) => e[0]).join(", ") + ")";
      results.push(rec); continue;
    }

    const bSl = boxOf(sloupek), bPr = boxOf(predni), bZa = boxOf(zadni);
    const Ynew = bZa.min.y;
    rec.Y_new = +Ynew.toFixed(1);
    rec.sloupek = [+bSl.min.y.toFixed(1), +bSl.max.y.toFixed(1)];

    if (Ynew <= T + 0.5) {
      rec.stav = "PRESKOCENO - degenerovany pripad Y_new<=" + T + "mm (dily se dle id=6 vynechavaji)";
      results.push(rec); continue;
    }

    // POZOR: v three 0.128 je Box3.center ZASTARALA FUNKCE, ne Vector3 -
    // "b.center.x" tise vrati undefined (ZADNA vyjimka) a kazde porovnani nad
    // nim spadne do spatne vetve. Stred se musi spocitat rucne. Presne tahle
    // past nechala prvni beh vyrobit spojnice-dolni pres OBE svislice
    // (prekryv 30/30/30 = zanoreni), nez to zachytila kontrola spoju.
    const cx = (b) => (b.min.x + b.max.x) / 2;
    // "vnitrni plocha" = ta, kterou je dil natoceny k protejsku spoje
    const innerToward = (b, target) => (cx(b) < cx(target) ? b.max.x : b.min.x);

    const nove = [];
    // (A) pricka-uzavreni-vyrezu: od vnitrni plochy ZADNI svislice k vnitrni
    //     plose PREDNI svislice, spodni celo lezi na hornim celu sloupku
    //     (overeno proti kompletnim noham, napr. id=57: zadni X[-751,-721],
    //     pricka X[-721,-455], predni X[-455,-425])
    if (!hasPricka) {
      const a = innerToward(bZa, bPr), b = innerToward(bPr, bZa);
      const p = JSON.parse(JSON.stringify(sablona));
      p.role = "pricka-uzavreni-vyrezu";
      p.scale = [sablona.scale[0], +(Math.abs(b - a) / BASE_UNIT).toFixed(6), sablona.scale[2]];
      p.position = [+((a + b) / 2).toFixed(4), +(bSl.max.y + T / 2).toFixed(4), sablona.position[2]];
      nove.push(p);
    }
    // (B) spojnice-dolni: od vnitrni plochy SLOUPKU k vnitrni plose PREDNI
    //     svislice, u podlahy (spodni celo srovnane se spodkem sloupku)
    if (!hasDolni) {
      const a = innerToward(bSl, bPr), b = innerToward(bPr, bSl);
      const p = JSON.parse(JSON.stringify(sablona));
      p.role = "spojnice-dolni";
      p.scale = [sablona.scale[0], +(Math.abs(b - a) / BASE_UNIT).toFixed(6), sablona.scale[2]];
      p.position = [+((a + b) / 2).toFixed(4), +(bSl.min.y + T / 2).toFixed(4), sablona.position[2]];
      nove.push(p);
    }

    // ---- OVERENI ----
    // POZOR: porovnavat je nutne proti VSEM dilum sestavy v teto noze, ne jen
    // proti dilum NOHY. Pricky PATER ("spojnice-sloupecN-patroM") lezi taky na
    // Z nohy a nejnizsi z nich muze sedet PRESNE tam, kam by prisla uzaviraci
    // pricka - pak uz je noha uzavrena a novy dil by byl DUPLICITA. Prvni verze
    // tohohle skriptu pricky pater vynechavala a navrhla u id=74 dil presne
    // pres existujici spojnice-sloupec0-patro0 (X i Y na milimetr shodne);
    // odhalil to az povinny 2D kotovany pohled.
    const legAll = row.parts.filter((p) => inLeg(p) && p.role && !/^car_body_/.test(p.part_id || ""));
    let flushOk = true, embedOk = true;
    const detail = [];
    for (const np of nove) {
      const bn = boxOf(np);
      let touches = 0;
      for (const other of legAll) {
        if (other.part_id === "product_3071") continue; // zaslepka = prislusenstvi, zastrcna geometrie
        const bo = boxOf(other);
        if (!bo) continue;
        const o = ov(bn, bo);
        if (isFlush(o)) { touches++; detail.push(np.role + " ~ " + other.role + " OK(" + o.x.toFixed(1) + "," + o.y.toFixed(1) + "," + o.z.toFixed(1) + ")"); }
        else if (isEmbedded(o)) {
          embedOk = false;
          const dup = Math.abs(o.x - (bn.max.x - bn.min.x)) < 1 && Math.abs(o.y - (bn.max.y - bn.min.y)) < 1;
          detail.push((dup ? "DUPLICITA (uz tam je) " : "ZANORENI ") + np.role + " X " + other.role +
            " (" + o.x.toFixed(1) + "," + o.y.toFixed(1) + "," + o.z.toFixed(1) + ")");
        }
      }
      // pricka musi drzet na 3 mistech (sloupek zespodu, obe svislice bokem),
      // spojnice-dolni na 2 (sloupek, predni svislice)
      const need = np.role === "pricka-uzavreni-vyrezu" ? 3 : 2;
      if (touches < need) { flushOk = false; detail.push("MALO SPOJU " + np.role + ": " + touches + " < " + need); }
    }
    rec.kontroly.spoje = flushOk ? "OK" : "SELHALO";
    rec.kontroly.self_kolize = embedOk ? "OK" : "SELHALO";
    rec.detail = detail;

    // kolize s karoserii
    const base = bodyBaseFor(row);
    if (!base) rec.kontroly.karoserie = "NELZE - neznama karoserie";
    else {
      const mod = collisionFor(base);
      if (mod.error) rec.kontroly.karoserie = "NELZE - " + mod.error;
      else {
        let hit = null;
        for (const np of nove) {
          const g = mod.buildLegObject([np]);
          if (mod.collidesWithWalls(g)) { hit = np.role; break; }
        }
        rec.kontroly.karoserie = hit ? "KOLIZE (" + hit + ")" : "OK";
      }
    }

    const allOk = flushOk && embedOk && rec.kontroly.karoserie === "OK";
    rec.stav = allOk ? "OPRAVENO" : "BLOKOVANO";
    rec.pridano = nove.map((p) => p.role);
    if (allOk) {
      if (!patched[row.id]) patched[row.id] = { id: row.id, name: row.name, add: [] };
      patched[row.id].add.push(...nove);
    }
    results.push(rec);
  }
}

// ---- vypis ----
console.log("=== NAVRH OPRAVY VYREZOVYCH NOH ===\n");
for (const r of results) {
  console.log("id=" + r.id + "  noha #" + r.poradi + " (z=" + r.z + ")  " + String(r.name).slice(0, 44));
  console.log("   Y_new=" + r.Y_new + "  sloupek=" + JSON.stringify(r.sloupek) + "  pridava: " + (r.pridano.join(", ") || "-"));
  console.log("   stav: " + r.stav + "   kontroly: " + JSON.stringify(r.kontroly));
  if (r.stav === "BLOKOVANO" && r.detail) for (const d of r.detail) if (/ZANORENI|MALO SPOJU/.test(d)) console.log("      " + d);
}
const cnt = (s) => results.filter((r) => r.stav === s).length;
console.log("\n=== SOUHRN ===");
console.log("nekompletnich noh:      " + results.length);
console.log("  opraveno (vse OK):    " + cnt("OPRAVENO"));
console.log("  blokovano (nepresla kontrola): " + cnt("BLOKOVANO"));
console.log("  preskoceno:           " + results.filter((r) => /PRESKOCENO/.test(r.stav)).length);
console.log("dotcenych sestav:       " + Object.keys(patched).length);
let nParts = 0; for (const k in patched) nParts += patched[k].add.length;
console.log("novych dilu celkem:     " + nParts);
if (outPath) { fs.writeFileSync(outPath, JSON.stringify(patched, null, 1)); console.log("\nnavrh ulozen -> " + outPath + "  (DO DB SE NIC NEZAPSALO)"); }
