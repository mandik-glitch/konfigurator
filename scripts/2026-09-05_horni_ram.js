// HORNI RAM REGALU (zona pro dlouhe predmety) - podelniky + pricky.
// bot8 2026-09-05. Nahrazuje jednoucelovy 2026-09-05_dlouhe_tyce_v1.js.
//
// Robert 2026-09-05, postupne upresneno:
//   "propojeni nohou v zadni casti" / "podelne propojeni uplne nahore"
//   "propojeni v ramci kazde nohy predni a zadni nejvyssi profil, tak aby
//    horni hrana profilu prevysovala vsechny boxy"
//   "ten podelnik musi byt mezi koncovymi nohami, stredove konce nohou se
//    o 30mm zkrati"
//   "toto je moznost Eko, bez vyplni"
//   "ale to tam jeste chybi dalsi podelniky spodni"
//
//   node scripts/2026-09-05_horni_ram.js            # spocitat + overit
//   node scripts/2026-09-05_horni_ram.js --json
//
// CO STAVI (zona mezi vrchem boxu a koncem noh):
//   4 podelniky (podel Z):  zadni horni, zadni spodni, celni horni, celni spodni
//   3 pricky   (podel X):   v rovine kazde nohy, nahore
// Tim vznikne po obvodu uzavreny ram, do jehoz drazek muzou pozdeji zapadnout
// vyplne (MDF 8mm seda, zasun 7mm - Robert 2026-09-05).
//
// PROC SPODNI PODELNIKY: bez nich nema svisla vypln do ceho zapadnout zespoda -
// mela by jen horni a bocni hranu. Robert na to upozornil sam.
//
// KONVENCE ORIENTACE (prevzata z existujicich dilu sestavy, nevymyslena znovu):
//   Object_7 = metrova tyc podel Y, prurez 30x30 v X a Z.
//   svisly [0,0,0,1] | podelny [-0.7071,0,0,0.7071] | pricny [0,0,-0.7071,0.7071]
//   delka vzdy scale.y = delka/1000, `position` = geometricky STRED dilu.
const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const PROFIL = "Object_7";
const T = 30;
// Robert 2026-09-06 OPRAVA: puvodne 4mm - SPATNE, vymyslene mimo zavedene
// pravidlo. Skutecna hodnota je POVINNYCH 30mm - stejna "mezera mezi boxem
// a luzkem nad nim" jako u KAZDEHO jineho prechodu mezi patry
// (shape_geometry_methods.id=3/id=6, KOMPONENTY_EUROBOXY.md:138:
// "Y_rail_top(patro N+1) = Y_rail_top(patro N) + H_box(patro N) + 30mm
// (mezera) + T"). Horni blok neni vyjimka - je to jen dalsi "patro" nad
// poslednim boxem, plati pro nej STEJNA mezera. Protoze se meri z
// `a.nejvyssiBox` (skutecna geometrie), zmena skladby boxu (jina
// kombinace vysek) se projevi automaticky, beze zmeny tady.
const MEZERA_NAD_BOXY = 30;
// Robert 2026-09-06: "podle karoserie, ktere jsou vetsinou nahore uzsi,
// musime mit: horni regalovy blok [s mensi hloubkou]". Cap/predni-svislice
// jsou overene jen pro HLAVNI polici (u boxu) - ve vysce horniho bloku uz
// se bok muze zatacet dovnitr (viz 2026-09-05_profil_zuzeni.js). Overeno na
// CI25: bez tehle opravy vyslo jen 5.8mm mezery u vrcholu - bezpecne, ale na
// hrane. MIN_MEZERA_KE_STENE je bezpecnostni rezerva NAD ramec detekce
// kolize (ta hlida jen "0 nebo vic"), aby se to nestavelo na krev.
const MIN_MEZERA_KE_STENE = 20;
// Robert 2026-09-07 (po realne chycene kolizi na Doblu): "pri kolizi se
// melo 5mm vratit" - spodni pasmo horniho bloku muze narazit na uhelniky
// na spoji spojnice-horni/cap (shape_geometry_methods.id=7), pokud lezi
// bliz k vrcholu nohy nez 30mm nad nejvyssim boxem. `ySpodnihoDol` v
// main() proto neni jen "nejvyssiBox + MEZERA_NAD_BOXY", ale i "nejvyssi
// uhelnik + MIN_MEZERA_OD_UHELNIKU", podle toho, ktere z obou vyjde vyse.
const MIN_MEZERA_OD_UHELNIKU = 5;
const Q_PODELNY = [-0.7071067811865475, 0, 0, 0.7071067811865476];
const Q_PRICNY  = [0, 0, -0.7071067811865475, 0.7071067811865476];
const L0 = 1000;
// Vypln do drazek (Robert 2026-09-05: "material mdf 8mm seda, zajede 7mm",
// arch "MDFL 1700 PE Steel Grey 2800/2070/8", kod 382223)
const DESKA = "product_3939";     // MDF deska Steel Grey 8mm
const DESKA_TL = 8;               // tloustka [mm] = sirka drazky profilu 30x30 Light
const ZASUN = 7;                  // o kolik hrana zajede do drazky [mm]
// Robert 2026-09-10: vodorovne MDF dno musi byt o 1 mm KRATSI nez podelnik,
// aby nekolidovalo se svislimi profily nohy ani s prickami. Rozdeleno na
// pulku z kazde strany.
const DNO_VULE = 1;               // o kolik je dno kratsi nez podelnik [mm]
const DESKA_L0 = 1000;            // GLB je 1000 x 1000 x 8, skaluje se v X a Y
// Robert 2026-09-07 ("lze je posunout aby horni hrana profilu licovala s
// horni hranou mdf"): pricka pasma S DESKOU uz neni vystredena v pasmu -
// jeji horni hrana licuje s horni hranou desky, takze jeji SPODNI hrana
// sahá o tohle o kolik NIZ, nez zacina nominalni "dol" pasma (30mm profil,
// 8mm deska uprostred 30mm pasma -> 11mm rezerva nad i pod deskou -> pricka
// posunuta o presne tuhle rezervu dolu). MEZERA_NAD_BOXY/MIN_MEZERA_OD_
// UHELNIKU se pocitaji tak, aby platily pro SKUTECNOU (nizsi) spodni hranu
// pricky, ne pro nominalni hranici pasma - jinak by pricka mohla zasahnout
// zpatky do boxu/uhelniku presne o tuhle rezervu (realne chyceno 2026-09-07
// pri prvni implementaci "police" - bez tehle korekce vyslo 6mm zanoreni
// pricka-spodni do uhelniku, presne T-DESKA_TL rozdil minus puvodni 5mm).
const PRICKA_DESKA_OFFSET = (T - DESKA_TL) / 2;

const R = v => Math.round(v * 10) / 10;
// bot8 2026-09-17 (postup_stavby_regalu_krok_za_krokem_2026_09_17, krok 14):
// role dilu nohy mohou nest priponu "-noha<i>" (index od prepazky) - stejna
// normalizace se pouziva PRI VYBERU dilu (analyzuj/podle) i PRI ZPETNEM
// PAROVANI, kde se sloupek ma zkratit (main() nize) - obe strany MUSI pouzit
// STEJNOU funkci, jinak zkratitKlice (postavena z bezNohyIdx('bare role'))
// nenajde odpovidajici puvodni dil (ma jeste priponu) a zkraceni se tise
// neaplikuje (nalezeno 2026-09-17 na K-020: stredova noha "cap-noha1"/
// "predni-svislice-noha1" zustala v puvodni delce, novy prubezny horni
// podelnik do ni pak 30x30x30mm kolidoval).
const bezNohyIdx = role => String(role || "").replace(/-noha\d+$/, "");

