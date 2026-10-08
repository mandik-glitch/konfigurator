// BACKFILL kusovniku (bom) a cenoveho rozpisu (price_summary) u vsech
// product_assemblies. bot8 2026-09-06.
//
// PROC TO EXISTUJE: admin skladova karta produktu ("detail produktu") ma
// zalozku "Kusovnik" (webapp/admin/js/sklad-produkty.js, kolem radku 3197) -
// JE UZ HOTOVA a cte primo `product_assemblies.data.bom`/`price_summary`
// pres /api/admin/product-assemblies/by-product/<id>. Jenze tahle pole se
// plni JEN kdyz se sestava ulozi ze sceny (Ctrl+Shift+S ->
// computeAssemblyBomAndPrice(), scene.html ~radek 4285) - vsech existujicich
// 123 sestav vzniklo primym zapisem skriptu do DB (dnesni i vcerejsi regaly,
// stavajici katalogove sestavy) a maji `bom:[]`/`price_summary:{}`. Zalozka
// tedy dnes ukazuje prazdno u UPLNE VSECH produktu.
//
// METODA: PRESNA KOPIE produkcni matematiky (computeAssemblyBomAndPrice +
// currentWeightPrice, scene.html), NE reimplementace od oka - viz skill
// 3d-scena-spoje bod 4 metodiky ("otestuj PRESNOU KOPII vysledneho
// produkcniho kodu"). Nejde spustit primo produkcni JS pres headless
// prohlizec (scene.html je @staff_required, zadny staff test ucet neexistuje
// a nemam ho zakladat - viz WORKFLOW.md/pamet "no test data in prod"),
// takze se stejna matematika PORTUJE 1:1 do Node.js a meri se na REALNE GLB
// geometrii (parseGlbMesh + Box3), presne jako vsechny dnesni geometricke
// skripty - `isProfilePart` se navic NEPORTUJE, ale primo POUZIJE z
// webapp/js/scene-geometry-shared.js (`require()`), takze u tehle jedne
// funkce neni zadne riziko rozjeti.
//
// DRIVEJSI GAP (do 2026-09-13, UZ UZAVREN): pocet spoju se u sestav
// postavenych primo skripty nikdy nezaznamenaval, takze `joint_czk`/
// `joint_count` tu vychazely vzdy 0 a `total_czk` byl DOLNI ODHAD - u #346
// (Doblo K-075 C) to vyslo 12414 Kc misto spravnych ~20961 Kc (chybelo
// presne 8140 Kc, cena 74 spoju). Zjisteno pri porovnani se skutecnym
// vystupem sceny (kontrolni kusovnik) - viz AGENTS_LOG.md 2026-09-13.
// Ted `detectRealJointCount()` (nize) pocita spoje GEOMETRICKY, presnou
// kopii produkcni touch-detekce + klasifikace (autoRegisterTouchedProfileJoints
// + inferProfileJointConnectors, scene.html), overenou 1:1 proti zive scene
// na sestave 346 (73 spoju, viz scripts/tmp_2026-09-13_bot8_joint_verify_346.js).
// `accessory_czk` pocita jen SKUTECNE UMISTENE prislusenstvi (uhelniky/
// zaslepky jako polozky kusovniku) - proste soucet cen vsech ne-materialovych
// dilu (presne jak to dela i produkcni `totalAccessoryParts`), nezavisle na
// jointCount. `PRICING_CONFIG.accessories` (hardware "kolik ks na 1 spoj")
// je dnes prazdne pole (0 aktivnich radku v cfg_accessories) - i se
// spravnym jointCount tahle cast vychazi 0, to NENI chyba backfillu.
//
//   node scripts/2026-09-06_backfill_bom_price.js --dry-run [--id 189]
//   node scripts/2026-09-06_backfill_bom_price.js           [--id 189]
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const {
  isProfilePart, isStampPart, isKontrolniPart, isCarBodyPart, computeConnectorsLocal, worldConnectorsOf,
} = require("/opt/konfigurator/webapp/js/scene-geometry-shared.js");
const JOINT_RULE_VERSION = 3; // scene.html - drz rucne synchronizovane, viz komentar tam

