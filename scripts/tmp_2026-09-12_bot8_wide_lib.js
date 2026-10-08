// Sdilena knihovna pro "siroky" prepocet kolizni rezervy (shape_geometry_methods.id=11)
// napric ruznymi vozidly/topologiemi (bot8, 2026-09-12, uzsi ukol nez proace_leg_builder -
// tady se JEN aplikuje presna aritmeticka delta na JIZ POSTAVENOU sestavu, nestavi se nic
// od nuly). Viz AGENTS_LOG.md zapis k tomuto skriptu pro presny kontext zadani.
//
// Princip klasifikace dilu je CISTE GEOMETRICKY (ne natvrdo seznam nazvu roli), protoze
// generator pouziva mirne odlisne nazvoslovi napric vozidly (napr. "col"/"sloupec",
// "zadni-svislice"/"zadni-svislice-dolni") - viz prubezne poznamky v teto session.
// Kazdy dil se bucketuje bud jako "leg-owned" (patri jedne konkretni noze, pohybuje se
// s ni CELY pri Z-shiftu) nebo "spanning" (lezi MEZI dvema nohama, interpoluje se
// pomerne). Prah frac<0.18 je zvolen tak, aby s rezervou oddelil typicke "T mm od nohy"
// offsety (T~30mm, tj. frac~0.03-0.13 na typickem rozponu 230-900mm) od skutecneho
// stredoveho/spanning umisteni (frac~0.4-0.6).
const fs = require("fs");
const path = require("path");
const THREE = require("three");
const { parseGlbMesh, glbBoundingBox } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const LEG_ROLE_RE = /^(predni-svislice|zadni-svislice|zadni-svislice-dolni|zadni-svislice-nad-zarezem|sloupek-pred-podbehem|pricka-uzavreni-vyrezu)$/;
const CUTOUT_ROLE_RE = /^(sloupek-pred-podbehem|zadni-svislice-nad-zarezem|pricka-uzavreni-vyrezu)$/;

function realParts(data) {
  return data.parts.filter(p => !String(p.part_id || "").startsWith("car_body_") && !String(p.role || "").startsWith("kontrolni-pomucka"));
}

// --- Krok 1: zjisti Z-shluky noh ---
function findLegClusters(parts, tol) {
  tol = tol == null ? 5 : tol;
  const zs = parts.filter(p => LEG_ROLE_RE.test(p.role)).map(p => p.position[2]);
  const sorted = [...zs].sort((a, b) => a - b);
  const clusters = [];
  for (const z of sorted) {
    if (clusters.length && Math.abs(z - clusters[clusters.length - 1].sum / clusters[clusters.length - 1].n) < tol) {
      const c = clusters[clusters.length - 1];
      c.sum += z; c.n++;
    } else {
      clusters.push({ sum: z, n: 1 });
    }
  }
  return clusters.map(c => c.sum / c.n);
}

// --- Krok 2: pro kazdou nohu zjisti pritomne role (cutout detekce) ---
function legRoleSets(parts, legZ, tol) {
  tol = tol == null ? 5 : tol;
  return legZ.map(z => {
    const roles = new Set(parts.filter(p => LEG_ROLE_RE.test(p.role) && Math.abs(p.position[2] - z) < tol).map(p => p.role));
    const hasCutout = roles.has("sloupek-pred-podbehem") || roles.has("zadni-svislice-nad-zarezem");
    return { z, roles: [...roles], hasCutout };
  });
}

// --- Zed (prepazka B) - realny GLB bounding box (hruby, jen pro orientaci) ---
function wallBBox(carBodyBase) {
  return glbBoundingBox(KAT + "car_bodies/" + carBodyBase + "_B.glb");
}

