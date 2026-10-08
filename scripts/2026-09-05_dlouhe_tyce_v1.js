// VERZE 1 pro ukladani dlouhych tyci: propojeni noh v ZADNI casti nad boxy.
// bot8 2026-09-05.
//
// Robert: "verze moznosti: propojeni nohou v zadni casti" + "toto je moznost
// Eko, bez vyplni" + "vem jeden regal a aplikuj verzi 1 pro ukladani dlouhych tyci".
//
//   node scripts/2026-09-05_dlouhe_tyce_v1.js            # spocitat + overit (nic neuklada)
//   node scripts/2026-09-05_dlouhe_tyce_v1.js --json
//
// CO TO DELA
// Vezme existujici regal (vychozi: product_assemblies id=187, Jumpy L2 CI25),
// najde v nem nohy a nejvyssi box, a nad boxy pripoji PODELNY profil spojujici
// vsechny nohy na zadni (stenove) strane. Nic neuklada do DB - jen spocita,
// overi kolize a vypise cisla pro technicky rez.
//
// PROC PRAVE TAM
// Robert upresnil: "proste chci propojit konce nohou" - tedy HORNI KONCE noh,
// ne nejakou vysku nad boxy. Nohy CI25 konci na Y=1190 (svislice
// "predni-svislice" i "cap"). Podelnik se proto kotvi tak, aby jeho horni
// hrana lícovala s koncem nohy.
// V ZADNI casti = na linii "cap" X[-681,-651]; to je nejzazsi (stenova)
// svislice, ktera nad urovni boxu jeste pokracuje (zadni svislice konci uz
// na Y=922).
//
// Predchozi verze mirila na "tesne nad boxy" (Y=930..960) - to bylo spatne
// pochopene zadani, ponechano jen jako volba --nad-boxy pro srovnani.
//
// EKO = jen profil, zadna police ani vyplne. Robert: "bud to tam vleze nebo
// nevleze, to si zakaznik poresi sam" - cilem je konstrukcni propojeni konců
// noh, ne navrh ulozneho lozе na konkretni prumer tyci.
const fs = require("fs");
const path = require("path");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const PROFIL = "Object_7";          // 30x30 profil, stejny jako zbytek regalu
const T = 30;                        // prurez profilu [mm]
const MEZERA_NAD_BOXY = 4;           // vule mezi hornim okrajem boxu a profilem [mm]