// ---- Detekce SKUTECNYCH spoju (uzaviraeni gapu popsaneho v hlavicce) ----
// bot8 2026-09-13: presna kopie touch-detekce + klasifikace z
// webapp/scene.html (autoRegisterTouchedProfileJoints +
// inferProfileJointConnectors) - poprve sestavena a overena proti zive
// scene ve scripts/tmp_2026-09-13_bot8_joint_verify_346.js (sestava 346:
// 74 fyzickych box-dotyku profil-profil, 73 z nich ma aspon jednu stranu
// skutecne "celo" = spoj podle PRAVIDLA_SPOJU.md "Presna definice spoje" -
// "bok-k-boku", Robert 2026-09-13: "bok profilu k boku neni spoj"). Tady
// zobecnena na libovolnou sestavu misto natvrdo 346.
const AXES_JOIN = ["x", "y", "z"];
const EPS_FACE_JOIN = 0.75, EPS_OVERLAP_JOIN = 0.5;

function profileLengthAxisWorld(entry) {
  const endIdxs = [];
  entry.connectorsLocal.forEach((c, i) => { if (c.kind === "end") endIdxs.push(i); });
  if (endIdxs.length !== 2) return null;
  const w = worldConnectorsOf(entry);
  return w[endIdxs[1]].point.clone().sub(w[endIdxs[0]].point).normalize();
}

function profileAxialOverlapMm(entry, profEntry) {
  const endIdxs = [];
  profEntry.connectorsLocal.forEach((c, i) => { if (c.kind === "end") endIdxs.push(i); });
  if (endIdxs.length !== 2) return Infinity;
  const profWorld = worldConnectorsOf(profEntry);
  const A = profWorld[endIdxs[0]].point, B = profWorld[endIdxs[1]].point;
  const axis = B.clone().sub(A);
  const L = axis.length();
  if (L < 1e-6) return Infinity;
  axis.normalize();
  entry.object3d.updateMatrixWorld(true);
  const bbox = new THREE.Box3().setFromObject(entry.object3d);
  if (bbox.isEmpty()) return Infinity;
  let mn = Infinity, mx = -Infinity;
  for (let xi = 0; xi < 2; xi++) for (let yi = 0; yi < 2; yi++) for (let zi = 0; zi < 2; zi++) {
    const corner = new THREE.Vector3(xi ? bbox.max.x : bbox.min.x, yi ? bbox.max.y : bbox.min.y, zi ? bbox.max.z : bbox.min.z);
    const t = corner.sub(A).dot(axis);
    if (t < mn) mn = t;
    if (t > mx) mx = t;
  }
  return Math.min(mx, L) - Math.max(mn, 0);
}

// presna kopie inferProfileJointConnectors (webapp/scene.html)
function inferProfileJointConnectors(entry, peer) {
  const entryAxis = profileLengthAxisWorld(entry);
  const peerAxis = profileLengthAxisWorld(peer);
  if (!entryAxis || !peerAxis) return null;
  const myWorld = worldConnectorsOf(entry);
  const peerWorld = worldConnectorsOf(peer);
  const axDot = Math.abs(entryAxis.dot(peerAxis));
  let myKinds, peerKinds;
  if (axDot < 0.1) {
    entry.object3d.updateMatrixWorld(true);
    peer.object3d.updateMatrixWorld(true);
    const boxE = new THREE.Box3().setFromObject(entry.object3d);
    const boxP = new THREE.Box3().setFromObject(peer.object3d);
    let dEndE = Infinity, dEndP = Infinity;
    myWorld.forEach(cw => { if (cw.kind === "end") dEndE = Math.min(dEndE, boxP.distanceToPoint(cw.point)); });
    peerWorld.forEach(cw => { if (cw.kind === "end") dEndP = Math.min(dEndP, boxE.distanceToPoint(cw.point)); });
    if (dEndE <= dEndP) { myKinds = ["end"]; peerKinds = ["mid"]; }
    else { myKinds = ["mid"]; peerKinds = ["end"]; }
  } else if (axDot > 0.9) {
    if (profileAxialOverlapMm(entry, peer) > 5) { myKinds = ["face"]; peerKinds = ["face"]; }
    else { myKinds = ["end"]; peerKinds = ["end"]; }
  } else {
    return { myKind: null, peerKind: null };
  }
  return { myKind: myKinds[0], peerKind: peerKinds[0] };
}

