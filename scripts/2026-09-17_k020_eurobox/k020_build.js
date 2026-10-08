// K-020 A - stavba nahledu: sloupec0 2box (2 patra), sloupec1 1box (1 patro, pres podbeh).
// Vystup: k020_parts.json + overeni (kolize steny, self-kolize, dosed nosniku/spojnic na 3 osach).
const THREE = require("three");
const fs = require("fs");
const L = require("./k020_lib.js");
const { T, D, H, TOP_Y } = L;
const KAT = "/opt/konfigurator/webapp/katalog/";
const EUROBOX = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
const GLB = { Object_7: KAT + "Object_7.glb", product_3071: KAT + "product_3071.glb", product_3788: KAT + "product_3788.glb", product_3793: KAT + "product_3793.glb", product_3794: KAT + "product_3794.glb", product_3795: KAT + "product_3795.glb" };
const NEST = 12, GAP = 30;

const ctx = L.makeCtx();
const front = L.placeFrontLeg(ctx);
const legs = [{ type: "plain", anchorZ: front.anchorZ, yNew: null, sb: 0 }];
// PLAN: [{N, levels:[[h,h,...]]}] - pole hodnot per patro musi mit delku N (test nize) a
// vsechny stejne (Robert 2026-09-17: "vzdy musi byt boxy na jednom luzku stejne vysky").
// Sloupce/sirky (2box+1box) jsou spolecne pro vsechny verze K-020 (stejna karoserie/D/rezervy jako #127) -
// PLAN lze predat z externiho JSON (argv[2]), jinak vychozi = verze A (#127).
const fs2 = require("fs");
const PLAN = process.argv[2] ? JSON.parse(fs2.readFileSync(process.argv[2], "utf8")) : [
  { N: 2, levels: [[270, 270], [170, 170]] },
  { N: 1, levels: [[220]] },
];
const OUT_PATH = process.argv[3] || (__dirname + "/k020_parts.json");
// Robert 2026-09-17: clenita noha se spodnim zadnim profilem (sloupek) az k podlaze,
// dole propojena prickou jako standard. false = "clenita noha s podperou zespodu" (sloupek nejde k zemi).
const SLOUPEK_K_PODLAZE = true; // standard, fallback na podperu zespodu viz nize
const log = [];
const parts = [];
const columns = [];
for (let c = 0; c < PLAN.length; c++) {
  const last = legs[legs.length - 1];
  const nz = last.anchorZ + ctx.dirAway * (T + L.CLEAR_SPACING[PLAN[c].N]);
  const leg = L.legAt(ctx, nz);
  if (!leg) throw new Error(`sloupec${c}: noha na Z=${nz} nejde postavit`);
  if (leg.type === "vyrez" && SLOUPEK_K_PODLAZE) {
    // STANDARD (Robert 2026-09-17): sloupek k podlaze, pakliže to karoserie dovoli; jinak
    // "clenita noha s podperou zespodu" (leg.sb z legAt zustava). shape_geometry_methods.id=6.
    const r = L.sloupekKPodlazeWallNear(ctx, nz, leg.yNew);
    const zkus = r ? { ...leg, sb: 0, wallNear: r.wallNear } : null;
    if (zkus && !ctx.collides(ctx.toWorld(L.legParts(zkus), nz))) {
      leg.sb = 0; leg.wallNear = r.wallNear; leg.sloupekPrvniVolna = r.prvniVolna; leg.varianta = "sloupek k podlaze";
    } else {
      leg.varianta = "s podperou zespodu";
    }
  }
  legs.push(leg);
  // podlaha sloupce: max(200, Y_new) + fresh krokovani nosniku pres cely rozpon (+30 podbeh)
  const lf = last, lt = leg, N = PLAN[c].N;
  const railsAt = fy => L.railsFor(ctx, N, lf, lt, fy + T / 2).parts;
  const base = Math.max(200, ...[lf, lt].filter(l => l.type === "vyrez").map(l => l.yNew));
  let floor = base;
  if (ctx.collides(railsAt(base))) {
    let y = base, clear = null;
    for (let s = 0; s < 700; s++) { y++; if (!ctx.collides(railsAt(y))) { clear = y; break; } }
    if (clear === null) throw new Error(`sloupec${c}: luzko bez bezkolizni vysky`);
    floor = clear + L.PODBEH_CLEARANCE;
  }
  // fyzicky strop siroka sonda
  const rr = L.railsFor(ctx, N, lf, lt, 0);
  const slab = y => { const m = new THREE.Mesh(new THREE.BoxGeometry(D, 10, rr.len)); m.position.set(ctx.offsetX + ctx.sgn * (D / 2), y + ctx.offsetY, (rr.zFrom + rr.zTo) / 2); m.updateMatrixWorld(true); return m; };
  let yy = floor + T, hit = null;
  for (let s = 0; s < 1200; s++) { yy++; if (ctx.collidesWithWalls(slab(yy))) { hit = yy; break; } }
  const physCeil = hit === null ? H : hit - 2; // sonda nenarazila do 1200 kroku -> strop = vyska nohy
  let railTop = floor + T;
  const lv = [];
  PLAN[c].levels.forEach((hs, li) => {
    if (hs.length !== N) throw new Error(`sloupec${c} patro${li}: pocet boxu ${hs.length} != N=${N}`);
    if (new Set(hs).size !== 1) throw new Error(`sloupec${c} patro${li}: ruzne vysky boxu na jednom luzku ${hs} (Robert 2026-09-17: vzdy stejne)`);
    const railCenter = railTop - T / 2;
    const isTop = li === PLAN[c].levels.length - 1;
    const hMax = Math.max(...hs);
    const boxTop = railTop + (hMax - NEST);
    if (railCenter > TOP_Y - T / 2 + 1e-6) throw new Error(`sloupec${c} patro${li}: nosnik ${railCenter} nad TOP_Y-T/2 (cele nosniku mimo profil nohy)`);
    if (!isTop && boxTop > TOP_Y + 1e-6) throw new Error(`sloupec${c} patro${li}: box top ${boxTop} > TOP_Y pod dalsim patrem`);
    if (boxTop > Math.min(H, physCeil) + 1e-6) throw new Error(`sloupec${c} patro${li}: box top ${boxTop} > strop ${Math.min(H, physCeil)}`);
    const r = L.railsFor(ctx, N, lf, lt, railCenter, c, li);
    parts.push(...r.parts);
    // sloty mezi sousednimi spojnicemi, od prepazky
    const cz = r.connZ.slice().sort((a, b) => (a - b) * ctx.dirAway);
    hs.forEach((h, si) => parts.push({ part_id: EUROBOX[h], role: `eurobox-sloupec${c}-patro${li}`, _slot: { z0: cz[si], z1: cz[si + 1], railTopY: railTop + ctx.offsetY, h } }));
    lv.push({ patro: li, railCenter, railTop, boxy: hs, boxTop });
    railTop = railTop + (hMax - NEST) + GAP + T;
  });
  columns.push({ sloupec: c, N, legFrom: legs.length - 2, legTo: legs.length - 1, floorBase: base, floor, physCeil, patra: lv });
}
// nohy + zaslepky nahoru (id=4)
const endRoles = { plain: ["predni-svislice", "zadni-svislice-dolni", "cap"], vyrez: ["predni-svislice", "zadni-svislice-nad-zarezem", "cap"] };
const legPartsAll = [];
legs.forEach((leg, i) => {
  const w = ctx.toWorld(L.legParts(leg), leg.anchorZ).map(p => ({ ...p, role: `${p.role}-noha${i}` }));
  legPartsAll.push(...w);
  const caps = w.filter(p => endRoles[leg.type].some(r => p.role === `${r}-noha${i}`)).map(p => ({
    part_id: "product_3071", position: [p.position[0], p.position[1] + p.scale[1] * 1000 / 2 + L.CAP_FLANGE, p.position[2]], quaternion: L.Q_ENDCAP_UP, scale: [1, 1, 1], role: `zaslepka-${p.role}`,
  }));
  legPartsAll.push(...caps);
});
parts.unshift(...legPartsAll);