// PAST (AGENTS_LOG.md:20892, bot22): part_id NENI nazev GLB souboru. U vetsiny
// produktu shodou okolnosti sedi (product_3071.glb existuje), ale u nekterych
// ne - napr. product_3045 -> product_2895.glb, a nase nova deska
// product_3939 -> deska_mdf_seda_8.glb. Bez mapovani vrati bboxDilu null a
// dil se z kontroly TISE vypadne (presne to se stalo tady poprve).
// product_3045 (uhelnikova spojka 30x30) -> product_2895.glb: znama past
// "part_id neni nazev GLB souboru" (AGENTS_LOG.md, bot22). Bez tohohle
// zaznamu bboxDilu() na uhelniky TICHE vraci null (soubor product_3045.glb
// neexistuje) a analyzuj()/kolizni kontrola je bez varovani vynecha ze
// vsech srovnani - realne chyceno 2026-09-07 pri aplikaci na Doblo, kdyz
// se ukazalo, ze "kolize s dily: zadna" u CI25 vzoru (id=187/189) STEJNE
// tak nikdy netestovala kolizi s jeho 9 uhelniky (product_3045 je v jeho
// datech take). Zapsano jako obecna oprava, ne jen pro Doblo.
const GLB_MAP = {
  "product_3939": "deska_mdf_seda_8.glb",
  "product_3045": "product_2895.glb",
};
function glbSoubor(pid) { return KAT + (GLB_MAP[pid] || pid + ".glb"); }

function bboxDilu(p, cache) {
  const pid = p.part_id;
  if (!cache[pid]) {
    const f = glbSoubor(pid);
    if (!fs.existsSync(f)) return null;
    cache[pid] = parseGlbMesh(f);
  }
  const o = cache[pid].clone(true);
  o.position.set(...p.position);
  o.quaternion.set(...p.quaternion);
  o.scale.set(...p.scale);
  o.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(o);
}

function analyzuj(data) {
  const cache = {};
  const dily = [];
  for (const p of data.parts) {
    if (String(p.part_id).startsWith("car_body_")) continue;
    const b = bboxDilu(p, cache);
    if (b) dily.push({ role: p.role || p.part_id, p, b });
  }
  const podle = r => dily.filter(d => bezNohyIdx(d.role) === r);
  const sloupky = (role) => podle(role)
    .map(d => ({ role, z0: d.b.min.z, z1: d.b.max.z, y0: d.b.min.y, y1: d.b.max.y,
                 x0: d.b.min.x, x1: d.b.max.x, p: d.p }))
    .sort((a, b) => a.z0 - b.z0);
  // ALTERNATIVNI NAZEV "zadni-svislice" (bot10, 2026-09-11, zadani bot8 +
  // rozhodnuti bot3): pilot na Berlingo K-005 (id=91) a Trafic L1 K-235
  // (id=103) tvrde spadl, protoze tahle dve vozidla nazyvaji stejnou
  // zadni/stenovou strukturni roli "zadni-svislice" (bez sufixu), ne "cap".
  // GEOMETRICKY OVERENO pred pridanim tohohle fallbacku (ne jen predpoklad):
  // u obou vozidel ma "zadni-svislice" IDENTICKY horni Y jako "predni-
  // svislice" na stejnem miste (id=91: obe 1070mm; id=103: 1252mm napric
  // vsemi 4 nohami vc. varianty "zadni-svislice-nad-zarezem" u vyrezove
  // nohy) - presne stejna geometricka role jako "cap" jinde (plati i
  // analogicky vzorec "-dolni"/"-nad-zarezem" = kratsi varianta pro vyrezove
  // nohy, irelevantni pro horni blok - viz algoritmus bod 1).
  // ZAMERNE JEN FALLBACK: pokud sestava "cap" MA, pouzije se "cap" jako
  // vzdy predtim, chovani pro uz overena vozidla (CI25, Doblo, OP18 apod.)
  // se timhle NEMENI. "zadni-svislice" se zkusi VYHRADNE kdyz "cap" v
  // sestave vubec neni.
  const zadni = sloupky("cap").length ? sloupky("cap") : sloupky("zadni-svislice");
  const celni = sloupky("predni-svislice");
  if (!zadni.length || !celni.length) throw new Error("sestava nema 'cap'/'zadni-svislice' / 'predni-svislice'");
  const boxy = dily.filter(d => d.role.startsWith("eurobox"));
  if (!boxy.length) throw new Error("sestava nema euroboxy");
  // Uhelniky na spoji spojnice-horni/cap (shape_geometry_methods.id=7,
  // "uhelniky-na-spoje-nohy") muzou sahat vys, nez zacina spodni pasmo
  // horniho bloku - viz main()/ySpodnihoDol.
  const uhelniky = dily.filter(d => d.role.startsWith("uhelnik"));
  const nejvyssiUhelnik = uhelniky.length ? Math.max(...uhelniky.map(d => d.b.max.y)) : null;
  return {
    dily, zadni, celni, boxy, nejvyssiUhelnik,
    nejvyssiBox: Math.max(...boxy.map(d => d.b.max.y)),
  };
}

// Postavi podelnik podel Z na linii danych sloupku, ve vyskovem pasmu [yDol,yHor].
// - Kdyz pasmo lezi NAD konci sloupku (rezim "nahore"), jde o JEDEN prubezny
//   profil mezi KONCOVYMI sloupky a stredove sloupky se zkrati o T, aby prosel.
// - Kdyz pasmo protina sloupky (rezim "spodni"), profil skrz ne prochazet nesmi
//   (pravidlo "zadne zanoreni") - deli se na SEGMENTY mezi sousednimi sloupky.
function podelnik(sloupky, yDol, yHor, nazev) {
  const xStred = (sloupky[0].x0 + sloupky[0].x1) / 2;
  const prvni = sloupky[0], posledni = sloupky[sloupky.length - 1];
  // "nahore" = pasmo sahá az na KONEC sloupku (jeho horni hrana lici s nimi).
  // Tehdy jde o jeden prubezny profil a stredove sloupky se o T zkrati.
  // POZOR: podminka musi byt na yHor, ne na yDol. S `yDol >= s.y1` vysla
  // nepravda i pro horni podelnik (yDol=1160 vs konec sloupku 1190), takze se
  // rozdelil na segmenty a stredove sloupky se vubec nezkratily - presne
  // opak toho, co Robert schvalil.
  const nahore = sloupky.every(s => yHor >= s.y1 - 1e-6);

  if (nahore) {
    const zOd = prvni.z1, zDo = posledni.z0;
    return {
      dily: [{
        part_id: PROFIL, position: [xStred, (yDol + yHor) / 2, (zOd + zDo) / 2],
        quaternion: Q_PODELNY, scale: [1, (zDo - zOd) / L0, 1], role: nazev,
      }],
      zkratit: sloupky.slice(1, -1),   // stredove sloupky pod nim
    };
  }
  const dily = [];
  for (let i = 0; i + 1 < sloupky.length; i++) {
    const zOd = sloupky[i].z1, zDo = sloupky[i + 1].z0;
    if (zDo - zOd <= 1) continue;
    dily.push({
      part_id: PROFIL, position: [xStred, (yDol + yHor) / 2, (zOd + zDo) / 2],
      quaternion: Q_PODELNY, scale: [1, (zDo - zOd) / L0, 1], role: `${nazev}-${i}`,
    });
  }
  return { dily, zkratit: [] };
}