// presna kopie touch-testu z autoRegisterTouchedProfileJoints
function touchAxis(boxA, boxB) {
  for (let axisIdx = 0; axisIdx < 3; axisIdx++) {
    const a = AXES_JOIN[axisIdx];
    const faceClose = Math.abs(boxA.max[a] - boxB.min[a]) < EPS_FACE_JOIN || Math.abs(boxA.min[a] - boxB.max[a]) < EPS_FACE_JOIN;
    if (!faceClose) continue;
    let overlaps = true;
    for (let j = 0; j < 3; j++) {
      if (j === axisIdx) continue;
      const oa = AXES_JOIN[j];
      const lo = Math.max(boxA.min[oa], boxB.min[oa]);
      const hi = Math.min(boxA.max[oa], boxB.max[oa]);
      const sizeA = boxA.max[oa] - boxA.min[oa];
      const sizeB = boxB.max[oa] - boxB.min[oa];
      const minSize = Math.min(sizeA, sizeB);
      if ((hi - lo) < (minSize - EPS_OVERLAP_JOIN)) { overlaps = false; break; }
    }
    if (overlaps) return axisIdx;
  }
  return -1;
}

// vraci pocet SKUTECNYCH spoju (aspon 1 strana "end") mezi vsemi profil-
// profil dvojicemi v `catParts` (uz filtrovane isProfilePart/isStampPart/
// isKontrolniPart vyse v computeAssemblyBomAndPrice).
function detectRealJointCount(catParts) {
  const profileEntries = [];
  catParts.forEach(({ part: p, catPart }) => {
    if (!isProfilePart(catPart) || !catPart.file) return;
    const mesh = ziskejMesh(catPart.file).clone(true);
    // KRITICKE (viz PRAVIDLA_SPOJU.md / hlavicka tohoto souboru):
    // computeConnectorsLocal MUSI bezet na identite, PRED umistenim.
    mesh.position.set(0, 0, 0);
    mesh.quaternion.set(0, 0, 0, 1);
    mesh.scale.set(1, 1, 1);
    mesh.updateMatrixWorld(true);
    const connectorsLocal = computeConnectorsLocal(mesh);
    mesh.position.set(p.position[0], p.position[1], p.position[2]);
    mesh.quaternion.set(p.quaternion[0], p.quaternion[1], p.quaternion[2], p.quaternion[3]);
    if (p.scale) mesh.scale.set(p.scale[0], p.scale[1], p.scale[2]); else mesh.scale.set(1, 1, 1);
    mesh.updateMatrixWorld(true);
    profileEntries.push({ object3d: mesh, connectorsLocal });
  });
  let count = 0;
  for (let i = 0; i < profileEntries.length; i++) {
    for (let j = i + 1; j < profileEntries.length; j++) {
      const a = profileEntries[i], b = profileEntries[j];
      const boxA = new THREE.Box3().setFromObject(a.object3d);
      const boxB = new THREE.Box3().setFromObject(b.object3d);
      if (boxA.isEmpty() || boxB.isEmpty()) continue;
      if (touchAxis(boxA, boxB) < 0) continue;
      const info = inferProfileJointConnectors(a, b);
      if (info && (info.myKind === "end" || info.peerKind === "end")) count++;
    }
  }
  return count;
}

const KAT = "/opt/konfigurator/webapp/katalog/";
const KATALOG_DUMP = "/tmp/katalog_pro_backfill.json";
const ASM_DUMP = "/tmp/vsechny_sestavy_pro_backfill.json";
const OUT_DIR = "/tmp/backfill_bom_vysledky";

const R = v => (v == null ? null : Math.round(v * 10) / 10);
const R0 = v => (v == null ? null : Math.round(v));

function nactiKatalog() {
  const d = JSON.parse(fs.readFileSync(KATALOG_DUMP, "utf8"));
  const map = new Map(d.parts.map(p => [String(p.id), p]));
  return { map, pricing: d.pricing_config };
}

function partDisplayName(part) {
  if (!part) return "díl";
  const name = part.name || part.nazev || "díl";
  const sku = part.sku;
  if (sku && !String(name).includes(sku)) return name + " [" + sku + "]";
  return name;
}

const meshCache = {};
function ziskejMesh(soubor) {
  if (!meshCache[soubor]) meshCache[soubor] = parseGlbMesh(KAT + soubor);
  return meshCache[soubor];
}

