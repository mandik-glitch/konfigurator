// SDÍLENÝ zdroj geometrických funkcí pro spojování profilů/příslušenství -
// POUŽÍVÁ JE JAK ŽIVÁ 3D SCÉNA (webapp/scene.html, přes <script src>, běží
// v prohlížeči zákazníka/admina), TAK Node.js ověřovací nástroje pro boty
// (scripts/2026-08-18_scene_geometry_lib.js, .claude/skills/3d-scena-spoje).
//
// Robert 2026-08-18/19 ("potřebujeme v podstatě dvě scény - tu pro prohlížeč
// a tu pro bota... musí být sdílená data"): PŮVODNĚ existovaly DVĚ nezávislé
// kopie téhle logiky (jedna inline ve scene.html, druhá jako ruční kopie v
// Node.js knihovně) - riziko, že se časem rozejdou a bot by testoval
// neaktuální chování. Tenhle soubor je teď JEDINÝ zdroj pravdy pro obě
// strany - žádná kopie navíc.
//
// PŘESUNUTO SEM ze scene.html beze změny chování (jen odstraněno z inline
// <script id="app-script">, nahrazeno <script src="js/scene-geometry-
// shared.js"> PŘED app-script blokem) - viz VLASTNOSTI_PROFILU.md a
// AGENTS_LOG.md 2026-08-18/19 pro historii/zdůvodnění jednotlivých funkcí.
//
// DŮLEŽITÉ pro budoucí úpravy: tohle je JEDINÝ soubor, který se edituje -
// scene.html i Node.js nástroje ho načítají stejný, beze změny. `.git/hooks/
// pre-commit` má kontrolu, která hlídá, že se komentáře/duplicity v
// scripts/2026-08-18_scene_geometry_lib.js (starší, dnes už jen "compat"
// wrapper) nerozejdou - viz ten soubor.
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    let three;
    try {
      three = require("three");
    } catch (e) {
      if (e && e.code === "MODULE_NOT_FOUND") {
        // bot8 2026-08-19 (gap audit): bez tohohle je chyba jen holy
        // "Cannot find module 'three'" s Node.js require-stackem, beze
        // stopy k tomu, ze reseni je `npm install` v ROOTU repa
        // (/opt/konfigurator/package.json), NE ve scripts/.
        e.message += " -- 'three' chybi. Spust `npm install` v ROOTU repa" +
          " (/opt/konfigurator), ne ve scripts/ - viz package.json a" +
          " .claude/skills/3d-scena-spoje/SKILL.md.";
      }
      throw e;
    }
    module.exports = factory(root, three);
  } else {
    factory(root, root.THREE);
  }
})(typeof self !== "undefined" ? self : this, function (root, THREE) {

// DULEZITE ZJISTENI: nase GLB profily maji delkovou osu (nejdelsi rozmer bbox)
// vzdy podel LOKALNIHO Y - overeno primo v exportovanych souborech (trimesh
// extents ~[40, 1000, 40] apod.). To znamena, ze bez dalsi upravy by dil s
// identity rotaci stal svisle (lokalni Y = svetove Y = nahoru), NE lezel na
// zemi. LENGTH_TILT dil "sklopi" na bok (delka podel sveta Z), a teprve na to
// se aplikuje azimutalni otoceni kolem svisle osy Y (rotation_deg) - tak vzniknou
// skutecne pravouhle tvary v pudorysu (ctverec, L, T), misto svislych "vezi".
// bot8 2026-08-19 (gap audit): Object.freeze() misto holeho `new THREE.
// Quaternion()` - tenhle singleton se ted exportuje pres modulovou hranici
// (browser global i Node require()), takze ho muze omylem primo zmutovat
// (.premultiply/.multiply/.set...) kdokoli budouci na obou stranach, misto
// aby si vzal .clone() jako jediny stavajici volajici (baseQuaternion nize).
// Zamrazeni to zmeni z tiche korupce sdileneho stavu (projevi se nekde
// uplne jinde, tezko dohledatelne) na okamzity hlasity TypeError presne na
// miste chyby - .clone() dal funguje normalne (vraci NEzamrazenou kopii).
const LENGTH_TILT = Object.freeze(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -Math.PI / 2));

function baseQuaternion(rotYdeg, orient) {
  const yaw = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), ((rotYdeg || 0) * Math.PI) / 180);
  if (orient === "vertical") return yaw; // delka zustava svisla (puvodni orientace dilu) - pro "prostorovy" svisly dil
  const q = LENGTH_TILT.clone();
  q.premultiply(yaw);
  return q;
}

