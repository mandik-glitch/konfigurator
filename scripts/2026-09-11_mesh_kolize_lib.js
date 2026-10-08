// MESH-PRESNY test kolize dvou dilu sestavy. Nahrazuje `Box3` prekryv jako
// DUKAZ kolize - ten smi slouzit uz jen jako predfiltr (broad phase).
//
// === PROC EXISTUJE ===
// Dosavadni kolizni kontroly (filter_uhelniky_collisions.cjs,
// sweep_kolizni_uhelniky.cjs) rozhodovaly podle prekryvu osove zarovnanych
// obalu. To ma dve chyby, obe zapsane ve skillu `3d-scena-spoje`:
//   past c.8  `Box3` prekryv SAM O SOBE neni dukaz kolize u dilu se
//             stohovaci/vnorovaci geometrii (schodek, drazka, odstupnovana
//             patka). Eurobox s 12mm nozkou zapadajici do luzka vykazuje
//             12mm prekryv na Y a pritom realne nekoliduje.
//   past c.7  Naopak hranovy raycast nevidi dil CELY vnoreny do vetsiho.
// Tenhle modul resi obe: verdikt dava SKUTECNA trojuhelnikova geometrie
// (prunik ploch) DOPLNENA o test vnoreni (vrchol uvnitr objemu).
//
// AABB navic u POOTOCENEHO dilu nadhodnocuje - obal pootocene desky je
// vetsi nez deska. Vsechny sestavy v katalogu maji pootocene dily
// (vodorovne panely maji quaternion[0] ~ 0.707), takze to neni teoreticka
// vyhrada.
//
// === CO JE "KOLIZE" ===
// Dva dily koliduji, kdyz se jejich HMOTA prekryva - ne kdyz se dotykaji.
// Dosed (flush) je UCEL spoje, ne vada: dva dily sdileji rovinu, prekryv
// je presne 0. Proto ma kazdy test kladnou mez TOL (default 0.05mm) a
// pta se "prenika o VIC nez TOL", ne "dotyka se".
// TOL neni naladena na vysledek: zmerena separace v datech je 0.00mm
// (dosed) vs >= 5.00mm (kolize), takze cokoli mezi lezi v prazdnem pasmu.
//
// === JAK SE ROZHODUJE A MERI ===
// Verdikt dava OBJEMOVY test: prostor, kde se obaly prekryvaji, se
// pravidelne navzorkuje a hleda se bod, ktery lezi uvnitr OBOU siti.
// Existuje-li, dva dily sdileji hmotu - to je kolize bez ohledu na to,
// jak vypadaji obaly. Prave tohle resi past c.8: eurobox s vybranim na
// spodku ma s nosnikem 12mm prekryv obalu, ale ani jeden navzorkovany
// bod nelezi uvnitr obou siti, takze verdikt je spravne "nekoliduje".
//
// Velikost kolize se hlasi DVEMA cisly, protoze jedno nestaci:
//
//   `odsun`  = NEJMENSI posun po svetove ose, po kterem se site prestanou
//              prekryvat. To je odpoved na "o kolik je zaboreny" a soucasne
//              na "slo by to spravit posunutim". Hleda se pulenim intervalu
//              mezi 0 a posunem, po kterem se rozejdou uz OBALKY (tam uz
//              kolize byt nemuze), takze horni mez je vzdy platna.
//   `oblast` = rozmery spolecne hmoty [dx,dy,dz]. Popisuje, JAK se prekryvaji.
//
// DVE PASTI, na obe se pri psani tehle knihovny narazilo:
// (1) Hloubku NELZE merit jako "nejhloubeji zanoreny VRCHOL". Dily sestavy
//     sdileji roviny (flush dosed je ucel spoje), takze vrcholy zaboreneho
//     dilu lezi presne NA stene toho druheho a vzdalenost od povrchu vyjde
//     0, i kdyz se objemy prekryvaji o 7mm. Dva kvadry 100^3 posunute o
//     95mm jsou presne takovy pripad - viz regresni test, cast 1.
// (2) Hloubkou NENI ani nejmensi rozmer spolecne hmoty. U uhelniku, jehoz
//     stena projde skrz profil, je nejmensi rozmer prekryvu roven TLOUSTCE
//     PLECHU UHELNIKU (6mm) - a ta je stejna, at je zaboreny o 7mm nebo
//     o 22mm. Zmereno 2026-09-11: spolecna hmota je 6 x 18 x 28mm u sestavy
//     #79 a 6 x 22 x 28mm u #116; prvni cislo je porad plech, lisi se druhe.
//
// Vzorkovani ma konecne rozliseni, takze se doplnuje testem PRUNIKU
// PLOCH (SAT nad dvojicemi trojuhelniku). Ten zachyti i prekryv tencí
// nez krok mrizky.
//
// === OMEZENI, KTERE JE POTREBA ZNAT ===
// Test vnoreni predpoklada VODOTESNOU sit (uzavreny objem). Katalogove
// GLB to splnuji (kvadry, uhelnik). U site s dirou by parita paprsku
// lhala - proto se parita hlasuje ze TRI ruznych smeru a pri neshode se
// vrchol povazuje za VNE (konzervativne: radeji nenahlasit hloubku, nez
// vyrobit nalez z artefaktu).
// `parseGlbMesh` cte VSECHNY meshe a VSECHNA primitiva (od 2026-10-02) a
// `zkontrolujPokrytiParseru()` hlida jen to, co parser NEUMI (transformace uzlu) - pak SELZE,
// aby se cast geometrie nemerila tise. (Driv: "jen meshes[0].primitives[0]" a pojistka
// odmitala kazdy vicemeshovy soubor - viz zkontrolujPokrytiParseru nize.)
const fs = require("fs");
const THREE = require("three");

