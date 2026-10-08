// Sdilena knihovna pro hromadne prepocitani kolizni rezervy (shape_geometry_
// methods.id=11) napric ruznymi vozidly/topologiemi (Proace 8 submodelu,
// K-159/K-239/K-248e/K-255/K-288/K-295). Zobecneni jednorazoveho skriptu
// scripts/tmp_2026-09-12_bot8_predelat_k075_c_10_30.js (K-075, Robertem
// oveřeno = product_assemblies.id=340) - viz AGENTS_LOG.md zapis k tomuto
// skriptu pro presne odvozeni formuli nize (zejmena "dorovnani" krok 5/6,
// ktery referencni skript NEIMPLEMENTOVAL primo - odvozeno zpetne diffem
// 134(stare 2/20mm)/340(nove 10/30mm), viz AGENTS_LOG zapis "bot8 2026-09-12
// wide batch").
//
// KLICOVA EMPIRICKA ZJISTENI (nezavisla na konkretnim voze, overena na
// 14 ruznych modelech + primo na 134/340 diffu):
//   1. "predni-svislice" = predni (ke kabine celeni) svislice KAZDEHO
//      sloupce (plna i vyrezova varianta ji ma) - noha je "vyrezova" jen
//      kdyz ma NAVIC zadni-svislice-nad-zarezem(+sloupek-pred-podbehem)
//      (+pricka-uzavreni-vyrezu) - zadni (ke stene) svislice presekana
//      podbehem kola. "Plna" noha ma misto toho proste "zadni-svislice"
//      nebo "zadni-svislice-dolni" (cely profil, bez preruseni).
//   2. Noha nejblize car_body "_B" (prepazka) GLB je VZDY plna (ve vsech
//      14 zmerenych modelech) a VZDY je to noha s NEJMENSIM (nejzapornejsim)
//      Z po serazeni - ta jedina dostava deltaZ.
//   3. pricka-uzavreni-vyrezu.position.y = Y_new + 15 (T/2, T=30mm univerzalni
//      konstanta tloustky profilu) - PLATI STEJNE pro stary i novy Y_new,
//      tedy pricka se proste posouva o presne deltaY (zadna zmena scale).
//   4. Krok 5/6 (dorovnani): nejnizsi patro ("patro0"/"p0") daneho sloupce
//      (nosnik-*) je pri navrhu POSTAVENO PRESNE na urovni "Y_new+15"
//      (= urovni horni hrany pricka sousedni vyrezove nohy) - overeno
//      primo: 134 (stare, oldYnew leg1=101.5) ma nosnik-col0-p0.y=116.5
//      (=101.5+15 presne), 340 (nove, newYnew=111.5) ma nosnik-col0-p0.y=
//      126.5 (=111.5+15 presne, tedy posun o +10=presne deltaY). Obecne:
//      deficit = max(0, (newYnew+15) - stara_hodnota_patro0.y); pokud >0,
//      rozloz LINEARNE do N-1 mezer (top fixni): shift(patro_i) = deficit *
//      (N-1-i)/(N-1), i=0 dole. Aplikuj na VSECHNY role dane (sloupec,patro)
//      dvojice (nosnik-*, eurobox-*, spojnice-*-patroI/-pI).
//
// Pouziti: viz na konci souboru export.

const fs = require("fs");
const path = require("path");

const T = 30; // profil tloustka (mm) - univerzalni konstanta projektu
const EPS_Z = 2; // mm tolerance pro Z-clustering sloupcu (legs)
const EPS_UHELNIK_Z = 60; // mm tolerance pro prirazeni uhelnik-nohaN k nejblizsimu sloupci (mezery mezi sloupci jsou vzdy stovky mm)
const EPS_SEAM_Y = 3; // mm tolerance pro "je tenhle uhelnik na svu?"

const COLUMN_OWNED_ROLES = new Set([
  "predni-svislice", "zadni-svislice", "zadni-svislice-dolni",
  "zadni-svislice-nad-zarezem", "sloupek-pred-podbehem",
  "pricka-uzavreni-vyrezu", "cap", "spojnice-dolni", "spojnice-horni",
]);

function isZaslepkaRole(role) {
  return typeof role === "string" && role.startsWith("zaslepka");
}