// meshe
const cache = {};
function meshOf(p) { const m = ctx.engine.parseGlbMesh(GLB[p.part_id]); m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale); m.updateMatrixWorld(true); return m; }
// umisteni euroboxu (probe pod Q_ALONG_Z, zmereno z kazde GLB zvlast)
for (const p of parts) {
  if (!p._slot) continue;
  const probe = meshOf({ part_id: p.part_id, position: [0, 0, 0], quaternion: L.Q_ALONG_Z, scale: [1, 1, 1] });
  const b = new THREE.Box3().setFromObject(probe);
  const cx = (b.min.x + b.max.x) / 2, cz = (b.min.z + b.max.z) / 2;
  const tx = ctx.offsetX + ctx.sgn * (D / 2), tz = (p._slot.z0 + p._slot.z1) / 2;
  p.position = [tx - cx, p._slot.railTopY - b.min.y - NEST, tz - cz];
  p.quaternion = L.Q_ALONG_Z.slice(); p.scale = [1, 1, 1];
  p._slotInfo = p._slot; delete p._slot;
}

// ---- OVERENI ----
const V = { rozsah: {}, kolizeSteny: [], selfKolize: [], dosed: [], boxy: [] };
const meshes = parts.map(meshOf);
const boxes = meshes.map(m => new THREE.Box3().setFromObject(m));
V.rozsah.dilu = parts.length;
V.rozsah.profilu = parts.filter(p => p.part_id === "Object_7").length;
V.rozsah.euroboxu = parts.filter(p => p.part_id.startsWith("product_37")).length;
V.rozsah.zaslepek = parts.filter(p => p.part_id === "product_3071").length;
parts.forEach((p, i) => { const g = new THREE.Group(); g.add(meshOf(p)); g.updateMatrixWorld(true); if (ctx.collidesWithWalls(g)) V.kolizeSteny.push(p.role); });
V.rozsah.testovanoProtiStenam = parts.length;
const ov = (A, B) => [0, 1, 2].map(k => Math.min(A.max.getComponent(k), B.max.getComponent(k)) - Math.max(A.min.getComponent(k), B.min.getComponent(k)));
let paru = 0;
for (let i = 0; i < parts.length; i++) for (let j = i + 1; j < parts.length; j++) {
  paru++;
  const o = ov(boxes[i], boxes[j]);
  if (o[0] > 0.5 && o[1] > 0.5 && o[2] > 0.5) {
    const a = parts[i], b = parts[j];
    const nest = a.part_id !== "Object_7" || b.part_id !== "Object_7";
    if (!nest) V.selfKolize.push([a.role, b.role, o.map(v => +v.toFixed(2))]);
  }
}
V.rozsah.paruSelfKolize = paru;
// dosed: kazdy nosnik a spojnice - pro kazdy profil, se kterym se dotyka (jedna osa |o|<=0.05, dve osy kladne),
// musi byt mensi celo CELE na druhem dilu: na dvou osach overlap >= min(rozmer) - 0.05
function sizeOf(B) { return [0, 1, 2].map(k => B.max.getComponent(k) - B.min.getComponent(k)); }
parts.forEach((p, i) => {
  if (p.part_id !== "Object_7" || !/^(nosnik|spojnice)/.test(p.role)) return;
  const touches = [];
  parts.forEach((q, j) => {
    if (i === j || q.part_id !== "Object_7") return;
    const o = ov(boxes[i], boxes[j]);
    const contactAxes = o.map((v, k) => Math.abs(v) <= 0.05 ? k : -1).filter(k => k >= 0);
    if (contactAxes.length !== 1) return;
    const k = contactAxes[0];
    const others = [0, 1, 2].filter(a => a !== k);
    if (!others.every(a => o[a] > 0.5)) return;
    const si = sizeOf(boxes[i]), sj = sizeOf(boxes[j]);
    const full = others.every(a => o[a] >= Math.min(si[a], sj[a]) - 0.05);
    touches.push({ s: q.role, osa: "xyz"[k], plnaPlocha: full, overlap: others.map(a => +o[a].toFixed(2)) });
  });
  V.dosed.push({ dil: p.role, pocetDotyku: touches.length, neplne: touches.filter(t => !t.plnaPlocha), dotyky: touches.map(t => `${t.s}:${t.osa}:${t.plnaPlocha ? "plna" : "NEPLNA"}`) });
});
// boxy: vyska dna nad nosnikem, mezera k dalsimu luzku
parts.forEach((p, i) => { if (!p._slotInfo) return; V.boxy.push({ role: p.role, h: p._slotInfo.h, min_y: +boxes[i].min.y.toFixed(1), max_y: +boxes[i].max.y.toFixed(1), railTop: +p._slotInfo.railTopY.toFixed(1) }); });