// --- Mistni (X,Y-pasmovy) Z-rozsah steny B v okoli konkretniho dilu -----------
// DULEZITE (zjisteno na Ford Connect/Custom, 2026-09-12): celkovy bbox steny B
// muze byt siroky (700-800mm v Z), protoze zed neni plocha, ale zahrnuje napr.
// tunel/podlahovy prolis smerem k motoru uprostred vozu (X blizko 0) - tenhle
// vybezek NENI v miste, kde stoji noha (typicky X ~300-700mm od stredu). Pouziti
// CELEHO bboxu by u takoveho vozu vybralo spatnou nohu jako "u prepazky" (viz
// AGENTS_LOG zapis, K-240 false positive na leg1 misto spravne leg0). Proto se
// mistni Z-rozsah steny pocita vzdy jen v X/Y pasmu KONKRETNI nohy.
function localWallZRange(carBodyBase, xTarget, yTarget, xTol, yTol) {
  xTol = xTol == null ? 80 : xTol; yTol = yTol == null ? 500 : yTol;
  const m = parseGlbMesh(KAT + "car_bodies/" + carBodyBase + "_B.glb");
  const pos = m.geometry.attributes.position;
  let maxZ = -Infinity, minZ = Infinity, n = 0;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
    if (Math.abs(x - xTarget) < xTol && Math.abs(y - yTarget) < yTol) {
      maxZ = Math.max(maxZ, z); minZ = Math.min(minZ, z); n++;
    }
  }
  return { minZ, maxZ, n };
}

// --- Urci, ktera noha je "u prepazky" a smer delty (empiricky, MISTNE, ne z
// celkoveho bboxu steny - viz komentar u localWallZRange) ---
// legInfo: pole {z, x, y} (x/y libovolneho dilu patřícího dane noze, napr.
// predni-svislice) - pouzije se k mistnimu vzorkovani steny.
function findPrepazkaLeg(carBodyBase, legInfo) {
  let best = -1, bestDist = Infinity, bestDir = 1, bestDetail = [];
  legInfo.forEach((leg, i) => {
    // nizkopolygonovy panel muze mit v uzkem X-pasmu 0 vertexu (velke trojuhelniky) -
    // rozsiruj pasmo, dokud neco nenajdeme.
    let r = { n: 0 };
    for (const xTol of [80, 150, 250, 400, 600]) {
      r = localWallZRange(carBodyBase, leg.x, leg.y, xTol, 500);
      if (r.n) break;
    }
    if (!r.n) { bestDetail.push({ i, n: 0 }); return; }
    const dLo = Math.abs(leg.z - r.minZ), dHi = Math.abs(leg.z - r.maxZ);
    const d = Math.min(dLo, dHi);
    const dir = dLo < dHi ? -1 : 1; // blize k minZ -> "pryc" je -Z, blize k maxZ -> "pryc" je +Z
    bestDetail.push({ i, n: r.n, minZ: r.minZ, maxZ: r.maxZ, d, dir });
    if (d < bestDist) { bestDist = d; best = i; bestDir = dir; }
  });
  return { idx: best, dist: bestDist, dir: bestDir, detail: bestDetail };
}

// --- OLD_YNEW pro kazdou cutout nohu, odvozeno PRIMO ze ulozenych dat (ne odhadem) ---
function computeOldYnew(parts, legZ, cutoutIdxs, tol) {
  tol = tol == null ? 5 : tol;
  const out = {};
  for (const i of cutoutIdxs) {
    const z = legZ[i];
    const sloupek = parts.find(p => p.role === "sloupek-pred-podbehem" && Math.abs(p.position[2] - z) < tol);
    const svisl = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && Math.abs(p.position[2] - z) < tol);
    if (!svisl) { out[i] = null; continue; }
    const botSvisl = svisl.position[1] - svisl.scale[1] * 500;
    // Nektera vozidla (zjisteno na Ford Custom FO21/K-256, 2026-09-12) nemaji
    // samostatny "sloupek-pred-podbehem" - zadni strana nohy pod zarezem je proste
    // nevyplnena (degenerate case, viz AGENTS_LOG "Y_new<=T" poznamka od bot16 pro
    // pribuzny pripad). V takovem pripade je OLD_YNEW proste spodek "nad-zarezem"
    // dilu samotneho, bez prumerovani se sloupkem.
    const yNew = sloupek ? (sloupek.position[1] + sloupek.scale[1] * 500 + botSvisl) / 2 : botSvisl;
    const matchGap = sloupek ? Math.abs((sloupek.position[1] + sloupek.scale[1] * 500) - botSvisl) : 0;
    const prickaP = parts.find(p => p.role === "pricka-uzavreni-vyrezu" && Math.abs(p.position[2] - z) < tol);
    const T = prickaP ? 2 * (prickaP.position[1] - yNew) : 30;
    out[i] = { yNew, matchGap, T, hasSloupek: !!sloupek };
  }
  return out;
}

