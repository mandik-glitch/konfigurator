// Ciste vypocetni jadro k scripts/2026-09-11_prestavba_vito_clenene_nohy.py.
// Bere JSON {radky, seznam, zvednuti, tolerance}, vraci JSON s vysledkem.
// NIC NEZAPISUJE do DB - jen pocita nad daty v pameti a vraci upravena data.
//
// isLegProfile/measureGapOverlap/seskupeni-podle-Z jsou DOSLOVNA KOPIE
// scripts/2026-09-05_add_uhelniky_all_legs.js (produkcni skript pouzity
// 2026-09-05 na cely katalog) - viz VLASTNOSTI_PROFILU.md metodika bod 4
// ("otestuj PRESNOU KOPII produkcniho kodu, ne vlastni paralelni
// implementaci").
const fs = require("fs");
const THREE = require("three");
const lib = require("/opt/konfigurator/scripts/2026-09-01_uhelniky_leg_joints_lib.js");
const M = require("/opt/konfigurator/scripts/2026-09-11_mesh_kolize_lib.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const OBJ7 = KAT + "Object_7.glb";
const catalog = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-09-01_uhelnik_catalog.json", "utf8"));

// === KOPIE z 2026-09-05_add_uhelniky_all_legs.js ===
function isLegProfile(p) {
  if (p.part_id !== "Object_7") return false;
  const r = p.role || "";
  if (/^spojnice-(sloupec|col)\d/.test(r)) return false;
  if (/^nosnik|^eurobox/.test(r)) return false;
  return /svislice|sloupek|spojnice-dolni|spojnice-horni|^cap$|pricka/.test(r);
}
function measureGapOverlap(bracketObj, geoFaces, P, C, dWall, axisDir, side) {
  if (!geoFaces || geoFaces.length < 2) return null;
  bracketObj.updateMatrixWorld(true);
  const n1 = dWall.clone().normalize(), n2 = axisDir.clone().multiplyScalar(side).normalize();
  const wallPlaneMax = (entry, n) => {
    const b = new THREE.Box3().setFromObject(entry.object3d);
    let m = -Infinity;
    for (let xi = 0; xi < 2; xi++) for (let yi = 0; yi < 2; yi++) for (let zi = 0; zi < 2; zi++) {
      const v = new THREE.Vector3(xi ? b.max.x : b.min.x, yi ? b.max.y : b.min.y, zi ? b.max.z : b.min.z).dot(n);
      if (v > m) m = v;
    }
    return m;
  };
  const w1 = wallPlaneMax(P, n1), w2 = wallPlaneMax(C, n2);
  const worldFacePts = geoFaces.slice(0, 2).map(f => new THREE.Vector3(f.x, f.y, f.z).applyMatrix4(bracketObj.matrixWorld));
  const distToWall = (p) => Math.min(Math.abs(p.dot(n1) - w1), Math.abs(p.dot(n2) - w2));
  return worldFacePts.map(p => distToWall(p));
}
// === konec kopie ===

function sedi(part, oc, tol) {
  const [role, x, y, z] = oc;
  if ((part.role || "") !== role) return false;
  const p = part.position || [];
  return p.length === 3 && [x, y, z].every((v, i) => Math.abs(p[i] - v) <= tol);
}

// Kolize koliznich uhelniku nad ZADANYMI dily sestavy (stejna definice
// jako scripts/2026-09-11_sweep_kolizni_uhelniky.cjs, ale bez souboroveho
// I/O - vola se rovnou nad daty v pameti pro "pred"/"po" srovnani).
function spocitejKolize(parts) {
  const jeUh = p => String(p.role || "").startsWith("uhelnik");
  const prip = [];
  for (const p of parts) {
    if (!p.position || R.jeKaroserie(p.part_id)) continue;
    const f = R.glbPath(p.part_id); if (!f) continue;
    prip.push({ p, g: M.dilVeSvete(f, p, parseGlbMesh) });
  }
  const uh = prip.filter(e => jeUh(e.p)), ost = prip.filter(e => !jeUh(e.p));
  let n = 0;
  for (const u of uh) for (const o of ost) {
    const ov = M.prekryvBoxu(u.g.box, o.g.box);
    if (Math.min(...ov) <= M.TOL_MM) continue;
    if (M.kolize(u.g, o.g, M.TOL_MM, true).koliduje) { n++; break; }
  }
  return n;
}

const vstup = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const { radky, seznam, zvednuti, tolerance } = vstup;
const out = { sestavy: [] };

for (const row of radky) {
  const d = typeof row.data === "string" ? JSON.parse(row.data) : row.data;
  const parts = d.parts || [];
  const oc = seznam[row.id];
  const idx = parts.findIndex(p => sedi(p, oc, tolerance));
  if (idx < 0) { out.chyba = `#${row.id}: příčka nenalezena při regeneraci (změnilo se mezi kontrolou a výpočtem?)`; break; }

  const prickaPred = parts[idx].position[1];
  const kolizePred = spocitejKolize(parts);

  // 1) posun pricky
  parts[idx] = { ...parts[idx], position: [parts[idx].position[0], parts[idx].position[1] + zvednuti, parts[idx].position[2]] };

  // 2) smazat VSECHNY uhelniky
  const pred = parts.length;
  const bezUhelniku = parts.filter(p => !String(p.role || "").startsWith("uhelnik"));
  const uhelnikuSmazano = pred - bezUhelniku.length;

  // 3) seskupit profily noh podle Z (presne jako produkcni skript) a
  // pro KAZDOU nohu znovu spustit applyUhelnikyToLeg
  const byZ = {};
  for (const p of bezUhelniku) {
    if (!p.position) continue;
    if (isLegProfile(p)) (byZ[Math.round(p.position[2])] ||= []).push(p);
  }
  const zs = Object.keys(byZ).map(Number).sort((a, b) => a - b);

  const noveUhelniky = [];
  const selhani = [];
  let maxGapAll = 0;
  zs.forEach((z, legIdx) => {
    const legParts = byZ[z];
    let results, stats, legEntries;
    try {
      legEntries = legParts.map((p, i) => lib.makeProfileEntry(OBJ7, { ...p, idx: i, cross_section_mm: [30, 30] }));
      ({ results, stats } = lib.applyUhelnikyToLeg(legEntries, catalog, KAT));
    } catch (e) { selhani.push({ z, duvod: "výjimka: " + e.message }); return; }

    const badNaN = results.filter(r => r.position.some(v => !Number.isFinite(v)) || r.quaternion.some(v => !Number.isFinite(v)));
    const wrongPart = results.filter(r => r.size_mm != null && r.size_mm !== 30);
    let maxGap = 0;
    for (const r of results) {
      const meta = catalog.find(c => c.part_id === r.part_id);
      if (!meta || !meta.geo_faces) continue;
      const P = legEntries.find(e => e.idx === r.joint.P_idx);
      const C = legEntries.find(e => e.idx === r.joint.C_idx);
      const geo = lib.cornerGeometry(P, C);
      if (!geo) continue;
      const dists = measureGapOverlap(r.object3d, meta.geo_faces, geo.P, geo.C, geo.dWall, geo.axisDir, r.joint.side);
      if (dists) maxGap = Math.max(maxGap, ...dists.map(v => Math.abs(v)));
    }
    if (!results.length) { selhani.push({ z, duvod: "žádný vnitřní spoj nalezen (0 úhelníků)" }); return; }
    if (badNaN.length) { selhani.push({ z, duvod: `${badNaN.length} dílů s NaN` }); return; }
    if (wrongPart.length) { selhani.push({ z, duvod: `${wrongPart.length} dílů se špatnou velikostí` }); return; }
    if (maxGap >= 1.0) { selhani.push({ z, duvod: `flush odchylka ${maxGap.toFixed(3)}mm >= 1mm` }); return; }
    maxGapAll = Math.max(maxGapAll, maxGap);
    for (const r of results) {
      noveUhelniky.push({
        part_id: r.part_id,
        position: r.position.map(v => +v.toFixed(4)),
        quaternion: r.quaternion.map(v => +v.toFixed(6)),
        scale: r.scale ? r.scale.map(v => +v.toFixed(6)) : [1, 1, 1],
        role: "uhelnik-noha" + legIdx,
      });
    }
  });

  const finalParts = bezUhelniku.concat(noveUhelniky);
  const dNove = { ...d, parts: finalParts };
  // bom/price_summary jsou snimky ze sceny - pocet dilu se meni (uhelniky
  // jsou polozka kusovniku), takze uz nesedi. Stejny vzor jako u mazani.
  if (dNove.bom) dNove.bom = [];
  if (dNove.price_summary) dNove.price_summary = null;

  const kolizePo = spocitejKolize(finalParts);

  out.sestavy.push({
    id: row.id, name: row.name, data: dNove,
    pricka_pred: prickaPred, pricka_po: prickaPred + zvednuti,
    uhelniku_smazano: uhelnikuSmazano, uhelniku_nove: noveUhelniky.length,
    noh_zpracovano: zs.length, noh_selhani: selhani.length, selhani,
    max_gap_mm: maxGapAll,
    kolizi_pred: kolizePred, kolizi_po: kolizePo,
  });
}

fs.writeFileSync(process.argv[3], JSON.stringify(out));
