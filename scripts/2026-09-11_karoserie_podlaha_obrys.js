// Podlaha jako narys z karoserie: vodorovny rez (Y = kousek nad
// podlahou, NE presne v 0 - v 0 by rovina mohla lehnout naplocho na
// samotnou podlahu a vratit nesmysl) skrz skutecnou GLB geometrii
// (L+R_D+B), sesbira useckova pruniky (STEJNA "sectionSegments()"
// technika jako scripts/2026-08-20_live_section_cut.js - bot3 2026-09-11
// "nastroj existuje, nepis ji znovu"), sesklada je do uzavrenych smycek
// (spolecne body = hrany grafu) a vybere NEJVETSI uzavrenou smycku jako
// hlavni pudorysny obrys.
//
// Vznik: Robert 2026-09-11, pres bot3, po zjednoduseni puvodniho
// "cely interier" napadu na "jen naznak karoserie + podlaha jako linka":
// "nejaky náznak karoserie a podlahu, podlahu muzeme udelat jako vyřez
// z karoserie, obrysová linka, zkus udelat z karoserie podlahu jako
// linku". Prototyp JEN pro K-075 (Fiat Doblo FI14) - Robert vyslovne
// "zadny katalog, jedna karoserie, jeden zaver".
//
// Overeno na K-075 (Y=30mm): rez da TRI souvisle skupiny usecek (vsechny
// sude stupne, zadna prerusena "vlajici" hrana), ne jednu:
//   #1 (226 usecek) = hlavni obrys - pokryva CELOU sirku i delku, to je
//      ten, co chceme.
//   #2 (168 usecek, X[614,760] Z[-926,145], jen prava strana) - LEZI
//      CELA MIMO #1 (0/169 bodu uvnitr) - nejspis prah posuvnych dveri
//      (soubor _R_D = prava strana s dvermi, proto jen tam), NE podbeh
//      (podbehy jsou u obou stran, jednostranny nalez by byl podezrely).
//      Do podlahy NEPATRI (je mimo obrys), ale je REALNA geometrie -
//      zahodit, ne mazat/upravovat original.
//   #3 (35 usecek, X[-760,760] Z[-1600,-1590], jen 10mm hloubky) =
//      tecny rez PREPAZKOU B (sedi presne na jeji zmerene pozici Z=
//      -1600) - sum z tenke skoro-svisle plochy, ne soucast pudorysu.
//      Zahodit.
// Podbehy se v Y=30mm JESTE NEPROJEVUJI (zvedaji se postupne) - hlavni
// obrys proto vyjde pres celou sirku, ne s vyrezy podbehu. To NEVADI
// pro podlahu (cely pudorys je spravne), jen je to jiny vysledek, nez
// "obrys s vyrezy podbehu" puvodne cekany.
//
// DULEZITE (nalezeno pri stavbe): #1 NENI jednoducha smycka - ma 5 bodu
// se stupnem >2 (vetveni, ne prerusena hrana), vsechny na svu MEZI
// SOUBORY (X=0 = _L/_R_D stred, poblíž Z prepazky) - _L a _R_D jsou dva
// NEZAVISLE autorske soubory, ktere se maji dotykat presne na X=0, ale
// jejich vrcholy tam nejsou bit-identicke, takze rez tam misty vytvori
// dotykajici se, ne plynule navazujici hrany. Naivni pruchod grafem
// (jedna usporadana smycka) by proto pri prvnim vetveni sebral jen
// POLOVINU obrysu (viz git historie - prvni verze takhle omylem vratila
// jen levou polovinu, X[-760,0] misto [-760,760]). Misto slozite opravy
// pruchodu grafem (mimo rozsah "jeden prototyp, jedno vozidlo") se
// hlavni obrys pocita jako KONVEXNI OBAL vsech bodu skupiny #1 - vzdy
// vrati platny jednoduchy uzavreny polygon, cenou za ztratu drobnych
// konkavnich detailu (zadne vyznamne v Y=30mm stejne nejsou, viz vyse).
// Pro dalsi vozidla by tohle zjednoduseni chtelo znovu overit vizualne,
// ne prevzit naslepo (proto zustava vypis vsech skupin, ne jen hlavni).
//
// Pouziti: node scripts/2026-09-11_karoserie_podlaha_obrys.js car_bodies/<base> [--json]
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/car_bodies/";

