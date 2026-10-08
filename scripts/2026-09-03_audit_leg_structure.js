// Audit STRUKTURY jednotlivych NOH eurobox regalu (bot22, 2026-09-03).
//
// Vznik: Robert nahlasil dve vady, ktere dosavadni audity NEPOKRYVALY:
//   (1) "nekde stale chybi pricky v nohach" - dosavadni
//       tmp_2026-09-01_bot16_crossbar_gap_audit.js meril pricky/spojnice
//       PATER REGALU (mezi nohama), NE pricky UVNITR nohy. Proto vysel
//       cisty (0/427) a vada zustala neodhalena.
//   (2) "2. noha od prepazky u nekterych sestav je spatne ve spodni casti
//       u podlahy" - odpovida zdokumentovanemu selhani v
//       KOMPONENTY_EUROBOXY.md (r. 285 a 349): vyrez-noha na miste BEZ
//       realneho podbehu dostane nesmyslne maly Y_new, a pak se
//       "spojnice-dolni" (fixni pozice) a "pricka-uzavreni-vyrezu"
//       (na Y_new+T/2) vertikalne SRAZI. Oprava dle id=6/id=4: pri
//       Y_new <= T se oba dily vynechavaji.
//
// METODA - zamerne NEZAVISLA NA POJMENOVANI ROLI (role se mezi davkami
// ruznych agentu prokazatelne lisi, viz KOMPONENTY_EUROBOXY.md r. 456):
// vse se meri z REALNE GLB geometrie (Box3 pres parseGlbMesh), a noha se
// posuzuje jako GRAF:
//   - uzly = dily nohy (klastrovane podle Z)
//   - hrana = dva dily se dotykaji "flush" (gap/overlap ~ 0 na PRAVE
//     jedne ose a kladny prekryv na zbylych dvou) - viz metodika skillu
//     3d-scena-spoje, bod 1 (kontrola na VSECH 3 osach, ne jen jedne)
// Z toho plynou dva nalezy:
//   CHYBI_PRICKA  = graf nohy je NESOUVISLY (svislice nejsou nicim
//                   spojene) => v noze chybi pricka/spojnice
//   SELF_KOLIZE   = dva dily TEZE nohy maji kladny prekryv na VSECH 3
//                   osach (skutecne zanoreni, ne dotyk) - porusuje
//                   nadrazene pravidlo "zadne zanoreni"
//
// READ-ONLY. Nic nemeni, jen reportuje.
//
// Pouziti:
//   node scripts/2026-09-03_audit_leg_structure.js <all_asm.json> [--json out.json]