// Robert 2026-08-11 ("rozky maji zobaky, a ty maji zapadnout do drazky do
// slotu, takze se zobak schova a dolehne to na steny rozku"): u
// prislusenstvi (uhelniky, rozky) se dosud dosedaci rovina brala z
// OBALOVEHO KVADRU - jenze ten konci na SPICCE zobacku, takze se dil o
// zobacek oprel a stal odsazeny od profilu misto aby zobacek zajel do
// drazky. Tahle funkce najde skutecnou DOSEDACI STENU: pro dany smer
// projde trojuhelniky, jejichz normala miri timhle smerem, a vrati
// rovinu s NEJVETSI plochou (steny rozku maji radove vetsi plochu nez
// spicka zobacku). Kdyz zadna vyrazna stena neni, vrati kraj kvadru
// (puvodni chovani) - dily bez zobacku se tedy chovaji jako dosud.
function dominantWallCoord(obj, axisIdx, sign, boxMin, boxMax) {
  const edge = sign > 0 ? boxMax.getComponent(axisIdx) : boxMin.getComponent(axisIdx);
  const depth = boxMax.getComponent(axisIdx) - boxMin.getComponent(axisIdx);
  if (!(depth > 0)) return edge;
  // Zobacek je mala cast dilu - stenu hledame jen v teto vnejsi vrstve.
  const searchDepth = Math.min(depth * 0.45, 25);   // mm
  const BINS = 60;
  const bins = new Float64Array(BINS);
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  const e1 = new THREE.Vector3(), e2 = new THREE.Vector3(), nrm = new THREE.Vector3();
  let total = 0;
  obj.updateMatrixWorld(true);
  obj.traverse(node => {
    if (!node.isMesh || !node.geometry || !node.geometry.attributes || !node.geometry.attributes.position) return;
    const geom = node.geometry;
    const pos = geom.attributes.position;
    const index = geom.index;
    const triCount = index ? index.count / 3 : pos.count / 3;
    for (let t = 0; t < triCount; t++) {
      const ia = index ? index.getX(t * 3) : t * 3;
      const ib = index ? index.getX(t * 3 + 1) : t * 3 + 1;
      const ic = index ? index.getX(t * 3 + 2) : t * 3 + 2;
      vA.fromBufferAttribute(pos, ia).applyMatrix4(node.matrixWorld);
      vB.fromBufferAttribute(pos, ib).applyMatrix4(node.matrixWorld);
      vC.fromBufferAttribute(pos, ic).applyMatrix4(node.matrixWorld);
      e1.subVectors(vB, vA); e2.subVectors(vC, vA);
      nrm.crossVectors(e1, e2);
      const area2 = nrm.length();
      if (area2 <= 1e-9) continue;
      // jen steny KOLME na hledany smer (normala miri ven timhle smerem)
      if (nrm.getComponent(axisIdx) / area2 * sign < 0.85) continue;
      const coord = (vA.getComponent(axisIdx) + vB.getComponent(axisIdx) + vC.getComponent(axisIdx)) / 3;
      const fromEdge = sign > 0 ? (edge - coord) : (coord - edge);
      if (fromEdge < -0.01 || fromEdge > searchDepth) continue;
      const bin = Math.min(BINS - 1, Math.max(0, Math.floor(fromEdge / searchDepth * BINS)));
      bins[bin] += area2 / 2;
      total += area2 / 2;
    }
  });
  if (total <= 0) return edge;
  let bestBin = 0, bestArea = 0;
  for (let i = 0; i < BINS; i++) {
    if (bins[i] > bestArea) { bestArea = bins[i]; bestBin = i; }
  }
  // Stena musi byt vyrazna (aspon 25 % nalezene plochy v teto vrstve),
  // jinak radeji zustava puvodni kraj kvadru.
  if (bestArea < total * 0.25) return edge;
  const offset = (bestBin + 0.5) / BINS * searchDepth;
  // Zanedbatelny posun = dil zadny zobacek nema, drz presne kraj obalky
  // (at se u techto dilu chova vse uplne stejne jako pred zmenou).
  if (offset < 0.3) return edge;
  return sign > 0 ? edge - offset : edge + offset;
}