// VOZIDLO: puvodne natvrdo zadratovany nazev (jen CI25) - Robert 2026-09-06
// "resime to jedno Jumpy jako vzor". Zobecneno 2026-09-07 (Robert: "aplikuj
// na Doblo regal verzi A, horni blok") na CLI parametr `--vozidlo=<base>`
// (base = GLB zakladni nazev BEZ "_L/_R_D/_B.glb", stejny format jako
// createEngine() ceka) - VOLAJICI si musi VOZIDLO dopredu zjistit z DB
// (part_id car_body_* -> car_bodies.glb_file -> odstranit "car_bodies/"
// prefix a "_L/_R_D/_B.glb" sufix), skript sam DB dotaz nedela. Default
// zustava CI25, aby se nezmenilo chovani puvodniho (dosud neschvaleneho)
// vzoru pri spusteni beze zmeny.
const VOZIDLO_DEFAULT = "Citroën_Jumpy_CI25_2021-";

function main() {
  const jsonOut = process.argv.includes("--json");
  const asmPath = process.argv.find(a => a.endsWith(".json") && !a.startsWith("--"))
    || "/tmp/claude-0/-opt-konfigurator/cd1e4f98-59ca-4757-a63c-ad69ec4e8fb4/scratchpad/asm187.json";
  const vozidloArg = process.argv.find(a => a.startsWith("--vozidlo="));
  const VOZIDLO = vozidloArg ? vozidloArg.slice("--vozidlo=".length) : VOZIDLO_DEFAULT;
  const data = JSON.parse(fs.readFileSync(asmPath, "utf8"));
  const a = analyzuj(data);
  const eng = createEngine(VOZIDLO);

  // --- vyskova pasma ------------------------------------------------------
  // Robert: "Y zalezi na typu nohy a boxech ktere jsou vlozene" - obe hranice
  // se odvozuji, nezadratovavaji.
  // OPRAVA (Robert 2026-09-13, "horni bloky 2.pasmo chyba vsude stejna,
  // prostredni noze chybi 30mm na vysku" - nalezeno na Doblo A/B, C jako
  // reference; puvodni pokus "Math.min -> Math.max" NEPOMOHL, skutecna
  // pricina byla jinde - zapsano cestne, at se stejna slepa ulicka
  // neopakuje). Puvodni kod bral Math.min pres VSECHNY sloupky vcetne
  // STREDNICH - ale stredni sloupek (u zarezu podbehu) je na Doblu K-075
  // ZAMERNE o presne T=30mm kratsi, viz Robertovo vlastni zadani v
  // hlavicce souboru: "stredove konce nohou se o 30mm zkrati", presne
  // proto, aby jimi jeden prubezny podelnik mohl "projet" (podelnik() nize
  // zkracuje stredni sloupky o T z DRUHE strany - je to par: sloupek uz
  // prichazi kratsi, podelnik ho jeste nezkracuje znovu). Vyska pasma se
  // proto NESMI odvozovat ze VSECH sloupku (stredni je vzdy o T nizsi
  // schvalne) - jen z KRAJNICH (prvni/posledni po Z, `sloupky()` uz trida).
  // U Doblo K-075 vysly oba kraje na 1220 (shodne pro celni i zadni),
  // presne na vysce, kterou ma #341 (Doblo C, Robertem schvalena
  // reference) skutecne ulozenou - overeno DEBUG_HB behem.
  const konceY1 = (skupina) => [skupina[0].y1, skupina[skupina.length - 1].y1];
  const yHornihoHor = Math.min(...konceY1(a.zadni), ...konceY1(a.celni));
  const yHornihoDol = yHornihoHor - T;
  if (process.env.DEBUG_HB) {
    console.error("DEBUG zadni y1:", a.zadni.map(s => [s.role, s.z0, s.y1]));
    console.error("DEBUG celni y1:", a.celni.map(s => [s.role, s.z0, s.y1]));
    console.error("DEBUG yHornihoHor:", yHornihoHor, "yHornihoDol:", yHornihoDol);
  }
  // "pri kolizi se melo 5mm vratit" (Robert 2026-09-07, po realne chycene
  // kolizi spodniho pasma s uhelniky na Doblu) - spodni hranice je vetsi
  // ze dvou: bezna 30mm mezera nad nejvyssim boxem, NEBO 5mm nad nejvyssim
  // uhelnikem, pokud ten sahá vys.
  // +PRICKA_DESKA_OFFSET: pricka tohohle pasma sahá o tolik NIZ nez "dol"
  // (viz PRICKA_DESKA_OFFSET vyse) - rezervy se pocitaji vuci SKUTECNE
  // (nizsi) spodni hrane pricky, ne vuci nominalni hranici pasma.
  const ySpodnihoDolMinBox = a.nejvyssiBox + MEZERA_NAD_BOXY + PRICKA_DESKA_OFFSET;
  const ySpodnihoDolMinUhelnik = a.nejvyssiUhelnik != null ? a.nejvyssiUhelnik + MIN_MEZERA_OD_UHELNIKU + PRICKA_DESKA_OFFSET : -Infinity;
  const ySpodnihoDol = Math.max(ySpodnihoDolMinBox, ySpodnihoDolMinUhelnik);
  const ySpodnihoHor = ySpodnihoDol + T;
  if (ySpodnihoHor >= yHornihoDol) {
    throw new Error(`KONFLIKT: mezi vrchem boxu (${R(a.nejvyssiBox)}) a koncem nohy `
      + `(${R(yHornihoHor)}) se dva podelniky nevejdou`);
  }

  // --- POLICE V POLOVINE VYSKY BLOKU ---------------------------------------
  // Robert 2026-09-07: "pridat dalsi ram s vyplni mdf jako police v polovine
  // vysky bloku." Dalsi vodorovne pasmo UPROSTRED volneho kanalu (mezi
  // spodnim a hornim pasmem) - stejna konstrukce jako spodni pasmo
  // (podelniky + pricky na VSECH nohach + MDF vypln). `--bez-police`
  // (Robert: "na dlouhe predmety si klient vybere variantu bez hornich
  // pricek a bude to vkladat i shora") vynecha ji - jeden neprerusen kanal
  // po cele vysce, pro zakaznika co chce dlouhe predmety.
  // --- ZAKLADNI (JEDNOPASMOVY) REZIM --------------------------------------
  // Robert 2026-09-10, doslovne: "Pozor zakladnim provedenim je pouze jedno
  // vyskove pasmo horniho bloku" -> "Zakladni je to spodni, horni pasmo je
  // pouze dalsi volba rozdeleni toho horniho bloku na dva."
  //
  // Do teto opravy skript stavel OBE pasma vzdy. `--jedno-pasmo` je zakladni
  // provedeni: JEN spodni ram (30 mm nad vrchem posledniho boxu, nese dna),
  // nad nim volna svetla vyska az ke koncum noh.
  //
  // Co v tomhle rezimu ODPADA a PROC:
  //  * horni podelniky a pricky - to JE horni pasmo,
  //  * police v polovine vysky - ta deli kanal MEZI dvema pasmy, bez horniho
  //    pasma nema horni hranici,
  //  * SVISLE VYPLNE (zada/celo/bok) - panel musi byt drzen po celem obvodu
  //    (ZASUN do drazky na vsech 4 hranach, viz algoritmus 6). Bez horniho
  //    podelniku nema horni hrana do ceho zajet, panel by visel na 3 hranach.
  //    Zakladni provedeni je tedy "ram + dna", ne uzavrena skrin.
  //  * zkracovani stredovych sloupku o T a odebirani hornich zaslepek - to je
  //    vlastnost HORNIHO pasma (algoritmus 3), nohy zustavaji v plne delce.
  const jednoPasmo = process.argv.includes("--jedno-pasmo");
  const bezPolice = jednoPasmo || process.argv.includes("--bez-police");
  // Robert 2026-09-10 ("verzi horniho bloku 4/6 udelejme bez podelniku v
  // polovine vysky a bez nejvrchnejsich pricek"): police uprostred kanalu
  // zustava, ale JEN JAKO PRICKY - bez podelniku. Dlouhe predmety pak lezi
  // primo na prickach a podelne nic nebrani nakladani z boku.
  // Pozor: pri --bez-vyplni je to jedno (zadne desky), ale s vyplnemi by
  // MDF police nemela na cem lezet - proto se v tom pripade vypln police
  // taky vynechava (viz stavDna nize).
  const policeBezPodelniku = process.argv.includes("--police-bez-podelniku");
  let policeDol = null, policeHor = null;
  if (!bezPolice) {
    const stredKanalu = (ySpodnihoHor + yHornihoDol) / 2;
    policeDol = stredKanalu - T / 2;
    policeHor = stredKanalu + T / 2;
    if (policeDol <= ySpodnihoHor || policeHor >= yHornihoDol) {
      throw new Error(`KONFLIKT: police v polovine (${R(policeDol)}-${R(policeHor)}) `
        + `se nevejde mezi spodni (${R(ySpodnihoHor)}) a horni (${R(yHornihoDol)}) pasmo`);
    }
  }

  // --- HLOUBKA ZADNI STRANY HORNIHO BLOKU dle zuzeni karoserie -------------
  // Robert 2026-09-06: "podle karoserie, ktere jsou vetsinou nahore uzsi,
  // musime mit: horni regalovy blok [s mensi hloubkou nez hlavni cast
  // regalu]". `cap` je overeny jen pro HLAVNI polici (u boxu) - ve vysce
  // horniho bloku uz se bok muze zatacet dovnitr (viz 2026-09-05_profil_
  // zuzeni.js). Zmereno na CI25: bez tehle opravy vyslo jen 5.8mm mezery u
  // vrcholu podelniku - proslo to (kolize=0), ale na hranu, ne bezpecne.
  //
  // Mери se NEJTESNEJSI bod steny pres CELY vyskovy rozsah horniho pasma
  // (yHornihoDol..yHornihoHor) A CELOU delku zadni linie (Z rozsah) - tedy
  // nejhorsi kombinace, ne prumer. Pokud by "cap" uz mel dost rezervy, X se
  // NEMENI (zadny zbytecny posun tam, kde neni potreba - napr. CI14 pri
  // rychlem testu 2026-09-06 nemel tenhle problem vubec).
  //
  // POSOUVA SE CELA zadni strana horniho bloku (oba jeho podelniky, zadni a
  // bokova vypln) na JEDNU bezpecnou hloubku - je to JEDEN plochy panel od
  // spodniho az po horni pasmo, nemuze mit dve ruzne hloubky. `cap` sam
  // (skutecna noha hlavni police) zustava presne tam, kde je - spojeni k
  // nove (mensi) hloubce resi kratka KONZOLA (bracket) na kazde zadni noze.
  function zmerNejtesnejsiStenu(sloupky, yOd, yDo) {
    const rc = new THREE.Raycaster(); rc.firstHitOnly = true; rc.far = 3000;
    const smer = new THREE.Vector3(eng.mirror ? -1 : 1, 0, 0);
    const zFrom = Math.min(...sloupky.map(s => s.z0)), zTo = Math.max(...sloupky.map(s => s.z1));
    let extrem = eng.mirror ? -Infinity : Infinity;
    for (let iy = 0; iy <= 6; iy++) {
      const y = yOd + (yDo - yOd) * iy / 6;
      for (let iz = 0; iz <= 24; iz++) {
        const z = zFrom + (zTo - zFrom) * iz / 24;
        rc.set(new THREE.Vector3(0, y, z), smer);
        const h = rc.intersectObject(eng.wallL, true);
        if (!h.length) continue;
        const x = eng.mirror ? -h[0].distance : h[0].distance;
        if (eng.mirror ? x > extrem : x < extrem) extrem = x;
      }
    }
    return isFinite(extrem) ? extrem : null;
  }
  const zadniStena = zmerNejtesnejsiStenu(a.zadni, yHornihoDol, yHornihoHor);
  const halfT = T / 2;
  let zadniHloubkaPosun = 0;
  let zadniBezpecnaX = null;
  if (zadniStena != null) {
    zadniBezpecnaX = eng.mirror
      ? zadniStena + MIN_MEZERA_KE_STENE + halfT
      : zadniStena - MIN_MEZERA_KE_STENE - halfT;
    const capX = (a.zadni[0].x0 + a.zadni[0].x1) / 2;
    const potrebaPosunout = eng.mirror ? zadniBezpecnaX > capX : zadniBezpecnaX < capX;
    if (potrebaPosunout) zadniHloubkaPosun = zadniBezpecnaX - capX;
  }
  // xOd/xDo pro pricky/pricka-spodni-prepazka/vypln-bok-prepazka: VZDY podle
  // SKUTECNE (nezmenene) polohy cap/predni-svislice, NIKDY podle "bezpecne"
  // posunute zadni linie (viz nize) - realne chyceno 2026-09-07 (Robert:
  // "pricky mezi prednimi a zadnimi vrchnimi nohami... musi byt dotazeny ke
  // stenam profilu nohou presne na dotyk... ve 2D pohledu pricky i podelniky
  // splyvaji s profily nohou"). Puvodni kod pocital xOd z "zadniProHorniBlok"
  // (posunute linie), takze kdykoli byl aplikovan posun (i mensi nez tehdejsi
  // prah pro konzolu), pricka ZUSTALA "viset" presne `posun` mm PRED skutecnym
  // celem cap - castecne kryte celo, presny opak Pravidla c.1 z PRAVIDLA_
  // SPOJU.md ("zadne zanoreni, zadne castecne kryte celo"). Pricka nepotrebuje
  // bezpecnou rezervu od steny navic - nesaha k ni o nic bliz, nez uz saha
  // samotny (jiz overene bezkolizni) cap.
  const xOd = Math.max(...a.zadni.map(s => s.x1));
  const xDo = Math.min(...a.celni.map(s => s.x0));

  const nove = [];
  const zkratit = [];

  // podelnik-celni-*: predni strana se pri zuzeni karoserie neposouva,
  // stavi se VZDY na skutecne "predni-svislice".
  const celniPasma = [
    ["podelnik-celni-spodni", ySpodnihoDol, ySpodnihoHor],
  ];
  if (!jednoPasmo) celniPasma.unshift(["podelnik-celni-horni", yHornihoDol, yHornihoHor]);
  if (!bezPolice && !policeBezPodelniku) celniPasma.push(["podelnik-celni-police", policeDol, policeHor]);
  for (const [nazev, dol, hor] of celniPasma) {
    const v = podelnik(a.celni, dol, hor, nazev);
    nove.push(...v.dily);
    zkratit.push(...v.zkratit);
  }

  const nohaUPrepazky = a.zadni[0];

  // --- pricky (v rovine kazde nohy) -----------------------------------------
  // Vedou od zadni svislice k celni, VZDY presne na dotyk (viz xOd/xDo vyse),
  // na VSECH nohach (Robert 2026-09-07, oprava predchoziho "jen u prepazky"
  // zjednoduseni - viz KOMPONENTY_EUROBOXY.md "OPRAVA... pricka patri na
  // vsechny nohy"). Horni pasmo nema pod sebou zadnou desku (je to strop
  // kanalu) - pricka zustava vystredena v pasmu. Pasma S DESKOU (spodni,
  // police) maji pricku posunutou tak, aby jeji HORNI hrana licovala s
  // HORNI hranou prilehle MDF desky (Robert: "lze je posunout aby horni
  // hrana profilu licovala s horni hranou mdf") - dulezite: profil pak
  // sahá NIZ, nez je nominalni spodni hranice pasma (o (T-DESKA_TL)/2 =
  // 11mm) - proto MIN_MEZERA_OD_UHELNIKU/MEZERA_NAD_BOXY pocitaji s touhle
  // rezervou navic (viz vyse).
  function stavPricky(dol, hor, label, maDesku, jenPrvni) {
    const yStred = maDesku
      ? (dol + hor) / 2 + DESKA_TL / 2 - halfT   // horni hrana = horni hrana desky
      : (dol + hor) / 2;                          // bez desky (horni pasmo) - vystredit
    a.zadni.forEach((cap, i) => {
      if (jenPrvni && i !== 0) return;      // jen noha u prepazky
      const z = (cap.z0 + cap.z1) / 2;
      // PRAVIDLO Robert 2026-09-10, doslovne: "prvni pricka dna nohy u
      // prepazky slouzi uz jako doraz tzn nebude licovat horni hranou s
      // deskou dna ale bude vyskove v urovni podelniku".
      //
      // Ostatni pricky pasma S DESKOU se posouvaji dolu tak, aby jejich
      // horni hrana licovala s deskou (nic necni nad rovinu dna). U nohy
      // u prepazky (a.zadni[0]) to ale NENI zadouci - ta pricka ma
      // DORAZOVOU funkci, tedy musi nad dno vycnivat. Proto zustava
      // vystredena v pasmu, presne v urovni podelniku.
      const jeDoraz = maDesku && i === 0;
      nove.push({
        part_id: PROFIL,
        position: [(xOd + xDo) / 2, jeDoraz ? (dol + hor) / 2 : yStred, z],
        quaternion: Q_PRICNY, scale: [1, (xDo - xOd) / L0, 1], role: `${label}-${i}`,
      });
    });
  }
  // Robert 2026-09-10 ("verzi 4 odstran nejvyssi sadu pricek") - navazuje na
  // jeho drivejsi "na dlouhe predmety si klient vybere variantu bez hornich
  // pricek a bude to vkladat i shora": podelniky horniho pasma zustavaji
  // (drzi ram), ale PRICNE pricky se vynechaji, takze je blok shora otevreny.
  const bezHornichPricek = process.argv.includes("--bez-hornich-pricek");
  // Robert 2026-09-10 ("sestava 5/6 odstranit nejvyssi pricky podbehove nohy
  // a stredni nohy, tzn u prepazky zustane"): mezistupen mezi "vsechny horni
  // pricky" a "zadna" - zustane JEN ta na noze u prepazky (a.zadni[0]).
  // Ta ma navic dorazovou funkci (viz krok 5_pricky), takze davá smysl ji
  // nechat i tam, kde ostatni prekazi nakladani seshora.
  const horniPrickaJenPrepazka = process.argv.includes("--horni-pricka-jen-prepazka");
  if (!jednoPasmo && !bezHornichPricek) stavPricky(yHornihoDol, yHornihoHor, "pricka-horni", false, horniPrickaJenPrepazka);
  stavPricky(ySpodnihoDol, ySpodnihoHor, "pricka-spodni", true);
  if (!bezPolice) stavPricky(policeDol, policeHor, "pricka-police", true);

  // --- ZADNI STRANA (podelnik-zadni-*, vypln-zada, vypln-dno, konzoly) ----
  // Jedina cast, kde muze byt potreba posun od steny (karoserie se nahoru
  // muze zuzovat). Realne chyceno 2026-09-07 (Doblo): puvodni kod POSOUVAL
  // VZDY, kdyz vypocet naznacil potrebu podle FIXNI 20mm rezervy
  // (MIN_MEZERA_KE_STENE) - i kdyz skutecna kolizni kontrola pri posun=0
  // vysla cista (cap samotny nikde nekoliduje s karoserii). Ted se posun=0
  // zkousi VZDY prvni a pouzije se, pokud s nim NIC nekoliduje s karoserii;
  // teprve kdyz by posun=0 KOLIDOVAL, pouzije se vypocitany bezpecny posun -
  // a POKAZDE, kdyz je vysledny posun != 0, se stavi i mostici KONZOLA
  // (drivejsi prah "> T" byl nespravny pro pozadavek "cele licujici celo" -
  // i posun mensi nez T uz vyrobi castecne kryte celo podelniku, viz
  // KOMPONENTY_EUROBOXY.md, "aktualizace pravidla 2026-09-07").
  const bezVyplni = process.argv.includes("--bez-vyplni");
  const yPanelDol = ySpodnihoHor - ZASUN;
  const yPanelHor = yHornihoDol + ZASUN;
  // Svisle panely (vypln-zada/vypln-celo) puvodne sahaly JEDNIM kusem od
  // spodniho po horni pasmo - kdyz je mezi nimi police, jeji rad (podelnik+
  // pricka) prochazi PRAVE stredem tohoto rozsahu a bez rozdeleni by s nim
  // svisly panel kolidoval (realne chyceno 2026-09-07 pri pridavani police,
  // prunik 8mm > povoleny ZASUN 7mm). Misto jednoho panelu se ted staví DVA
  // (pod policí, nad policí), kazdy se svym vlastnim ZASUN zapustenim do
  // police stejne jako do spodniho/horniho pasma.
  const panelYUseky = bezPolice
    ? [["", yPanelDol, yPanelHor]]
    : [["-a", yPanelDol, policeDol + ZASUN], ["-b", policeHor - ZASUN, yPanelHor]];

  function panelSvisly(cil, xStred, zOd, zDo, role) {
    // Zakladni jednopasmove provedeni nema horni podelnik, do ktereho by
    // horni hrana panelu zajela - panel by visel na 3 hranach misto 4.
    if (jednoPasmo) return;
    for (const [sufix, yDol, yHor] of panelYUseky) {
      cil.push({
        part_id: DESKA,
        position: [xStred, (yDol + yHor) / 2, (zOd + zDo) / 2],
        // GLB desky lezi v rovine XY s tloustkou v Z -> otocit do roviny YZ
        quaternion: [0, 0.7071067811865476, 0, 0.7071067811865475],
        scale: [(zDo - zOd) / DESKA_L0, (yHor - yDol) / DESKA_L0, 1],
        role: role + sufix,
      });
    }
  }

  function zadniStranaProPosun(posun) {
    const zadniProHorniBlok = a.zadni.map(s => ({ ...s, x0: s.x0 + posun, x1: s.x1 + posun }));
    const noveL = [];
    const zkratitL = [];
    const zadniPasma = [
      ["podelnik-zadni-spodni", ySpodnihoDol, ySpodnihoHor],
    ];
    if (!jednoPasmo) zadniPasma.unshift(["podelnik-zadni-horni", yHornihoDol, yHornihoHor]);
    if (!bezPolice && !policeBezPodelniku) zadniPasma.push(["podelnik-zadni-police", policeDol, policeHor]);
    for (const [nazev, dol, hor] of zadniPasma) {
      const v = podelnik(zadniProHorniBlok, dol, hor, nazev);
      noveL.push(...v.dily);
      zkratitL.push(...v.zkratit);
    }
    // KONZOLA (bracket) z cap na posunutou zadni linii - VZDY kdyz je posun
    // nenulovy (viz vyse), na KAZDE zadni noze, na vysce KAZDEHO pasma
    // s deskou (spodni, + police pokud je).
    if (posun !== 0) {
      const konzolyDol = [ySpodnihoDol];
      if (!bezPolice) konzolyDol.push(policeDol);
      a.zadni.forEach((s, i) => {
        const z = (s.z0 + s.z1) / 2;
        const capX = (s.x0 + s.x1) / 2;
        const novaX = capX + posun;
        const smer = Math.sign(novaX - capX);
        const capFace = capX + smer * halfT;
        const novaFace = novaX - smer * halfT;
        const delka = Math.abs(novaFace - capFace);
        konzolyDol.forEach((dol, jm) => {
          noveL.push({
            part_id: PROFIL, position: [(capFace + novaFace) / 2, dol - halfT, z],
            quaternion: Q_PRICNY, scale: [1, delka / L0, 1],
            role: `konzola-horni-blok-hloubka-${i}-${jm}`,
          });
        });
      });
    }
    const vyplneL = [];
    if (!bezVyplni) {
      const xs = (zadniProHorniBlok[0].x0 + zadniProHorniBlok[0].x1) / 2;
      for (let i = 0; i + 1 < zadniProHorniBlok.length; i++) {
        panelSvisly(vyplneL, xs, zadniProHorniBlok[i].z1 - ZASUN, zadniProHorniBlok[i + 1].z0 + ZASUN, `vypln-zada-${i}`);
      }
      // Vodorovna MDF deska (dno spodniho pasma / police) - stejna stavba
      // pro obe, jen jine Y pasmo a jiny prefix role.
      function stavDna(dol, hor, prefix) {
        const yDnaStred = (dol + hor) / 2;
        const xDnaOd = Math.max(...zadniProHorniBlok.map(s2 => s2.x1)) - ZASUN;
        const xDnaDo = Math.min(...a.celni.map(s2 => s2.x0)) + ZASUN;
        for (let i = 0; i + 1 < zadniProHorniBlok.length; i++) {
          // PRAVIDLO Robert 2026-09-10 (po kontrole Dobla C ve scene),
          // doslovne: "dno mdf na oba sloupce ktere zapada do podelniku, musi
          // byt vzdy kratsi o 1mm nez podelnik(nosnik) proto aby nekolidoval
          // se svislimi profily nohy ani s prickami".
          //
          // PUVODNE se dno o ZASUN(7mm) na KAZDE strane PRODLUZOVALO do
          // pricek - tedy o 14 mm DELSI nez podelnik. Nove je o 1 mm KRATSI:
          // z kazde strany 0,5 mm od cela podelniku. Dno tak lezi VYHRADNE v
          // drazkach obou podelniku (podel X) a konce ma volne - nedotyka se
          // ani svislic nohy, ani pricek.
          const zOd = zadniProHorniBlok[i].z1 + DNO_VULE / 2;
          const zDo = zadniProHorniBlok[i + 1].z0 - DNO_VULE / 2;
          vyplneL.push({
            part_id: DESKA,
            position: [(xDnaOd + xDnaDo) / 2, yDnaStred, (zOd + zDo) / 2],
            quaternion: [-0.7071067811865475, 0, 0, 0.7071067811865476],
            scale: [(xDnaDo - xDnaOd) / DESKA_L0, (zDo - zOd) / DESKA_L0, 1],
            role: `${prefix}-${i}`,
          });
        }
      }
      stavDna(ySpodnihoDol, ySpodnihoHor, "vypln-dno");
      // bez podelniku nema MDF police na cem lezet (drzela by se jen na
      // dvou hranach misto ctyr) - proto se vynecha i vypln.
      if (!bezPolice && !policeBezPodelniku) stavDna(policeDol, policeHor, "vypln-police");
    }
    return { nove: noveL, vyplne: vyplneL, zkratit: zkratitL };
  }

  function koliduje(dily) {
    return dily.some(d => {
      const m = parseGlbMesh(glbSoubor(d.part_id));
      m.position.set(...d.position); m.quaternion.set(...d.quaternion); m.scale.set(...d.scale);
      m.updateMatrixWorld(true);
      return eng.collidesWithWalls(m);
    });
  }

  const zeroVariant = zadniStranaProPosun(0);
  const zeroVariantKoliduje = koliduje([...zeroVariant.nove, ...zeroVariant.vyplne]);
  const zadniStranaFinal = zeroVariantKoliduje ? zadniStranaProPosun(zadniHloubkaPosun) : zeroVariant;
  if (!zeroVariantKoliduje) zadniHloubkaPosun = 0;
  nove.push(...zadniStranaFinal.nove);
  zkratit.push(...zadniStranaFinal.zkratit);

  // --- zkraceni stredovych sloupku + odebrani jejich hornich zaslepek ------
  // OPRAVENO 2026-09-15 (bot8, K-122 A/B/C - Robert: "stredove nohy maji
  // spatne nastavenou vysku"). Puvodni kod odecital PEVNYCH T=30mm od
  // KAZDEHO stredoveho sloupku, jako by vsechny stredni sloupky zacinaly
  // na stejne vysce jako krajni (yHornihoHor). To plati pro K-124/125e
  // (vsechny 3 nohy 1190mm) i pro puvodni Doblo pripad - ale K-122 A/B/C
  // ma stredni nohu UZ ZAMERNE o 30mm kratsi nez krajni (1160 vs 1190,
  // stejny vzor jako Doblovy "zarez podbehu" sloupek, jen bez explicitni
  // "-nad-zarezem" role). Odecteni dalsich 30mm z ni udelalo nohu
  // CELKEM o 60mm kratsi (top=1130), tedy 30mm POD yHornihoDol (1160) -
  // podelnik pak nad ni visel ve vzduchu s 30mm mezerou misto na ni dosedl.
  // SPRAVNE: dopocitat, o kolik KAZDY konkretni sloupek skutecne PRESAHUJE
  // cilovou vysku (yHornihoDol), a zkratit jen o TOHLE (0, kdyz uz na ni
  // presne sedi - jako K-122 stredni noha), ne o pausalni T.
  const zkratitKlice = new Set(zkratit.map(s => `${s.role}@${Math.round((s.z0 + s.z1) / 2)}`));
  const upraveneParts = [];
  const upravy = { zkraceno: [], odebranoZaslepek: 0 };
  for (const p0 of data.parts) {
    const role = bezNohyIdx(p0.role || p0.part_id);
    const zc = Math.round(p0.position[2]);
    if (zkratitKlice.has(`${role}@${zc}`)) {
      const aktualniVrch = p0.position[1] + p0.scale[1] * L0 / 2;
      const zkratitO = aktualniVrch - yHornihoDol;
      if (zkratitO < -1e-6) {
        throw new Error(`stredovy sloupek ${role}@${zc} je NIZSI nez yHornihoDol `
          + `(${R(aktualniVrch)} < ${R(yHornihoDol)}) - horni podelnik by na nej nedosedl`);
      }
      if (zkratitO > 1e-6) {
        upraveneParts.push({ ...p0,
          position: [p0.position[0], p0.position[1] - zkratitO / 2, p0.position[2]],
          scale: [p0.scale[0], p0.scale[1] - zkratitO / L0, p0.scale[2]] });
        upravy.zkraceno.push({ role, z: zc, o: R(zkratitO) });
      } else {
        upraveneParts.push(p0);   // uz presne na cilove vysce, nic zkracovat
      }
      continue;
    }
    // zaslepka na konci prave zkraceneho sloupku uz nema volne celo - podelnik
    // na nej dosedne, zaslepka by byla plat ve spoji. Presny nazev role se
    // lisi mezi karoseriemi (CI25 "zaslepka", Doblo "zaslepka-cap"/
    // "zaslepka-predni-svislice"/...) - realne chyceno 2026-09-07 pri
    // aplikaci na Doblo (id=134): presna shoda "zaslepka" nechala Dobliny
    // zaslepky na miste, novy podelnik do nich pak kolidoval. Prefixova
    // shoda pokryje obe konvence.
    if (String(role).startsWith("zaslepka") && p0.position[1] > yHornihoDol) {
      const patriKeZkracenemu = zkratit.some(s =>
        Math.abs((s.z0 + s.z1) / 2 - p0.position[2]) < 1 &&
        p0.position[0] > s.x0 - 1 && p0.position[0] < s.x1 + 1);
      if (patriKeZkracenemu) { upravy.odebranoZaslepek++; continue; }
    }
    upraveneParts.push(p0);
  }
  // --- VYPLNE, cast nezavisla na posunu (Robert: "zaplnit steny vrchu
  //     regalu takto: zada, krajni bok u prepazky, celo") -------------------
  // "zada"/"dno" uz jsou v zadniStranaFinal.vyplne (zavisi na posunu).
  // "celo" (predni strana, nikdy se neposouva) a "krajni bok u prepazky"
  // (pouziva xOd/xDo, ted VZDY skutecna poloha cap/predni-svislice, viz
  // vyse) se stavi tady, VZDY, nezavisle na tom, jak vyslo rozhodnuti o
  // zadni strane. Panel zapadne ZASUN mm do drazky kazdeho ramoveho profilu,
  // ktery ho drzi. Zadni konec (u dveri) zustava OTEVRENY - tudy se dlouhe
  // predmety zasouvaji.
  const vyplne = [...zadniStranaFinal.vyplne];
  if (!bezVyplni) {
    const xsCelo = (a.celni[0].x0 + a.celni[0].x1) / 2;
    for (let i = 0; i + 1 < a.celni.length; i++) {
      panelSvisly(vyplne, xsCelo, a.celni[i].z1 - ZASUN, a.celni[i + 1].z0 + ZASUN, `vypln-celo-${i}`);
    }
    // KRAJNI BOK U PREPAZKY: v rovine koncove nohy, mezi zadni a celni linii.
    // POZOR - tenhle panel sedi na STEJNE Z jako "pricka-*-0" (obojí u
    // prepazkove nohy), NARORDIL od vypln-zada/celo, ktere lezi v MEZERACH
    // MEZI nohami, kde segmentovany podelnik (spodni/police) fyzicky
    // vubec neexistuje na teto Z - jeho hranice se proto NESMI pocitat
    // podle podelniku (to funguje jen pro zada/celo), ale podle SKUTECNE
    // pricky na teto Z (jedina vec, co tu fyzicky je, mimo cap/predni-
    // svislice samotne). Realne chyceno 2026-09-08 (Robert po screenshotu:
    // "bocni horni mdf nezapada do drazek") - puvodni kod pouzival
    // podelnikovy 7mm zasun i tady, coz pro "police" pasmo (jeho pricka je
    // o PRICKA_DESKA_OFFSET=11mm NIZ nez podelnik) davalo 4mm MEZERU misto
    // dotyku.
    //
    // DRUHA OPRAVA (Robert, po prvni oprave): pouhy FLUSH dotyk (0mm)
    // NESTACI - "musi se zapustit do horni i dolni pricky min 5mm", stejny
    // princip zasunu jako VSUDE JINDE (ZASUN=7mm, splnuje "min 5mm"), jen
    // do PRICKY misto (na teto Z neexistujiciho) podelniku. Hranice u
    // "horni" pasma (bez desky, pricka-horni tam splyva s podelnik-horni)
    // zustava beze zmeny - tam uz 7mm zasun spravne cili do podelniku i
    // pricky soucasne (splyvaji).
    // OPRAVENO 2026-09-15 (bot8, Jumpy K-120..K-125e horni bloky, varianta
    // 04 - Robert: "ty horni bloky maji problem v geometrii", nalezeno
    // systematickym pruchodem vsech novych sestav). Puvodni vypocet mysli
    // prickaTopY() jako prickou SROVNANOU S DESKOU, ale pricka u prepazky
    // (i=0) je DORAZ - vystredena v pasmu, ne srovnana s deskou - viz
    // stavPricky() vyse, "jeDoraz". Zavodni dusledek: 18mm skutecne
    // interpenetrace (pricka-spodni-0 x vypln-bok-prepazka-a, pricka-
    // police-0 x vypln-bok-prepazka-b), zmereno na 18 z 18 postizenych
    // Jumpy sestav (vsechny "04" varianty).
    //
    // SPRAVNA HODNOTA (odvozeno zpetne z Doblo K-075 A-04, id=384, ktera
    // ma 0 kolizi - jeji ulozena geometrie byla rucne opravena, ale tahle
    // oprava se nikdy nepropsala zpatky do skriptu): kdyz je pricka
    // vystredena v pasmu vysky T, jeji horni hrana VZDY presne splyva s
    // "hor" hranici pasma (dol+T/2+T/2=dol+T=hor) - staci tedy pouzit
    // primo hranici pasma (ySpodnihoHor/policeDol/policeHor), NE
    // prickaTopY(). Overeno: presne sedi na vsechny 4 hranice ulozene u
    // id=384 (996.5/1078.25/1108.25/1190). Zadny ZASUN navic - pricka
    // trci "na plocho" (nezapada do drazky), panel na ni jen dosedne.
    const panelYUsekyBok = bezPolice
      ? panelYUseky
      : [
          ["-a", ySpodnihoHor, policeDol],
          ["-b", policeHor, yPanelHor],
        ];
    // Stejny duvod jako u panelSvisly: bez horniho podelniku nema horni hrana
    // bocni vyplne do ceho zajet. Overeno behem zavadeni rezimu 2026-09-10 -
    // panel vysel jen se 2 zasuny misto 4, presne ta vada.
    for (const [sufix, yDol, yHor] of (jednoPasmo ? [] : panelYUsekyBok)) {
      vyplne.push({
        part_id: DESKA,
        position: [(xOd + xDo) / 2, (yDol + yHor) / 2,
                   (nohaUPrepazky.z0 + nohaUPrepazky.z1) / 2],
        quaternion: [0, 0, 0, 1],   // rovina XY = presne orientace GLB
        scale: [(xDo - xOd + 2 * ZASUN) / DESKA_L0, (yHor - yDol) / DESKA_L0, 1],
        role: "vypln-bok-prepazka" + sufix,
      });
    }
  }

  const upravenaData = { ...data, parts: [...upraveneParts, ...nove, ...vyplne] };

  // --- overeni PO uprave ---------------------------------------------------
  const cache = {};
  const vse = [...nove, ...vyplne];
  const boxyNovych = vse.map(d => bboxDilu(d, cache));
  const chybi = vse.filter((d, i) => !boxyNovych[i]).map(d => `${d.role} (${d.part_id})`);
  if (chybi.length) throw new Error(`bez GLB, nelze overit: ${chybi.join(", ")}`);
  const aUpr = analyzuj(upravenaData);
  // ZAMERNY prunik = hrana vyplne zajizdi ZASUN mm do drazky ramoveho profilu.
  // Neni to kolize, je to ten spoj. Povoluje se JEN mezi vyplni a profilem
  // (ramovym nebo svislici nohy) a JEN do hloubky ZASUN v nejmelci ose.
  // Tloustka desky (8 mm) je v jine ose a do posouzeni nevstupuje.
  // "pricka" (bez sufixu) pokryje horni/spodni/police jednotne - drivejsi
  // vypis "pricka-horni|pricka-spodni" zapomel na pozdeji pridanou
  // "pricka-police" (realne chyceno 2026-09-07 pri pridavani police).
  const RAMOVE = /^(podelnik|pricka|cap|predni-svislice)/;
  function zamernyZasun(roleA, roleB, px, py, pz) {
    const a1 = String(roleA).startsWith("vypln"), b1 = String(roleB).startsWith("vypln");
    if (a1 === b1) return false;                       // vypln vs vypln, nebo profil vs profil
    const profil = a1 ? roleB : roleA;
    if (!RAMOVE.test(String(profil))) return false;
    const hloubky = [px, py, pz].filter(v => v > 0.5).sort((m, n) => m - n);
    return hloubky.length > 0 && hloubky[0] <= ZASUN + 0.5;
  }
  const kolize = [];
  let zasunyPocet = 0;
  const zasunyPanelu = {};
  const pocitejZasun = (rA, rB) => {
    const r = String(rA).startsWith("vypln") ? rA : rB;
    zasunyPanelu[r] = (zasunyPanelu[r] || 0) + 1;
  };
  for (let i = 0; i < vse.length; i++) {
    const bs = boxyNovych[i];
    for (const d of aUpr.dily) {
      if (/^(podelnik|pricka|vypln|konzola)/.test(String(d.role))) continue;
      const px = Math.min(bs.max.x, d.b.max.x) - Math.max(bs.min.x, d.b.min.x);
      const py = Math.min(bs.max.y, d.b.max.y) - Math.max(bs.min.y, d.b.min.y);
      const pz = Math.min(bs.max.z, d.b.max.z) - Math.max(bs.min.z, d.b.min.z);
      if (px <= 0.5 || py <= 0.5 || pz <= 0.5) continue;
      if (zamernyZasun(vse[i].role, d.role, px, py, pz)) { zasunyPocet++; pocitejZasun(vse[i].role, d.role); continue; }
      kolize.push({ novy: vse[i].role, role: d.role, prunik: [R(px), R(py), R(pz)] });
    }
  }
  // vzajemne kolize novych dilu
  for (let i = 0; i < vse.length; i++) for (let j = i + 1; j < vse.length; j++) {
    const A = boxyNovych[i], B = boxyNovych[j];
    const px = Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x);
    const py = Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y);
    const pz = Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z);
    if (px <= 0.5 || py <= 0.5 || pz <= 0.5) continue;
    // ZAMERNY prunik: hrana vyplne zajizdi ZASUN mm do drazky ramoveho profilu.
    // Neni to kolize - je to ten spoj. Povoluje se jen mezi vyplni a profilem
    // ramu, a jen do hloubky ZASUN (+0,5 mm tolerance) v JEDNE ose.
    if (zamernyZasun(vse[i].role, vse[j].role, px, py, pz)) { zasunyPocet++; pocitejZasun(vse[i].role, vse[j].role); continue; }
    kolize.push({ novy: vse[i].role, role: vse[j].role, prunik: [R(px), R(py), R(pz)] });
  }

  // `eng` uz existuje (vytvoren na zacatku main() - pouzit i pro mereni
  // bezpecne hloubky zadni linie vyse).
  const kolizeKaroserie = vse.filter(d => {
    const m = parseGlbMesh(glbSoubor(d.part_id));
    m.position.set(...d.position); m.quaternion.set(...d.quaternion); m.scale.set(...d.scale);
    m.updateMatrixWorld(true);
    return eng.collidesWithWalls(m);
  }).map(d => d.role);

  const vysledek = {
    zadniHloubkaPosunPouzit: R(zadniHloubkaPosun),
    nejvyssiBox: R(a.nejvyssiBox),
    konecNohy: R(yHornihoHor),
    pasmoHorni: [R(yHornihoDol), R(yHornihoHor)],
    pasmoSpodni: [R(ySpodnihoDol), R(ySpodnihoHor)],
    svetlaVyskaRamu: R(yHornihoDol - ySpodnihoHor),
    nove: vse.map((d, i) => ({ role: d.role, delka: R(d.scale[1] * L0),
      X: [R(boxyNovych[i].min.x), R(boxyNovych[i].max.x)],
      Y: [R(boxyNovych[i].min.y), R(boxyNovych[i].max.y)],
      Z: [R(boxyNovych[i].min.z), R(boxyNovych[i].max.z)] })),
    upravy, kolize, kolizeKaroserie, zasuny: zasunyPocet, zasunyPanelu,
    // Kolik zasunu se u panelu OCEKAVA: svisle vyplne 4 (drzene po celem
    // obvodu), ale VODOROVNA DNA a POLICE jen 2 - Robert 2026-09-10 ("dno
    // ... musi byt vzdy kratsi o 1mm nez podelnik ... aby nekolidoval se
    // svislimi profily nohy ani s prickami"): dno lezi vyhradne v drazkach
    // obou podelniku a konce ma ZAMERNE volne. Bez teto vyjimky by kontrola
    // hlasila kazde dno jako "nedostatecne drzene", coz uz neni pravda.
    panelyMaloDrzene: Object.entries(zasunyPanelu)
      .filter(([r, n]) => n < (/^vypln-(dno|police)/.test(r) ? 2 : 4))
      .map(([r, n]) => ({ role: r, zasunu: n })),
    upraveneParts: upravenaData.parts,
  };

  if (jsonOut) { console.log(JSON.stringify(vysledek, null, 1)); return; }
  console.log("=== HORNI RAM regalu (zona pro dlouhe predmety) ===");
  console.log(`  zadni hloubkovy posun pouzit: ${vysledek.zadniHloubkaPosunPouzit} mm`);
  console.log(`  vrch nejvyssiho boxu: ${vysledek.nejvyssiBox} mm`);
  console.log(`  konec nohy:           ${vysledek.konecNohy} mm`);
  console.log(`  pasmo hornich profilu: Y=[${vysledek.pasmoHorni}]`);
  console.log(`  pasmo spodnich:        Y=[${vysledek.pasmoSpodni}]`);
  console.log(`  svetla vyska ramu:     ${vysledek.svetlaVyskaRamu} mm (sem prijde vypln)`);
  console.log(`\n  NOVE DILY (${vse.length}):`);
  vysledek.nove.forEach(d => console.log(`   ${d.role.padEnd(26)} ${String(d.delka).padStart(6)} mm  Y=[${d.Y}] Z=[${d.Z}]`));
  console.log(`\n  zkraceno stredovych sloupku: ${upravy.zkraceno.length} (${upravy.zkraceno.map(z => z.role).join(", ")})`);
  console.log(`  odebrano hornich zaslepek:   ${upravy.odebranoZaslepek}`);
  // Vypln musi byt drzena po CELEM obvodu - u obdelnikoveho panelu tedy
  // nejmene 4 zasuny (dna jich mivaji vic, protoze u prepazky dosedaji i na
  // obe svislice nohy). Ocekavany pocet: svisle vyplne 4, vodorovna dna a
  // police 2 (viz panelyMaloDrzene vyse) - mene = nedostatecne drzeny.
  console.log(`  zamernych zasunu do drazek: ${vysledek.zasuny}`);
  Object.entries(vysledek.zasunyPanelu).sort().forEach(([r, n]) =>
    console.log(`     ${r.padEnd(22)} ${n}x`));
  console.log(`  panely pod ocekavanym poctem zasunu: ${vysledek.panelyMaloDrzene.length
    ? JSON.stringify(vysledek.panelyMaloDrzene) : "zadny"}`);
  console.log(`\n  kolize s dily:     ${kolize.length ? JSON.stringify(kolize) : "zadna"}`);
  console.log(`  kolize s karoserii: ${kolizeKaroserie.length ? kolizeKaroserie.join(", ") : "zadna"}`);
}

if (require.main === module) main();
module.exports = { analyzuj, podelnik };