// --- Klasifikace + transformace vsech dilu ---
// config = { legZ, prepazkaIdx, deltaZ, cutoutIdxs, oldYnew (map idx->{yNew,T}), deltaY, fracTol }
function transformParts(parts, config) {
  const { legZ, prepazkaIdx, deltaZ, cutoutIdxs, oldYnew, deltaY } = config;
  const fracTol = config.fracTol == null ? 0.18 : config.fracTol;
  const sortedLegZ = [...legZ].sort((a, b) => a - b);
  // mapovani puvodniho indexu (jak prisel z legZ) na sorted pozici uz je stejne, pokud
  // legZ uz je sorted (findLegClusters vraci sorted) - predpoklada se to volajicim.
  const newLegZ = legZ.map((z, i) => z + (i === prepazkaIdx ? deltaZ : 0));

  const out = [];
  const report = { legOwned: 0, spanningPlain: 0, spanningNosnik: 0, seamShift: 0, unchanged: 0, ambiguous: [] };

  for (const raw of parts) {
    const p = JSON.parse(JSON.stringify(raw));
    const z = p.position[2];
    // najdi nejblizsi nohu a jeji vzdalenost + druhou nejblizsi pro frac test
    let distances = legZ.map((lz, i) => ({ i, d: Math.abs(z - lz) }));
    distances.sort((a, b) => a.d - b.d);
    const nearest = distances[0];

    // najdi bounding pair (dve sousedni nohy v sorted poradi, mezi kterymi z lezi)
    let lo = -1, hi = -1;
    for (let i = 0; i < sortedLegZ.length - 1; i++) {
      if (z >= sortedLegZ[i] - 1e-6 && z <= sortedLegZ[i + 1] + 1e-6) { lo = i; hi = i + 1; break; }
    }
    let isSpanning = false, fracOld = null;
    if (lo >= 0) {
      const span = sortedLegZ[hi] - sortedLegZ[lo];
      fracOld = (z - sortedLegZ[lo]) / span;
      if (fracOld >= fracTol && fracOld <= (1 - fracTol)) isSpanning = true;
    }

    if (isSpanning) {
      // mapuj lo/hi (sorted-index) zpet na puvodni legZ indexy (findLegClusters uz vraci
      // sorted, takze lo/hi == puvodni indexy 1:1)
      const loIdx = lo, hiIdx = hi;
      const newLo = sortedLegZ[loIdx] + (loIdx === prepazkaIdx ? deltaZ : 0);
      const newHi = sortedLegZ[hiIdx] + (hiIdx === prepazkaIdx ? deltaZ : 0);
      const newZ = newLo + fracOld * (newHi - newLo);
      p.position[2] = newZ;
      if (p.role && p.role.startsWith("nosnik")) {
        const oldSpan = sortedLegZ[hiIdx] - sortedLegZ[loIdx];
        const newSpan = newHi - newLo;
        const oldLenMm = p.scale[1] * 1000;
        const newLenMm = oldLenMm + (newSpan - oldSpan);
        p.scale[1] = newLenMm / 1000;
        report.spanningNosnik++;
      } else {
        report.spanningPlain++;
      }
      out.push(p);
      continue;
    }

    // leg-owned
    const legIdx = nearest.i;
    let touched = false;
    if (legIdx === prepazkaIdx && deltaZ) {
      p.position[2] = z + deltaZ;
      report.legOwned++;
      touched = true;
    }
    if (cutoutIdxs.includes(legIdx) && oldYnew[legIdx]) {
      const { yNew, T } = oldYnew[legIdx];
      const newYnew = yNew + deltaY;
      if (p.role === "sloupek-pred-podbehem") {
        const oldH = p.scale[1] * 1000, floorY = p.position[1] - oldH / 2;
        const newH = newYnew - floorY;
        p.position[1] = floorY + newH / 2;
        p.scale[1] = newH / 1000;
        report.seamShift++; touched = true;
      } else if (p.role === "zadni-svislice-nad-zarezem") {
        const oldH = p.scale[1] * 1000, topY = p.position[1] + oldH / 2;
        const newH = topY - newYnew;
        p.position[1] = newYnew + newH / 2;
        p.scale[1] = newH / 1000;
        report.seamShift++; touched = true;
      } else if (p.role === "pricka-uzavreni-vyrezu") {
        // Vodorovny dil "lezici" presne na sevu - NENI to kolmy profil se scale[1]
        // jako vyska (je casto otoceny, scale[1] je jeho DELKA/sirka, ne vyska -
        // viz poznamky v teto session), takze zadne stretchovani, jen posun cely
        // o deltaY (jeho stara Y = yNew+T/2 vzdy, tedy nova = yNew+T/2+deltaY =
        // stara+deltaY - odvozeno primo z dat, T se odecte).
        p.position[1] = p.position[1] + deltaY;
        report.seamShift++; touched = true;
      } else {
        // obecny test: je Y blizko sevu (yNew) nebo druhe rady konzoly (yNew+T)?
        const y = p.position[1];
        if (Math.abs(y - yNew) < 3 || Math.abs(y - (yNew + T)) < 3) {
          p.position[1] = y + deltaY;
          report.seamShift++; touched = true;
        }
      }
    }
    if (!touched) report.unchanged++;
    out.push(p);
  }
  return { parts: out, report, newLegZ };
}