function computeConnectorsLocal(obj, opts) {
  const wallSnap = !!(opts && opts.wallSnap);
  const box = new THREE.Box3().setFromObject(obj);
  const size = new THREE.Vector3(); box.getSize(size);
  const center = new THREE.Vector3(); box.getCenter(center);
  const dims = [size.x, size.y, size.z];
  let axisIdx = 0;
  if (dims[1] > dims[axisIdx]) axisIdx = 1;
  if (dims[2] > dims[axisIdx]) axisIdx = 2;
  const half = dims[axisIdx] / 2;
  const axisVec = new THREE.Vector3(axisIdx === 0 ? 1 : 0, axisIdx === 1 ? 1 : 0, axisIdx === 2 ? 1 : 0);
  // druha nejvetsi (prurezova) osa - pouziva se pro "T" spoj uprostred delky dilu
  let crossIdx = (axisIdx + 1) % 3;
  const altIdx = (axisIdx + 2) % 3;
  if (dims[altIdx] > dims[crossIdx]) crossIdx = altIdx;
  const crossVec = new THREE.Vector3(crossIdx === 0 ? 1 : 0, crossIdx === 1 ? 1 : 0, crossIdx === 2 ? 1 : 0);
  // U prislusenstvi se dosedaci rovina posouva na skutecnou stenu (viz
  // dominantWallCoord vyse); u profilu zustava kraj obalky jako dosud.
  const wallHalf = (idx, sign, fallbackHalf) => {
    if (!wallSnap) return fallbackHalf;
    const coord = dominantWallCoord(obj, idx, sign, box.min, box.max);
    return Math.abs(coord - center.getComponent(idx));
  };
  const connectors = [
    { point: center.clone().addScaledVector(axisVec, wallHalf(axisIdx, 1, half)), normal: axisVec.clone(), kind: "end" },
    { point: center.clone().addScaledVector(axisVec, -wallHalf(axisIdx, -1, half)), normal: axisVec.clone().negate(), kind: "end" },
    { point: center.clone(), normal: crossVec.clone(), kind: "mid" },
  ];
  // Pulsirky prurezu (obe osy KOLME na delku, s jejich polovicnimi sirkami) -
  // pouzivaji se pro presne dolehani spoju plochou na plochu (viz
  // crossAxisHalfWidthTowardDirection a attachEntryToParent nize). Overeno
  // na referencnim souboru "spojeni vice profilu.fbx" od Roberta.
  const otherIdx = [0, 1, 2].filter(i => i !== axisIdx);
  connectors.crossAxesLocal = otherIdx.map(i => ({
    dir: new THREE.Vector3(i === 0 ? 1 : 0, i === 1 ? 1 : 0, i === 2 ? 1 : 0),
    halfWidth: dims[i] / 2,
  }));

  // Robert 2026-07-24 ("promysli do hloubky moznosti magnetovani..."): nove
  // konektory typu "face" - jeden na kazdou ze 4 podelnych sten profilu
  // (obe strany obou prurezovych os). Potrebne pro detekci napojeni
  // "plocha na plochu" (bocni laminace, kolmy rost) - viz VLASTNOSTI_
  // PROFILU.md sekce 2k. PRIDAVAJI SE AZ NA KONEC pole (indexy 3-6) - VSECHEN
  // stavajici kod pristupuje ke "end"/"mid" konektorum bud pevnymi indexy
  // 0/1/2, nebo filtrem podle .kind, takze pridani nic nerozbije.
  otherIdx.forEach(i => {
    const faceNormal = new THREE.Vector3(i === 0 ? 1 : 0, i === 1 ? 1 : 0, i === 2 ? 1 : 0);
    const faceHalf = dims[i] / 2;
    const otherCrossIdx = otherIdx.find(j => j !== i);
    const faceMeta = {
      kind: "face",
      faceLength: dims[axisIdx],   // delka steny podel osy profilu
      faceWidth: dims[otherCrossIdx], // sirka steny (druhy prurezovy rozmer)
    };
    // bot8 2026-08-19 (gap audit kolo 2): drive `axisVec: axisVec.clone()`
    // bylo soucasti faceMeta a pres `...faceMeta` se STEJNA Vector3 instance
    // sdilela mezi OBEMA push() konektory (kladny i zaporny normal) - stejna
    // trida chyby jako LENGTH_TILT (sdileny mutovatelny objekt pres hranici
    // funkce). Zjisteno primo: conns[3].axisVec === conns[4].axisVec bylo
    // true, mutace jednoho (.negate()) tise zmenila i druhy. Kazdy push() ted
    // dostava svuj VLASTNI clone.
    connectors.push(
      { point: center.clone().addScaledVector(faceNormal, wallHalf(i, 1, faceHalf)), normal: faceNormal.clone(), axisVec: axisVec.clone(), ...faceMeta },
      { point: center.clone().addScaledVector(faceNormal, -wallHalf(i, -1, faceHalf)), normal: faceNormal.clone().negate(), axisVec: axisVec.clone(), ...faceMeta },
    );
  });

  // Robert 2026-08-12 ("oznaci plochy objektu podle geometrie a ja to klikem
  // potvrdim"): kdyz ma dil ULOZENE geometricke plochy (viz
  // detectGeometricFaces + panel 🎓 Naucit napojeni), pridaji se jako
  // DALSI konektory typu "face" - Kontrola ploch/Place All/Pozice
  // uhelniku uz je automaticky pouziji, protoze vsechny pracuji nad
  // stejnym connectorsLocal polem. Puvodnich 6 box-konektoru zustava
  // (nenahrazuji se) - u nekterych dilu se muze hodit obojí zaroven.
  if (opts && Array.isArray(opts.geoFaces)) {
    opts.geoFaces.forEach(f => {
      const faceArea = Math.max(1, (f.area || 100));
      const approxSide = Math.sqrt(faceArea);
      connectors.push({
        point: new THREE.Vector3(f.x, f.y, f.z),
        normal: new THREE.Vector3(f.nx, f.ny, f.nz).normalize(),
        kind: "face",
        faceLength: approxSide, faceWidth: approxSide,
        axisVec: axisVec.clone(),
        isGeoFace: true,
      });
    });
  }
  return connectors;
}

// Zjisti, o kolik "vycuhuje" prurez dilu (entry) ve smeru worldDir od jeho
// stredove/delkove osy - tedy polovinu sirky dilu v tom smeru. Pouziva se na
// OBOU stranach spoje: 1) kolik se ma pripojovany dil odsadit OD rodice, aby
// nesahal skrz jeho stred, 2) kolik se ma "zasunout" podel delky rodice, aby
// nepresahoval za jeho spicku. Pracuje jen s 90-stupnovymi natocenimi, takze
// smer bud presne sedi s nekterou prurezovou osou (projekce ~1), nebo je na
// ni kolmy (~0) - proto staci prah 0.5.
function crossAxisHalfWidthTowardDirection(connectorsLocal, quat, worldDir) {
  let best = 0;
  (connectorsLocal.crossAxesLocal || []).forEach(ax => {
    const worldAxis = ax.dir.clone().applyQuaternion(quat).normalize();
    const proj = Math.abs(worldAxis.dot(worldDir));
    if (proj > 0.5) best = Math.max(best, ax.halfWidth);
  });
  return best;
}

function worldConnectorsOf(entry) {
  entry.object3d.updateMatrixWorld(true);
  return entry.connectorsLocal.map(c => {
    const out = {
      point: c.point.clone().applyMatrix4(entry.object3d.matrixWorld),
      normal: c.normal.clone().transformDirection(entry.object3d.matrixWorld).normalize(),
      kind: c.kind,
      owner: entry,
    };
    // Robert 2026-07-24 (magnet/snap): "face" konektory nesou navic delku
    // steny a smer delkove osy dilu - potrebne pro detekci plocha-na-plochu
    // (viz findConnectionCandidates nize). Zpetne kompatibilni - "end"/"mid"
    // konektory tyto vlastnosti nemaji, out.axisVec/faceLength/faceWidth
    // zustanou proste nedefinovane.
    if (c.axisVec) out.axisVec = c.axisVec.clone().transformDirection(entry.object3d.matrixWorld).normalize();
    if (c.faceLength != null) out.faceLength = c.faceLength;
    if (c.faceWidth != null) out.faceWidth = c.faceWidth;
    return out;
  });
}

function firstFreeConnectorIndex(entry, kinds) {
  kinds = kinds || ["end"];
  if (!entry.usedConn) entry.usedConn = new Set();
  for (let i = 0; i < entry.connectorsLocal.length; i++) {
    if (kinds.includes(entry.connectorsLocal[i].kind) && !entry.usedConn.has(i)) return i;
  }
  return null;
}

