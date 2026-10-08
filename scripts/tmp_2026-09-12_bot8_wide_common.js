// Sdilena infrastruktura pro sirokou aplikaci shape_geometry_methods.id=11
// ("prepocet-kolizni-rezervy-existujici-sestavy") na 12 dalsich modelu
// (K-021,K-284,K-009,K-019,K-089,K-095e,K-125e,K-236,K-246e,K-253,K-286,
// K-293e - K-119 uz hotovo drivejsi soubeznou session, viz AGENTS_LOG).
//
// Generalizuje uz 5x naostro overenou transformAssembly() z
// tmp_2026-09-12_bot8_batch_184.js na LIBOVOLNY pocet noh/sloupcu (K-019 ma
// 4 nohy/3 sloupce, K-095e/K-125e/K-293e maji 3 nohy/2 sloupce, K-236 ma 5
// noh/4 sloupce) - puvodni funkce byla napevno na presne 1 sdilenou nohu.
//
// KLICOVE EMPIRICKE NALEZY (tmp_2026-09-12_bot8_wide_wallcheck.js/wallcheck2.js):
// - "noha u prepazky" (dostava deltaZ) je VZDY noha s nejnizsim (nejzapornejsim)
//   Z v kazdem z 13 modelu - raycasting na REALNY povrch car_body_B.glb
//   potvrdil, ze tahle noha je VZDY radove blize (16-86mm) nez vsechny ostatni
//   (250-2400mm) - AZ NA VYJIMKU T7 (K-284/K-286), kde ANI nejblizsi noha neni
//   blizko (~950-1900mm) - u tehle dvou modelu tedy deltaZ NEMA zadny fyzicky
//   dopad (zadny dil se v Z neposouva vlivem prepazky), overeno explicitne,
//   ne predpoklad.
// - deltaY (podbeh) se aplikuje NEZAVISLE na kazdou vyrezovou nohu (ma
//   zadni-svislice-nad-zarezem) BEZ OHLEDU na to, jestli je to zrovna "noha
//   u prepazky" - je to jiny fyzicky rozmer (odsazeni od kola/podbehu), ne
//   navazany na zed.
const fs = require("fs");
const path = require("path");
const THREE = require("three");
const { parseGlbMesh } = require("./2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("../webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const R = require("./2026-09-11_glb_resolver.js");
const { execSync } = require("child_process");

const DELTA_Z = 8;   // 10mm - 2mm (prepazka)
const DELTA_Y = 10;  // 30mm - 20mm (podbeh)
const HALF_T = 15;   // polovina tloustky profilu 30mm
const near = (a, b, eps) => Math.abs(a - b) < (eps == null ? 1 : eps);

// ---- DB helpers ----
function dbFetchAssemblies(ids) {
  const dumpPy = `
import json, pymysql
env = {}
with open("api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT",3306)), user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SELECT id, name, kod_sestavy, category_id, car_model_id, technicky_ok, data FROM product_assemblies WHERE id IN (${ids.join(",")})")
out = {}
for r in cur.fetchall():
    r["data"] = json.loads(r["data"])
    out[r["id"]] = r
conn.close()
print(json.dumps(out))
`;
  const tmpf = "/tmp/_dump_wide_" + ids.join("_") + ".py";
  fs.writeFileSync(tmpf, dumpPy);
  const raw = execSync(`api/venv/bin/python3 ${tmpf}`, { cwd: "/opt/konfigurator", maxBuffer: 1024 * 1024 * 200 }).toString();
  return JSON.parse(raw);
}

// ---- vyrez shift formula (shape_geometry_methods.id=6), shodne s batch_184.js ----
function shiftVyrezPart(p, role, oldYnew, deltaY) {
  const [x, y, z] = p.position;
  const newYnew = oldYnew + deltaY;
  if (role === "sloupek-pred-podbehem") {
    const oldH = p.scale[1] * 1000, floorY = y - oldH / 2, newH = newYnew - floorY;
    return { ...p, position: [x, floorY + newH / 2, z], scale: [p.scale[0], newH / 1000, p.scale[2]] };
  }
  if (role === "zadni-svislice-nad-zarezem") {
    const oldH = p.scale[1] * 1000, topY = y + oldH / 2, newH = topY - newYnew;
    return { ...p, position: [x, newYnew + newH / 2, z], scale: [p.scale[0], newH / 1000, p.scale[2]] };
  }
  if (role === "pricka-uzavreni-vyrezu") {
    // DULEZITE (nalezeno empiricky na K-293e, viz AGENTS_LOG): `scale[1]`
    // u tohohle dilu NEODPOVIDA vysce v mm jako u sloupek-pred-podbehem/
    // zadni-svislice-nad-zarezem (kde scale*1000=skutecna vyska profilu) -
    // realna GLB geometrie je vzdy jen ~30mm dil bez ohledu na scale
    // (overeno primo mesh Box3, K-293e: scale=0.289 ale realny box jen
    // 30.0002mm). U rodiny K-118/K-089 (a pravdepodobne cele Jumpy/Expert/
    // Proace platformy) vychazi puvodni Y presne oldYnew+HALF_T (svar+15mm,
    // overeno na 184: 306.0001-291.0001=15.0000 presne) - tam ma smysl
    // posunout SPOLU s hranici (translate o deltaY zachova presne tenhle
    // vztah). U K-293e ale puvodni Y=384 vs oldYnew+15=324 (offset +75mm,
    // NENI navazany na svar) - posun o deltaY tam vyrobil NOVOU self-kolizi
    // s uhelnik-noha1 (overeno timhle skriptem). Bezpecne reseni: posunout
    // JEN kdyz je dil skutecne navazany na svar (puvodni Y do ~30mm od
    // oldYnew+HALF_T), jinak nechat beze zmeny (jeho vztah k noze byl
    // zjevne jiny/nezavisly, force-posun by mohl vyrobit kolizi jinde).
    if (near(y, oldYnew + HALF_T, 30)) {
      return { ...p, position: [x, y + deltaY, z] };
    }
    return p;
  }
  throw new Error("neznama vyrez role: " + role);
}

// ---- Analyza noh: vraci pole {z, isPlain, isVyrez, oldYnew, gap} serazene podle Z ----
function analyzeLegs(parts) {
  const zs = [...new Set(parts.filter(p => p.role === "predni-svislice").map(p => p.position[2]))].sort((a, b) => a - b);
  return zs.map(z => {
    const isPlainDolni = parts.some(p => (p.role === "zadni-svislice-dolni" || p.role === "zadni-svislice") && near(p.position[2], z));
    const sloupek = parts.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], z));
    const svisl = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], z));
    let oldYnew = null, gap = null;
    if (sloupek && svisl) {
      const topSloupek = sloupek.position[1] + sloupek.scale[1] * 1000 / 2;
      const botSvisl = svisl.position[1] - svisl.scale[1] * 1000 / 2;
      gap = botSvisl - topSloupek;
      oldYnew = topSloupek;
    }
    return { z, isPlain: isPlainDolni, isVyrez: !!(sloupek && svisl), oldYnew, gap };
  });
}