// --- rozpozna sloupec/patro z role (podporuje "col"/"sloupec", "p"/"patro") ---
const COL_PATRO_RE = /^(eurobox|nosnik|spojnice)-(?:col|sloupec)(\d+)-(?:p|patro)(\d+)$/;
function parseColPatro(role) {
  const m = COL_PATRO_RE.exec(role || "");
  if (!m) return null;
  return { kind: m[1], col: Number(m[2]), patro: Number(m[3]) };
}

// --- Krok 6: dorovnani - rozlozi "shortfall" (mm, o kolik nejnizsi patro visi)
// ROVNOMERNE do N-1 mezer mezi patry DANEHO sloupce (nejvyssi patro beze zmeny,
// nejnizsi dostane cely shortfall, mezilehla linearne interpolovana) - Robert
// 2026-09-12, viz shape_geometry_methods.id=11 krok 6 a jeho "proc" pole.
// colIdx = cislo sloupce (z role, "col0"/"sloupec0" apod.)
function applyDorovnani(parts, colIdx, shortfallMm) {
  const affected = parts.filter(p => { const pc = parseColPatro(p.role); return pc && pc.col === colIdx; });
  const patra = [...new Set(affected.map(p => parseColPatro(p.role).patro))].sort((a, b) => a - b);
  const N = patra.length;
  if (N < 2) return { touched: 0, patra, note: "min. 2 patra potreba pro rozlozeni, sloupec ma " + N };
  const shiftByPatro = {};
  patra.forEach((patro, i) => { shiftByPatro[patro] = shortfallMm * (N - 1 - i) / (N - 1); });
  let touched = 0;
  for (const p of parts) {
    const pc = parseColPatro(p.role);
    if (!pc || pc.col !== colIdx) continue;
    const shift = shiftByPatro[pc.patro];
    if (shift) { p.position[1] += shift; touched++; }
  }
  return { touched, patra, shiftByPatro };
}

// --- Krok 5: kontrola visiciho luzka po zkraceni vyrezove nohy ---
// Pro kazdou cutout nohu zkontroluje OBA sousedni sloupce (pokud existuji) - najde
// nejnizsi patro (podle Y) roli nosnik-*/eurobox-* v danem sloupci a porovna s newYnew.
function checkHangingShelves(newParts, config) {
  const { legZ, cutoutIdxs, oldYnew, deltaY } = config;
  const sortedLegZ = [...legZ].sort((a, b) => a - b);
  const results = [];
  for (const cIdx of cutoutIdxs) {
    if (!oldYnew[cIdx]) continue;
    const newYnew = oldYnew[cIdx].yNew + deltaY;
    for (const side of [cIdx - 1, cIdx]) {
      if (side < 0 || side >= sortedLegZ.length - 1) continue;
      const loZ = sortedLegZ[side], hiZ = sortedLegZ[side + 1];
      // DULEZITE (najito souběžnou sesterskou session ve stejnem behu, potvrzeno
      // i tady primym mereni na K-123e id=187): referencni Y patra smi brat JEN
      // z "nosnik" (pripadne "spojnice" jako fallback) - "eurobox" ma pivot podle
      // vlastni (casto rotovane) geometrie boxu, NE podle urovne patra, a muze
      // vyjit o stovky mm jinde nez skutecna nosna konstrukce. Prumerovani nebo
      // primichani eurobox do min() by dalo falesny (typicky moc nizky) prah.
      const nosnikParts = newParts.filter(p => {
        const z = p.position[2];
        return z > loZ + 20 && z < hiZ - 20 && /^nosnik-/.test(p.role || "");
      });
      const refParts = nosnikParts.length ? nosnikParts : newParts.filter(p => {
        const z = p.position[2];
        return z > loZ + 20 && z < hiZ - 20 && /^spojnice-/.test(p.role || "");
      });
      if (!refParts.length) continue;
      const minY = Math.min(...refParts.map(p => p.position[1]));
      const gap = minY - newYnew; // kladne = bezpecne, zaporne = visi
      const lowest = refParts.find(p => p.position[1] === minY);
      const pc = parseColPatro(lowest.role);
      results.push({ cutoutLeg: cIdx, colBetween: [side, side + 1], lowestPatroY: minY, newYnew, gap, colIdx: pc ? pc.col : null });
    }
  }
  return results;
}