function linkJointPeers(a, b) {
  if (!a || !b || a === b) return;
  a.licPeers = a.licPeers || new Set();
  b.licPeers = b.licPeers || new Set();
  a.licPeers.add(b);
  b.licPeers.add(a);
}

function isProfilePart(part) {
  return !!(part.length_mm && part.cross_section_mm && part.cross_section_mm[0] != null);
}

// ⭐ Ochranne razitko (logo LOGIMAN.CZ + vypln drazky pod nim) NENI dil
// k vyrobe: nesmi do kusovniku, do ceny, do poctu spoju ani do koliznich
// kontrol. Od 2026-09-11 se razitka propisuji primo do dat sestavy (pri
// zarazeni do slozky stromu), takze je uvidi VSECHNO, co prochazi
// `data.parts` - ne jen render. Kazde takove misto musi tenhle filtr
// pouzit.
//
// Proc zrovna tady: pravidlo projektu ("co umi 3D scena skrze admina, musi
// umet Node.js skrze bota uplne stejne") - predikat potrebuje scene.html
// i davkove skripty, takze patri do sdileneho souboru, ne inline.
//
// PYTHON PROTEJSEK: `je_razitko()` ve scripts/razitkovac.py - meni se OBA
// najednou. Tam je i duvod, proc maji oba dily JEDEN prefix (do 2026-09-11
// mela vypln prefix `vypln-`, ktery uz patri generatoru hornich bloku, a
// mazaci skript ji proto mazal a loga nechaval viset nad otevrenymi
// drazkami).
//
// Bere i stare `logo-ochrana-N` bez druheho segmentu (sestava 134 z rucniho
// dema 2026-09-08) - prefix sedi i na nej.
const STAMP_ROLE_PREFIX = "logo-ochrana";

function isStampPart(partOrRole) {
  const role = (partOrRole && typeof partOrRole === "object")
    ? (partOrRole.role || "") : (partOrRole || "");
  return String(role).startsWith(STAMP_ROLE_PREFIX);
}

// ⭐ Kontrolni pomucka (Robert 2026-09-12, pres bot3: "vloz to normalne
// jako ostatni tvary... mimo kusovnik, cenu i spoje - stejny filtr jako
// razitka") - napr. "Obložení karoserie (kontrola)", panely obtazene z
// Etsy sablony pro vizualni porovnani s realnou karoserii K-075. STEJNY
// princip a STEJNA mista jako STAMP_ROLE_PREFIX/isStampPart vyse - jen
// jiny prefix, protoze duvod vzniku je jiny (kontrola/porovnani, ne
// ochranna znacka). Kazde misto, ktere pouziva isStampPart, MUSI pouzit
// i tenhle filtr (BOM/cena, kolizni kontrola karoserie, a navic vyhradne
// tady: NIKDY se nesmi dostat do ulozenych dat sestavy/tvaru - proto se
// filtruje uz v collectSelectedEntriesForSave(), ne az pri vypoctu ceny).
const KONTROLNI_ROLE_PREFIX = "kontrolni-pomucka";

function isKontrolniPart(partOrRole) {
  const role = (partOrRole && typeof partOrRole === "object")
    ? (partOrRole.role || "") : (partOrRole || "");
  return String(role).startsWith(KONTROLNI_ROLE_PREFIX);
}

// ⭐ Karoserie (vozidlo) - referencni geometrie ("car_body_<car_bodies.id>"),
// ne skutecny dil k vyrobe (zadny price_czk/weight_kg v katalogu - viz
// fetch_katalog_parts). Robert 2026-09-13 ("proc to nesedi se scenou?" -
// Pocet dilu/Prislusenstvi (ks) v refreshSummary skoclo +3, kdyz do sceny
// pribyla karoserie): na rozdil od isStampPart/isKontrolniPart (role-based
// prefix) je karoserie identifikovana PART_ID prefixem, ne rolí - a tenhle
// filtr chybel VSUDE (computeAssemblyBomAndPrice, refreshSummary, kontrolni
// kusovnik) krome scripts/2026-09-06_backfill_bom_price.js (mel vlastni
// nezavislou kopii stejne kontroly). Cena/hmotnost tim postizene nebyly
// (null u karoserie v katalogu = 0 prispevek), jen SUROVE POCTY dilu.
// Prijima entry ({part:{id}}), ulozeny part-spec ({part_id}), katalogovy
// zaznam primo ({id}) nebo rovnou string id - stejna flexibilita jako
// ostatni volajici tuhle funkci potrebuji na ruznych mistech.
const CAR_BODY_ID_PREFIX = "car_body_";

function isCarBodyPart(entryOrPartOrId) {
  let id;
  if (entryOrPartOrId && typeof entryOrPartOrId === "object") {
    id = (entryOrPartOrId.part && entryOrPartOrId.part.id) || entryOrPartOrId.part_id || entryOrPartOrId.id;
  } else {
    id = entryOrPartOrId;
  }
  return String(id || "").startsWith(CAR_BODY_ID_PREFIX);
}

