// Kontrolni skript: "regal jen k podbehu" (bot16, 2026-09-03, Robert: "porad je
// spousta regalu jen k podbehu, udelej kontrolni skript ktery ti to odhali").
//
// Pro kazdy is_public=1 radek product_assemblies zmeri proti REALNE GLB
// geometrii karoserie (stejny collidesWithWalls jako stavebni pipeline):
//   - rackRearZ   : skutecny zadni konec regalu (Box3 vsech profilu Object_7)
//   - archStartZ  : zacatek podbehu u steny = prvni usek (krok 10mm od predni nohy
//                   dozadu), kde by stenovy clen nohy musel stat >=100mm nad podlahou,
//                   souvisle >=300mm a s vrcholem >=150mm; kratsi/nizsi hrbolky
//                   (kotevni oka, vylisy) se hlasi zvlast jako "bumps"
//   - okno(z)     : pro kazde z za regalem volny svisly prostor mezi nejnizsim
//                   volnym Y stenoveho clenu/sloupku (podlaha / vrsek podbehu) a
//                   nejvyssim volnym Y pevnych clenu nohy (predni-svislice, cap -
//                   regal za podbehem smi byt i nizsi, hlasi se jako maxTopDrop)
//   - usableLen   : delka souvisleho useku hned za regalem, kde okno >= 200mm
//                   (rail 30 + mezera 30 + box 120 + rezerva)
//   - oficialni ložná délka (karoserie_model_reference.cargo_length_mm podle kodu
//     [XXNN] v nazvu car_models). Robert 2026-09-03: "nektere auta maji podbeh
//     'nekonecny', je potreba se ridit napr. delkou lozne plochy ofic." - proto:
//       * oficialni zadni hranice = PREDNI HRANA L STENY (boxL0) + ložná délka.
//         Overeno na 120 sestavach: modelovana L stena ma delku ~= oficialni ložné
//         délce (-100..+30mm u PSA/Ford/VW/Renault), tj. jeji predni hrana je
//         modelarske datum prepazky. Box _B meshe se NEDA pouzit - jeho zasah do
//         korby se meni s vyskou (Custom 2023: 234mm v urovni hrudi vs. 30mm u
//         podlahy; Caddy: nizky prah az 460/800mm za prepazkou), takze
//         "prepazka+ložná" davalo konec 160-800mm za skutecnym.
//       * za regalem se skenuje jen po min(konec GLB, oficialni konec); je-li GLB
//         kratsi nez oficialni o >150mm (Crew Cab s referenci pro nekrew verzi,
//         nebo skutecne useknuty model), hlasi se glbKratsi a presah regalu za GLB,
//         ale pred oficialni konec, dostane verdikt PRESAH_ZA_GLB (ne za konec auta)
//       * podbehNekonecny = podbeh zacina a az k zadni hranici uz se neobjevi
//         >=150mm rovne podlahy u steny (Caddy, Transit Connect: podbeh prechazi
//         primo do zadniho ramu). Regal tam musi jit PRES podbeh (vyrez nohy) az k
//         ramu - zadni hranici urcuje ložná délka, ne konec podbehu.
// Verdikty:
//   JEN_K_PODBEHU      regal konci pred/na zacatku podbehu a hned za nim je >= 460mm
//                      (1 sloupec 1box: 430 + profil 30) souvisle vyuzitelne delky
//   NEDOTAZENO         regal uz je nad podbehem, ale hned za nim porad zbyva >= 460mm
//   VOLNO_ZA_PREKAZKOU hned za regalem je prekazka (sloupek/dverni ram), ale dal
//                      dozadu je >= 460mm volny usek - k rucnimu posouzeni
//   PRESAH_ZA_KONEC    regal konci > 50mm za zadni hranici (blizsi z GLB/oficialni)
//   PRESAH_ZA_GLB      regal konci za koncem GLB, ale v oficialni ložné délce -
//                      GLB je kratsi nez skutecne auto, nelze overit geometrii
//   OK                 jinak
//
// Vstup: <dumpdir>/all_public_rows.tsv, <dumpdir>/rows/<id>.json, <dumpdir>/car_bodies.tsv,
//        <dumpdir>/karoserie_model_reference.tsv
// (vyrobi scripts/2026-09-03_audit_regal_jen_k_podbehu.py read-only z DB - spoustej ten).
// Vystup: JSON report na stdout, prubeh na stderr.
// Omezeni: collidesWithWalls detekuje jen krizeni ploch (ne obsazeni), proto se
// vsude pouzivaji vysoke slaby od podlahy/vrsku clenu; sliding door na strane
// regalu se v GLB jevi jako tlustsi stena => za regalem "stena"/"cap" (napr. Custom
// 2023 FO38/39/47/48, T7 VW27) - to NENI jen-k-podbehu.
const fs = require("fs");
const THREE = require("three");
const path = require("path");
const { makeCollisionModule } = require(path.join(__dirname, "2026-09-01_collision_module_factory.js"));
const { parseGlbMesh } = require(path.join(__dirname, "2026-08-19_glb_real_geometry.js"));