// ---- Analyza sloupcu: najde colPrefix (z rolí nosnik-<col>-<level>) a jeho Z-rozpeti (mezi 2 sousednimi nohami) ----
function analyzeColumns(parts, legZs) {
  const nosnikRe = /^nosnik-([\w]+)-([\w]+)$/;
  const cols = {};
  for (const p of parts) {
    const m = nosnikRe.exec(p.role || "");
    if (!m) continue;
    const [, col] = m;
    (cols[col] = cols[col] || []).push(p.position[2]);
  }
  const out = [];
  for (const col in cols) {
    const zMin = Math.min(...cols[col]), zMax = Math.max(...cols[col]);
    // sloupec spanuje MEZI dvema sousednimi nohama - najdi nejblizsi legZ pod zMin a nad zMax
    const zLow = Math.max(...legZs.filter(lz => lz <= zMin + 5));
    const zHigh = Math.min(...legZs.filter(lz => lz >= zMax - 5));
    out.push({ prefix: col, zLow, zHigh });
  }
  return out;
}

// ---- levels (patra) usporadana vzestupne podle Y, pro dany sloupec ----
function columnLevels(parts, colPrefix) {
  const nosnikRe = new RegExp(`^nosnik-${colPrefix}-(\\w+)$`);
  const nosnikParts = parts.filter(p => nosnikRe.test(p.role || ""));
  const levelSet = [...new Set(nosnikParts.map(p => nosnikRe.exec(p.role)[1]))];
  levelSet.sort((a, b) => {
    const ya = Math.min(...nosnikParts.filter(p => nosnikRe.exec(p.role)[1] === a).map(p => p.position[1]));
    const yb = Math.min(...nosnikParts.filter(p => nosnikRe.exec(p.role)[1] === b).map(p => p.position[1]));
    return ya - yb;
  });
  return levelSet;
}