function attachEntryToParent(entry, parentEntry, quat, forcedParentConnIdx, childConnIdx, opts) {
  opts = opts || {};
  // DULEZITE (oprava bugu): u vodorovnych dilu je jedno, ktery ze 2 koncu se
  // pouzije jako "pripojovaci" (konektor 0 vs 1) - LENGTH_TILT je symetricky.
  // Ale u SVISLYCH dilu (orient:"vertical", zadna tilt rotace) uz konektor 0
  // vzdy znamena lokalni +Y = "horni" konec a konektor 1 "dolni" konec, a to
  // bez ohledu na natoceni. Kdyby se svisly dil vzdy pripojoval konektorem 0
  // (jako predtim), rostl by od bodu pripojeni SMEREM DOLU misto nahoru -
  // presne tenhle bug mel dosavadni "prostorovy L". childConnIdx (default 0)
  // proto pro svisle dily nastavuje volajici (runAIPlan) na 1, aby se
  // pripojoval "spodek" dilu a "vrchol" zustal volny, rostouci vzhuru.
  childConnIdx = childConnIdx || 0;
  entry.object3d.quaternion.copy(quat);
  entry.object3d.position.set(0, 0, 0);
  entry.object3d.updateMatrixWorld(true);

  let parentConnIdx;
  if (forcedParentConnIdx != null) {
    // vyslovny pozadavek (napr. T-spoj na stred, nebo trojcestny roh) - obsazenost
    // rodicovskeho konektoru zde zamerne nekontrolujeme, aby slo sdilet jeden bod
    // vice dily (realny roh, kam se sejdou 3 profily).
    parentConnIdx = forcedParentConnIdx;
  } else {
    parentConnIdx = firstFreeConnectorIndex(parentEntry);
    if (parentConnIdx === null) return false; // rodic uz nema volny konec
  }

  const parentConnWorld = worldConnectorsOf(parentEntry)[parentConnIdx];

  // PRESNE DOLEHANI PLOCHOU NA PLOCHU (ne prunik stredem) - overeno na
  // referencnim FBX "spojeni vice profilu" od Roberta primym vypoctem
  // souradnic: rodic zustava "pruchozi" (cely, nezkraceny), pripojovany dil
  // se posune ve DVOU krocich:
  //   1) VEN od stredove osy rodice, ve smeru, kterym se sam vydava, o
  //      polovinu SIRKY RODICE v tom smeru - jinak by prochazel skrz jeho
  //      stred (Robertuv pozadavek "nemuzou do sebe vstupovat").
  //   2) ZPET podel DELKOVE osy rodice (dovnitr, ne ven), o polovinu SIRKY
  //      PRIPOJOVANEHO DILU v tom smeru - jinak by presahoval za spicku
  //      rodice mimo jeho telo, misto aby lipl presne na jeho koncovou hranu.
  // U "mid" konektoru (T-spoj doprostred boku) se krok 2 vynecha - tam zadna
  // "spicka" neni, pripojujeme se doprostred delky rodice.
  // OPRAVA (2. pokus - prvni pokus prilis preskakoval offset u svislych dilu a
  // vratil se prunik, viz Robertovo "prostorove objekty jsou spatne"):
  // Krok 1 (odsazeni OD stredove osy rodice ve smeru, kam se dil vydava) MUSI
  // platit VZDY, i pro svisly sloupek - jinak sloupek pulkou tela zapadne do
  // rodicovskeho profilu (presne to "vstupovani do sebe", co jsme resili).
  // Krok 2 (zpetne zasunuti podel DELKOVE osy rodice, aby dil nepresahl za
  // jeho spicku) davá smysl JEN mezi dvema dily VE STEJNE (vodorovne) rovine -
  // u svisleho spoje zadna "spicka ve stejnem smeru" neexistuje (sloupek jde
  // kolmo), takze se tam vynecha - jinak zbytecne vychyluje sloupek do strany
  // a rozjede horni ram vuci spodnimu.
  const otherChildConnIdx = 1 - childConnIdx;
  const childDirWorld = entry.connectorsLocal[otherChildConnIdx].point.clone()
    .sub(entry.connectorsLocal[childConnIdx].point)
    .applyQuaternion(quat)
    .normalize();
  const target = parentConnWorld.point.clone();
  const isVerticalJoint = childConnIdx !== 0 || parentEntry.vertical;
  const parentHalf = crossAxisHalfWidthTowardDirection(parentEntry.connectorsLocal, parentEntry.object3d.quaternion, childDirWorld);
  target.addScaledVector(childDirWorld, parentHalf);
  if (parentConnWorld.kind !== "mid" && !isVerticalJoint) {
    const childHalf = crossAxisHalfWidthTowardDirection(entry.connectorsLocal, quat, parentConnWorld.normal);
    target.addScaledVector(parentConnWorld.normal, -childHalf);
  }

  const rotatedLocal = entry.connectorsLocal[childConnIdx].point.clone().applyQuaternion(quat);
  const pos = target.clone().sub(rotatedLocal);
  entry.object3d.position.copy(pos);
  entry.object3d.updateMatrixWorld(true);

  // Robert 2026-07-24: zivy nahled (preview) pri najeti mysi na tlacitko v
  // panelu "Moznosti napojeni" - potrebuje zmenit jen GEOMETRII (pozice/
  // natoceni), bez trvaleho zaznamenani spoje (usedConn/jointCount), aby
  // slo pri opusteni tlacitka vratit zpet beze stopy. opts.skipBookkeeping
  // (vychozi false - vsichni stavajici volajici se chovaji presne jako
  // drive) tohle umoznuje.
  if (!opts.skipBookkeeping) {
    // Robert 2026-08-16 ("rám je špatně" -> vysledovano az sem, "Prostorové
    // L"/"Kvádr" maji na spolecnem rohu falesnou oranzovou sipku): drive se
    // usedConn na rodici nastavovalo jen pri AUTO-VYBERU konektoru
    // (forcedParentConnIdx == null), NE pri vyslovnem pozadavku (T-spoj,
    // trojcestny roh - viz komentar par radku vyse). Duvod pro vynechani
    // OBSAZENOSTNI KONTROLY u forced rezimu (aby slo sdilet 1 bod vice dily)
    // je spravny a zustava - ale zapis SAMOTNY (marker "tenhle konektor uz
    // neco pouziva") na tom nezavisi: firstFreeConnectorIndex (jediny cti
    // usedConn pro gating) se vola JEN ve vetvi forcedParentConnIdx==null
    // vyse, takze oznaceni usedConn i ve forced rezimu nemuze zablokovat
    // dalsi sdileny pripoj na stejny bod (viz "trojcestny roh" o par radku
    // vyse - oba pripoje na stejny forced index projdou beze zmeny). Bez
    // teto opravy zustaval spolecny roh "Prostoroveho L"/"Kvadru" datove
    // volny (usedConn nikdy nenastaveno), takze refreshEndpointMarkers() na
    // nem kreslil falesnou oranzovou sipku, i kdyz uz na nem realne sedely
    // 2 dalsi dily.
    parentEntry.usedConn = parentEntry.usedConn || new Set();
    parentEntry.usedConn.add(parentConnIdx);
    entry.usedConn = new Set([childConnIdx]); // tento konektor tohoto dilu je ted spojeny s rodicem
  }
  // Cela plocha pripojovaneho konce je ted pritisknuta na stenu rodice (viz
  // PRAVIDLA_SPOJU.md 2d) - zvenku neni videt. (Puvodne se tu podle
  // tohohle priznaku vynechavalo kresleni textury cela profilu - ta byla
  // na Robertovu zadost 2026-07-24 cela odstranena, priznak ale zustava
  // ulozeny pro pripadne budouci pouziti.)
  // Realny fyzicky spoj (viz PRAVIDLA_SPOJU.md sekce 2d, potvrzeno
  // Robertem 2026-07-23): celo jednoho profilu (zavit) dolehne na stenu
  // druheho (otvor) - JEDEN šroub, JEDEN spoj, at uz je to konec-na-konec
  // (L) nebo konec-na-bok kdekoli po delce (T). Kazde volani teto funkce =
  // presne 1 takovy spoj - pocitame ho JEN na "child" strane (entry), aby
  // se pri souctu v refreshSummary() nepocitalo 2x (jednou za kazdy
  // ucastnici se konec) - viz oprava "L tvar ukazoval 2 spoje misto 1".
  // jointCount je citac (ne bool) - jeden dil (napr. sloupek u kvadru) muze
  // mit VICE spoju (dole k ramu, nahore k dalsimu ramu).
  if (!opts.skipBookkeeping) {
    entry.hiddenEndConn = entry.hiddenEndConn || new Set();
    entry.hiddenEndConn.add(childConnIdx);
    entry.vertical = childConnIdx !== 0; // viz isVerticalJoint vyse - potrebuje i pripadny DALSI dil, ktery se pripoji na tento
    entry.jointCount = (entry.jointCount || 0) + 1;
    linkJointPeers(entry, parentEntry);
    // Robert 2026-08-03 ("spojovani profilu na stejnem principu jako
    // prislusenstvi"): zaznamenej "posledni aktivni spoj" pro obe strany -
    // jen mezi DVEMA PROFILY (ne kdyz je jedna strana prislusenstvi, to ma
    // svuj vlastni attachedTo/spin system vyse) - viz sortedProfileJointCandidates
    // nize, pouziva se pro R-cykleni mezi jiz spojenymi profily.
    // OPRAVA (2026-08-03, Robertovo hlaseni "obraceny L a oba prostorove L
    // nelze vlozit"): attachEntryToParent se vola i na VIRTUALNI entries bez
    // .part (viz virtualEntry() - pouziva outerCornerOfPositionJoin/
    // spatialLOuterCornerMin pro pouhe zmereni rohu, PRED skutecnym
    // vlozenim do sceny) - isProfilePart(undefined) tam shodilo vyjimku a
    // potichu preseklo cely buildLReversedShape/buildSpatialLShape*
    // jeste PRED pridanim čehokoli do sceny. Explicitni "entry.part &&"
    // guard nejdriv, at se isProfilePart vubec nezavola bez part.
    if (entry.part && parentEntry.part && isProfilePart(entry.part) && isProfilePart(parentEntry.part)) {
      entry.lastJoint = { otherEntry: parentEntry, myConnIdx: childConnIdx, otherConnIdx: parentConnIdx, iHoldCount: true };
      parentEntry.lastJoint = { otherEntry: entry, myConnIdx: parentConnIdx, otherConnIdx: childConnIdx, iHoldCount: false };
    }
  }
  return true;
}

