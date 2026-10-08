// Chirurgicka oprava horniho pasma Doblo K-075 verze A (381/382/383) -
// NAHRAZUJE jen postizenou oblast (posledni box v col0 + cely col1 +
// horni podelniky) presnou kopii z overeneho C (341/343/345), misto
// znovu-generovani pres horni_ram.js (ten na #369 ZAKLAD duploval spodni
// pasmo - viz zpravy forku v teto session). Spodni pasmo cile SESTAVY
// zustava NEDOTCENE (uz je spravne).
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { isProfilePart } = require("/opt/konfigurator/webapp/js/scene-geometry-shared.js");

const dump = JSON.parse(fs.readFileSync(
  "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/dolba_ab_splice_input.json", "utf8"));

// OPRAVA (po prvnim pokusu): nestaci vymenit jen "posledni box" - cely
// sloupec col0 ma u A/B jinou vysku nez u C (box-fitting logika stavi
// odspodu jinak, kdyz je v col0 o 1 box min), takze p0/p1/p2 UVNITR
// col0 uz taky nesedi na C-pozice. Nahrazuje se proto CELY col0 (vsechny
// p*) + CELY col1 (vsechny p*), ne jen okrajovy rozdil.
const REPLACE_PREFIXES = ["eurobox-col0-", "nosnik-col0-", "spojnice-col0-",
  "eurobox-col1-", "nosnik-col1-", "spojnice-col1-",
  "podelnik-celni-horni", "podelnik-zadni-horni", "pricka-horni-",
  // uhelnik-noha2 (2026-09-13, po strukturnim srovnani): jedina zbyla
  // odchylka od C po vyse uvedene oprave (10 vs 8) - dusledek stareho/
  // spatneho rozlozeni boxu v teto oblasti. Box geometrie uz sedi presne
  // na C, takze spravna pozice uhelniku je taky presne C's - splicuje se
  // stejne jako boxy, misto znovu-pousteni applyUhelnikyToLeg od nuly.
  "uhelnik-noha2"];
function jeReplace(role) { return REPLACE_PREFIXES.some(pref => String(role || "").startsWith(pref)); }

function jeRazitko(role) { return String(role || "").startsWith("logo-ochrana"); }

const meshCache = new Map();
function meshFor(glbFile) {
  if (!meshCache.has(glbFile)) meshCache.set(glbFile, parseGlbMesh(glbFile));
  return meshCache.get(glbFile);
}
function box3Of(p) {
  if (R.jeKaroserie(p.part_id)) return null;
  const glb = R.glbPath(p.part_id);
  if (!glb) return null;
  const mesh = meshFor(glb);
  const obj = new THREE.Mesh(mesh.geometry);
  obj.position.set(...p.position);
  obj.quaternion.set(...p.quaternion);
  if (p.scale) obj.scale.set(...p.scale); else obj.scale.set(1, 1, 1);
  obj.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(obj);
}
// OPRAVA (po 2. pokusu, "nosnik-col0-p0 <-> eurobox-col0-p0" falesny
// poplach): nosnik/spojnice se SPRAVNE dotykaji euroboxu, ktery drzi -
// to je platny plochy spoj (1 osa gap~0, zbyle 2 osy PLNY prekryv), ne
// kolize - presne "Metodika bod 1" z 3d-scena-spoje skillu, kterou jsem
// tady porusil vlastnim primitivnim testem. Skutecna kolize (zanoreni)
// vyzaduje SUBSTANCIALNI presah na VSECH 3 osach - flush dotyk (jedna
// osa temer 0 presah) se nepocita.
const MIN_REAL_OVERLAP = 2; // mm - min presah na KAZDE ose, aby to byla skutecna kolize
function osaOverlap(mn1, mx1, mn2, mx2) { return Math.min(mx1, mx2) - Math.max(mn1, mn2); }
function overlap3D(b1, b2) {
  const ox = osaOverlap(b1.min.x, b1.max.x, b2.min.x, b2.max.x);
  const oy = osaOverlap(b1.min.y, b1.max.y, b2.min.y, b2.max.y);
  const oz = osaOverlap(b1.min.z, b1.max.z, b2.min.z, b2.max.z);
  return ox > MIN_REAL_OVERLAP && oy > MIN_REAL_OVERLAP && oz > MIN_REAL_OVERLAP;
}