// Skutecna vysledna geometrie dilu ve sestave - stejny princip jako u
// currentLengthMm/currentBoardDimsMm (mereni na REALNE geometrii), jen misto
// konektoru (ktere se u skripty postavenych sestav nikdy nezaznamenaly)
// pouziva primo transformovany Box3. Pro rovne profily/desky bez naklonu
// (jen 0/90° rotace, jak vsechny dnesni stavebni skripty pouzivaji) je
// vysledek IDENTICKY s merenim mezi konektory.
function zmerRozmery(part, catPart) {
  if (!catPart.file) return null;
  const mesh = ziskejMesh(catPart.file).clone(true);
  mesh.position.set(...part.position);
  mesh.quaternion.set(...part.quaternion);
  mesh.scale.set(...part.scale);
  mesh.updateMatrixWorld(true);
  const b = new THREE.Box3().setFromObject(mesh);
  const dims = [b.max.x - b.min.x, b.max.y - b.min.y, b.max.z - b.min.z].sort((a, c) => a - c);
  return { min: dims[0], mid: dims[1], max: dims[2] };
}

// Presna kopie currentWeightPrice() (scene.html) - vraci {weight, price, lengthMm, widthMm, heightMm}.
function currentWeightPrice(part, catPart, gapy) {
  if (catPart.is_board_material) {
    const d = zmerRozmery(part, catPart);
    if (!d || catPart.price_czk_approx_PLACEHOLDER == null) {
      return { weight: catPart.weight_kg_approx, price: catPart.price_czk_approx_PLACEHOLDER, lengthMm: null };
    }
    // tloustka = nejmensi rozmer, sirka/vyska = zbyle dva (poradi nehraje
    // roli pro plochu)
    const widthMm = d.mid, heightMm = d.max;
    const areaM2 = (widthMm / 1000) * (heightMm / 1000);
    return {
      weight: catPart.weight_kg_approx, price: catPart.price_czk_approx_PLACEHOLDER * areaM2,
      lengthMm: null, widthMm, heightMm,
    };
  }
  if (!isProfilePart(catPart)) {
    return { weight: catPart.weight_kg_approx, price: catPart.price_czk_approx_PLACEHOLDER, lengthMm: null };
  }
  const d = zmerRozmery(part, catPart);
  const lenNow = d ? d.max : null;
  if (lenNow == null) gapy.push(`${part.part_id}: nelze zmerit delku (chybi GLB?)`);
  const factor = lenNow != null ? lenNow / catPart.length_mm : 1;
  return {
    weight: catPart.weight_kg_approx != null ? catPart.weight_kg_approx * factor : null,
    price: catPart.price_czk_approx_PLACEHOLDER != null ? catPart.price_czk_approx_PLACEHOLDER * factor : null,
    lengthMm: lenNow,
  };
}