// Detekuje pojmenovani sloupcu/pater v danem sete dilu ("sloupecN-patroM" vs "colN-pM").
function detectNaming(parts) {
  for (const p of parts) {
    const m = /^(nosnik|eurobox|spojnice)-(sloupec|col)(\d+)-(patro|p)(\d+)$/.exec(p.role || "");
    if (m) return { colPrefix: m[2], patroSep: m[4] };
  }
  return null; // zadne vicepatrove sloupce (nemelo by nastat, ale osetreno)
}

function near(a, b, eps) { return Math.abs(a - b) < (eps == null ? 0.5 : eps); }

// Vrati serazene pole {z, type:'plain'|'cutout', idx} podle Z (idx0 = nejblize prepazce, tedy nejmensi Z).
function detectLegs(parts) {
  const clusters = []; // {z (avg), roles:{role:count}, zs:[]}
  for (const p of parts) {
    if (!COLUMN_OWNED_ROLES.has(p.role)) continue;
    const z = p.position[2];
    let c = clusters.find(c => Math.abs(c.z - z) < EPS_Z);
    if (!c) { c = { z, roles: {}, zs: [] }; clusters.push(c); }
    c.roles[p.role] = (c.roles[p.role] || 0) + 1;
    c.zs.push(z);
    c.z = c.zs.reduce((a, b) => a + b, 0) / c.zs.length;
  }
  clusters.sort((a, b) => a.z - b.z);
  return clusters.map((c, idx) => ({
    z: c.z, idx,
    type: c.roles["zadni-svislice-nad-zarezem"] ? "cutout" : "plain",
    roles: c.roles,
  }));
}

// Zmeri stary Y_new (svisla vyska svu sloupek/svislice-nad-zarezem) pro danou vyrezovou nohu.
function measureOldYnew(parts, legZ) {
  const zsn = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], legZ, EPS_Z));
  if (!zsn) return null;
  const oldYnewFromZsn = zsn.position[1] - zsn.scale[1] * 1000 / 2;
  const sloupek = parts.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], legZ, EPS_Z));
  if (sloupek) {
    const oldYnewFromSloupek = sloupek.position[1] + sloupek.scale[1] * 1000 / 2;
    if (Math.abs(oldYnewFromZsn - oldYnewFromSloupek) > 1) {
      throw new Error(`oldYnew nesedi mezi zadni-svislice-nad-zarezem (${oldYnewFromZsn}) a sloupek-pred-podbehem (${oldYnewFromSloupek}) na Z=${legZ}`);
    }
  }
  return oldYnewFromZsn;
}

// Najde nejblizsi noha (z pole legs) pro dany Z (pro uhelnik-nohaN prirazeni).
function nearestLeg(legs, z) {
  let best = null, bestD = Infinity;
  for (const leg of legs) {
    const d = Math.abs(leg.z - z);
    if (d < bestD) { bestD = d; best = leg; }
  }
  return bestD <= EPS_UHELNIK_Z ? best : null;
}