// Rucne zaregistruje 1 fyzicky spoj mezi konkretnimi konektory dvou dilu -
// pro pripady, kdy geometrie vznika jinak nez pres attachEntryToParent
// (uzaviraci roh smycky, kopie horniho ramu u kvadru...), ale fyzicky spoj
// tam presto je (viz PRAVIDLA_SPOJU.md 2d).
function registerJoint(entryA, idxA, entryB, idxB) {
  entryA.usedConn = entryA.usedConn || new Set();
  entryB.usedConn = entryB.usedConn || new Set();
  entryA.usedConn.add(idxA);
  entryB.usedConn.add(idxB);
  entryB.jointCount = (entryB.jointCount || 0) + 1;
  // Robert 2026-09-13 ("tlacitko Čela oznacilo jen nektere"): attachEntryToParent
  // zaznamenava hiddenEndConn PRESNE v okamziku pripocteni jointCount (viz tam) -
  // tahle funkce to drive nedelala, takze spoje vznikle TUDY (uzaviraci roh
  // smycky apod.) byly pro znacky "Čela = spoj" neviditelne, i kdyz se
  // realne pocitaly do ceny. idxB je presne ten konektor, ktery entryB.jointCount
  // prave zvysil - stejny vztah jako childConnIdx v attachEntryToParent.
  entryB.hiddenEndConn = entryB.hiddenEndConn || new Set();
  entryB.hiddenEndConn.add(idxB);
  linkJointPeers(entryA, entryB);
  // Robert 2026-08-03 - viz stejny komentar (a oprava "entry.part &&" guard)
  // v attachEntryToParent vyse.
  if (entryA.part && entryB.part && isProfilePart(entryA.part) && isProfilePart(entryB.part)) {
    entryA.lastJoint = { otherEntry: entryB, myConnIdx: idxA, otherConnIdx: idxB, iHoldCount: false };
    entryB.lastJoint = { otherEntry: entryA, myConnIdx: idxB, otherConnIdx: idxA, iHoldCount: true };
  }
}