const clean = parts.map(({ _slotInfo, ...r }) => r);
// WORKFLOW.md pravidlo 25 (zmena 2026-09-17): sestava vkladana botem MUSI obsahovat i karoserii -
// car_bodies 849/850/851 (VW32 _L/_R_D/_B) na pozici, vuci ktere se stavelo (surova GLB = identita).
[849, 850, 851].forEach(id => clean.push({ part_id: `car_body_${id}`, position: [0, 0, 0], quaternion: [0, 0, 0, 1], scale: [1, 1, 1] }));
fs.writeFileSync(OUT_PATH, JSON.stringify({ parts: clean, join_groups: [], frame_groups: [] }));
fs.writeFileSync(__dirname + "/k020_build_out.json", JSON.stringify({ front, offsetX: ctx.offsetX, offsetY: ctx.offsetY, legs, columns, V }, null, 1));
console.log(JSON.stringify({ legs, columns }, null, 1));
console.log("ROZSAH", JSON.stringify(V.rozsah));
console.log("KOLIZE SE STENOU:", V.kolizeSteny.length, JSON.stringify(V.kolizeSteny));
console.log("SELF-KOLIZE profil-profil:", V.selfKolize.length, JSON.stringify(V.selfKolize));
const bad = V.dosed.filter(d => d.neplne.length || d.pocetDotyku < 2);
console.log("DOSED nosniku/spojnic: kontrolovano", V.dosed.length, "problemu", bad.length);
bad.forEach(d => console.log("  ", JSON.stringify(d)));
V.dosed.slice(0, 50).forEach(d => console.log("   ", d.dil, "->", d.dotyky.join(", ")));
console.log("BOXY", JSON.stringify(V.boxy));