// Hlavni transformace. parts = pole dilu (BEZ car_body_*, ty se nemeni a
// nemaji se predavat vubec, nebo se proste ignoruji podle part_id prefixu).
// Vraci { parts: novaPole, report: {...} }.
function transformAssembly(allParts, { deltaZ = 8, deltaY = 10 } = {}) {
  const carBodyParts = allParts.filter(p => String(p.part_id || "").startsWith("car_body_"));
  const parts = allParts.filter(p => !String(p.part_id || "").startsWith("car_body_")).map(p => JSON.parse(JSON.stringify(p)));

  const naming = detectNaming(parts);
  const legs = detectLegs(parts);
  if (!legs.length) throw new Error("Nenalezeny zadne sloupce (legs) - neocekavana struktura sestavy.");
  const frontLeg = legs[0]; // empiricky vzdy noha nejblize prepazce, vzdy 'plain'

  const oldYnewByLegIdx = {};
  for (const leg of legs) {
    if (leg.type === "cutout") {
      const y = measureOldYnew(parts, leg.z);
      if (y == null) throw new Error(`Vyrezova noha na Z=${leg.z} nema zadni-svislice-nad-zarezem?!`);
      oldYnewByLegIdx[leg.idx] = y;
    }
  }

  const report = { frontLegZ: frontLeg.z, legs: legs.map(l => ({ z: +l.z.toFixed(2), type: l.type, oldYnew: oldYnewByLegIdx[l.idx] })), naming, rebalance: [], counts: {} };
  const bump = (k) => { report.counts[k] = (report.counts[k] || 0) + 1; };

  // --- KROK: deltaZ na predni nohu (frontLeg) a jeji sdileny sloupec (bay 0) ---
  for (const p of parts) {
    const role = p.role || "";
    if (COLUMN_OWNED_ROLES.has(role) && near(p.position[2], frontLeg.z, EPS_Z)) {
      p.position[2] += deltaZ; bump("front-leg-owned:" + role); continue;
    }
    if (isZaslepkaRole(role) && near(p.position[2], frontLeg.z, EPS_Z)) {
      p.position[2] += deltaZ; bump("front-leg-zaslepka:" + role); continue;
    }
  }
  // uhelnik-nohaN pripojene k predni noze (klasifikace dle Z blizkosti, ne cisla v roli)
  for (const p of parts) {
    if (!/^uhelnik-noha\d+$/.test(p.role || "")) continue;
    const leg = nearestLeg(legs, p.position[2]);
    if (!leg) { bump("uhelnik-unmatched:" + p.role); continue; }
    if (leg.idx === frontLeg.idx) { p.position[2] += deltaZ; bump("uhelnik-front-shift:" + p.role); }
    // (Y-shift pro vyrezove nohy se resi v samostatnem loopu nize, aby se
    // predeslo dvojite aplikaci kdyby leg byl soucasne front i cutout.)
  }

  // --- bay0 (mezi frontLeg a legs[1]) - jedina ovlivnena deltaZ ---
  if (naming && legs.length > 1) {
    const { colPrefix, patroSep } = naming;
    const bay0Re = new RegExp(`^(nosnik|eurobox|spojnice)-${colPrefix}0-${patroSep}(\\d+)$`);
    const nextLeg = legs[1];
    for (const p of parts) {
      const m = bay0Re.exec(p.role || "");
      if (!m) continue;
      const family = m[1];
      if (family === "nosnik") {
        p.position[2] += deltaZ / 2;
        p.scale[1] = (p.scale[1] * 1000 - deltaZ) / 1000;
        bump("bay0-nosnik-resize:" + p.role);
      } else if (family === "eurobox") {
        p.position[2] += deltaZ / 2;
        bump("bay0-eurobox-shift:" + p.role);
      } else if (family === "spojnice") {
        const dFront = Math.abs(p.position[2] - frontLeg.z);
        const dNext = Math.abs(p.position[2] - nextLeg.z);
        if (dFront < dNext) { p.position[2] += deltaZ; bump("bay0-spojnice-front:" + p.role); }
        else { bump("bay0-spojnice-fixed:" + p.role); }
      }
    }
  }

  // --- KROK: deltaY na vsechny vyrezove nohy (jejich vlastni dily) ---
  for (const leg of legs) {
    if (leg.type !== "cutout") continue;
    const oldYnew = oldYnewByLegIdx[leg.idx];
    const newYnew = oldYnew + deltaY;
    for (const p of parts) {
      if (!near(p.position[2], leg.z, EPS_Z)) continue;
      const role = p.role || "";
      if (role === "zadni-svislice-nad-zarezem") {
        const topY = p.position[1] + p.scale[1] * 1000 / 2;
        const newHeight = topY - newYnew;
        p.position[1] = newYnew + newHeight / 2;
        p.scale[1] = newHeight / 1000;
        bump("cutout-zsn-resize");
      } else if (role === "sloupek-pred-podbehem") {
        const floorY = p.position[1] - p.scale[1] * 1000 / 2;
        const newHeight = newYnew - floorY;
        p.position[1] = floorY + newHeight / 2;
        p.scale[1] = newHeight / 1000;
        bump("cutout-sloupek-resize");
      } else if (role === "pricka-uzavreni-vyrezu") {
        p.position[1] += deltaY;
        bump("cutout-pricka-shift");
      }
      // predni-svislice/cap/zaslepka-*/zadni-svislice-dolni na cutout noze
      // (nemely by tu byt - cutout noha nema "-dolni" varianty) zustavaji beze zmeny.
    }
    // uhelnik-nohaN na svu teto nohy
    for (const p of parts) {
      if (!/^uhelnik-noha\d+$/.test(p.role || "")) continue;
      const nearestL = nearestLeg(legs, p.position[2]);
      if (!nearestL || nearestL.idx !== leg.idx) continue;
      if (near(p.position[1], oldYnew, EPS_SEAM_Y) || near(p.position[1], oldYnew + 30, EPS_SEAM_Y)) {
        p.position[1] += deltaY;
        bump("uhelnik-seam-shift:" + p.role);
      } else {
        bump("uhelnik-seam-unaffected:" + p.role);
      }
    }
  }

  // --- KROK 5/6: dorovnani pater v kazdem sloupci (bay) sousedicim s vyrezovou nohou ---
  if (naming) {
    const { colPrefix, patroSep } = naming;
    for (let bay = 0; bay < legs.length - 1; bay++) {
      const legA = legs[bay], legB = legs[bay + 1];
      const thresholds = [];
      if (legA.type === "cutout") thresholds.push(oldYnewByLegIdx[legA.idx] + deltaY + T / 2);
      if (legB.type === "cutout") thresholds.push(oldYnewByLegIdx[legB.idx] + deltaY + T / 2);
      if (!thresholds.length) continue;
      const threshold = Math.max(...thresholds);

      // zjisti N (pocet pater) a Y pozici patro0 (pred zmenou v tomhle kroku).
      // POZOR: referencni Y BERE VYHRADNE z "nosnik" (strukturalni nosny
      // profil, konstantni Y napric box-kompozicemi) - "eurobox" ma pivot
      // zavisly na TYPU/VYSCE konkretniho boxu v tom patre (naprosto jiny
      // vertikalni referencni bod, prumerovani s nim by zkreslilo deficit -
      // zjisteno empiricky na 134: eurobox-col0-p0.y=1101.6 vs nosnik.y=116.5
      // pro STEJNE patro0). "spojnice" v datech souhlasi s nosnik (pouzitelna
      // jako fallback, kdyby nosnik chybel).
      const patroRe = new RegExp(`^(nosnik|eurobox|spojnice)-${colPrefix}${bay}-${patroSep}(\\d+)$`);
      let maxPatro = -1;
      const patro0YsNosnik = [], patro0YsSpojnice = [];
      for (const p of parts) {
        const m = patroRe.exec(p.role || "");
        if (!m) continue;
        const pi = Number(m[2]);
        if (pi > maxPatro) maxPatro = pi;
        if (pi === 0 && m[1] === "nosnik") patro0YsNosnik.push(p.position[1]);
        if (pi === 0 && m[1] === "spojnice") patro0YsSpojnice.push(p.position[1]);
      }
      const patro0Ys = patro0YsNosnik.length ? patro0YsNosnik : patro0YsSpojnice;
      if (maxPatro < 0 || !patro0Ys.length) continue; // bay bez viceparoveho obsahu (nemelo by nastat)
      const N = maxPatro + 1;
      const patro0Y = patro0Ys.reduce((a, b) => a + b, 0) / patro0Ys.length;
      const deficit = threshold - patro0Y;
      if (deficit <= 0.01) {
        report.rebalance.push({ bay, N, patro0Y: +patro0Y.toFixed(2), threshold: +threshold.toFixed(2), deficit: +deficit.toFixed(2), applied: false });
        continue;
      }
      for (let i = 0; i < N; i++) {
        const shift = N > 1 ? deficit * (N - 1 - i) / (N - 1) : deficit;
        if (shift <= 0.001) continue;
        const tierRe = new RegExp(`^(nosnik|eurobox|spojnice)-${colPrefix}${bay}-${patroSep}${i}$`);
        for (const p of parts) {
          if (tierRe.test(p.role || "")) { p.position[1] += shift; bump(`rebalance-bay${bay}-patro${i}`); }
        }
      }
      report.rebalance.push({ bay, N, patro0Y: +patro0Y.toFixed(2), threshold: +threshold.toFixed(2), deficit: +deficit.toFixed(2), applied: true, gapShrink: +(deficit / (N - 1)).toFixed(3) });
    }
  }

  return { parts: [...parts, ...carBodyParts], report };
}

module.exports = { transformAssembly, detectLegs, detectNaming, measureOldYnew, T };