// --- SAT test proti realne karoserii (mesh-presny raycasting) ---
function loadWalls(carBodyBase) {
  function loadWall(suf) {
    const m = parseGlbMesh(KAT + "car_bodies/" + carBodyBase + suf + ".glb");
    m.material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
    m.updateMatrixWorld(true);
    m.geometry.computeBoundsTree();
    return m;
  }
  return [loadWall("_L"), loadWall("_R_D"), loadWall("_B")];
}

function meshWorldEdgeSample(mesh, maxEdges) {
  const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
  const edges = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (let t = 0; t < triCount; t += step) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); } else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    edges.push([vA.clone(), vB.clone()], [vB.clone(), vC.clone()], [vC.clone(), vA.clone()]);
  }
  return edges;
}

function satVerify(parts, carBodyBase) {
  const walls = loadWalls(carBodyBase);
  const raycaster = new THREE.Raycaster();
  function collidesWithWallsReal(mesh) {
    const edges = meshWorldEdgeSample(mesh, 300);
    for (const [p0, p1] of edges) {
      const dir = p1.clone().sub(p0), dist = dir.length();
      if (dist < 1e-6) continue;
      dir.normalize();
      raycaster.set(p0, dir); raycaster.far = dist;
      if (raycaster.intersectObjects(walls, false).length) return true;
    }
    return false;
  }
  let collisions = 0, skipped = 0;
  const collided = [];
  const meshes = [];
  for (const p of parts) {
    const glbPath = R.glbPath(p.part_id);
    if (!glbPath) { skipped++; continue; }
    const m = parseGlbMesh(glbPath);
    m.position.set(...p.position);
    m.quaternion.set(...p.quaternion);
    m.scale.set(...p.scale);
    m.updateMatrixWorld(true);
    meshes.push({ p, mesh: m });
    if (collidesWithWallsReal(m)) { collisions++; collided.push({ role: p.role, position: p.position }); }
  }
  // self-kolize hruba pojistka
  let selfSusp = 0;
  const susp = [];
  const box3s = meshes.map(({ p, mesh }) => ({ p, box: new THREE.Box3().setFromObject(mesh) }));
  for (let i = 0; i < box3s.length; i++) {
    for (let j = i + 1; j < box3s.length; j++) {
      const a = box3s[i], b = box3s[j];
      if (a.p.role === b.p.role) continue;
      if (a.box.intersectsBox(b.box)) {
        const ix = Math.min(a.box.max.x, b.box.max.x) - Math.max(a.box.min.x, b.box.min.x);
        const iy = Math.min(a.box.max.y, b.box.max.y) - Math.max(a.box.min.y, b.box.min.y);
        const iz = Math.min(a.box.max.z, b.box.max.z) - Math.max(a.box.min.z, b.box.min.z);
        const vol = Math.max(0, ix) * Math.max(0, iy) * Math.max(0, iz);
        if (vol > 2000) { selfSusp++; susp.push({ a: a.p.role, b: b.p.role, vol: Math.round(vol) }); }
      }
    }
  }
  return { collisions, skipped, collided, selfSusp, susp, total: meshes.length };
}

module.exports = {
  realParts, findLegClusters, legRoleSets, wallBBox, localWallZRange, findPrepazkaLeg, computeOldYnew,
  transformParts, checkHangingShelves, applyDorovnani, parseColPatro, satVerify, loadWalls, KAT,
};