// ---- Genericka transformace - libovolny pocet noh/sloupcu ----
// cfg: { legs: [{z,isPlain,isVyrez,oldYnew}], wallLegZ: number|null, columns: [{prefix,zLow,zHigh}] }
function transformAssemblyGeneric(parts, cfg) {
  const { legs, wallLegZ, columns } = cfg;
  const vyrezLegs = legs.filter(l => l.isVyrez);
  const log = { wallLegRigid: 0, vyrezShift: 0, vyrezAssocShift: 0, colWallEnd: 0, colWallMid: 0,
    colOtherEnd: 0, colOtherMid: 0, dorovnani: 0, carBody: 0, unaffected: 0 };
  const LEG_FRAME_ROLES = new Set([
    "predni-svislice", "cap", "spojnice-dolni", "spojnice-horni", "spojnice-horni-uzavreni",
    "zadni-svislice-dolni", "zadni-svislice", "zaslepka", "zaslepka-predni-svislice",
    "zaslepka-zadni-svislice-dolni", "zaslepka-zadni-svislice",
  ]);
  const VYREZ_ROLES = new Set(["sloupek-pred-podbehem", "zadni-svislice-nad-zarezem", "pricka-uzavreni-vyrezu"]);

  // pripravit dorovnani fce per-sloupec (pocita se pozdeji podle namerene deficitu)
  const dorovnaniByCol = {}; // colPrefix -> {levels, deficit}

  const nosnikRe = /^nosnik-([\w]+)-([\w]+)$/;
  const spojniceRe = /^spojnice-([\w]+)-([\w]+)$/;
  const euroboxRe = /^eurobox-([\w]+)-([\w]+)$/;

  function findCol(z) {
    return columns.find(c => z > c.zLow - 5 && z < c.zHigh + 5);
  }
  function findLeg(z) {
    return legs.find(l => near(z, l.z));
  }

  // KROK A: prvni pruchod - spocitat pro kazdy sloupec, jestli potrebuje dorovnani (kontrola patra0 vs Y_new na obou koncich)
  for (const col of columns) {
    const levels = columnLevels(parts, col.prefix);
    if (!levels.length) continue;
    const legLow = findLeg(col.zLow), legHigh = findLeg(col.zHigh);
    let bindingYNew = null;
    for (const leg of [legLow, legHigh]) {
      if (leg && leg.isVyrez) {
        const yNew = leg.oldYnew + DELTA_Y;
        if (bindingYNew == null || yNew > bindingYNew) bindingYNew = yNew;
      }
    }
    if (bindingYNew == null) continue; // zadny konec neni vyrezovy -> zadne dorovnani
    const level0 = levels[0];
    const nosnikRe0 = new RegExp(`^nosnik-${col.prefix}-${level0}$`);
    const level0Parts = parts.filter(p => nosnikRe0.test(p.role || ""));
    const floorEdge = Math.min(...level0Parts.map(p => p.position[1])) - HALF_T;
    const rawDeficit = bindingYNew - floorEdge;
    if (rawDeficit > 0.01) {
      // OCHRANNY STROP: puvodni (rawDeficit>DELTA_Y) znamena, ze patro0 bylo
      // JIZ PRED touhle konverzi pod prahem vyrezove nohy (pre-existujici stav,
      // nesouvisi s prevodem 2/20->10/30mm) - najito empiricky na K-019 col1
      // (rawDeficit=48mm, presto ze noha ma i nezavislou predni-svislici,
      // ktera fyzicky podpiru drzi - viz AGENTS_LOG). Doslovna aplikace
      // celeho rawDeficit tam VYROBI NOVOU self-kolizi (eurobox patra N do
      // ramu patra N+1), overeno primo timhle skriptem. Tenhle ukol ma
      // opravit JEN dusledek pridane +10mm rezervy, ne predelavat cizi,
      // uz zivy/schvaleny navrh - proto strop na DELTA_Y (presne to, co
      // konverze prida, stejny duch jako krok 2 procedury "presna
      // aritmeticka konstanta").
      const deficit = Math.min(rawDeficit, DELTA_Y);
      dorovnaniByCol[col.prefix] = { levels, deficit, rawDeficit, capped: rawDeficit > DELTA_Y };
    }
  }

  function dorovnaniShift(colPrefix, level) {
    const d = dorovnaniByCol[colPrefix];
    if (!d) return 0;
    const N = d.levels.length, i = d.levels.indexOf(level);
    if (i < 0 || N <= 1) return 0;
    return d.deficit * (N - 1 - i) / (N - 1);
  }

  // Doprovodne dily (uhelnik/zaslepka) sedi az ~30mm stranou od presne
  // stredove Z osy nohy (jsou to sikme/rohove konzoly na profilu tloustky
  // 30mm) - presna role (predni-svislice apod.) je VZDY presne na ose (tol 1mm),
  // ale asociace "patri tehle noze" potrebuje sirsi toleranci. Overeno
  // self-checkem proti 184->348 (bez tohohle by 12/12 uhelniku vyslo spatne).
  const ZTOL_ACCESSORY = 60;

  const out = [];
  for (const orig of parts) {
    const p = JSON.parse(JSON.stringify(orig));
    const role = p.role || "";
    const [x, y, z] = p.position;

    if (String(p.part_id || "").startsWith("car_body_")) { out.push(p); log.carBody++; continue; }

    // -- vyrez trio na kterekoli vyrezove noze --
    if (VYREZ_ROLES.has(role)) {
      const leg = vyrezLegs.find(l => near(z, l.z));
      if (leg) { out.push(shiftVyrezPart(p, role, leg.oldYnew, DELTA_Y)); log.vyrezShift++; continue; }
    }

    // -- doprovodne dily vyrezove nohy (zaslepka/uhelnik) na jejim starem svaru Y (nebo +30 odsazeni) --
    if (/^zaslepka-zadni-svislice-nad-zarezem/.test(role) || /^uhelnik-/.test(role) || /^zaslepka-sloupek-pred-podbehem/.test(role)) {
      const leg = vyrezLegs.find(l => near(z, l.z, ZTOL_ACCESSORY));
      if (leg) {
        if (near(y, leg.oldYnew, 3) || near(y, leg.oldYnew + 30, 3)) {
          out.push({ ...p, position: [x, y + DELTA_Y, z] }); log.vyrezAssocShift++; continue;
        }
        // uhelnik/zaslepka na vyrezove noze, ale mimo starou vysku svaru - patri k "plna" casti sdilene nohy, nechame beze zmeny
        out.push(p); log.unaffected++; continue;
      }
      // uhelnik na nohe, ktera neni vyrezova - kontrola jestli je to wall leg (viz nize)
    }

    // -- wall leg (rigid, cele deltaZ) - jen "ramove" role, vyrez trio uz vyreseno vyse --
    if (wallLegZ != null && near(z, wallLegZ, LEG_FRAME_ROLES.has(role) ? 1 : ZTOL_ACCESSORY)) {
      if (LEG_FRAME_ROLES.has(role) || /^uhelnik-/.test(role) || /^zaslepka/.test(role)) {
        out.push({ ...p, position: [x, y, z + DELTA_Z] }); log.wallLegRigid++; continue;
      }
    }

    // -- KATCH-ALL: cokoli sedici PRESNE (tol 1mm) na Z znamé nohy je soucast
    //    jejiho ramu, bez ohledu na presny nazev role (napr. "spojnice-dolni-
    //    kratka" u K-089 leg1 - varianta nazvu, ktera NENI v LEG_FRAME_ROLES,
    //    ale strukturalne se chova stejne jako spojnice-dolni). Overeno, ze
    //    zadny sloupcovy dil (nosnik/spojnice/eurobox-<col>-<level>) nikdy
    //    nesedi presne na Z nohy (vzdy min. ~30mm odsazeny), takze tenhle
    //    catch-all je bezpecny a nekoliduje se sloupcovymi dily nize. --
    if (findLeg(z)) {
      const leg = findLeg(z);
      if (leg === legs.find(l => wallLegZ != null && near(l.z, wallLegZ))) {
        out.push({ ...p, position: [x, y, z + DELTA_Z] }); log.wallLegRigid++; continue;
      }
      out.push(p); log.unaffected++; continue;
    }

    // -- sloupcove nosniky/eurobox (jen kdyz "col" je SKUTECNY znamy sloupec, ne nahodna shoda regexu) --
    let m = nosnikRe.exec(role) || euroboxRe.exec(role);
    if (m && columns.some(c => c.prefix === m[1])) {
      const [, col, level] = m;
      const colDef = columns.find(c => c.prefix === col);
      const isNosnik = nosnikRe.test(role);
      const dy = dorovnaniShift(col, level);
      if (colDef && wallLegZ != null && near(colDef.zLow, wallLegZ)) {
        const newScale = isNosnik ? [p.scale[0], p.scale[1] - DELTA_Z / 1000, p.scale[2]] : p.scale;
        out.push({ ...p, position: [x, y + dy, z + DELTA_Z / 2], scale: newScale }); log.colWallMid++; continue;
      }
      out.push({ ...p, position: [x, y + dy, z] }); log.colOtherMid++; continue;
    }
    // -- sloupcove spojnice (3 varianty - konec u wall leg / konec u druhe nohy / uprostred) --
    m = spojniceRe.exec(role);
    if (m && columns.some(c => c.prefix === m[1])) {
      const [, col, level] = m;
      const colDef = columns.find(c => c.prefix === col);
      const dy = dorovnaniShift(col, level);
      const isWallCol = colDef && wallLegZ != null && near(colDef.zLow, wallLegZ);
      if (!isWallCol) { out.push({ ...p, position: [x, y + dy, z] }); log.colOtherEnd++; continue; }
      const NEAR_LEG_TOL = 60;
      const distWall = Math.abs(z - colDef.zLow);
      const distOther = Math.abs(z - colDef.zHigh);
      if (distWall < NEAR_LEG_TOL) { out.push({ ...p, position: [x, y + dy, z + DELTA_Z] }); log.colWallEnd++; continue; }
      if (distOther < NEAR_LEG_TOL) { out.push({ ...p, position: [x, y + dy, z] }); log.colWallEnd++; continue; }
      out.push({ ...p, position: [x, y + dy, z + DELTA_Z / 2] }); log.colWallMid++; continue;
    }
    // -- vypln-dno / podelnik (horni blok) - stejny princip jako nosnik (Z rozpeti mezi 2 nohami colDef) --
    m = /^(vypln-dno|podelnik)-([\w]+)(?:-([\w]+))?$/.exec(role);
    if (m) {
      const col = columns.find(c => z > c.zLow - 5 && z < c.zHigh + 5);
      if (col && wallLegZ != null && near(col.zLow, wallLegZ)) {
        out.push({ ...p, position: [x, y, z + DELTA_Z / 2], scale: [p.scale[0], p.scale[1], p.scale[2] - DELTA_Z / 1000] });
        log.colWallMid++; continue;
      }
    }

    out.push(p); log.unaffected++;
  }
  return { parts: out, log, dorovnaniByCol };
}