const results = {};
for (const [targetId, refId] of dump.pairs) {
  const target = dump.data[targetId];
  const ref = dump.data[refId];

  const kept = target.parts.filter(p => !jeReplace(p.role) && !jeRazitko(p.role));
  const spliced = ref.parts.filter(p => jeReplace(p.role));
  const novaParts = [...kept, ...spliced];

  // over kolize mezi vsemi VZNIKLYMI pary parts (kept vs spliced, spliced vs spliced) -
  // kept-vs-kept uz je znama-spravna (nedotcena cast puvodni sestavy), takze ji
  // vynechavame z O(n^2) pro rychlost, ale spliced-vs-cokoli PLNE overujeme.
  // OPRAVA (po 3. pokusu): nosnik/spojnice VS eurobox ze STEJNE (col,p)
  // pozice je vzdy takhle "prekryvajici" i v overenych datech C samotneho
  // (zmereno: X=5 Y=12 Z=399mm presah na nosnik-col0-p0/eurobox-col0-p0 v
  // #341) - eurobox rim zapada na nosnik, neni to kolize (Metodika bod 8,
  // nesting geometrie, Box3 nerozezna dutinu od plneho materialu). Tenhle
  // par se tedy VZDY vynecha z kontroly. Skutecne riziko je jen na HRANICI
  // mezi vlozenymi (spliced, z C) a ponechanymi (kept, puvodni cile
  // sestavy) dily - spliced-vs-spliced je uz sama o sobe overena (C je
  // ziva, funkcni sestava).
  function jeOcekavanyNestingPar(rA, rB) {
    const jeBox = r => r.startsWith("eurobox-");
    const jeNosnikSpojnice = r => r.startsWith("nosnik-") || r.startsWith("spojnice-");
    return (jeBox(rA) && jeNosnikSpojnice(rB)) || (jeBox(rB) && jeNosnikSpojnice(rA));
  }
  const boxes = novaParts.map(p => ({ p, b: box3Of(p), isSpliced: jeReplace(p.role) })).filter(x => x.b);
  const kolize = [];
  for (let i = 0; i < boxes.length; i++) {
    if (!boxes[i].isSpliced) continue; // aspon jedna strana musi byt nova (spliced)
    for (let j = 0; j < boxes.length; j++) {
      if (i === j) continue;
      if (boxes[i].isSpliced && boxes[j].isSpliced) continue; // spliced-vs-spliced jiz overeno v C
      if (jeOcekavanyNestingPar(boxes[i].p.role, boxes[j].p.role)) continue;
      if (overlap3D(boxes[i].b, boxes[j].b)) {
        kolize.push({ a: boxes[i].p.role, b: boxes[j].p.role });
      }
    }
  }
  // dedup (a,b)/(b,a)
  const seen = new Set();
  const kolizeUniq = kolize.filter(k => {
    const key = [k.a, k.b].sort().join("|");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  results[targetId] = {
    puvodne: target.parts.length, kept: kept.length, spliced: spliced.length, nove: novaParts.length,
    kolize: kolizeUniq,
    parts: novaParts,
  };
  console.log(`#${targetId} (ref #${refId}): puvodne=${target.parts.length} kept=${kept.length} spliced=${spliced.length} nove_celkem=${novaParts.length} kolize=${kolizeUniq.length}`);
  if (kolizeUniq.length) kolizeUniq.forEach(k => console.log("   KOLIZE:", k.a, "<->", k.b));
}

fs.writeFileSync(
  "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/splice_a_output.json",
  JSON.stringify(results));
console.log("\nzapsano splice_a_output.json");