const TOL_MM = 0.05;

// --- pomocne vektorove operace nad plochymi poli (rychlejsi nez THREE.Vector3
// v horke smycce, ktera bezi radove 10^8x) ---
const sub = (o, ax, bx) => [o[ax] - o[bx], o[ax + 1] - o[bx + 1], o[ax + 2] - o[bx + 2]];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

// Promitne 3 body na osu a vrati [min,max].
function rozsah(ax, t, i0) {
  const d0 = ax[0] * t[i0] + ax[1] * t[i0 + 1] + ax[2] * t[i0 + 2];
  const d1 = ax[0] * t[i0 + 3] + ax[1] * t[i0 + 4] + ax[2] * t[i0 + 5];
  const d2 = ax[0] * t[i0 + 6] + ax[1] * t[i0 + 7] + ax[2] * t[i0 + 8];
  return [Math.min(d0, d1, d2), Math.max(d0, d1, d2)];
}

// SAT pro dva trojuhelniky: 2 normaly + 9 krizovych soucinu hran.
// Vraci nejmensi prekryv pres vsechny osy (<= 0 => oddelene).
// Osa kratsi nez EPS_OSA je degenerovana (rovnobezne hrany) a preskakuje se
// - jinak by normalizace delila nulou a vyrobila falesny "prekryv".
const EPS_OSA = 1e-9;
function satTriTri(A, ia, B, ib) {
  const ea = [sub(A, ia + 3, ia), sub(A, ia + 6, ia + 3), sub(A, ia, ia + 6)];
  const eb = [sub(B, ib + 3, ib), sub(B, ib + 6, ib + 3), sub(B, ib, ib + 6)];
  const osy = [cross(ea[0], ea[1]), cross(eb[0], eb[1])];
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) osy.push(cross(ea[i], eb[j]));
  let nej = Infinity;
  for (const ax of osy) {
    const len = Math.sqrt(dot(ax, ax));
    if (len < EPS_OSA) continue;                      // degenerovana osa
    const n = [ax[0] / len, ax[1] / len, ax[2] / len];
    const [aMin, aMax] = rozsah(n, A, ia);
    const [bMin, bMax] = rozsah(n, B, ib);
    const ov = Math.min(aMax, bMax) - Math.max(aMin, bMin);
    if (ov <= 0) return 0;                            // nalezena delici osa
    if (ov < nej) nej = ov;
  }
  return nej === Infinity ? 0 : nej;
}

// Moller-Trumbore: protne paprsek (orig, dir) trojuhelnik? Vraci t nebo -1.
// `dir` nemusi byt jednotkovy; pro paritu staci znamenko t > 0.
function paprsekTri(orig, dir, T, i) {
  const e1 = [T[i + 3] - T[i], T[i + 4] - T[i + 1], T[i + 5] - T[i + 2]];
  const e2 = [T[i + 6] - T[i], T[i + 7] - T[i + 1], T[i + 8] - T[i + 2]];
  const p = cross(dir, e2);
  const det = dot(e1, p);
  if (Math.abs(det) < 1e-12) return -1;               // paprsek v rovine steny
  const inv = 1 / det;
  const tv = [orig[0] - T[i], orig[1] - T[i + 1], orig[2] - T[i + 2]];
  const u = dot(tv, p) * inv;
  if (u < 0 || u > 1) return -1;
  const q = cross(tv, e1);
  const v = dot(dir, q) * inv;
  if (v < 0 || u + v > 1) return -1;
  const t = dot(e2, q) * inv;
  return t > 1e-9 ? t : -1;
}