// ---- Verifikace: SAT proti realne karoserii + gap presne na klicovem svu + self-kolize ----
function loadWall(base, suf) {
  const m = parseGlbMesh(path.join("/opt/konfigurator/webapp/katalog/car_bodies/", base + suf + ".glb"));
  m.material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
  m.updateMatrixWorld(true);
  m.geometry.computeBoundsTree();
  return m;
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
function verifyAssembly(parts, carBodyBase) {
  const raycaster = new THREE.Raycaster();
  const walls = [loadWall(carBodyBase, "_L"), loadWall(carBodyBase, "_R_D"), loadWall(carBodyBase, "_B")];
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
  function partMesh(p) {
    const glbPath = R.glbPath(p.part_id);
    if (!glbPath) return null;
    const m = parseGlbMesh(glbPath);
    m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
    m.updateMatrixWorld(true);
    return m;
  }
  const realParts = parts.filter(p => !String(p.part_id || "").startsWith("car_body_"));
  let satCollisions = 0, skipped = 0;
  const satDetail = [];
  const meshes = [];
  for (const p of realParts) {
    const mesh = partMesh(p);
    if (!mesh) { skipped++; continue; }
    meshes.push({ p, mesh });
    if (collidesWithWallsReal(mesh)) { satCollisions++; satDetail.push({ role: p.role, position: p.position }); }
  }
  let selfSusp = 0;
  const selfDetail = [];
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
        if (vol > 2000) { selfSusp++; selfDetail.push({ a: a.p.role, b: b.p.role, vol: Math.round(vol) }); }
      }
    }
  }
  return { satCollisions, skipped, satDetail, selfSusp, selfDetail, checked: meshes.length };
}

module.exports = {
  DELTA_Z, DELTA_Y, HALF_T, near,
  dbFetchAssemblies, shiftVyrezPart, analyzeLegs, analyzeColumns, columnLevels,
  transformAssemblyGeneric, verifyAssembly,
};