const DUMP = process.argv[2];
const ONLY = process.argv[3] ? new Set(process.argv[3].split(",").map(Number)) : null;
if (!DUMP) { console.error("usage: node 2026-09-03_audit_regal_jen_k_podbehu.js <dumpdir> [id,id,...]"); process.exit(2); }
const KAT = path.join(__dirname, "..", "webapp", "katalog") + "/";
const ZSTEP = 10, YSTEP = 20, WINDOW_MIN = 200, COL_MIN = 460, GAP_TOL = 40, ARCH_MIN_RISE = 100, ARCH_MIN_LEN = 300, ARCH_PEAK_MIN = 150;

const rows = fs.readFileSync(`${DUMP}/all_public_rows.tsv`, "utf8").trim().split("\n").map(l => {
  const [id, cat, model, shop, ...rest] = l.split("\t");
  return { id: Number(id), category_id: cat === "None" ? null : Number(cat), name: rest.join("\t") };
});
const carBodies = {};
fs.readFileSync(`${DUMP}/car_bodies.tsv`, "utf8").trim().split("\n").forEach(l => {
  const [id, name, glb, modelId, modelName] = l.split("\t");
  carBodies[Number(id)] = { name, glb, modelName };
});
const cargoRef = {}; // kod -> {cargoLength, cargoWidth, cargoHeight, realName}
try {
  fs.readFileSync(`${DUMP}/karoserie_model_reference.tsv`, "utf8").trim().split("\n").forEach(l => {
    const [code, L, W, H, realName] = l.split("\t");
    if (code) cargoRef[code] = { cargoLength: Number(L) || 0, cargoWidth: Number(W) || 0, cargoHeight: Number(H) || 0, realName };
  });
} catch (e) { /* bez reference - jen GLB */ }
const CODE_RE = /\[([A-Za-z]{2,3}\d{1,3})\]/;
function codeFor(cbId) {
  const rec = carBodies[cbId]; if (!rec) return null;
  const m = CODE_RE.exec(rec.modelName || "") || CODE_RE.exec(rec.name || "");
  return m ? m[1].toUpperCase() : null;
}
function baseFor(cbId) {
  const rec = carBodies[cbId]; if (!rec || !rec.glb) return null;
  return rec.glb.replace(/^car_bodies\//, "").replace(/_B_wall\.glb$/, "").replace(/_B\.glb$/, "").replace(/_R_D\.glb$/, "").replace(/_L\.glb$/, "");
}
const modCache = {};
function getMod(base) {
  if (!modCache[base]) { try { modCache[base] = makeCollisionModule(KAT + "car_bodies/" + base); } catch (e) { modCache[base] = { error: e.message }; } }
  return modCache[base];
}
const meshCache = {};
function glbMesh(pid) {
  if (meshCache[pid] === undefined) { try { meshCache[pid] = parseGlbMesh(KAT + pid + ".glb"); } catch (e) { meshCache[pid] = null; } }
  return meshCache[pid];
}
function worldBox(part, off) {
  const src = glbMesh(part.part_id); if (!src) return null;
  const m = src.clone(); m.geometry = src.geometry;
  m.position.set(part.position[0] - off[0], part.position[1] - off[1], part.position[2] - off[2]);
  m.quaternion.set(...part.quaternion); m.scale.set(...part.scale); m.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(m);
}
function slab(x0, x1, y0, y1, z0, z1) {
  const g = new THREE.BoxGeometry(Math.max(1, x1 - x0), Math.max(1, y1 - y0), Math.max(1, z1 - z0));
  const m = new THREE.Mesh(g); m.position.set((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2); m.updateMatrixWorld(true); return m;
}
const r1 = v => Math.round(v * 10) / 10;

const report = [];
for (const row of rows) {
  if (ONLY && !ONLY.has(row.id)) continue;
  const out = { id: row.id, name: row.name, category_id: row.category_id };
  let data; try { data = JSON.parse(fs.readFileSync(`${DUMP}/rows/${row.id}.json`, "utf8")); } catch (e) { out.error = "no data"; report.push(out); continue; }
  const parts = data.parts || [];
  const cbParts = parts.filter(p => p.part_id.startsWith("car_body_"));
  if (!cbParts.length) { out.error = "bez karoserie"; report.push(out); continue; }
  const cbId = Number(cbParts[0].part_id.slice(9));
  const off = cbParts[0].position || [0, 0, 0];
  const base = baseFor(cbId);
  out.base = base; out.car_body_offset = off;
  if (!base) { out.error = "car_body id " + cbId + " neni v car_bodies"; report.push(out); continue; }
  const mod = getMod(base);
  if (mod.error) { out.error = "GLB: " + mod.error; report.push(out); continue; }
  const { collidesWithWalls, boxL0, boxB0 } = mod;
  // orientace: zadek = smer od prepazky (B) k tezisti L steny
  const rearSign = Math.sign(((boxL0.min.z + boxL0.max.z) / 2) - ((boxB0.min.z + boxB0.max.z) / 2)) || 1;
  const rz = z => z * rearSign; // "rear coordinate": roste smerem k zadku
  const profiles = parts.filter(p => p.part_id === "Object_7");
  if (!profiles.length) { out.error = "zadne profily Object_7"; report.push(out); continue; }
  const boxes = profiles.map(p => ({ p, b: worldBox(p, off) })).filter(x => x.b);
  const rackWallX = Math.min(...boxes.map(x => x.b.min.x));
  const rackOuterX = Math.max(...boxes.map(x => x.b.max.x));
  const floorY = Math.min(...boxes.map(x => x.b.min.y));
  const hTop = Math.max(...boxes.map(x => x.b.max.y));
  // strana steny: regal je namontovany na stene, u ktere stoji (levá stěna = -X;
  // u neotocenych karoserii (Jumpy) je stejna stena na +X) - podle teziste regalu
  const wallSign = ((rackWallX + rackOuterX) / 2) < 0 ? -1 : 1;
  const isWallSideBox = b => wallSign < 0 ? b.min.x < rackWallX + 10 : b.max.x > rackOuterX - 10;
  const wallSide = boxes.filter(x => isWallSideBox(x.b) && (x.b.max.y - x.b.min.y) > 100);
  const TOP_Y = wallSide.length ? Math.max(...wallSide.map(x => x.b.max.y)) : hTop;
  const rearZs = boxes.map(x => rearSign > 0 ? x.b.max.z : x.b.min.z);
  const frontZs = boxes.map(x => rearSign > 0 ? x.b.min.z : x.b.max.z);
  const rackRearR = Math.max(...rearZs.map(rz)), rackFrontR = Math.min(...frontZs.map(rz));
  const bodyEndR = Math.max(rz(boxL0.min.z), rz(boxL0.max.z));
  const lFrontR = Math.min(rz(boxL0.min.z), rz(boxL0.max.z)); // predni hrana L steny = modelarske datum prepazky
  const bulkheadR = Math.max(rz(boxB0.min.z), rz(boxB0.max.z)); // max zasah _B meshe (jen informativne, viz hlavicka)
  // oficialni zadni hranice = predni hrana L steny + ložná délka (kdyz je v referenci); limit skenu = blizsi z GLB/oficialni
  const code = codeFor(cbId); const ref = code ? cargoRef[code] : null;
  const officialEndR = ref && ref.cargoLength > 0 ? lFrontR + ref.cargoLength : null;
  const limitR = officialEndR === null ? bodyEndR : Math.min(bodyEndR, officialEndR);
  const glbMinusOfficial = officialEndR === null ? null : bodyEndR - officialEndR;
  const glbShorter = glbMinusOfficial !== null && glbMinusOfficial < -150;
  out.official = { code, cargoLength: ref ? ref.cargoLength : null, realName: ref ? ref.realName : null, endZ: officialEndR === null ? null : r1(rearSign * officialEndR), glbLength: r1(bodyEndR - lFrontR), glbMinusOfficial: glbMinusOfficial === null ? null : r1(glbMinusOfficial), glbShorter, bulkheadMeshBehindLFront: r1(bulkheadR - lFrontR) };
  const zr = (rA, rB) => rearSign > 0 ? [rA, rB] : [-rB, -rA];
  // sablona ZADNI nohy: svisle cleny (vc. cap) na Z posledni nohy
  const legMembers = boxes.filter(x => rz(rearSign > 0 ? x.b.max.z : x.b.min.z) > rackRearR - 40 && (x.b.max.y - x.b.min.y) > 60)
    .map(x => ({ role: x.p.role || "", b: x.b, wallSide: isWallSideBox(x.b), sloupek: /sloupek/.test(x.p.role || "") }));
  const fixedMembers = legMembers.filter(m => !m.wallSide && !m.sloupek); // predni-svislice, cap, ...
  const sloupekMembers = legMembers.filter(m => m.sloupek);
  out.rearLegRoles = legMembers.map(m => m.role);
  // okno za regalem: "vesla by se sem stejna noha (s vyrezovou adaptaci u steny)?"
  function memberSlab(m, rA, y0, y1) { const len = m.b.max.z - m.b.min.z; const [z0, z1] = zr(rA, rA + len); return slab(m.b.min.x, m.b.max.x, y0, y1, z0, z1); }
  function lowestFree(mList, rA, yFrom, yTo) {
    for (let y = yFrom; y < yTo - WINDOW_MIN + YSTEP; y += YSTEP) {
      if (!mList.some(m => collidesWithWalls(memberSlab(m, rA, y, yTo)))) return y;
    }
    return null;
  }
  // nejvyssi volne Y pro clen (slab od jeho spodku po y), skenuje se dolu od jeho vrsku
  function highestFree(m, rA, yLow) {
    for (let y = m.b.max.y; y >= yLow + WINDOW_MIN; y -= YSTEP) {
      if (!collidesWithWalls(memberSlab(m, rA, yLow, y))) return y;
    }
    return null;
  }
  // okno = (min strop pevnych clenu, kdyz by regal byl nizsi) - (max spodek stenoveho clenu / sloupku)
  function windowAt(rA) {
    let top = TOP_Y, topWhy = null;
    for (const m of fixedMembers) {
      const t = highestFree(m, rA, Math.max(m.b.min.y, floorY));
      if (t === null) return { win: 0, bottom: null, top: null, why: m.role };
      if (t < top) { top = t; topWhy = m.role; }
    }
    const wallM = legMembers.filter(m => m.wallSide);
    if (!wallM.length) return { win: 0, bottom: null, top: null, why: "bez-stenoveho-clenu" };
    const wb = lowestFree(wallM, rA, floorY, top);
    if (wb === null) return { win: 0, bottom: null, top, why: "stena" };
    let sb = floorY;
    if (sloupekMembers.length) { const s = lowestFree(sloupekMembers, rA, floorY, top); if (s === null) return { win: 0, bottom: null, top, why: "sloupek" }; sb = s; }
    const bottom = Math.max(wb, sb);
    return { win: top - bottom, bottom, top, why: top - bottom < WINDOW_MIN ? (topWhy || "stena") : null };
  }
  // podbeh = usek, kde stenovy clen zadni nohy (vysoky slab X[wallX,wallX+30], Y[y,TOP_Y] -
  // krizi horni plochu podbehu, takze funguje i pro "obsazeni") ma nejnizsi volne Y
  // aspon ARCH_MIN_RISE nad podlahou, souvisle aspon ARCH_MIN_LEN. Skenuje se cely
  // regal od predni nohy (i podbeh POD regalem se tak zachyti) az za konec karoserie.
  const wallOnly = legMembers.filter(m => m.wallSide);
  const rises = []; // [r, rise] od predni nohy az po skutecnou zadni stenu
  if (wallOnly.length) {
    for (let r = rackFrontR; r < bodyEndR + 300; r += ZSTEP) {
      // blokovano nahore (sloupek/dverni ram/zadni stena) = Infinity; neprerusovat, muze byt jen lokalni prekazka
      if (wallOnly.some(m => collidesWithWalls(memberSlab(m, r, TOP_Y - 40, TOP_Y)))) { rises.push([r, Infinity]); continue; }
      const y = lowestFree(wallOnly, r, floorY, TOP_Y);
      rises.push([r, y === null ? Infinity : y - floorY]);
    }
  }
  // segmenty s rise >= ARCH_MIN_RISE; podbeh = segment dlouhy >= ARCH_MIN_LEN s max rise >= ARCH_PEAK_MIN
  const segments = [], blockedSegs = [];
  for (const [r, rise] of rises) {
    if (rise === Infinity) { const lb = blockedSegs[blockedSegs.length - 1]; if (lb && lb.endR === r) lb.endR = r + ZSTEP; else blockedSegs.push({ startR: r, endR: r + ZSTEP }); continue; }
    if (rise >= ARCH_MIN_RISE) { const last = segments[segments.length - 1]; if (last && last.endR === r) { last.endR = r + ZSTEP; last.peak = Math.max(last.peak, rise); } else segments.push({ startR: r, endR: r + ZSTEP, peak: rise }); }
  }
  const archSegs = segments.filter(sg => sg.endR - sg.startR >= ARCH_MIN_LEN && sg.peak >= ARCH_PEAK_MIN);
  const bumps = segments.filter(sg => !archSegs.includes(sg)).map(sg => ({ z: [r1(rearSign * sg.startR), r1(rearSign * sg.endR)], peak: r1(sg.peak) }));
  const archStartR = archSegs.length ? archSegs[0].startR : null, archEndR = archSegs.length ? archSegs[archSegs.length - 1].endR : null;
  const archPeak = archSegs.length ? Math.max(...archSegs.map(sg => sg.peak)) : null;
  // volno PRED regalem: cleny prvni (predni) nohy posouvane dopredu az do kolize (max 1500mm)
  const frontMembers = boxes.filter(x => rz(rearSign > 0 ? x.b.min.z : x.b.max.z) < rackFrontR + 40 && (x.b.max.y - x.b.min.y) > 60);
  let frontFree = 0;
  for (let d = ZSTEP; d <= 1500; d += ZSTEP) {
    const hit = frontMembers.some(m => { const len = m.b.max.z - m.b.min.z; const [z0, z1] = zr(rackFrontR - d, rackFrontR - d + len); return collidesWithWalls(slab(m.b.min.x, m.b.max.x, m.b.min.y, m.b.max.y, z0, z1)); });
    if (hit) break;
    frontFree = d;
  }
  out.frontFree = frontFree;
  const profile = [];
  let usableLen = 0, maxBottom = floorY, minTop = TOP_Y, runs = [], cur = null;
  for (let r = rackRearR; r < limitR; r += ZSTEP) {
    const w = windowAt(r);
    profile.push([r1(rearSign * r), r1(w.win), w.bottom === null ? w.why : r1(w.bottom - floorY), w.top === null ? null : r1(TOP_Y - w.top)]);
    if (w.win >= WINDOW_MIN) {
      if (cur && cur.endR + GAP_TOL >= r) cur.endR = r + ZSTEP; else { cur = { startR: r, endR: r + ZSTEP }; runs.push(cur); }
      if (runs[0] === cur) { usableLen = cur.endR - rackRearR; if (w.bottom > maxBottom) maxBottom = w.bottom; if (w.top < minTop) minTop = w.top; }
    }
  }
  // prvni usek musi navazovat primo na regal (do GAP_TOL), jinak je to "volno za prekazkou"
  if (runs.length && runs[0].startR > rackRearR + GAP_TOL) usableLen = 0;
  const best = runs.reduce((m, x) => (!m || x.endR - x.startR > m.endR - m.startR) ? x : m, null);
  const bestRun = best ? best.endR - best.startR : 0;
  const overhang = rackRearR - limitR; // >0 = regal konci za zadni hranici (GLB nebo oficialni ložné délky - co je bliz)
  // podbeh "nekonecny": za koncem podbehu uz az k zadni hranici neni >=150mm rovne podlahy u steny
  // (rise < ARCH_MIN_RISE) - podbeh prechazi primo do zadniho ramu/dveri (Caddy, Transit Connect)
  const flatAfterArch = archEndR === null ? null : rises.filter(([r, rise]) => r >= archEndR && r < limitR && rise < ARCH_MIN_RISE).length * ZSTEP;
  const archInfinite = archEndR !== null && (archEndR >= limitR - 50 || flatAfterArch < 150);
  const rackEndsBeforeArch = archStartR !== null && rackRearR <= archStartR + 20;
  let verdict = "OK";
  if (usableLen >= COL_MIN) verdict = rackEndsBeforeArch ? "JEN_K_PODBEHU" : "NEDOTAZENO";
  else if (bestRun >= COL_MIN) verdict = "VOLNO_ZA_PREKAZKOU";
  else if (overhang > 50) verdict = (glbShorter && officialEndR !== null && rackRearR <= officialEndR + 50) ? "PRESAH_ZA_GLB" : "PRESAH_ZA_KONEC";
  Object.assign(out, {
    rearSign, wallSign, rack: { wallX: r1(wallSign < 0 ? rackWallX : rackOuterX), outerX: r1(wallSign < 0 ? rackOuterX : rackWallX), floorY: r1(floorY), topY: r1(TOP_Y), hTop: r1(hTop), frontZ: r1(rearSign * rackFrontR), rearZ: r1(rearSign * rackRearR), lengthZ: r1(rackRearR - rackFrontR) },
    body: { lFrontZ: r1(rearSign * lFrontR), bulkheadMeshZ: r1(rearSign * bulkheadR), endZ: r1(rearSign * bodyEndR), boxL: [r1(boxL0.min.z), r1(boxL0.max.z)] },
    arch: archStartR === null ? null : { startZ: r1(rearSign * archStartR), endZ: r1(rearSign * archEndR), peak: r1(archPeak), rackRearVsStart: r1(rackRearR - archStartR), flatAfter: r1(flatAfterArch), infinite: archInfinite },
    limitZ: r1(rearSign * limitR), rackToLimit: r1(limitR - rackRearR),
    bumps, blocked: blockedSegs.map(sg => [r1(rearSign * sg.startR), r1(rearSign * sg.endR)]),
    behind: { usableLen: r1(usableLen), bestRun: r1(bestRun), bestRunZ: best ? [r1(rearSign * best.startR), r1(rearSign * best.endR)] : null, runs: runs.map(x => [r1(rearSign * x.startR), r1(rearSign * x.endR)]), toBodyEnd: r1(bodyEndR - rackRearR), toLimit: r1(limitR - rackRearR), overhang: r1(overhang), maxFloorRise: r1(maxBottom - floorY), maxTopDrop: r1(TOP_Y - minTop), profile },
    verdict,
  });
  report.push(out);
  process.stderr.write(`id=${row.id} ${verdict} usable=${usableLen.toFixed(0)} best=${bestRun.toFixed(0)} front=${frontFree} rackRear=${(rearSign * rackRearR).toFixed(0)} arch=${archStartR === null ? "-" : (rearSign * archStartR).toFixed(0)} end=${(rearSign * bodyEndR).toFixed(0)} ofic=${officialEndR === null ? "-" : (rearSign * officialEndR).toFixed(0)}${archInfinite ? " podbeh∞" : ""} ${row.name}\n`);
}
console.log(JSON.stringify(report, null, 1));