const fs = require("fs");
const THREE = require("/opt/konfigurator/node_modules/three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const TOUCH_EPS = 1.0;   // mm - tolerance "flush" dotyku
const OVERLAP_EPS = 1.0; // mm - nad tuhle hodnotu na vsech 3 osach = zanoreni

const inputPath = process.argv[2];
const jsonOutIdx = process.argv.indexOf("--json");
const jsonOut = jsonOutIdx > 0 ? process.argv[jsonOutIdx + 1] : null;

const input = JSON.parse(fs.readFileSync(inputPath, "utf8"));
const rows = input.rows || input;

const meshCache = {};
function getBox3(part) {
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

// prekryv bounding boxu na jednotlivych osach: >0 prekryv, <0 mezera
function overlaps(a, b) {
  const o = {};
  for (const ax of ["x", "y", "z"]) {
    o[ax] = Math.min(a.max[ax], b.max[ax]) - Math.max(a.min[ax], b.min[ax]);
  }
  return o;
}

// je to platny "flush" dotyk? presne 1 osa ~0, zbyle 2 kladny prekryv
function isFlushTouch(o) {
  const near = [], pos = [];
  for (const ax of ["x", "y", "z"]) {
    if (Math.abs(o[ax]) <= TOUCH_EPS) near.push(ax);
    else if (o[ax] > TOUCH_EPS) pos.push(ax);
  }
  return near.length === 1 && pos.length === 2;
}

// skutecne zanoreni: kladny prekryv na VSECH 3 osach
function isEmbedded(o) {
  return o.x > OVERLAP_EPS && o.y > OVERLAP_EPS && o.z > OVERLAP_EPS;
}

// Je dil NOSNOU casti nohy? Vylucuje (a) euroboxy/nosniky/spojnice PATER
// (ty patri sloupci mezi nohama, ne noze samotne) - POZOR, existuji DVE
// konvence pojmenovani teze veci: "spojnice-sloupecN-patroM" i
// "spojnice-colN-pM" (viz KOMPONENTY_EUROBOXY.md r. 456), (b) zaslepky.
//
// Zaslepky (role "zaslepka*", vzdy part_id product_3071) jsou PRISLUSENSTVI
// na volne celo, ne nosny dil - do grafu propojenosti ani do kolizniho testu
// NEPATRI. Zmereno z GLB: product_3071 je deska 30x30x9mm otocena tloustkou
// DOLU, tj. zapada 6mm DOVNITR duteho profilu a 3mm precniva. Jeji 6mm
// prekryv s profilem je tedy ZAMERNA zastrcna geometrie, ne zanoreni -
// presne pripad, pred kterym varuje skill 3d-scena-spoje, metodika bod 8
// ("Box3 presah sam o sobe neni dukaz kolize u dilu se stohovaci/vnorovaci
// geometrii"). Prvni verze tohohle skriptu je nebrala v potaz a hlasila
// kvuli tomu 120/120 sestav jako vadne - falesny poplach.
//
// Naopak role "cap" NENI zaslepka, ale nosny profil Object_7 (horni pricnik)
// - do konstrukce nohy patri.
function isLegPart(role, partId) {
  const r = role || "";
  if (partId === "product_3071") return false; // zaslepka = prislusenstvi
  if (/^eurobox/.test(r)) return false;
  if (/^nosnik/.test(r)) return false;
  if (/^spojnice-(sloupec|col)\d/.test(r)) return false; // pricky PATER, obe konvence
  return /svislice|sloupek|pricka|spojnice|^cap$/.test(r);
}

const report = { rows: [], summary: {} };
let nMissing = 0, nEmbedded = 0, nRowsBad = 0;

for (const row of rows) {
  const legParts = [];
  for (const p of row.parts || []) {
    if (!isLegPart(p.role, p.part_id)) continue;
    const box = getBox3(p);
    if (!box) continue;
    legParts.push({ role: p.role || "", box, z: Math.round(p.position[2]) });
  }
  if (!legParts.length) continue;

  // klastrovani do noh podle Z (nohy jsou od sebe stovky mm, dily jedne
  // nohy sdili Z; tolerance 60mm pokryje i drobne odchylky pricek)
  const zs = [...new Set(legParts.map((p) => p.z))].sort((a, b) => a - b);
  const clusters = [];
  for (const z of zs) {
    const last = clusters[clusters.length - 1];
    if (last && z - last[last.length - 1] <= 60) last.push(z);
    else clusters.push([z]);
  }

  const legs = clusters.map((cz) => {
    const set = new Set(cz);
    return { zs: cz, zMin: Math.min(...cz), parts: legParts.filter((p) => set.has(p.z)) };
  });
  legs.sort((a, b) => a.zMin - b.zMin); // rostouci Z = od prepazky dozadu

  const rowRep = { id: row.id, name: row.name, legs: [] };
  let rowBad = false;

  legs.forEach((leg, idx) => {
    const n = leg.parts.length;
    // graf dotyku
    const adj = Array.from({ length: n }, () => []);
    const embedded = [];
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const o = overlaps(leg.parts[i].box, leg.parts[j].box);
        if (isFlushTouch(o)) { adj[i].push(j); adj[j].push(i); }
        else if (isEmbedded(o)) {
          embedded.push({
            a: leg.parts[i].role, b: leg.parts[j].role,
            overlap: { x: +o.x.toFixed(1), y: +o.y.toFixed(1), z: +o.z.toFixed(1) },
            yMin: +Math.max(leg.parts[i].box.min.y, leg.parts[j].box.min.y).toFixed(1),
          });
        }
      }
    }
    // souvislost grafu
    const seen = new Set([0]); const stack = [0];
    while (stack.length) {
      const c = stack.pop();
      for (const nb of adj[c]) if (!seen.has(nb)) { seen.add(nb); stack.push(nb); }
    }
    const disconnected = n > 1 && seen.size < n;
    const isolated = leg.parts.filter((_, i) => !seen.has(i)).map((p) => p.role);

    if (disconnected) { nMissing++; rowBad = true; }
    if (embedded.length) { nEmbedded++; rowBad = true; }

    rowRep.legs.push({
      poradi: idx + 1, z: leg.zMin, dilu: n,
      role: leg.parts.map((p) => p.role),
      chybi_pricka: disconnected, nespojene_dily: isolated,
      self_kolize: embedded,
    });
  });

  if (rowBad) nRowsBad++;
  report.rows.push(rowRep);
}

report.summary = {
  sestav: report.rows.length,
  sestav_s_vadou: nRowsBad,
  noh_s_chybejici_prickou: nMissing,
  noh_se_self_kolizi: nEmbedded,
};

// ---- textovy vypis ----
console.log("=== NOHY S VADOU ===");
for (const r of report.rows) {
  const bad = r.legs.filter((l) => l.chybi_pricka || l.self_kolize.length);
  if (!bad.length) continue;
  console.log(`\nid=${r.id}  ${String(r.name).slice(0, 60)}`);
  for (const l of bad) {
    const tag = [];
    if (l.chybi_pricka) tag.push("CHYBI_PRICKA");
    if (l.self_kolize.length) tag.push("SELF_KOLIZE");
    console.log(`   noha #${l.poradi} (${l.poradi === 1 ? "u prepazky" : l.poradi + ". od prepazky"}) z=${l.z} dilu=${l.dilu}  [${tag.join(", ")}]`);
    if (l.chybi_pricka) console.log(`      nespojene dily: ${l.nespojene_dily.join(", ")}`);
    for (const e of l.self_kolize) {
      console.log(`      zanoreni: ${e.a}  X  ${e.b}  prekryv=(${e.overlap.x}, ${e.overlap.y}, ${e.overlap.z}) mm, u podlahy Y=${e.yMin}`);
    }
  }
}
console.log("\n=== SOUHRN ===");
console.log(JSON.stringify(report.summary, null, 1));
// rozlozeni podle poradi nohy
const byOrder = {};
for (const r of report.rows) for (const l of r.legs) {
  if (l.chybi_pricka || l.self_kolize.length) byOrder[l.poradi] = (byOrder[l.poradi] || 0) + 1;
}
console.log("vadne nohy podle poradi od prepazky:", JSON.stringify(byOrder));
if (jsonOut) { fs.writeFileSync(jsonOut, JSON.stringify(report, null, 1)); console.log("JSON ->", jsonOut); }