function applyLengthScale(entry, scaleFactor, fixedConnIdx, axisConnIdxA, axisConnIdxB) {
  const obj = entry.object3d;
  // Robert 2026-07-25: "boxedit funguje, prodlužování profilů oranžovou
  // šipkou funguje, ale nefunguje to když se použijou obojí postupně po
  // sobě" - SKUTECNA pricina: tahle funkce vzdy PRETVORILA CELY obj.scale
  // vektor na (1,1,1) a nastavila JEN delkovou osu - takze pokud uz
  // predtim BoxEdit zmenil PRUREZOVOU osu (X/Y, multiplikativne pres
  // obj.scale[comp] *= faktor, viz resizeEntryWorldAxis nize), kazde
  // DALSI volani teto funkce (dalsi tah za oranzovou sipku, nebo BoxEdit
  // zmena DELKY) tuhle prurezovou zmenu tise ZAHODILO (vratilo zpet na
  // 1). Diky tomu fungovala kazda funkce SAMA O SOBE (nova cast se ridi
  // vzdy AZ PO predchozim skalovani), ale kombinace obou v libovolnem
  // poradi ztratila tu DRIVEJSI zmenu. Oprava: menit JEN slozku scale
  // odpovidajici delkove ose, ostatni 2 slozky nechat, jak jsou (misto
  // jejich tvrdeho prepsani na 1).
  // Robert 2026-08-07 ("postavit 2D protahovani pro desky"): volitelne
  // axisConnIdxA/B (vychozi 0/1 - puvodni chovani pro profil) - deska ma
  // 4 hranove konektory ve 2 nezavislych parech (sirka [0,1], vyska
  // [2,3]), takze potrebuje urcit smer osy z JINE dvojice nez profil.
  const idxA = axisConnIdxA != null ? axisConnIdxA : 0;
  const idxB = axisConnIdxB != null ? axisConnIdxB : 1;
  const localAxis = entry.connectorsLocal[idxA].point.clone().sub(entry.connectorsLocal[idxB].point).normalize();
  const absAxis = [Math.abs(localAxis.x), Math.abs(localAxis.y), Math.abs(localAxis.z)];
  const beforeFixed = worldConnectorsOf(entry)[fixedConnIdx].point.clone();
  if (absAxis[0] > 0.9) obj.scale.x = scaleFactor;
  else if (absAxis[1] > 0.9) obj.scale.y = scaleFactor;
  else obj.scale.z = scaleFactor;
  obj.updateMatrixWorld(true);
  const afterFixed = worldConnectorsOf(entry)[fixedConnIdx].point.clone();
  const delta = beforeFixed.clone().sub(afterFixed);
  obj.position.add(delta);
  obj.updateMatrixWorld(true);
}

// Bot16, 2026-08-31 ("Roztahuj" - živé protažení vodorovné příčky +
// navazujících 2 svislých profilů, viz scene.html komentář u "====
// Roztahuj ===="). ČISTĚ NUMERICKÁ funkce (žádné THREE/DOM), proto rovnou
// tady (viz pravidlo výše v NASTROJE_SCENY.md: "píšeš-li ve scéně novou
// funkci, kterou by mohl potřebovat i Node.js skript - piš ji ROVNOU do
// scene-geometry-shared.js") - použitá živě ve scene.html i v
// scripts/2026-08-31_roztahuj_verify.js, jedna sdílená implementace.
//
// Pro požadovanou (myší taženou) světovou Y příčky spočítá OMEZENOU
// (clampnutou) Y tak, aby délka OBOU navazujících svislých profilů
// zůstala v [minLen,maxLen] (nikdy nulová/záporná délka), a vrátí
// výslednou Y příčky + novou délku/near-Y každého z nich.
//
// `verticals` = pole prvků {farY, delta, sign} - detekci samotnou (najít
// TYHLE 2 profily v aktuální scéně) dělá roztahujFindPartners přímo v
// scene.html (potřebuje živý `placed`, stejný precedent jako
// uhelnikAutPlaceForPair, který taky zůstává ve scene.html a pro Node.js
// ověření se portuje zvlášť - viz KOMPONENTY_EUROBOXY.md).
//   farY  = světové Y VZDÁLENÉHO konce profilu (ten se při tažení nehýbe)
//   delta = konstantní odsazení jeho BLÍZKÉHO konce ("švu") od Y příčky
//           v okamžiku uchopení (typicky +-T/2, ale měří se přímo, ne
//           předpokládá)
//   sign  = +1/-1, směr od švu, kterým leží vzdálený (fixní) konec
function roztahujComputeForY(desiredY, verticals, minLen, maxLen) {
  // near_Y(crossY) = crossY + delta; length(crossY) = sign*(farY - near_Y(crossY))
  // length == minLen/maxLen  =>  crossY = (farY - sign*length) - delta
  let lo = -Infinity, hi = Infinity;
  verticals.forEach(v => {
    const a = (v.farY - v.sign * minLen) - v.delta;
    const b = (v.farY - v.sign * maxLen) - v.delta;
    lo = Math.max(lo, Math.min(a, b));
    hi = Math.min(hi, Math.max(a, b));
  });
  if (hi < lo) { const m = (lo + hi) / 2; lo = m; hi = m; } // degenerovany pripad (nemelo by nastat) - aspon nespadne
  const crossY = Math.max(lo, Math.min(hi, desiredY));
  const legs = verticals.map(v => {
    const nearY = crossY + v.delta;
    const length = Math.max(minLen, Math.min(maxLen, v.sign * (v.farY - nearY)));
    return { nearY, length };
  });
  return { crossY, legs };
}