const CUT_Y_MM = 30;

function sectionSegments(obj, origin, cutNormal, projFn) {
  const segs = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  obj.traverse(n => {
    if (!n.isMesh || !n.geometry || !n.geometry.attributes.position) return;
    const pos = n.geometry.attributes.position, index = n.geometry.index;
    const triCount = index ? index.count / 3 : pos.count / 3;
    for (let t = 0; t < triCount; t++) {
      const ia = index ? index.getX(t * 3) : t * 3, ib = index ? index.getX(t * 3 + 1) : t * 3 + 1, ic = index ? index.getX(t * 3 + 2) : t * 3 + 2;
      vA.fromBufferAttribute(pos, ia).applyMatrix4(n.matrixWorld);
      vB.fromBufferAttribute(pos, ib).applyMatrix4(n.matrixWorld);
      vC.fromBufferAttribute(pos, ic).applyMatrix4(n.matrixWorld);
      const pts = [];
      [[vA, vB], [vB, vC], [vC, vA]].forEach(([p1, p2]) => {
        const d1 = p1.clone().sub(origin).dot(cutNormal), d2 = p2.clone().sub(origin).dot(cutNormal);
        if ((d1 > 0) !== (d2 > 0)) {
          const s = d1 / (d1 - d2);
          pts.push(projFn(p1.clone().lerp(p2, s)));
        }
      });
      if (pts.length === 2) segs.push([pts[0][0], pts[0][1], pts[1][0], pts[1][1]]);
    }
  });
  return segs;
}

function keyOf(x, z) { return `${x.toFixed(1)},${z.toFixed(1)}`; }

function connectedComponents(segs) {
  const uf = {};
  function ufind(a) { if (!(a in uf)) uf[a] = a; while (uf[a] !== a) { uf[a] = uf[uf[a]]; a = uf[a]; } return a; }
  function uunion(a, b) { const ra = ufind(a), rb = ufind(b); if (ra !== rb) uf[ra] = rb; }
  for (const [x1, z1, x2, z2] of segs) uunion(keyOf(x1, z1), keyOf(x2, z2));
  const groups = {};
  for (const s of segs) {
    const r = ufind(keyOf(s[0], s[1]));
    (groups[r] = groups[r] || []).push(s);
  }
  return Object.values(groups);
}

// Prevede neusporadany seznam usecek JEDNE komponenty na usporadanou
// smycku bodu (predpoklada, ze kazdy bod ma stupen 2 - proste uzavrena
// smycka, zadne vetveni). Kdyby to neplatilo, projde tolik hran, kolik
// jde, a vrati neuplnou smycku - volajici muze delku porovnat s poctem
// vstupnich usecek.
function walkLoop(segList) {
  const adj = new Map(), pointOf = new Map();
  for (const [x1, z1, x2, z2] of segList) {
    const k1 = keyOf(x1, z1), k2 = keyOf(x2, z2);
    pointOf.set(k1, [x1, z1]); pointOf.set(k2, [x2, z2]);
    if (!adj.has(k1)) adj.set(k1, []);
    if (!adj.has(k2)) adj.set(k2, []);
    adj.get(k1).push(k2);
    adj.get(k2).push(k1);
  }
  const start = keyOf(segList[0][0], segList[0][1]);
  const loop = [start];
  const visitedEdges = new Set();
  let cur = start;
  for (let i = 0; i < segList.length + 2; i++) {
    const neighbors = adj.get(cur) || [];
    const next = neighbors.find(n => !visitedEdges.has(cur + "|" + n));
    if (next == null) break;
    visitedEdges.add(cur + "|" + next); visitedEdges.add(next + "|" + cur);
    loop.push(next);
    cur = next;
    if (cur === start) break;
  }
  return loop.map(k => pointOf.get(k));
}

// Andrew monotone chain - staci pro plochy XZ body, zadna zavislost
// navic. Vraci body proti smeru hodinovych rucicek, uzavreny (posledni
// == prvni se NEpridava, volajici si to doplni sam kde potrebuje).
function convexHull(points) {
  const pts = [...new Map(points.map(p => [keyOf(p[0], p[1]), p])).values()]
    .sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (pts.length < 3) return pts;
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower = [];
  for (const p of pts) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop();
    lower.push(p);
  }
  const upper = [];
  for (let i = pts.length - 1; i >= 0; i--) {
    const p = pts[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop();
    upper.push(p);
  }
  lower.pop(); upper.pop();
  return lower.concat(upper);
}