// Presna kopie computeAssemblyBomAndPrice() (scene.html ~4285), jen misto
// `entries` (zive THREE.js objekty ve scene) bere ulozene `parts` + katalog.
// jointCount se NIKDY nerekonstruuje (viz hlavicka souboru) - proto 0 vsude.
function computeAssemblyBomAndPrice(parts, katalog, pricing, gapy) {
  const rows = [];
  const catParts = [];
  for (const p of parts) {
    if (isCarBodyPart(p)) continue;
    // Ochranne razitko neni dil k vyrobe - nesmi do kusovniku ani do ceny.
    // MUSI byt PRED `katalog.get`: vypln drazky v kataloogu neni, takze by
    // jinak u kazde orazitkovane sestavy pribyl radek "NENI v aktualnim
    // katalogu" - a hluk v mechanismu, kterym se poznavaji skutecne mezery,
    // je horsi nez zadny mechanismus. Logo v katalogu naopak JE, takze by
    // se objevilo jako viditelna polozka kusovniku "Logo LOGIMAN.CZ" -
    // tedy by zakaznikovi pojmenovalo ochranny prvek.
    if (isStampPart(p) || isKontrolniPart(p)) continue;
    const catPart = katalog.get(String(p.part_id));
    if (!catPart) {
      gapy.push(`${p.part_id} (role ${p.role || "?"}): NENI v aktualnim katalogu - vyrazen z kusovniku`);
      continue;
    }
    rows.push(currentWeightPrice(p, catPart, gapy));
    catParts.push({ part: p, catPart });
  }
  const isMaterialPart = c => isProfilePart(c) || !!c.is_board_material;
  const totalW = rows.reduce((s, r) => s + (r.weight || 0), 0);
  const totalMaterial = rows.reduce((s, r, i) => s + (isMaterialPart(catParts[i].catPart) ? (r.price || 0) : 0), 0);
  const totalAccessoryParts = rows.reduce((s, r, i) => s + (isMaterialPart(catParts[i].catPart) ? 0 : (r.price || 0)), 0);
  const totalCut = catParts.reduce((s, e) => s + (e.catPart.price_per_cut_czk || 0), 0);
  const totalProfiles = catParts.reduce((s, e) => s + (isProfilePart(e.catPart) ? 1 : 0), 0);
  const totalProfileFlatFee = totalProfiles * (pricing.profile_flat_fee_czk || 0);
  const totalJoints = detectRealJointCount(catParts); // 2026-09-13: gap uzavren, viz detectRealJointCount vyse
  const totalJointPrice = totalJoints * (pricing.joint_price_czk || 0);
  const totalAccessoryHardware = (pricing.accessories || []).reduce(
    (s, a) => s + (a.qty_per_joint || 0) * totalJoints * (a.price_czk || 0), 0
  );
  const totalAccessory = totalAccessoryParts + totalAccessoryHardware;
  // Balne (Robert 2026-09-11, viz scene.html computeAssemblyBomAndPrice) -
  // POSLEDNI krok, procento ze souctu VSECH uz zaokrouhlenych polozek.
  const materialCzk = Math.round(totalMaterial);
  const cutCzk = Math.round(totalCut);
  const profileFlatFeeCzk = Math.round(totalProfileFlatFee);
  const jointCzk = Math.round(totalJointPrice);
  const accessoryCzk = Math.round(totalAccessory);
  const subtotalCzk = materialCzk + cutCzk + profileFlatFeeCzk + jointCzk + accessoryCzk;
  const packagingCzk = Math.round(subtotalCzk * (pricing.packaging_pct || 0) / 100);
  const grandTotal = subtotalCzk + packagingCzk;
  // Montaz - nabizena SLUZBA (Robert 2026-09-13, viz scene.html
  // computeAssemblyBomAndPrice) - % z grandTotal, NEPRICITA se do
  // total_czk (stejny princip jako tam).
  const montazCzk = Math.round(grandTotal * (pricing.montaz_pct || 0) / 100);

  const itemGroups = new Map();
  catParts.forEach((e, i) => {
    const r = rows[i];
    const lenRounded = r.lengthMm != null ? Math.round(r.lengthMm) : null;
    const boardDimKey = r.widthMm != null ? `${Math.round(r.widthMm)}x${Math.round(r.heightMm)}` : null;
    const key = `${e.catPart.id}|${lenRounded}|${boardDimKey}`;
    const unit = r.price != null ? Math.round(r.price) : 0;
    let g = itemGroups.get(key);
    if (g) { g.qty += 1; } else {
      g = {
        name: `${partDisplayName(e.catPart)} (${e.catPart.layer})`,
        dim: lenRounded != null ? lenRounded + " mm" : (boardDimKey ? Math.round(r.widthMm) + " × " + Math.round(r.heightMm) + " mm" : "-"),
        unit_price: unit, qty: 1,
      };
      itemGroups.set(key, g);
    }
  });
  const bom = [...itemGroups.values()].map(g => ({ name: g.name, dim: g.dim, qty: g.qty, unit_price: g.unit_price, total: Math.round(g.unit_price * g.qty) }));

  return {
    bom,
    price_summary: {
      // `count` musi kopirovat STEJNY filtr jako produkce (scene.html: entries =
      // entries.filter(e => !isStampPart(e)) PRED vypoctem entries.length) -
      // bez !isStampPart tu vyjde vyssi cislo u kazde orazitkovane sestavy.
      // Zmereno 2026-09-11 na 279 (89 ulozeno vs 99 bez filtru, rozdil =
      // presne 10 razitkovych dilu) a na 332 (96 vs 108, rozdil 12).
      count: parts.filter(p => !isCarBodyPart(p) && !isStampPart(p) && !isKontrolniPart(p)).length,
      weight_kg: Math.round(totalW * 1000) / 1000,
      material_czk: materialCzk,
      cut_czk: cutCzk,
      profile_flat_fee_czk: profileFlatFeeCzk,
      joint_czk: jointCzk,
      joint_count: totalJoints,
      joint_rule_version: JOINT_RULE_VERSION,
      accessory_czk: accessoryCzk,
      scene_price_coefficient_applied: pricing.scene_price_coefficient || pricing.price_coefficient || 1,
      packaging_czk: packagingCzk,
      total_czk: Math.round(grandTotal),
      montaz_pct_applied: pricing.montaz_pct || 0,
      montaz_czk: montazCzk,
    },
  };
}