function bboxDilu(p, cache) {
  const pid = p.part_id;
  if (!cache[pid]) {
    const f = KAT + pid + ".glb";
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
  const podle = r => dily.filter(d => d.role === r);
  const caps = podle("cap");
  if (!caps.length) throw new Error("sestava nema dily role 'cap' - jina konstrukce nohy");

  const boxy = dily.filter(d => d.role.startsWith("eurobox"));
  if (!boxy.length) throw new Error("sestava nema euroboxy");
  const nejvyssiBox = Math.max(...boxy.map(d => d.b.max.y));

  // linie "cap" v ose X (zadni cast nad boxy) - u vsech noh stejna
  const predni = podle("predni-svislice");
  if (!predni.length) throw new Error("sestava nema 'predni-svislice'");
  const predniX0 = Math.min(...predni.map(d => d.b.min.x));
  const predniX1 = Math.max(...predni.map(d => d.b.max.x));
  const predniPodleZ = predni.map(d => ({ z0: d.b.min.z, z1: d.b.max.z, yKonec: d.b.max.y }))
    .sort((p1, p2) => p1.z0 - p2.z0);
  const capX0 = Math.min(...caps.map(d => d.b.min.x));
  const capX1 = Math.max(...caps.map(d => d.b.max.x));
  // konec KAZDE nohy zvlast - nohy nemusi byt stejne vysoke
  const capyPodleZ = caps.map(d => ({ z0: d.b.min.z, z1: d.b.max.z, yKonec: d.b.max.y }))
    .sort((p1, p2) => p1.z0 - p2.z0);
  // Z rozsah = od nejzazsi po nejblizsi nohu (profil je propojuje vsechny)
  const capZ0 = Math.min(...caps.map(d => d.b.min.z));
  const capZ1 = Math.max(...caps.map(d => d.b.max.z));
  const capYmax = Math.max(...caps.map(d => d.b.max.y));

  return { dily, caps, capyPodleZ, predni, predniX0, predniX1, predniPodleZ,
           nejvyssiBox, capX0, capX1, capZ0, capZ1, capYmax, boxy };
}

// KONVENCE ORIENTACE PROFILU (prevzata z existujicich dilu teto sestavy,
// nevymyslena znovu - viz nosnik-sloupec0-patro3 / spojnice-horni / predni-svislice):
//   Object_7 je metrova tyc orientovana podel Y, prurez 30x30 v X a Z.
//   svisly (podel Y):     quaternion [0, 0, 0, 1]
//   podelny (podel Z):    quaternion [-0.7071, 0, 0, 0.7071]   (-90 kolem X)
//   pricny (podel X):     quaternion [0, 0, -0.7071, 0.7071]   (-90 kolem Z)
//   delka se vzdy dela scale.y = delka/1000, `position` je geometricky STRED dilu.
// Prvni pokus tohle ignoroval a vyrobil svisly 1000mm profil misto podelneho -
// proto je konvence radeji zapsana sem.
const Q_PODELNY = [-0.7071067811865475, 0, 0, 0.7071067811865476];
const Q_PRICNY = [0, 0, -0.7071067811865475, 0.7071067811865476];
const DELKA_PROFILU_MM = 1000;

function main() {
  const jsonOut = process.argv.includes("--json");
  const asmPath = "/tmp/claude-0/-opt-konfigurator/cd1e4f98-59ca-4757-a63c-ad69ec4e8fb4/scratchpad/asm187.json";
  const data = JSON.parse(fs.readFileSync(asmPath, "utf8"));
  const a = analyzuj(data);

  // --- umisteni podelneho profilu -----------------------------------------
  // VYCHOZI: horni hrana podelniku lícuje s KONCEM nohy (Robert: "proste chci
  // propojit konce nohou"). Volba --nad-boxy zachovava starsi umisteni tesne
  // nad nejvyssim boxem, jen pro srovnani.
  // Robert 2026-09-05: "Y zalezi na typu nohy a boxech ktere jsou vlozene" -
  // vyska se proto NEZADRATOVAVA, odvozuje se pro KAZDY SEGMENT zvlast ze dvou
  // veci, ktere se vuz od vozu i regal od regalu lisi:
  //   (1) konec nohy - a to MINIMUM z obou noh, ktere segment spojuje
  //       (nohy nemusi byt stejne vysoke; kdyby se vzalo maximum, u nizsi nohy
  //        by podelnik precnival za jeji konec),
  //   (2) vrch nejvyssiho vlozeneho boxu - spodni hrana podelniku pod nej
  //       nesmi klesnout.
  // Kdyby (2) bylo vys nez (1), je to skutecny konflikt dane kombinace noha +
  // skladba boxu a hlasi se jako chyba, nemlci se o tom.
  const nadBoxy = process.argv.includes("--nad-boxy");
  const xStred = (a.capX0 + a.capX1) / 2;      // linie zadni (stenove) casti nad boxy
  const zOd = a.capZ0, zDo = a.capZ1;
  const delka = zDo - zOd;

  // ROBERT 2026-09-05 (upresneni): "ten podelnik musi byt mezi koncovymi
  // nohami, stredove konce nohou se o 30mm zkrati".
  // Tedy JEDEN PRUBEZNY profil od koncove nohy ke koncove noze (T-styl: dorazi
  // celem na jejich "cap", neprochazi skrz), a KAZDA STREDOVA noha se nahore
  // zkrati o T=30mm, aby pod nim prosla a profil na ni dosedl.
  // Predchozi verze delala dva samostatne segmenty mezi sousednimi nohami -
  // to bylo spatne pochopeni.
  const capyZ = a.capyPodleZ;
  if (capyZ.length < 2) throw new Error("regal ma min. 2 nohy pro podelnik");
  const prvni = capyZ[0], posledni = capyZ[capyZ.length - 1];
  const stredove = capyZ.slice(1, -1);

  // vyska: min z KONCOVYCH noh (ty profil nesou celem), viz Robert
  // "Y zalezi na typu nohy a boxech ktere jsou vlozene"
  const yHor = nadBoxy ? (a.nejvyssiBox + MEZERA_NAD_BOXY + T)
                       : Math.min(prvni.yKonec, posledni.yKonec);
  const yDol = yHor - T;
  if (yDol < a.nejvyssiBox) {
    throw new Error(`KONFLIKT: spodek podelniku ${Math.round(yDol)} by byl pod vrchem `
      + `nejvyssiho boxu ${Math.round(a.nejvyssiBox)} - tahle kombinace noha+boxy to nedovoli`);
  }

  const zOdSeg = prvni.z1, zDoSeg = posledni.z0;
  const delkaSeg = zDoSeg - zOdSeg;
  const segmenty = [{
    part_id: PROFIL,
    position: [xStred, (yDol + yHor) / 2, (zOdSeg + zDoSeg) / 2],
    quaternion: Q_PODELNY,
    scale: [1, delkaSeg / DELKA_PROFILU_MM, 1],
    role: "podelnik-konce-noh-zadni",
  }];

  // --- PRICKY (verze 2) ----------------------------------------------------
  // Robert: "propojeni v ramci kazde nohy predni a zadni nejvyssi profil, tak
  // aby horni hrana profilu prevysovala vsechny boxy" + "podelnik je ok dal to
  // chce ty pricky".
  // Pricka vede podel X od zadni (cap) svislice k predni svislici, u KAZDE nohy,
  // horni hranou lícujici s koncem te nohy.
  // POZOR na stredove nohy: tam uz na zkracenem capu SEDI podelnik (Y[yDol,yHor],
  // X[capX0,capX1]). Pricka proto nesmi zacinat na capu, ale az na VNITRNI hrane
  // podelniku - jinak by do nej zajela. U koncovych noh podelnik dorazi celem
  // zboku (jiny Z), takze tam pricka muze zacit na capu normalne.
  const pricky = [];
  const stredoveZ = new Set(stredove.map(c => Math.round((c.z0 + c.z1) / 2)));
  for (let i = 0; i < capyZ.length; i++) {
    const cap = capyZ[i];
    const zStred = Math.round((cap.z0 + cap.z1) / 2);
    const pv = a.predniPodleZ.find(q => Math.abs((q.z0 + q.z1) / 2 - zStred) < 1);
    if (!pv) { console.error(`noha Z=${zStred}: chybi predni-svislice, pricka preskocena`); continue; }
    const jeStredova = stredoveZ.has(zStred);
    // Horni hrana pricky lícuje s koncem nohy u VSECH noh stejne.
    // U stredove nohy se pricka neopira o zkraceny cap (ten konci o T niz),
    // ale o PODELNIK, ktery na nem sedi a saha zpet az na yHor - takze zadna
    // sleva na vysce. Prvni verze tu odecetla T i u stredove nohy a pricka
    // vysla o 30 mm niz nez u krajnich noh (viditelne schod v konstrukci).
    const yHorP = Math.min(jeStredova ? yHor : cap.yKonec, pv.yKonec);
    const yDolP = yHorP - T;
    if (yDolP < a.nejvyssiBox) {
      console.error(`noha Z=${zStred}: pricka by byla pod vrchem boxu, preskocena`);
      continue;
    }
    const xOd = jeStredova ? a.capX1 : a.capX1;   // vnitrni hrana zadni svislice
    const xDo = a.predniX0;                        // zadni hrana predni svislice
    const delkaP = xDo - xOd;
    if (delkaP <= 1) { console.error(`noha Z=${zStred}: nulova delka pricky`); continue; }
    pricky.push({
      part_id: PROFIL,
      position: [(xOd + xDo) / 2, (yDolP + yHorP) / 2, zStred],
      quaternion: Q_PRICNY,
      scale: [1, delkaP / DELKA_PROFILU_MM, 1],
      role: `pricka-konce-nohy-${i}`,
      _y: [yDolP, yHorP],
    });
  }

  // zkraceni stredovych noh o T a odstraneni jejich horni zaslepky:
  // profil na zkraceny konec DOSEDNE, takze uz to neni volne celo - zaslepka
  // mezi profil a nohu nepatri (byl by to 9mm plat ve spoji).
  const upravy = { zkraceneCapy: [], odstraneneZaslepky: [] };
  for (const stred of stredove) {
    const zStred = (stred.z0 + stred.z1) / 2;
    for (const d of a.dily) {
      const dz = (d.b.min.z + d.b.max.z) / 2;
      if (Math.abs(dz - zStred) > 1) continue;
      if (d.role === "cap") {
        const novaDelka = (d.b.max.y - d.b.min.y) - T;
        upravy.zkraceneCapy.push({
          z: Math.round(zStred),
          puvodni: { scaleY: d.p.scale[1], posY: d.p.position[1], vrch: Math.round(d.b.max.y) },
          novy: {
            scaleY: novaDelka / DELKA_PROFILU_MM,
            posY: d.p.position[1] - T / 2,
            vrch: Math.round(d.b.max.y - T),
          },
        });
      } else if (d.role === "zaslepka"
                 && d.b.min.x >= xStred - T && d.b.max.x <= xStred + T
                 && d.b.max.y > yDol) {
        upravy.odstraneneZaslepky.push({ z: Math.round(zStred), Y: [Math.round(d.b.min.y), Math.round(d.b.max.y)] });
      }
    }
  }

  // --- sestaveni UPRAVENE sady dilu ---------------------------------------
  // Kontroly musi bezet proti stavu PO uprave, ne pred ni. Prvni verze
  // kontrolovala novy profil proti PUVODNIM dilum a hlasila kolizi
  // s capem/zaslepkou stredove nohy - tedy prave s tim, co se ma zkratit
  // a odstranit. Falesny poplach, ale stejne zavazny jako opravdovy: bez teto
  // opravy by "kolize 0" nikdy nenastalo a nikdo by nepoznal skutecnou kolizi.
  const idxCap = new Map(upravy.zkraceneCapy.map(u => [u.z, u]));
  const zaslepkyKOdstraneni = new Set(upravy.odstraneneZaslepky.map(u => u.z));
  const priloz = process.argv.includes("--bez-pricek") ? [] : pricky;
  const upraveneParts = [];
  for (const p0 of data.parts) {
    if (String(p0.part_id).startsWith("car_body_")) { upraveneParts.push(p0); continue; }
    const zStred = Math.round(p0.position[2]);
    const role = p0.role || p0.part_id;
    if (role === "cap" && idxCap.has(zStred)) {
      const u = idxCap.get(zStred);
      upraveneParts.push({ ...p0,
        position: [p0.position[0], u.novy.posY, p0.position[2]],
        scale: [p0.scale[0], u.novy.scaleY, p0.scale[2]] });
      continue;
    }
    if (role === "zaslepka" && zaslepkyKOdstraneni.has(zStred)
        && p0.position[0] >= xStred - T && p0.position[0] <= xStred + T
        && p0.position[1] > yDol) {
      continue;   // odstranena
    }
    upraveneParts.push(p0);
  }
  const upravenaData = { ...data, parts: [...upraveneParts, ...segmenty, ...priloz] };

  // --- overeni -------------------------------------------------------------
  const cache = {};
  const vsechnyNove = [...segmenty, ...priloz];
  const boxy = vsechnyNove.map(sg => bboxDilu(sg, cache));
  const bNovy = boxy.reduce((acc, b) => acc ? acc.union(b) : b.clone(), null);
  const R = v => Math.round(v * 10) / 10;

  const bPod = boxy[0];
  const vysledek = {
    sestava: 187,
    nejvyssiBox: R(a.nejvyssiBox),
    profil: {
      X: [R(bPod.min.x), R(bPod.max.x)],
      Y: [R(bPod.min.y), R(bPod.max.y)],
      Z: [R(bPod.min.z), R(bPod.max.z)],
      delka: R(bPod.max.z - bPod.min.z),
      segmenty: segmenty.map((sg, i) => ({
        role: sg.role,
        Z: [R(boxy[i].min.z), R(boxy[i].max.z)],
        Y: [R(boxy[i].min.y), R(boxy[i].max.y)],
        delka: R(boxy[i].max.z - boxy[i].min.z),
      })),
    },
    kontroly: {},
  };

  // 1) horni hrana profilu MUSI prevysovat vsechny boxy
  vysledek.kontroly.nadBoxy = {
    ok: bNovy.min.y >= a.nejvyssiBox,
    rezervaPodSpodkem: R(bNovy.min.y - a.nejvyssiBox),
    prevyseniNadBoxy: R(bNovy.max.y - a.nejvyssiBox),
  };

  // 2) profil nesmi kolidovat s zadnym dilem regalu (krome doteku s 'cap')
  // dily PO uprave, proti kterym se kontroluje
  const aUpr = analyzuj(upravenaData);
  const kolize = [];
  for (let i = 0; i < vsechnyNove.length; i++) {
    const bs = boxy[i];
    for (const d of aUpr.dily) {
      if (String(d.role).startsWith("podelnik") || String(d.role).startsWith("pricka")) continue;
      const px = Math.min(bs.max.x, d.b.max.x) - Math.max(bs.min.x, d.b.min.x);
      const py = Math.min(bs.max.y, d.b.max.y) - Math.max(bs.min.y, d.b.min.y);
      const pz = Math.min(bs.max.z, d.b.max.z) - Math.max(bs.min.z, d.b.min.z);
      if (px > 0.5 && py > 0.5 && pz > 0.5) {
        kolize.push({ segment: vsechnyNove[i].role, role: d.role, prunik: [R(px), R(py), R(pz)] });
      }
    }
  }
  vysledek.kontroly.kolizeSDily = kolize;

  // 3) kolize se skutecnou karoserii
  const eng = createEngine("Citroën_Jumpy_CI25_2021-");
  vysledek.kontroly.kolizeSKaroserii = vsechnyNove.some(sg => {
    const mesh = parseGlbMesh(KAT + PROFIL + ".glb");
    mesh.position.set(...sg.position);
    mesh.quaternion.set(...sg.quaternion);
    mesh.scale.set(...sg.scale);
    mesh.updateMatrixWorld(true);
    return eng.collidesWithWalls(mesh);
  });

  // 5) mezera mezi podelnikem a stenou v jeho vysce - urcuje, jestli tyc
  //    ulozena na profil muze zapadnout mezi profil a bok, misto aby lezela na nem
  {
    const rc = new THREE.Raycaster(); rc.firstHitOnly = true; rc.far = 3000;
    const smer = new THREE.Vector3(eng.mirror ? -1 : 1, 0, 0);
    const yTest = bNovy.max.y;
    const vzd = [];
    for (let i = 0; i < 15; i++) {
      const z = bNovy.min.z + (bNovy.max.z - bNovy.min.z) * (i / 14);
      rc.set(new THREE.Vector3(0, yTest, z), smer);
      const h = rc.intersectObject(eng.wallL, true);
      if (h.length) vzd.push(h[0].distance);
    }
    const stenaX = vzd.length ? -Math.min(...vzd) : null;   // mirror => zaporne X
    vysledek.kontroly.mezeraKeStene = stenaX == null ? null
      : R(Math.abs(bNovy.min.x - stenaX));
    vysledek.kontroly.stenaXvVysceProfilu = stenaX == null ? null : R(stenaX);
  }

  // 4) kolik prostoru zbyva nad profilem ke strese
  const boxL = eng.boxL0;
  vysledek.kontroly.prostorNadProfilem = R(boxL.max.y - bNovy.max.y);

  vysledek.dily = vsechnyNove;
  vysledek.upravy = upravy;
  vysledek.upraveneParts = upravenaData.parts;

  if (jsonOut) { console.log(JSON.stringify(vysledek, null, 1)); return; }

  console.log(`=== VERZE 1 (Eko): podelnik spojujici ${nadBoxy ? "nohy nad boxy" : "KONCE noh"}, zadni cast ===`);
  console.log(`  sestava:            id=187 Jumpy L2 CI25`);
  console.log(`  nejvyssi box konci: Y=${vysledek.nejvyssiBox} mm`);
  console.log(`  konec nohy (cap):   Y=${R(a.capYmax)} mm`);
  console.log(`  podelny profil:     X=[${vysledek.profil.X}]  Y=[${vysledek.profil.Y}]  Z=[${vysledek.profil.Z}]`);
  console.log(`  (Y se odvozuje: min(konec obou noh segmentu), kontrola proti vrchu boxu pod nim)`);
  console.log(`  delka podelniku:    ${vysledek.profil.delka} mm (mezi koncovymi nohami)`);
  console.log(`  zkracene stredove nohy: ${upravy.zkraceneCapy.length}x o ${T} mm`);
  upravy.zkraceneCapy.forEach(u => console.log(`     Z=${u.z}: vrch ${u.puvodni.vrch} -> ${u.novy.vrch} mm`));
  console.log(`  odstranene horni zaslepky stredovych noh: ${upravy.odstraneneZaslepky.length}x`);
  console.log(`  pricky (verze 2): ${priloz.length}x`);
  priloz.forEach(pk => console.log(`     ${pk.role}: Z=${Math.round(pk.position[2])} Y=[${pk._y.map(Math.round)}] delka ${Math.round(pk.scale[1]*DELKA_PROFILU_MM)} mm`));
  console.log();
  console.log("  KONTROLY");
  const k = vysledek.kontroly;
  console.log(`   horni hrana nad vsemi boxy:  ${k.nadBoxy.ok ? "OK" : "CHYBA"}  (spodek +${k.nadBoxy.rezervaPodSpodkem} mm, vrch +${k.nadBoxy.prevyseniNadBoxy} mm nad boxy)`);
  console.log(`   kolize s dily regalu:        ${kolize.length === 0 ? "zadna" : JSON.stringify(kolize)}`);
  console.log(`   kolize s karoserii:          ${k.kolizeSKaroserii ? "ANO - PROBLEM" : "zadna"}`);
  console.log(`   volny prostor nad profilem:  ${k.prostorNadProfilem} mm ke strese`);
  console.log(`   mezera profil <-> bok:       ${k.mezeraKeStene} mm (bok je ve vysce profilu na X=${k.stenaXvVysceProfilu})`);
}

if (require.main === module) main();
module.exports = { analyzuj };