// Kolizni test proti karoserii (puvodne checkCarBodyCollisions ve
// scene.html) - PRESUNUTO SEM 2026-08-30 (Robert: "co umí 3D scéna skrze
// admina, musí umět Node.js skrze bota úplně stejně") - drive existovala
// RUCNI kopie tehle logiky v kazdem Node.js skriptu pro umisteni sestavy
// do karoserie (nohy T6/Jumpy apod.), presne to riziko rozjeti, kteremu
// ma tenhle soubor jako celek predejit (viz hlavicka souboru vyse).
// `checkCarBodyCollisions` samotna (iteruje zivy `placed`, throttling,
// obarvovani UI) ZUSTAVA ve scene.html - potrebuje zivy stav sceny,
// nema smysl v Node.js. Tady jsou jen ZNOVUPOUZITELNE cisté funkce, ktere
// `checkCarBodyCollisions` VOLA a ktere Node.js skripty pouzivaji uplne
// stejne pro vlastni kolizni testy (viz scripts/2026-08-18_scene_geometry_lib.js).
const COLLISION_MAX_EDGES_PER_PART_DEFAULT = 300;

function meshWorldEdgeSample(mesh, maxEdges) {
  const geo = mesh.geometry;
  const pos = geo && geo.attributes && geo.attributes.position;
  if (!pos) return [];
  const idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
  const edges = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (let t = 0; t < triCount; t += step) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); }
    else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    edges.push([vA.clone(), vB.clone()], [vB.clone(), vC.clone()], [vC.clone(), vA.clone()]);
  }
  return edges;
}

// BVH akcelerace (three-mesh-bvh, viz webapp/js/three-mesh-bvh.js) - cte
// globalni `MeshBVHLib` (prohlizec: <script src="js/three-mesh-bvh.js">
// primo nastavi window.MeshBVHLib; Node.js: volajici skript musi udelat
// `global.MeshBVHLib = require(".../three-mesh-bvh.js")` PRED prvnim
// volanim - proste `const MeshBVHLib = require(...)` NESTACI, bare
// identifikator by tu uvnitr modulu nebyl videt).
//
// POZOR (nalezeno bot16, 2026-08-29): `mesh.geometry.computeBoundsTree()`
// (three-mesh-bvh v0.5.24) korumpuje `geometry.boundingBox` jako VEDLEJSI
// UCINEK - `Box3().setFromObject()` volany PO tomhle muze vratit spatne
// hodnoty (u karoserie Jumpy CI14 nahlasil min.z=0 misto skutecnych
// 2024.4mm), zatimco samotny raycasting/BVH strom zustava spravny. VZDY
// zmerit Box3 PRED volanim ensureWallBoundsTree/computeBoundsTree na
// dane geometrii, nikdy az po nem - viz AGENTS_LOG.md 2026-08-29.
function ensureWallBoundsTree(mesh) {
  if (typeof MeshBVHLib === "undefined" || !mesh.geometry) return false;
  if (!mesh.geometry.boundsTree) mesh.geometry.computeBoundsTree();
  return true;
}

function setMeshesCollisionColor(wallMeshes, colliding) {
  wallMeshes.forEach(m => {
    if (!m.material) return;
    const mats = Array.isArray(m.material) ? m.material : [m.material];
    mats.forEach(mat => {
      if (!mat.color) return;
      if (colliding) {
        if (mat.userData.origColorHex == null) mat.userData.origColorHex = mat.color.getHex();
        mat.color.setHex(0xff2020);
      } else if (mat.userData.origColorHex != null) {
        mat.color.setHex(mat.userData.origColorHex);
        mat.userData.origColorHex = null;
      }
    });
  });
}

// Testuje, jestli SKUTECNA geometrie `object3d` (hranovy vzorek
// trojuhelniku kazdeho jeho meshe, az `maxEdges` na mesh) protina
// nektery z `wallMeshes` (hranovy raycasting, vyuzije BVH strom pokud
// uz byl pripraveny pres ensureWallBoundsTree). `raycasterInstance` je
// volitelny (znovupouziti napric mnoha volani bez alokace navic).
function objectCollidesWithWalls(object3d, wallMeshes, maxEdges, raycasterInstance) {
  maxEdges = maxEdges || COLLISION_MAX_EDGES_PER_PART_DEFAULT;
  const raycaster = raycasterInstance || new THREE.Raycaster();
  object3d.updateMatrixWorld(true);
  let hit = false;
  object3d.traverse(n => {
    if (hit || !n.isMesh) return;
    const edges = meshWorldEdgeSample(n, maxEdges);
    for (const [p0, p1] of edges) {
      const dir = p1.clone().sub(p0);
      const dist = dir.length();
      if (dist < 1e-6) continue;
      dir.normalize();
      raycaster.set(p0, dir);
      raycaster.far = dist;
      if (raycaster.intersectObjects(wallMeshes, false).length) { hit = true; break; }
    }
  });
  return hit;
}

const api = {
  LENGTH_TILT, baseQuaternion, dominantWallCoord, computeConnectorsLocal,
  crossAxisHalfWidthTowardDirection, worldConnectorsOf, firstFreeConnectorIndex,
  linkJointPeers, isProfilePart, STAMP_ROLE_PREFIX, isStampPart,
  KONTROLNI_ROLE_PREFIX, isKontrolniPart,
  CAR_BODY_ID_PREFIX, isCarBodyPart,
  attachEntryToParent, registerJoint, applyLengthScale,
  roztahujComputeForY,
  COLLISION_MAX_EDGES_PER_PART_DEFAULT, meshWorldEdgeSample, ensureWallBoundsTree,
  setMeshesCollisionColor, objectCollidesWithWalls,
};

if (typeof module === "object" && module.exports) {
  return api;
} else {
  // Prohlizec: pripoj vsechny funkce jako GLOBALY (presne jak fungovaly,
  // kdyz byly definovane inline v <script id="app-script">) - stavajici
  // volajici kod ve scene.html se NEMENI, vola je porad jako holé globaly.
  Object.assign(root, api);
}

});