function main() {
  const args = process.argv.slice(2);
  const DRY = args.includes("--dry-run");
  const idIdx = args.indexOf("--id");
  const onlyId = idIdx >= 0 ? parseInt(args[idIdx + 1], 10) : null;

  const { map: katalog, pricing } = nactiKatalog();
  const sestavy = JSON.parse(fs.readFileSync(ASM_DUMP, "utf8"));

  if (!DRY) fs.mkdirSync(OUT_DIR, { recursive: true });

  const vysledky = [];
  let chyby = 0;
  for (const s of sestavy) {
    if (onlyId != null && s.id !== onlyId) continue;
    let d;
    try { d = JSON.parse(s.data); } catch (e) { console.error(`id=${s.id}: nelze parsovat data JSON: ${e.message}`); chyby++; continue; }
    const gapy = [];
    let vysl;
    try { vysl = computeAssemblyBomAndPrice(d.parts || [], katalog, pricing, gapy); }
    catch (e) { console.error(`id=${s.id} "${s.name}": VYJIMKA: ${e.message}`); chyby++; continue; }
    vysledky.push({ id: s.id, name: s.name, gapy, bom: vysl.bom, price_summary: vysl.price_summary, puvodniData: d });
    if (gapy.length) console.log(`  id=${s.id} "${s.name.slice(0, 50)}" - ${gapy.length} nalezu: ${gapy[0]}`);
  }

  console.log(`\nZpracovano: ${vysledky.length} sestav, chyb: ${chyby}`);
  const sGapy = vysledky.filter(v => v.gapy.length);
  console.log(`Sestav s nejakym nalezem (chybejici GLB/katalog): ${sGapy.length}`);
  const totalJointsAll = vysledky.reduce((s, v) => s + (v.price_summary.joint_count || 0), 0);
  const totalJointCzkAll = vysledky.reduce((s, v) => s + (v.price_summary.joint_czk || 0), 0);
  console.log(`Spoje celkem (vsechny zpracovane sestavy): ${totalJointsAll} ks = ${totalJointCzkAll.toLocaleString("cs-CZ")} Kc`
    + ` (joint_price=${pricing.joint_price_czk} Kc/spoj)`);

  if (DRY) {
    console.log("\n--- UKAZKA (prvnich 3 sestav) ---");
    vysledky.slice(0, 3).forEach(v => {
      console.log(`\nid=${v.id} "${v.name}"`);
      console.log(`  price_summary:`, JSON.stringify(v.price_summary));
      console.log(`  bom (${v.bom.length} radku), prvnich 5:`);
      v.bom.slice(0, 5).forEach(r => console.log(`    ${r.qty}x ${r.name} (${r.dim}) á ${r.unit_price} Kc = ${r.total} Kc`));
    });
    console.log("\n--- DRY RUN: nic se nezapsalo ---");
    fs.writeFileSync("/tmp/backfill_dry_run_result.json", JSON.stringify(vysledky, null, 1));
    console.log("Plny vysledek: /tmp/backfill_dry_run_result.json");
    return;
  }

  // zapis: jeden JSON soubor na sestavu (id, novy bom/price_summary) - DB
  // zapis dela navazny Python skript (pymysql neni v Node), tenhle skript
  // jen SPOCITA. Zadny primy zapis do DB odtud.
  for (const v of vysledky) {
    fs.writeFileSync(`${OUT_DIR}/assembly_${v.id}.json`,
      JSON.stringify({ id: v.id, bom: v.bom, price_summary: v.price_summary }, null, 1));
  }
  console.log(`\nVypocteno a zapsano ${vysledky.length} souboru do ${OUT_DIR}/`);
  console.log("Dalsi krok: scripts/2026-09-06_zapis_bom_do_db.py");
}

main();