// === TEST "LEZI BOD UVNITR HMOTY DILU" ===
// Delalo by se to paritou paprsku: vyslat z bodu polopřimku a spocitat
// pruseciky se sti - lichy pocet = uvnitr. Ma to DVE pasti, na obe se v
// tomhle projektu narazilo:
//
// (1) SITE NEJSOU VODOTESNE. `Object_7` (profil 30x30 uzavreny, 50
//     trojuhelniku) je trubka OTEVRENA NA KONCICH - vytlaceny prurez bez
//     cel. Paprsek vyslany z hmoty steny PO OSE trubky proto vyleti ven
//     BEZ jedineho pruseciku a parita rekne "vne", i kdyz je bod uprostred
//     materialu. Presne tohle 2026-09-11 zmenilo verdikt u kalibracni
//     dvojice z "koliduje 5.89mm" na "cisto" - chytil to az regresni test
//     proti Robertove odpovedi.
//     -> Vodotesnost se MERI (kazda hrana presne dvema trojuhelniky) a u
//        otevrene site se hlasuje z peti smeru misto tri.
// (2) OSOVE ZAROVNANA SCENA. Paprsek poslany po svetove ose trefuje v teto
//     scene hrany a rohy site az podezrele casto (vsechno je zarovnane),
//     a hrana se zapocita dvakrat. -> smery jsou zamerne SIKME.
//
// Rychlost resi predfiltr: paprsek se proti kazdemu trojuhelniku nejdriv
// odbavi zkouskou jeho obalky (slab test). Vysledek je totozny jako bez
// predfiltru - jen se vynechaji trojuhelniky, ktere paprsek nemuze trefit.
// U konvexni site (kvadr, deska) se paprsky nepotrebuji vubec: bod je
// uvnitr, kdyz lezi pod vsemi rovinami sten.
const SMERY = [[0.5773, 0.5774, 0.5775], [-0.7071, 0.3162, 0.6325], [0.2673, -0.8018, 0.5345],
               [-0.3015, -0.9045, 0.3015], [0.8018, 0.2673, -0.5345]];

// Obalky trojuhelniku + vodotesnost. Pocita se jednou na dil.
function analyzujSit(D) {
  const T = D.T, n = T.length / 9;
  const lo = new Float64Array(n * 3), hi = new Float64Array(n * 3);
  const hrany = new Map();
  const kl = (x, y, z) => `${x.toFixed(3)},${y.toFixed(3)},${z.toFixed(3)}`;
  for (let t = 0; t < n; t++) {
    const i = t * 9;
    for (let a = 0; a < 3; a++) {
      let mn = Infinity, mx = -Infinity;
      for (let k = 0; k < 9; k += 3) { const v = T[i + k + a]; if (v < mn) mn = v; if (v > mx) mx = v; }
      lo[t * 3 + a] = mn; hi[t * 3 + a] = mx;
    }
    const v = [kl(T[i], T[i + 1], T[i + 2]), kl(T[i + 3], T[i + 4], T[i + 5]), kl(T[i + 6], T[i + 7], T[i + 8])];
    for (let e = 0; e < 3; e++) {
      const k = [v[e], v[(e + 1) % 3]].sort().join("|");
      hrany.set(k, (hrany.get(k) || 0) + 1);
    }
  }
  let vodotesna = true;
  for (const c of hrany.values()) if (c !== 2) { vodotesna = false; break; }
  D._triLo = lo; D._triHi = hi; D._vodotesna = vodotesna;
  return D;
}

// Protne polopřimka (orig, dir) obalku trojuhelniku t? (slab test)
function paprsekObalku(orig, inv, lo, hi, t) {
  let t0 = 0, t1 = Infinity;
  for (let a = 0; a < 3; a++) {
    const i = t * 3 + a;
    let a0 = (lo[i] - orig[a]) * inv[a], a1 = (hi[i] - orig[a]) * inv[a];
    if (a0 > a1) { const p = a0; a0 = a1; a1 = p; }
    if (a0 > t0) t0 = a0;
    if (a1 < t1) t1 = a1;
    if (t0 > t1) return false;
  }
  return true;
}