function computeOutline(base) {
  const group = new THREE.Group();
  for (const suf of ["_L", "_R_D", "_B"]) {
    const p = KAT + base + suf + ".glb";
    const m = parseGlbMesh(p);
    m.updateMatrixWorld(true);
    group.add(m);
  }
  group.updateMatrixWorld(true);
  const origin = new THREE.Vector3(0, CUT_Y_MM, 0);
  const normal = new THREE.Vector3(0, 1, 0);
  const proj = (p) => [p.x, p.z];
  const segs = sectionSegments(group, origin, normal, proj);
  const comps = connectedComponents(segs).sort((a, b) => b.length - a.length);
  const loops = comps.map((c, i) => {
    // Vetveni (viz komentar nahore) delaji z naivniho pruchodu grafem
    // nespolehlivy nastroj - hlavni skupina (i===0) se proto vraci jako
    // KONVEXNI OBAL vsech jejich bodu, ne jako usporadana smycka hran.
    // Mensi skupiny (#2/#3, zahazovane) si walkLoop ponechavaji - u nich
    // jde jen o informativni bbox pro rozhodnuti "patri/nepatri dovnitr",
    // presny tvar nepotrebujeme.
    const allPts = [...new Map(c.flatMap(s => [[keyOf(s[0], s[1]), [s[0], s[1]]], [keyOf(s[2], s[3]), [s[2], s[3]]]])).values()];
    const points = i === 0 ? convexHull(allPts) : walkLoop(c);
    const closed = i !== 0 && points.length > 2 && keyOf(...points[0]) === keyOf(...points[points.length - 1]);
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    for (const [x, z] of allPts) { if (x < minX) minX = x; if (x > maxX) maxX = x; if (z < minZ) minZ = z; if (z > maxZ) maxZ = z; }
    return {
      segCount: c.length, pointCount: points.length, closed,
      method: i === 0 ? "convexHull" : "walkLoop",
      bbox: { minX, maxX, minZ, maxZ }, points,
    };
  });
  return { cutY: CUT_Y_MM, loopCount: loops.length, loops };
}

module.exports = { computeOutline, convexHull };

if (require.main !== module) return;

const args = process.argv.slice(2);
const asJson = args.includes("--json");
const baseArg = args.find(a => !a.startsWith("--"));
if (!baseArg) { console.error("Pouziti: node ... car_bodies/<base> [--json]"); process.exit(1); }
const base = baseArg.replace(/^car_bodies\//, "");

let result;
try {
  result = computeOutline(base);
} catch (e) {
  console.log(JSON.stringify({ ok: false, error: e.message }));
  process.exit(asJson ? 0 : 1);
}

if (asJson) {
  // hlavni vystup pro Python job-builder: nejvetsi skupina (index 0),
  // jako konvexni obal (viz komentar nahore - overeno na K-075, pro jine
  // vozy by se tohle meritko melo znovu potvrdit, ne slepe prevzit).
  const main = result.loops[0] || null;
  console.log(JSON.stringify({
    ok: !!main,
    base, cutY: result.cutY,
    loopCount: result.loopCount,
    mainLoop: main ? { pointCount: main.pointCount, method: main.method, bbox: main.bbox, points: main.points } : null,
    otherLoops: result.loops.slice(1).map(l => ({ segCount: l.segCount, closed: l.closed, bbox: l.bbox })),
  }));
} else {
  console.log(`\n=== ${base} - rez v Y=${result.cutY}mm ===`);
  result.loops.forEach((l, i) => {
    console.log(`  skupina #${i}: ${l.segCount} usecek, ${l.pointCount} bodu (${l.method}), uzavrena=${l.closed}, bbox X[${l.bbox.minX.toFixed(0)},${l.bbox.maxX.toFixed(0)}] Z[${l.bbox.minZ.toFixed(0)},${l.bbox.maxZ.toFixed(0)}]`);
  });
}