function jeUvnitr(bod, T, D) {
  if (!D) { D = { T }; }
  if (!D._triLo) analyzujSit(D);
  // Otevrena sit: nektere smery lzou (viz hlavicka), tak se hlasuje z vice.
  const kolik = D._vodotesna ? 3 : SMERY.length;
  let pro = 0, celkem = 0;
  for (let s = 0; s < kolik; s++) {
    const d = SMERY[s];
    const inv = [1 / d[0], 1 / d[1], 1 / d[2]];
    let n = 0;
    for (let t = 0; t < T.length / 9; t++) {
      if (!paprsekObalku(bod, inv, D._triLo, D._triHi, t)) continue;
      if (paprsekTri(bod, d, T, t * 9) > 0) n++;
    }
    if (n % 2 === 1) pro++;
    celkem++;
  }
  return pro * 2 > celkem;
}
const jeUvnitrPomalu = (bod, T) => {
  let pro = 0;
  for (const d of SMERY) {
    let n = 0;
    for (let i = 0; i < T.length; i += 9) if (paprsekTri(bod, d, T, i) > 0) n++;
    if (n % 2 === 1) pro++;
  }
  return pro * 2 > SMERY.length;
};

// Nejkratsi vzdalenost bodu od trojuhelniku (Ericson, Real-Time Collision
// Detection, 5.1.5) - pouziva se jako "jak hluboko pod povrchem".
function vzdalBodTri(p, T, i) {
  const a = [T[i], T[i + 1], T[i + 2]], b = [T[i + 3], T[i + 4], T[i + 5]], c = [T[i + 6], T[i + 7], T[i + 8]];
  const ab = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
  const ac = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
  const ap = [p[0] - a[0], p[1] - a[1], p[2] - a[2]];
  const d1 = dot(ab, ap), d2 = dot(ac, ap);
  let q;
  if (d1 <= 0 && d2 <= 0) q = a;
  else {
    const bp = [p[0] - b[0], p[1] - b[1], p[2] - b[2]];
    const d3 = dot(ab, bp), d4 = dot(ac, bp);
    if (d3 >= 0 && d4 <= d3) q = b;
    else {
      const vc = d1 * d4 - d3 * d2;
      if (vc <= 0 && d1 >= 0 && d3 <= 0) { const v = d1 / (d1 - d3); q = [a[0] + v * ab[0], a[1] + v * ab[1], a[2] + v * ab[2]]; }
      else {
        const cp = [p[0] - c[0], p[1] - c[1], p[2] - c[2]];
        const d5 = dot(ab, cp), d6 = dot(ac, cp);
        if (d6 >= 0 && d5 <= d6) q = c;
        else {
          const vb = d5 * d2 - d1 * d6;
          if (vb <= 0 && d2 >= 0 && d6 <= 0) { const w = d2 / (d2 - d6); q = [a[0] + w * ac[0], a[1] + w * ac[1], a[2] + w * ac[2]]; }
          else {
            const va = d3 * d6 - d5 * d4;
            if (va <= 0 && (d4 - d3) >= 0 && (d5 - d6) >= 0) {
              const w = (d4 - d3) / ((d4 - d3) + (d5 - d6));
              q = [b[0] + w * (c[0] - b[0]), b[1] + w * (c[1] - b[1]), b[2] + w * (c[2] - b[2])];
            } else {
              const den = 1 / (va + vb + vc), v = vb * den, w = vc * den;
              q = [a[0] + ab[0] * v + ac[0] * w, a[1] + ab[1] * v + ac[1] * w, a[2] + ab[2] * v + ac[2] * w];
            }
          }
        }
      }
    }
  }
  const dx = p[0] - q[0], dy = p[1] - q[1], dz = p[2] - q[2];
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

// Pojistka: "0 kolizi" musi znamenat ZMERENO. `parseGlbMesh` cte VSECHNY meshe a VSECHNA primitiva
// (od 2026-10-02; driv jen meshes[0].primitives[0] a tahle pojistka kvuli tomu odmitala kazdy
// vicemeshovy soubor - product_3219 (3 meshe, 33 sestav) pak shodil cely sweep, kolizni priznaky se
// 146x za sebou nepocitaly). Odmita se jen to, co parser NEUMI a tise by zmeril spatne: transformace
// uzlu (glbRizikaParseru), mod primitiva != TRIANGLES, sparse accessor (to vyhodi uz sam parser).
function zkontrolujPokrytiParseru(glbPath) {
  const rizika = require("./2026-08-19_glb_real_geometry.js").glbRizikaParseru(glbPath);
  if (rizika.length) {
    throw new Error(`${glbPath}: parseGlbMesh by nezmeril celou geometrii - ${rizika.join("; ")}. `
      + "Rozsir parser (aplikuj transformace uzlu), nez tohle zmeris.");
  }
}
const zkontrolujJedinyPrimitiv = zkontrolujPokrytiParseru;   // stary nazev (zpetna kompatibilita)

// Lokalni trojuhelniky GLB (pole delky 9*N). Cachuje se podle cesty.
const cacheLok = {};
function lokalniTrojuhelniky(glbPath, parseGlbMesh) {
  if (glbPath in cacheLok) return cacheLok[glbPath];
  zkontrolujPokrytiParseru(glbPath);
  const g = parseGlbMesh(glbPath).geometry;
  const pos = g.attributes.position.array;
  const idx = g.index ? g.index.array : null;
  const n = idx ? idx.length : pos.length / 3;
  const out = new Float64Array(n * 3);
  for (let k = 0; k < n; k++) {
    const v = (idx ? idx[k] : k) * 3;
    out[k * 3] = pos[v]; out[k * 3 + 1] = pos[v + 1]; out[k * 3 + 2] = pos[v + 2];
  }
  cacheLok[glbPath] = out;
  return out;
}

// Dil ve svetovych souradnicich: trojuhelniky + jejich AABB + unikatni vrcholy.
function dilVeSvete(glbPath, part, parseGlbMesh) {
  const lok = lokalniTrojuhelniky(glbPath, parseGlbMesh);
  const m = new THREE.Matrix4();
  const q = part.quaternion || [0, 0, 0, 1], s = part.scale || [1, 1, 1];
  m.compose(new THREE.Vector3(...part.position),
    new THREE.Quaternion(q[0], q[1], q[2], q[3]),
    new THREE.Vector3(s[0], s[1], s[2]));
  const e = m.elements;
  const T = new Float64Array(lok.length);
  let minx = Infinity, miny = Infinity, minz = Infinity, maxx = -Infinity, maxy = -Infinity, maxz = -Infinity;
  for (let i = 0; i < lok.length; i += 3) {
    const x = lok[i], y = lok[i + 1], z = lok[i + 2];
    const X = e[0] * x + e[4] * y + e[8] * z + e[12];
    const Y = e[1] * x + e[5] * y + e[9] * z + e[13];
    const Z = e[2] * x + e[6] * y + e[10] * z + e[14];
    T[i] = X; T[i + 1] = Y; T[i + 2] = Z;
    if (X < minx) minx = X; if (X > maxx) maxx = X;
    if (Y < miny) miny = Y; if (Y > maxy) maxy = Y;
    if (Z < minz) minz = Z; if (Z > maxz) maxz = Z;
  }
  // `vrch` (unikatni vrcholy) se pocita az kdyz je potreba - dedup pres
  // toFixed je u dilu s tisici trojuhelniky drahy a vetsina dilu se do
  // narrow phase nikdy nedostane.
  const D = { T, box: { min: [minx, miny, minz], max: [maxx, maxy, maxz] } };
  Object.defineProperty(D, "vrch", {
    configurable: true,
    get() {
      const v = [], videno = new Set();
      for (let i = 0; i < T.length; i += 3) {
        const k = `${T[i].toFixed(3)},${T[i + 1].toFixed(3)},${T[i + 2].toFixed(3)}`;
        if (!videno.has(k)) { videno.add(k); v.push([T[i], T[i + 1], T[i + 2]]); }
      }
      Object.defineProperty(this, "vrch", { value: v, configurable: true });
      return v;
    },
  });
  return D;
}

// Posune uz pripraveny dil o vektor. Pouziva se pri hledani, jestli by
// kolizi odstranil posun: prestavba dilu pres `dilVeSvete` by pro kazdou
// zkousenou pozici znovu transformovala geometrii, dedupovala vrcholy a
// analyzovala sit - u stovek zkousenych pozic je to drtiva vetsina casu,
// pritom posun je jen pricteni vektoru ke vsemu, co uz je spocitane.
function posunDil(D, delta) {
  const T = new Float64Array(D.T.length);
  for (let i = 0; i < T.length; i += 3) {
    T[i] = D.T[i] + delta[0]; T[i + 1] = D.T[i + 1] + delta[1]; T[i + 2] = D.T[i + 2] + delta[2];
  }
  const N = { T, box: { min: D.box.min.map((v, a) => v + delta[a]), max: D.box.max.map((v, a) => v + delta[a]) } };
  Object.defineProperty(N, "vrch", {
    configurable: true,
    get() { const v = D.vrch.map(p => [p[0] + delta[0], p[1] + delta[1], p[2] + delta[2]]);
            Object.defineProperty(this, "vrch", { value: v, configurable: true }); return v; },
  });
  if (D._triLo) {
    const n = D._triLo.length;
    N._triLo = new Float64Array(n); N._triHi = new Float64Array(n);
    for (let i = 0; i < n; i += 3) for (let a = 0; a < 3; a++) {
      N._triLo[i + a] = D._triLo[i + a] + delta[a]; N._triHi[i + a] = D._triHi[i + a] + delta[a];
    }
    N._vodotesna = D._vodotesna;
  }
  if (D._konvex !== undefined) {
    N._konvex = D._konvex;
    N._roviny = D._roviny.map(r => ({ n: r.n, d: r.d + r.n[0] * delta[0] + r.n[1] * delta[1] + r.n[2] * delta[2] }));
  }
  return N;
}

// Prekryv dvou AABB po osach (zaporne = mezera). Broad phase, NE verdikt.
function prekryvBoxu(a, b) {
  return [Math.min(a.max[0], b.max[0]) - Math.max(a.min[0], b.min[0]),
          Math.min(a.max[1], b.max[1]) - Math.max(a.min[1], b.min[1]),
          Math.min(a.max[2], b.max[2]) - Math.max(a.min[2], b.min[2])];
}

// --- test "lezi bod uvnitr site" ---
// Rychla cesta pro KONVEXNI sit (kvadr, deska - v katalogu vetsina dilu):
// bod je uvnitr, kdyz lezi pod vsemi rovinami sten. Presne a bez paprsku.
// U nekonvexni site (uhelnik je L) se pouzije parita paprsku.
function pripravVnitrek(D) {
  const T = D.T;
  const roviny = [];
  for (let i = 0; i < T.length; i += 9) {
    const u = [T[i + 3] - T[i], T[i + 4] - T[i + 1], T[i + 5] - T[i + 2]];
    const v = [T[i + 6] - T[i], T[i + 7] - T[i + 1], T[i + 8] - T[i + 2]];
    const n = cross(u, v);
    const len = Math.sqrt(dot(n, n));
    if (len < 1e-9) continue;                       // degenerovany trojuhelnik
    const nn = [n[0] / len, n[1] / len, n[2] / len];
    const d = nn[0] * T[i] + nn[1] * T[i + 1] + nn[2] * T[i + 2];
    if (!roviny.some(r => Math.abs(r.n[0] - nn[0]) < 1e-6 && Math.abs(r.n[1] - nn[1]) < 1e-6
                       && Math.abs(r.n[2] - nn[2]) < 1e-6 && Math.abs(r.d - d) < 1e-4)) {
      roviny.push({ n: nn, d });
    }
  }
  // konvexni <=> zadny vrchol neni nad zadnou rovinou steny
  let konvex = roviny.length > 0 && roviny.length <= 64;
  if (konvex) {
    for (const r of roviny) {
      for (const v of D.vrch) {
        if (v[0] * r.n[0] + v[1] * r.n[1] + v[2] * r.n[2] > r.d + 1e-3) { konvex = false; break; }
      }
      if (!konvex) break;
    }
  }
  D._konvex = konvex;
  D._roviny = roviny;
  return D;
}
function uvnitr(D, p, tol) {
  if (D._konvex === undefined) pripravVnitrek(D);
  if (D._konvex) {
    for (const r of D._roviny) {
      if (p[0] * r.n[0] + p[1] * r.n[1] + p[2] * r.n[2] > r.d - tol) return false;
    }
    return true;
  }
  return jeUvnitr(p, D.T, D);
}

// Navzorkuje prekryvovou oblast a vrati body, ktere lezi uvnitr OBOU siti.
// Mrizka je posunuta o pul kroku dovnitr, aby body nepadaly presne do rovin
// sten (tam je parita paprsku i test polorovinou nespolehlivy). Prave proto
// se sem vnitrni tolerance NEPREDAVA (`uvnitr(..., 0)`): kdyby se pri
// vzorkovani oreza(va)l povrchovy plast tloustky tol, namerena tloustka by
// byla soustavne o 2*tol mensi nez skutecna. Verdikt uz je zajisten jinde -
// broad phase pousti dal jen prekryv obalu > tol.
function bodyVObou(A, B, O, n, tol, prvniStaci) {
  const krok = [(O.max[0] - O.min[0]) / n[0], (O.max[1] - O.min[1]) / n[1], (O.max[2] - O.min[2]) / n[2]];
  const body = [], idx = [];
  for (let i = 0; i < n[0]; i++) {
    const x = O.min[0] + (i + 0.5) * krok[0];
    for (let j = 0; j < n[1]; j++) {
      const y = O.min[1] + (j + 0.5) * krok[1];
      for (let k = 0; k < n[2]; k++) {
        const p = [x, y, O.min[2] + (k + 0.5) * krok[2]];
        if (uvnitr(A, p, 0) && uvnitr(B, p, 0)) { body.push(p); idx.push([i, j, k]); if (prvniStaci) return { body, idx, krok }; }
      }
    }
  }
  return { body, idx, krok };
}

// Rozdeli navzorkovane body na SOUVISLE oblasti (sousedstvi po 6 smerech
// v mrizce). Bez toho by obalka bodu spojila dva oddelene pruniky do jedne
// a tloustka by vysla jako jejich rozestup - napr. lista sirsi nez drazka
// se zaboruje o 3mm po KAZDE strane, ale obalka vsech bodu je siroka 26mm.
function souvisleOblasti(idx) {
  const kl = (a) => `${a[0]},${a[1]},${a[2]}`;
  const zbyva = new Map(idx.map((a, i) => [kl(a), i]));
  const oblasti = [];
  for (const [k0, i0] of zbyva) {
    if (!zbyva.has(k0)) continue;
    const fronta = [idx[i0]], skupina = [];
    zbyva.delete(k0);
    while (fronta.length) {
      const a = fronta.pop(); skupina.push(a);
      for (const d of [[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]]) {
        const s2 = [a[0]+d[0], a[1]+d[1], a[2]+d[2]], k2 = kl(s2);
        if (zbyva.has(k2)) { zbyva.delete(k2); fronta.push(s2); }
      }
    }
    oblasti.push(skupina);
  }
  return oblasti;
}

// Protina se aspon jedna dvojice sten HLOUBEJI nez tol? (doplnek vzorkovani
// pro prekryv tenci nez krok mrizky)
function protinajiSeSteny(A, B, O, tol) {
  const vOblasti = (T) => {
    const idx = [];
    for (let i = 0; i < T.length; i += 9) {
      let lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
      for (let k = 0; k < 9; k += 3) for (let a = 0; a < 3; a++) {
        const v = T[i + k + a]; if (v < lo[a]) lo[a] = v; if (v > hi[a]) hi[a] = v;
      }
      if (hi[0] >= O.min[0] - tol && lo[0] <= O.max[0] + tol &&
          hi[1] >= O.min[1] - tol && lo[1] <= O.max[1] + tol &&
          hi[2] >= O.min[2] - tol && lo[2] <= O.max[2] + tol) idx.push(i);
    }
    return idx;
  };
  const ia = vOblasti(A.T), ib = vOblasti(B.T);
  let nej = 0;
  for (const i of ia) for (const j of ib) {
    const p = satTriTri(A.T, i, B.T, j);
    if (p > tol && p > nej) nej = p;
  }
  return nej;
}

const DELENI_HRUBE = [16, 16, 16];
const DELENI_JEMNE = 64;        // na NEJTENCI ose, na zbylych DELENI_HRUBE

// HLAVNI TEST. Vraci {koliduje, odsun, oblast, typ, prunikBox, prunikPlochy}.
//   typ "objem"  = navzorkovana spolecna hmota (`odsun` + `oblast`)
//   typ "plocha" = steny se protinaji, ale prekryv je tencí nez krok mrizky
//   typ null     = nekoliduje (dosed, mezera, nebo jen prekryv obalu)
function kolize(A, B, tol, rychly) {
  tol = tol == null ? TOL_MM : tol;
  const ov = prekryvBoxu(A.box, B.box);
  const prunikBox = Math.min(ov[0], ov[1], ov[2]);
  // Prekryv obalu je HORNI MEZ skutecneho pruniku (posun o nej obaly oddeli,
  // takze oddeli i dily). Pod tol uz nema co merit.
  if (prunikBox <= tol) {
    return { koliduje: false, odsun: 0, oblast: [0, 0, 0], typ: null, prunikBox: zaokr(prunikBox), prunikPlochy: 0 };
  }
  const O = {
    min: [Math.max(A.box.min[0], B.box.min[0]), Math.max(A.box.min[1], B.box.min[1]), Math.max(A.box.min[2], B.box.min[2])],
    max: [Math.min(A.box.max[0], B.box.max[0]), Math.min(A.box.max[1], B.box.max[1]), Math.min(A.box.max[2], B.box.max[2])],
  };
  const hrube = bodyVObou(A, B, O, DELENI_HRUBE, tol, rychly);
  // `rychly` = staci verdikt (hleda se posun, ne mereni) -> jakmile je
  // spolecny bod, neni co dal zjistovat; protinani sten se pak resi jen kdyz
  // zadny spolecny bod nebyl.
  if (rychly && hrube.body.length) {
    return { koliduje: true, odsun: 0, oblast: [0, 0, 0], typ: "objem", prunikBox: zaokr(prunikBox), prunikPlochy: 0 };
  }
  const plochy = protinajiSeSteny(A, B, O, tol);
  if (!hrube.body.length) {
    // Zadna spolecna hmota na hrube mrizce. Kdyz se pritom steny protinaji,
    // je prekryv tencí nez krok - porad kolize, jen mele.
    if (plochy > tol) {
      const krokMin = Math.min(...hrube.krok);
      return { koliduje: true, odsun: zaokr(krokMin), oblast: [0, 0, 0], typ: "plocha",
               prunikBox: zaokr(prunikBox), prunikPlochy: zaokr(plochy), mensiNez: zaokr(krokMin) };
    }
    return { koliduje: false, odsun: 0, oblast: [0, 0, 0], typ: null, prunikBox: zaokr(prunikBox), prunikPlochy: 0 };
  }
  // Jemne premereni tloustky: nejvic deleni na osu, kde je oblast nejtencí.
  // Rozmery spolecne hmoty (popis toho, JAK se prekryvaji). Meri se po
  // SOUVISLYCH oblastech zvlast a bere se ta nejvetsi - obalka pres vsechny
  // body by u dvou oddelenych pruniku vratila jejich rozestup, ne rozmer.
  const nejvetsi = (v) => {
    let nej = null;
    for (const sk of souvisleOblasti(v.idx)) {
      const mi = [Infinity, Infinity, Infinity], ma = [-Infinity, -Infinity, -Infinity];
      for (const a of sk) for (let o = 0; o < 3; o++) { if (a[o] < mi[o]) mi[o] = a[o]; if (a[o] > ma[o]) ma[o] = a[o]; }
      const t = [0, 1, 2].map(o => (ma[o] - mi[o] + 1) * v.krok[o]);
      if (!nej || sk.length > nej.bodu) nej = { rozmery: t, bodu: sk.length };
    }
    return nej;
  };
  const jemne = bodyVObou(A, B, O, [32, 32, 32], tol);
  const obl = nejvetsi(jemne.body.length ? jemne : hrube);
  return {
    koliduje: true,
    odsun: zaokr(odsunOd(A, B, tol)),
    oblast: obl ? obl.rozmery.map(zaokr) : [0, 0, 0],
    typ: "objem",
    prunikBox: zaokr(prunikBox),
    prunikPlochy: zaokr(plochy),
  };
}

// Nejmensi posun po svetove ose, po kterem se site prestanou prekryvat.
// Pro smer +a je posunem, ktery s jistotou oddeli OBALKY, `B.max[a]-A.min[a]`
// (pro -a analogicky `A.max[a]-B.min[a]`) - oddelene obalky znamenaji
// oddelene site, takze je to platna horni mez a puleni intervalu na ni muze
// stavet. POZOR na rozdil: `prekryvBoxu` vraci DELKU PRUNIKU obalek, ne tuhle
// vzdalenost; u dilu, kde jeden obal lezi cely uvnitr druheho, se lisi
// radove (kvadr 20mm uprostred kvadru 100mm ma prunik 20mm, ale dostat ho
// ven chce 60mm).
//
// Predpoklad: jakmile se dily pri posouvani rozejdou, uz se pri vetsim posunu
// znovu nepotkaji. U dilu teto sestavy (profily, desky, uhelnik) to plati;
// u tvaru s vice rameny by to platit nemuselo.
function odsunOd(A, B, tol) {
  let nej = Infinity;
  for (let a = 0; a < 3; a++) {
    for (const zn of [1, -1]) {
      const horni = zn > 0 ? B.box.max[a] - A.box.min[a] : A.box.max[a] - B.box.min[a];
      if (!(horni > 0) || horni >= nej) continue;
      let lo = 0, hi = horni;
      for (let k = 0; k < 14 && hi - lo > 0.05; k++) {
        const mid = (lo + hi) / 2;
        const d = [0, 0, 0]; d[a] = zn * mid;
        if (kolize(posunDil(A, d), B, tol, true).koliduje) lo = mid; else hi = mid;
      }
      if (hi < nej) nej = hi;
    }
  }
  return nej === Infinity ? 0 : nej;
}

const zaokr = (v) => Math.round(v * 100) / 100;

module.exports = { TOL_MM, dilVeSvete, kolize, jeUvnitrPomalu, analyzujSit, prekryvBoxu, satTriTri, jeUvnitr, vzdalBodTri,
                   zkontrolujJedinyPrimitiv, zkontrolujPokrytiParseru, uvnitr, posunDil, odsunOd, pripravVnitrek, bodyVObou, protinajiSeSteny, souvisleOblasti };
