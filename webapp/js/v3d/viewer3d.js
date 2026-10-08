/*
 * viewer3d.js - sdileny 3D prohlizec online nabidky (bot10, 2026-10-01).
 *
 * Classic script nad globalnim THREE r128 (stejne jako nabidka-online.html:
 * three.min.js + OrbitControls + GLTFLoader z jsdelivr), navic potrebuje
 * examples/js: environments/RoomEnvironment.js, renderers/CSS2DRenderer.js,
 * shaders/HorizontalBlurShader.js, shaders/VerticalBlurShader.js
 * (presne poradi viz V3D.deps). Bez nich bezi taky, jen bez prostredi /
 * popisku kot / kontaktniho stinu.
 *
 * API:
 *   var v = V3D.mount(container, {
 *     modelUrl | arrayBuffer,           // GLB
 *     mode: 'real' | 'wire',            // vychozi: spec -> 'real', legacy -> 'wire'
 *     allowReal: false,                 // legacy GLB (bez v3d): jen dratovy, segment Vzhled skryty
 *                                       // (Robert 2026-09-14); true = povolit i Skutecny
 *     dims: 0 | 1 | 2,                  // vychozi: spec -> 1, legacy -> 2 (jako dnes); s hudKoty:false -> 0
 *                                       // dims:0 = koty se nestavi vubec (ani geometrie, ani DOM popisky)
 *                                       // dokud je nekdo nezapne (HUD / v.setDims)
 *     hudKoty: true | false,            // false = HUD nema prepinac Koty (verejna stranka); vychozi true
 *     hudDock: 'top',                   // tlacitka HUD v pruhu NAD platnem (nezakryvaji model); platno je zbytek vysky. Vychozi: tlacitka v rozich platna
 *     bom: { items, onPick(groupIdx) }, // klikaci kusovnik (userData.g / bomgrp_N)
 *     onPick(slotId),                   // klik/klepnuti na dil: slotId = cele cislo userData.g nejblizsiho
 *                                       // predka (nic jineho - zadna jmena uzlu); uzly bez g klik ignoruji;
 *                                       // pohyb ma prednost jen u dilu z motions[].pick, jinak onPick
 *     track(key, detail),               // statistiky (interact_3d_model, v3d_view, v3d_dims, v3d_mode, v3d_anim)
 *     reducedMotion,                    // vychozi z prefers-reduced-motion
 *     onReady(api), onError(err)
 *   });
 *   v.ready (Promise; dispose() pred nactenim = reject 'disposed'; setModel ho nerusi)
 *   v.setModel(urlNeboArrayBuffer, {keepCamera:false}) -> Promise<api>: vymena modelu za behu (viz nize)
 *   v.setView('front'|'side'|'top'|'iso'|'reset') ; v.setDims(0|1|2)
 *   v.setMode('real'|'wire') ; v.play(id, dir) ; v.playAll(dir) ; v.setT(id, t)
 *   v.highlight(setOrArray) ; v.zoom(+1|-1) ; v.fullscreen(bool?) ; v.state() ; v.dispose()
 *   v.snapshot({width, type, quality, background}) -> Promise<dataURL> (png/jpeg; pixely platna, texty kot v obraze nejsou; viz kod)
 *   v.cameraInfo() ; v.onCamera(cb) -> odhlaseni (stav kamery po kazdem snimku)
 *   1.11.0 (bot10 2026-10-06, Robert): motions[].g = 'left'|'right'|'bulkhead' (strana spolecne nabidky) -> tlacitka pohybu ve VICE RADACH podle strany (popisek strany, barva, Otevrit/Zavrit vse jen pro stranu,
 *     cislovani n po stranach); opts.selDims: true -> klik na dil / cip pohybu vybere komponent a ukaze jeho rozmery (v.selectMotion(id|null); zrusi klik mimo model, Vychozi pohled, vyber jineho dilu)
 *   1.12.0: barvy a sytost materialu: opts.matConfig / v.setMatConfig({sat: 0-2, colors: {'#puvodni': '#nova'}}) / v.getMatConfig() / v.resetMatConfig() / v.materialPalette() (nehlinikove materialy podle PUVODNI barvy)
 *   1.13.0: opts.hoverHint: true -> pri najeti MYSI (ne dotykem) na pohyblivy dil se dil podsviti (pruhledna oranzova vrstva na jeho meshich, material modelu se nemeni), kurzor je ruka a u kurzoru se
 *     ukaze vyzva "Suplik 2 · Leva strana / Kliknutim otevrete" (po otevreni "zavrete"; box na zavrenem vysuvu: "otevrete: Vysuv 1"). Jen tam, kde klik skutecne spusti pohyb (pravidlo jako pickAt;
 *     dil, jehoz klik jde do onPick stranky, vyzvu nema). Texty L.hover_open / L.hover_close. Drateny vzhled: jen popisek a kurzor. Vychozi vypnuto (nabidky a kontrolni scena zapinaji).
 *   1.14.0: odlesky a AO plynule (Robert 2026-10-07: "reseni odlesku materialu, jejich AO"): matConfig.gloss {'#puvodni': 0-2} = lesk NE-hlinikoveho materialu podle jeho puvodni barvy (1 = beze zmeny, 0 = mat,
 *     2 = dvojnasobny; drsnost' = puvodni^lesk); opts.aluConfig / v.setAluConfig({refl: 0-1.5, rough: 0.5-2}) = sila odrazu a matnost hliniku (nasobky hodnot zvolene varianty hliniku);
 *     opts.aoConfig / v.setAoConfig({k: 0-2, r: 0.25-3}) = sila a dosah AO (nasobky hodnot zvolene varianty AO; pri AO 'Vyp' bez ucinku); getAluConfig / resetAluConfig, getAoConfig / resetAoConfig; ladici hooky aluInfo(), aoValues().
 *   1.15.0: V3D.addEnvLibrary([{key, label, mul0, rot0_deg, url, lo}]) = HDRI doplnena ze Sdileneho disku (api/v3d_env_import.py; verejny GET /api/public/v3d-vzhled je vraci jako hdri_extra): rozsiri
 *     V3D.envLibrary (pred volbu Mistnost) a knihovnu pro normalizeEnvConfig / setEnvConfig / opts.envConfig; vraci pole pridanych klicu. Volat PRED V3D.mount a PRED V3D.envPicker. Jen klice
 *     [a-z][a-z0-9_]{2,39} bez kolize s vestavenymi, URL jen /api/public/v3d-env/<klic>_1024.hdr (a _256.hdr jako nahled).
 *   1.16.0: AO po komponentech (Robert 2026-10-07: "nenasel jsem AO pro jednotlive komponenty, jen pro hlinikove profily"): matConfig.ao {'#puvodni': 0-2} = sila AO na dilech teto PUVODNI barvy
 *     (nasobek sily AO; 1 = beze zmeny, 0 = bez AO, 2 = dvojnasobna) a aluConfig.ao 0-2 = totez pro hlinikove profily. Uplatni se jen pri zapnutem AO; AO se pocita z hloubky celeho obrazu (jako dosud),
 *     vaha se jen priklada k tmavnuti kazdeho pixelu podle materialu zakryvajiciho povrch (extra pruchod sceny do rtW, jen kdyz ma nejaky material vahu jinou nez 1). getMatConfig / getAluConfig / materialPalette
 *     nesou ao; hooky matInfo()/aluInfo() aoW, aoValues() wPasses / wMeshes.
 *   1.17.0: VYCHOZI UHEL POHLEDU 3D (Robert 2026-10-08: "chci nastavit vychozi uhel pohledu 3D v generatorech"): opts.isoAngles {az, el} (stupne) = uhel pohledu "3D" (az = otoceni od cela modelu,
 *     el = naklon nad vodorovnou; vychozi 35 / 25) - plati pro prvni zaber, tlacitko 3D / Vychozi pohled i znovuzaber pri zmene velikosti; vzdalenost se dopocte presne jako dosud (cely model v zaberu).
 *     v.setIsoAngles({az, el} | null, fly) (null = puvodnich 35 / 25; fly=true kameru tam preleti) -> true | false (mimo meze), v.currentAngles() -> {az, el} AKTUALNI kamery vuci celu modelu (stejne
 *     stupne; to, co admin ulozi jako vychozi) | null, state().isoAngles, V3D.normalizeIsoAngles(c) -> {az (-180..180], el (-15..85)} zaokrouhleno na 0,1 | null. Bez volby se nic nemeni.
 *   opts.envEager: true               // HDRI prostredi se stahuje hned pri mountu (chovani do 1.9.0); vychozi false: velke HDRI (1-2 MB) se stahuje AZ PO prvnim
 *                                     // zobrazenem modelu (soutezilo o pasmo s GLB a zdrzovalo ho na mobilni siti o ~0,8 s) a do te doby osvetluje maly nahled
 *                                     // stejneho HDRI (env/<klic>_256.hdr, 33-133 kB; na vzhled modelu vliv do 3/255), po prichodu plneho HDRI se vymeni.
 *                                     // Explicitni zmena prostredi (setEnvironment/setEnvConfig/resetEnvConfig) a snapshot() plne HDRI pousti hned.
 *   opts.plugins: [function (ctx) { ...; return dispose }] - rozsireni po postaveni modelu (animace z GLB, popisky, kamera);
 *     ctx = { THREE, gltf, model, scene, camera, controls, renderer, root, stage, container, state, labels, requestRender,
 *     setAnimating(bool), onFrame(fn(tMs)) -> off } (viz komentar "pluginy" v kodu; priklad: js/v3d/demo-stavebnice.js)
 *   v.setAO('vyp'|'jemne'|'stredni'|'silne') -> true | false (neznama volba / prohlizec bez highp); opts.aoVariant = vychozi;
 *     V3D.aoVariants = [{key, label}]; state().ao / .aoActive / .aoSupported. Zakaznik (bez opts.ladeni) ma 'vyp' = kresleni
 *     presne jako bez AO; opts.ladeni:true -> HUD radek "AO", pamatuje se (localStorage v3dAO), jde predvolit v URL (?ao=<klic>),
 *     vychozi 'stredni'. AO nema zadnou zavislost (V3D.depsOptional = []), v dratenem vzhledu je vypnute.
 *
 * setModel(src, {keepCamera}) (bot16/bot3 2026-10-02):
 *  - src = URL (string) | ArrayBuffer | typed array (Uint8Array...). Stary model zustane videt a
 *    ovladatelny, dokud se novy nenacte a nepostavi; pak se vymeni naraz (zadny prazdny snimek).
 *  - keepCamera:true = pozice kamery, target a vzdalenost beze zmeny (limity vzdalenosti se jen
 *    rozsiri, aby je nova scena nepresunula); false (vychozi) = jako po prvnim nacteni (3D pohled
 *    na cely novy model). Pri zmene spec.front se nazev pohledu (HUD) zrusi.
 *  - Znovu se spocita vsechno z noveho GLB (spec v3d v scenes[0].extras.v3d, pivoty, pohyby,
 *    blokujici dvojice, koty, kusovnik/g, stin); GLB bez spec = legacy jako dnes. Stav pohybu a
 *    zvyrazneni se resetuje. Volba Vzhled/Koty (HUD, v.setMode/setDims) se zachova.
 *    Volitelne {bom: {items, onPick}} (jako opts.bom) vymeni kusovnik (gating items[].mesh_group) az
 *    po uspesne vymene; bez nej zustava puvodni opts.bom. onPick(slot) se nemeni.
 *  - Geometrie, materialy, textury, cile renderu a popisky kot stareho modelu se uvolni.
 *  - Selhani (nenacteni, rozbity GLB, vyjimka pri stavbe) = reject; stary model, kamera i stav
 *    zustanou beze zmeny. Rychle opakovani: kazde dalsi volani okamzite odmitne nedokoncena
 *    starsi (Error s .superseded = true) - vyhrava posledni, nikdy dva modely. dispose() odmitne
 *    nedokoncena volani (Error 'V3D: disposed'). Promise se resolvuje hodnotou api.
 *   V3D.isFullscreen(container?) - je prohlizec (v kontejneru) na cele obrazovce?
 *     (stranka nabidky: sipky na klavesnici nesmi behem toho prepinat slidy)
 *
 * Pohyby v kombinaci (nalez 3 kontroly 2026-10-01):
 *  - "Otevrit vse" otevira jen supliky, vysuvy a dvirka; boxy jen jednotlive.
 *    U oboustranne sestavy (pohyby na obe strany podel front) jen stranu
 *    privracenou ke kamere.
 *  - Pri nacteni se spocitaji blokujici dvojice (Box3 meshu podstromu v
 *    otevrenem stavu, jen novy presah proti zavrenemu stavu). Otevreni pohybu
 *    nejdriv zavre to, co mu blokuje misto (zvednuty box x vysunuty vysuv nad
 *    nim, box x sklopena dvirka, boxy dvou stran v ulicce).
 *  - Klik na box pri zavrenem vysuvu jen vysune vysuv; druhy klik zvedne box.
 *
 * Cipy pohybu (Robert 2026-10-02): popisek = druh + cislo v ramci druhu: "Šuplík 1", "Výsuv 2", "Dvířka 3",
 * "Podlahová dvířka 1" a u boxu podle motions[].sub (vycet) "KLT box 1" / "Multibox 2" / "Eurobox 3" /
 * "Kufřík 1"; box bez sub = "Box N". Zadny text ze spec se nezobrazuje, jen fixni ceske nazvy. Cipy jsou
 * seskupene podle druhu (jedna skupina = jeden druh / druh boxu, oddelene carou); "Otevrit vse / Zavrit vse"
 * zustavaji na konci a pri dlouhe liste se drzi u praveho okraje.
 *
 * Datova struktura v3d v1 (scenes[0].extras.v3d) - viz validateSpec().
 * GLB bez v3d (dnesni nabidka 103 s bomgrp_N) = legacy: dratovy rezim,
 * celkove kóty + delky profilu, zvyrazneni kusovniku - jako dnes.
 *
 * Zasady (pasti z nabidka-online.html):
 *  - JEDEN stav materialu: kazdy zapis mesh.material jde pres
 *    refreshMeshMaterial() a deje se jen synchronne (nacteni, setMode,
 *    highlight). Zadne timery/promisy, ktere by material prepsaly pozdeji
 *    (bug "drateny se pri prvnim pohybu zmeni na renderovany").
 *  - Zadny globalni prepis barvy/drsnosti/kovovosti (dnesni r. 2244).
 *  - HDRI se nestahuje PRED prvnim modelem (jen maly nahled 33-133 kB; plne HDRI az po modelu, viz opts.envEager); RoomEnvironment se generuje na GPU, 0 B.
 *  - Kresleni na vyzadani; smycka rAF bezi jen behem dojezdu ovladani,
 *    preletu kamery a animace.
 *  - Dotyk v kontejneru se nepropaguje (stranka ma swipe na deckEl).
 */
(function (global) {
  'use strict';

  var V3D = global.V3D = global.V3D || {};
  V3D.version = '1.17.0';

  // Zive instance (kvuli V3D.isFullscreen - pri zaloze pres CSS je root
  // presunuty do body, takze container.contains(root) nestaci).
  var live = [];
  V3D.isFullscreen = function (container) {
    for (var i = 0; i < live.length; i++) {
      var r = live[i];
      if (container && r.container !== container && !(container.contains && container.contains(r.container))) continue;
      if (r.isFs()) return true;
    }
    return false;
  };

  var CDN = 'https://cdn.jsdelivr.net/npm/three@0.128.0/';
  V3D.deps = [
    CDN + 'build/three.min.js',
    CDN + 'examples/js/controls/OrbitControls.js',
    CDN + 'examples/js/loaders/GLTFLoader.js',
    CDN + 'examples/js/environments/RoomEnvironment.js',
    CDN + 'examples/js/renderers/CSS2DRenderer.js',
    CDN + 'examples/js/shaders/HorizontalBlurShader.js',
    CDN + 'examples/js/shaders/VerticalBlurShader.js'
  ];

  // ------------------------------------------------------------------
  // Konstanty
  // ------------------------------------------------------------------
  var DEG = Math.PI / 180;
  var DIM_COLOR = 0x2fe07a;                  // --accent-glow (stejne jako dnesni koty)
  var WIRE_DARK = 0x16324f;                  // --navy, hrany svetlych dilu (jako dnes)
  var HOVER_MS = 100;                        // odstup dovyhodnoceni vyzvy ke kliknuti po animaci / pohybu kamery / kliknuti (hoverHint)
  var TIP_ICON = '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false"><path d="M5 4.6V14l2.5-2.3 1.9 3.6 1.8-.9-1.9-3.5H13z" fill="currentColor"/>'
    + '<path d="M2.3 5.6l1.3.5M3.6 2.6l1 1M6.8 1.3l.2 1.4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" fill="none"/></svg>';     // kurzor s "klik" paprsky
  var HIGHLIGHT = 0xff7a3d;                  // --orange, zvyrazneni kusovniku (jako dnes)
  var T_RE = /^[0-9 ]{1,7}( mm)?$/;          // jediny povoleny text ve spec
  var PIVOT_RE = /^p\d{1,4}$/;
  var MOTION_ID_RE = /^m\d{1,4}$/;
  var BOMGRP_RE = /^bomgrp_(\d+)(?:_\d+)*$/; // legacy (GLTFLoader pridava _1, _2 u duplicit)
  var KIND_LABEL = { drawer: 'Šuplík', door: 'Dvířka', floor_door: 'Podlahová dvířka', box: 'Box', slide: 'Výsuv' };
  // motions[].sub (jen k=box): vycet, zadny volny text (neznama hodnota se zahodi -> "Box N")
  var SUB_LABEL = { klt: 'KLT box', multibox: 'Multibox', eurobox: 'Eurobox', kufrik: 'Kufřík' };
  var LOOK_ENV = { vd: 1.4, nat: 1.0 };      // envMapIntensity (r128 nema scene.environmentIntensity)
  // Varianty vzhledu HLINIKU (Robert 2026-10-02: "dal bych pryc ty odlesky, nabidni moznosti do kontrolni sceny, ja si
  // vyberu"). Vandr hlinik (Alumi2: baseColor ~#BBBAB3, metallicFactor vynechan = 1, roughness 0,28) je v zivem 3D
  // plne kovovy a zrcadli svetla RoomEnvironment. Varianta prepise JEN materialy rozpoznane podle podpisu (sanitizer
  // jmena materialu prejmenuje na mNN), synchronne pri nacteni modelu a pri v.setAluminium(); 'puvodni' nic nemeni.
  // m = metalness, r = roughness, e = nasobek envMapIntensity, k = nasobek barvy (linearni).
  var ALU_VARIANTS = [
    { key: 'puvodni', label: 'Dnešní (lesklý kov)', p: null },
    { key: 'satin', label: 'Saténový', p: { m: 1.0, r: 0.45, e: 0.85, k: 1.0 } },
    { key: 'matny', label: 'Matný kartáčovaný', p: { m: 1.0, r: 0.7, e: 0.8, k: 1.0 } },
    { key: 'eloxovany', label: 'Eloxovaný (polomatný)', p: { m: 0.6, r: 0.55, e: 0.7, k: 1.0 } },
    { key: 'bez', label: 'Bez odlesků (mat)', p: { m: 0.0, r: 0.65, e: 0.6, k: 1.0 } }
  ];
  V3D.aluVariants = ALU_VARIANTS.map(function (v) { return { key: v.key, label: v.label }; });
  function aluVariantByKey(k) { for (var i = 0; i < ALU_VARIANTS.length; i++) if (ALU_VARIANTS[i].key === k) return ALU_VARIANTS[i]; return null; }
  // podpis Vandr hliniku: stredne svetla neutralni (linearni 0,3-0,7), kovova (>=0,9; chybejici metallicFactor = 1),
  // lesklost 0,15-0,45, bez clearcoatu/pruhlednosti (vyloucuje bily lak, ocel, plasty i modry KLT)
  function isAluMaterial(mat) {
    if (!mat || !mat.isMeshStandardMaterial || !mat.color) return false;
    if (mat.transparent || mat.clearcoat > 0 || mat.transmission > 0) return false;
    var c = mat.color, mx = Math.max(c.r, c.g, c.b), mn = Math.min(c.r, c.g, c.b), avg = (c.r + c.g + c.b) / 3;
    return mat.metalness >= 0.9 && mat.roughness >= 0.15 && mat.roughness <= 0.45 && mx - mn < 0.08 && avg >= 0.3 && avg <= 0.7;
  }
  // Robert 2026-10-02: "Pouzivat pouze hdri tlumene" -> VYCHOZI a jedine nabizene prostredi je 'hdri_tlumene' (zadna volba v HUD);
  // 'mistnost' zustava jen jako zaloha, kdyz se HDRI nenacte (a pro ?env= pri ladeni).
  // Varianty PROSTREDI (Robert 2026-10-02: "nejaky hdri byt musi, protoze je to vyblite"). Dnesni 'mistnost' =
  // RoomEnvironment (vygenerovana bila mistnost, 0 B) + bile HemisphereLight 0,6 -> scena vyblije. 'hdri*' = stejna HDRI jako
  // rendery karet (crossfit_gym, render_hdri_file_id 4125, zmensena na 1024x512, env/crossfit_1024.hdr), rotace Blender 177 st. =
  // three sphere.rotation.y (180-177) st. (overeno cislene proti Blenderu), sila 1,4 = LOOK_ENV.vd (hdri_sila). hemi = intenzita
  // bileho svetla shora, mul = nasobek envMapIntensity. Pozadi kresli CSS, takze HDRI se nezobrazuje, jen osvetluje.
  var HDRI_FILE = 'crossfit_1024.hdr', HDRI_LO = 'crossfit_256.hdr', HDRI_ROT = (180 - 177) * Math.PI / 180;     // *_256.hdr = nahled 256x128 (viewer 1.10.0, viz opts.envEager)
  var ENV_VARIANTS = [
    { key: 'mistnost', label: 'Místnost (dnešní)', file: null, rot: 0, hemi: 0.6, mul: 1 },
    { key: 'hdri', label: 'HDRI karet (jako render)', file: HDRI_FILE, lo: HDRI_LO, rot: HDRI_ROT, hemi: 0.6, mul: 1 },
    { key: 'hdri_bez_svetla', label: 'HDRI karet, bez světla shora', file: HDRI_FILE, lo: HDRI_LO, rot: HDRI_ROT, hemi: 0, mul: 1 },
    { key: 'hdri_tlumene', label: 'HDRI karet, tlumené', file: HDRI_FILE, lo: HDRI_LO, rot: HDRI_ROT, hemi: 0, mul: 0.6 }
  ];
  V3D.envVariants = ENV_VARIANTS.map(function (v) { return { key: v.key, label: v.label }; });
  function envVariantByKey(k) { for (var i = 0; i < ENV_VARIANTS.length; i++) if (ENV_VARIANTS[i].key === k) return ENV_VARIANTS[i]; return null; }
  // Knihovna HDRI pro admina generatoru (Robert 2026-10-04: "v generatoru stolu chci mit moznost menit jako admin HDRi primo v generatoru"):
  // zmensene nahledy 1024x512 HDRI z knihovny Sdileneho disku (scripts/2026-10-04_v3d_hdri_nahledy/zmensi_hdri.py), mul0 = normalizace jasu proti
  // crossfit (sila 1 = zhruba stejne svetlo u vsech), rot0 = zakladni natoceni (rad). Konfigurace prostredi {hdri, strength, rot_deg, hemi}:
  // hdri = klic knihovny | 'mistnost', strength 0,1-3 (nasobek envMapIntensity, 1 = jako HDRI karet), rot_deg -180..180 (pridava se k rot0), hemi 0-1,2 (svetlo shora).
  // Vychozi {crossfit, 0,6, 0, 0} je presne dnesni 'hdri_tlumene'. opts.envConfig / v.setEnvConfig(cfg) / v.getEnvConfig() / v.resetEnvConfig().
  var HDRI_LIBRARY = [
    { key: 'crossfit', label: 'Crossfit gym (HDRI karet)', file: HDRI_FILE, lo: HDRI_LO, mul0: 1, rot0: HDRI_ROT },
    { key: 'tv_studio', label: 'TV studio', file: 'tv_studio_1024.hdr', lo: 'tv_studio_256.hdr', mul0: 0.53, rot0: 0 },
    { key: 'berg_inner', label: 'Berg inner', file: 'berg_inner_1024.hdr', lo: 'berg_inner_256.hdr', mul0: 1.44, rot0: 0 },
    { key: 'teufelsberg', label: 'Teufelsberg lookout', file: 'teufelsberg_1024.hdr', lo: 'teufelsberg_256.hdr', mul0: 0.89, rot0: 0 }
  ];
  V3D.envLibrary = HDRI_LIBRARY.map(function (h) { return { key: h.key, label: h.label }; }).concat([{ key: 'mistnost', label: 'Místnost (bez HDRI)' }]);
  var ENV_CFG_DEFAULT = { hdri: 'crossfit', strength: 0.6, rot_deg: 0, hemi: 0 };
  var ENV_MUL0_MIN = 0.05, ENV_MUL0_MAX = 20;                          // doplnena HDRI: normalizace jasu mul0 (api/v3d_env_import.py MUL0_MEZE)
  var ENV_EXTRA_KEY_RE = /^[a-z][a-z0-9_]{2,39}$/, ENV_EXTRA_URL_RE = /^\/api\/public\/v3d-env\/[a-z][a-z0-9_]{2,39}_(1024|256)\.hdr$/, ENV_EXTRA_MAX = 24;
  function envLibByKey(k) { for (var i = 0; i < HDRI_LIBRARY.length; i++) if (HDRI_LIBRARY[i].key === k) return HDRI_LIBRARY[i]; return null; }
  function normEnvCfg(c) {
    if (!c || typeof c !== 'object') return null;
    var lib = envLibByKey(c.hdri);
    if (!lib && c.hdri !== 'mistnost') return null;
    function num(x, def, lo, hi) { x = Number(x); if (!isFinite(x)) x = def; return Math.min(hi, Math.max(lo, x)); }
    var rot = Number(c.rot_deg); if (!isFinite(rot)) rot = 0; rot = (((rot + 180) % 360) + 360) % 360 - 180;     // zabalit do -180..180 (540 = -180)
    return { hdri: lib ? lib.key : 'mistnost', strength: Math.round(num(c.strength, 0.6, 0.1, 3) * 100) / 100, rot_deg: Math.round(rot * 10) / 10, hemi: Math.round(num(c.hemi, 0, 0, 1.2) * 100) / 100 };
  }
  V3D.normalizeEnvConfig = function (c) { return normEnvCfg(c); };
  // uhel vychoziho 3D pohledu (1.17.0): {az, el} ve stupnich, jinak null; az se zabali do (-180, 180], el musi byt v mezich (nic se potichu neorezava)
  var ISO_EL_MIN = -15, ISO_EL_MAX = 85;
  function normalizeIsoAngles(c) {
    if (!c || typeof c !== 'object') return null;
    if (typeof c.az !== 'number' || typeof c.el !== 'number' || !isFinite(c.az) || !isFinite(c.el)) return null;
    if (c.el < ISO_EL_MIN || c.el > ISO_EL_MAX) return null;
    var az = ((c.az + 180) % 360 + 360) % 360 - 180;
    if (az === -180) az = 180;
    return { az: Math.round(az * 10) / 10, el: Math.round(c.el * 10) / 10 };
  }
  V3D.normalizeIsoAngles = normalizeIsoAngles;
  // HDRI doplnena ze Sdileneho disku -> knihovna za behu (viz hlavicka 1.15.0); opakovane volani se stejnym klicem je bez ucinku
  V3D.addEnvLibrary = function (list) {
    var added = [];
    (Array.isArray(list) ? list : []).forEach(function (h) {
      if (!h || typeof h !== 'object' || typeof h.key !== 'string' || !ENV_EXTRA_KEY_RE.test(h.key) || h.key === 'mistnost' || envLibByKey(h.key)) return;
      if (typeof h.url !== 'string' || !ENV_EXTRA_URL_RE.test(h.url) || (h.lo != null && (typeof h.lo !== 'string' || !ENV_EXTRA_URL_RE.test(h.lo)))) return;
      if (HDRI_LIBRARY.length >= 4 + ENV_EXTRA_MAX) return;
      var label = (typeof h.label === 'string' && h.label.trim()) ? h.label.trim().slice(0, 60) : h.key;
      var rot = Number(h.rot0_deg); if (!isFinite(rot)) rot = 0;
      var m0 = Number(h.mul0); if (!isFinite(m0)) m0 = 1;
      HDRI_LIBRARY.push({ key: h.key, label: label, file: h.url, lo: h.lo || null, mul0: Math.min(ENV_MUL0_MAX, Math.max(ENV_MUL0_MIN, m0)), rot0: rot * Math.PI / 180 });
      V3D.envLibrary.splice(V3D.envLibrary.length - 1, 0, { key: h.key, label: label });
      added.push(h.key);
    });
    return added;
  };
  function envFromCfg(c) {
    var lib = envLibByKey(c.hdri);
    return { key: 'custom', label: 'Vlastní', file: lib ? lib.file : null, lo: lib ? lib.lo : null, rot: lib ? lib.rot0 + c.rot_deg * Math.PI / 180 : 0, hemi: c.hemi, mul: lib ? c.strength * lib.mul0 : c.strength };
  }
  function cfgOfVariant(k) {            // dnesni pojmenovane varianty vyjadrene jako konfigurace (pro getEnvConfig)
    if (k === 'hdri') return { hdri: 'crossfit', strength: 1, rot_deg: 0, hemi: 0.6 };
    if (k === 'hdri_bez_svetla') return { hdri: 'crossfit', strength: 1, rot_deg: 0, hemi: 0 };
    if (k === 'mistnost') return { hdri: 'mistnost', strength: 1, rot_deg: 0, hemi: 0.6 };
    return { hdri: ENV_CFG_DEFAULT.hdri, strength: ENV_CFG_DEFAULT.strength, rot_deg: ENV_CFG_DEFAULT.rot_deg, hemi: ENV_CFG_DEFAULT.hemi };
  }
  // adresar tohoto skriptu (HDRI lezi v env/ vedle nej); zjistit hned pri behu skriptu, pozdeji je currentScript null
  function envUrl(f) { return f.charAt(0) === '/' ? f : SCRIPT_BASE + 'env/' + f; }       // vestavena HDRI lezi v env/ vedle skriptu, doplnena maji absolutni URL (/api/public/v3d-env/...)
  var SCRIPT_BASE = (function () {
    try { var sc = global.document && global.document.currentScript; if (sc && sc.src) return sc.src.replace(/[?#].*$/, '').replace(/[^\/]*$/, ''); } catch (e) { /* vychozi */ }
    return '/js/v3d/';
  })();
  // ladeni (opts.ladeni:true): v HUD pribude volba Prostredi a Hliniku (pro kontrolni scenu / staff); posledni volba se pamatuje
  // v tomto prohlizeci (localStorage v3dAlu) a jde predvolit v URL (?alu=<klic>; ?env=<klic> jen pro srovnani prostredi). Zakaznik ji nema.
  function ladeniPref(klic, param, platne) {
    try {
      var q = new URLSearchParams(global.location.search).get(param);
      if (q && platne(q)) return q;
      var l = global.localStorage.getItem(klic);
      if (l && platne(l)) return l;
    } catch (e) { /* bez uloziste / URL */ }
    return null;
  }
  function ladeniUrl(param, platne) {
    try { var q = new URLSearchParams(global.location.search).get(param); if (q && platne(q)) return q; } catch (e) { /* bez URL */ }
    return null;
  }
  function ladeniUloz(klic, v) { try { global.localStorage.setItem(klic, v); } catch (e) { /* bez uloziste */ } }
  // RGBELoader (three r128 examples) si viewer v pripade potreby dotahne sam z CDN (stejna verze jako V3D.deps), aby stranky
  // nabidky/produktu nemusely menit seznam skriptu; kdyz se nenacte, pouzije se zalozni prostredi 'mistnost'.
  var RGBE_URL = 'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/RGBELoader.js';
  var rgbeLoading = null;
  function ensureRgbe() {
    if (global.THREE && global.THREE.RGBELoader) return Promise.resolve();
    if (!rgbeLoading) {
      rgbeLoading = new Promise(function (res, rej) {
        var sc = global.document.createElement('script');
        sc.src = RGBE_URL; sc.async = true;
        sc.onload = function () { if (global.THREE && global.THREE.RGBELoader) res(); else { rgbeLoading = null; rej(new Error('RGBELoader se nenačetl')); } };
        sc.onerror = function () { rgbeLoading = null; rej(new Error('RGBELoader nelze stáhnout')); };
        global.document.head.appendChild(sc);
      });
    }
    return rgbeLoading;
  }
  // Barvy a sytost materialu (Robert 2026-10-06): konfigurace {sat: 0-2 (1 = beze zmeny), colors: {"#puvodni": "#nova"}} se uplatni na NE-hlinikove materialy podle jejich PUVODNI barvy
  // (sRGB hex z modelu): stejna puvodni barva = stejna zmena ve vsech nabidkach. opts.matConfig / v.setMatConfig(cfg) / getMatConfig() / resetMatConfig() / materialPalette().
  // Meze jsou shodne s api/v3d_vzhled.py (SAT_MEZE, BARVY_MAX), shodu hlida scripts/2026-10-06_v3d_vzhled_testy/test_vzhled_api.py.
  var MAT_SAT_MAX = 2, MAT_COLORS_MAX = 40;
  var GLOSS_MAX = 2;                                        // lesk materialu: nasobek 0-2 (1 = beze zmeny)
  var ALU_REFL_MAX = 1.5, ALU_ROUGH_MIN = 0.5, ALU_ROUGH_MAX = 2;      // hlinik: sila odrazu 0-1,5, matnost (nasobek drsnosti) 0,5-2
  var AO_K_MAX = 2, AO_R_MIN = 0.25, AO_R_MAX = 3;                       // AO: sila 0-2, dosah 0,25-3 (nasobek hodnot varianty)
  var AO_MAT_MAX = 2;                                       // AO po komponentech: nasobek sily AO materialu podle puvodni barvy 0-2 (1 = beze zmeny); stejny strop plati pro hlinik (aluConfig.ao)
  function clampNum(x, def, lo, hi) { x = Number(x); if (!isFinite(x)) x = def; return Math.round(Math.min(hi, Math.max(lo, x)) * 100) / 100; }
  var HEX6_RE = /^#[0-9a-f]{6}$/;
  function normMatCfg(c) {
    if (!c || typeof c !== 'object') return null;
    var sat = (typeof c.sat === 'number' && isFinite(c.sat)) ? Math.min(MAT_SAT_MAX, Math.max(0, c.sat)) : 1;
    var colors = {}, n = 0;
    if (c.colors && typeof c.colors === 'object' && !Array.isArray(c.colors)) {
      Object.keys(c.colors).forEach(function (k) {
        var s = String(k).toLowerCase(), d = String(c.colors[k]).toLowerCase();
        if (HEX6_RE.test(s) && HEX6_RE.test(d) && s !== d && n < MAT_COLORS_MAX) { colors[s] = d; n++; }
      });
    }
    var gloss = {}, gn = 0;
    if (c.gloss && typeof c.gloss === 'object' && !Array.isArray(c.gloss)) {
      Object.keys(c.gloss).forEach(function (k) {
        var s = String(k).toLowerCase(), g = c.gloss[k];
        if (HEX6_RE.test(s) && typeof g === 'number' && isFinite(g) && gn < MAT_COLORS_MAX) {
          g = clampNum(g, 1, 0, GLOSS_MAX);
          if (g !== 1) { gloss[s] = g; gn++; }
        }
      });
    }
    var ao = {}, an = 0;
    if (c.ao && typeof c.ao === 'object' && !Array.isArray(c.ao)) {
      Object.keys(c.ao).forEach(function (k) {
        var s = String(k).toLowerCase(), g = c.ao[k];
        if (HEX6_RE.test(s) && typeof g === 'number' && isFinite(g) && an < MAT_COLORS_MAX) {
          g = clampNum(g, 1, 0, AO_MAT_MAX);
          if (g !== 1) { ao[s] = g; an++; }
        }
      });
    }
    sat = Math.round(sat * 100) / 100;
    if (sat === 1 && !n && !gn && !an) return null;
    return { sat: sat, colors: colors, gloss: gloss, ao: ao };
  }
  function normAluCfg(c) {
    if (!c || typeof c !== 'object') return null;
    var refl = clampNum(c.refl, 1, 0, ALU_REFL_MAX), rough = clampNum(c.rough, 1, ALU_ROUGH_MIN, ALU_ROUGH_MAX), ao = clampNum(c.ao, 1, 0, AO_MAT_MAX);
    return (refl === 1 && rough === 1 && ao === 1) ? null : { refl: refl, rough: rough, ao: ao };
  }
  function normAoCfg(c) {
    if (!c || typeof c !== 'object') return null;
    var k = clampNum(c.k, 1, 0, AO_K_MAX), r = clampNum(c.r, 1, AO_R_MIN, AO_R_MAX);
    return (k === 1 && r === 1) ? null : { k: k, r: r };
  }
  // Texty HUD (bot16 2026-10-02: anglicky mini-shop). V3D.mount(el, { labels: { klic: 'text' } }) prepise jen zadane klice
  // (retezce), chybejici/neplatny klic = cesky vychozi jako dosud. Texty jdou vzdy pres textContent/setAttribute (zadne HTML).
  var LABELS_DEFAULT = {
    view_front: 'Zepředu', view_side: 'Z boku', view_top: 'Shora', view_iso: '3D',
    dims_cap: 'Kóty', dims_off: 'Vyp', dims_1: 'Rozměry', dims_2: 'Detail',
    mode_cap: 'Vzhled', mode_real: 'Skutečný', mode_wire: 'Drátěný',
    alu_cap: 'Hliník',
    reset: 'Výchozí pohled', zoom_in: 'Přiblížit', zoom_out: 'Oddálit', fullscreen: 'Celá obrazovka', fullscreen_exit: 'Zavřít celou obrazovku',
    chips_aria: 'Pohyblivé díly', open_all: 'Otevřít vše', close_all: 'Zavřít vše',
    side_left: 'Levá strana', side_right: 'Pravá strana', side_bulkhead: 'Přepážka',
    open_all_title: 'Otevře šuplíky, výsuvy a dvířka (boxy jednotlivě)',
    open_all_title_two_sided: 'Otevře šuplíky, výsuvy a dvířka na straně ke kameře (boxy jednotlivě)',
    loading: 'Načítám 3D model…', load_failed: '3D model se nepodařilo načíst.',
    kind_drawer: 'Šuplík', kind_door: 'Dvířka', kind_floor_door: 'Podlahová dvířka', kind_slide: 'Výsuv', kind_box: 'Box',
    kind_klt: 'KLT box', kind_multibox: 'Multibox', kind_eurobox: 'Eurobox', kind_kufrik: 'Kufřík',
    hint_mouse: 'Táhněte myší = otočit · kolečko = přiblížit · pravé tlačítko = posun',
    hint_touch: 'Táhněte prstem = otočit · dvěma prsty = přiblížit',
    hint_click_tail: ' · kliknutím na šuplík nebo dvířka je otevřete',
    hint_tap_tail: ' · klepnutím na šuplík nebo dvířka je otevřete',
    hover_open: 'Kliknutím otevřete', hover_close: 'Kliknutím zavřete'
  };
  V3D.labelKeys = Object.keys(LABELS_DEFAULT);
  function mergeLabels(user) {
    var out = {};
    Object.keys(LABELS_DEFAULT).forEach(function (k) {
      out[k] = (user && typeof user[k] === 'string' && user[k].length <= 200) ? user[k] : LABELS_DEFAULT[k];
    });
    return out;
  }
  var SIDE_KEYS = ['left', 'right', 'bulkhead'];             // motions[].g: strana spolecne nabidky (leva / prava / prepazka), jinak bez radku strany
  var KIND_LABEL_KEY = { drawer: 'kind_drawer', door: 'kind_door', floor_door: 'kind_floor_door', slide: 'kind_slide', box: 'kind_box' };
  var VIEWS = ['front', 'side', 'top', 'iso'];
  var ISO_AZ = 35, ISO_EL = 25;              // 3D pohled: front +35 st. azimut, 25 st. elevace
  var FLIGHT_MS = 600, ZOOM_MS = 220, STAGGER_MS = 120, TAP_PX = 6;
  var SHADOW_PAD = 150 + 75;                 // TT_FLOOR: pudorys + 150 + 75 mm (render)
  var SHADOW_OPACITY = 0.7;
  var FIT_PAD = 1 / 0.9;                     // objekt vyplni ~90 % (Robert 2026-08-09)
  var BLOCK_TOL = 1.5;                       // mm: presah Box3 mensi nez tohle = dotyk, ne kolize
  var SIDE_MIN = 20;                         // mm: posun podel front, od ktereho ma pohyb "stranu"
  var CAM_SIDE_EPS = 0.17;                   // kamera skoro kolmo na front (+-10 st.) -> strana front

  // ------------------------------------------------------------------
  // Ciste funkce (bez THREE) - testovatelne i v node
  // ------------------------------------------------------------------
  function clamp(x, a, b) { return x < a ? a : (x > b ? b : x); }
  function clamp01(x) { return clamp(x, 0, 1); }
  function easeInOutCubic(x) { x = clamp01(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; }
  function isNum(x) { return typeof x === 'number' && isFinite(x); }
  function isVec3(a) { return Array.isArray(a) && a.length === 3 && isNum(a[0]) && isNum(a[1]) && isNum(a[2]); }
  function norm3(a) { var l = Math.hypot(a[0], a[1], a[2]); return l > 1e-12 ? [a[0] / l, a[1] / l, a[2] / l] : null; }

  function motionTotalMs(m) {
    var s = 0;
    for (var i = 0; i < m.steps.length; i++) s += Math.max(1, m.steps[i].ms);
    return s;
  }

  // Postup kroku pohybu v case t (0..1): kroky jdou po castech za sebou
  // (pin nejdriv, pak dvirka), kazdy s vlastnim easeInOutCubic. Zpetny
  // chod (t 1 -> 0) tak automaticky jede v opacnem poradi.
  function stepProgress(m, t) {
    var total = motionTotalMs(m), acc = 0, out = [];
    t = clamp01(t);
    for (var i = 0; i < m.steps.length; i++) {
      var d = Math.max(1, m.steps[i].ms);
      out.push(easeInOutCubic((t * total - acc) / d));
      acc += d;
    }
    return out;
  }

  // Cista funkce apply(motion, t): vrati prispevky kroku k pivotum.
  //   T: posun pivotu o ax * v * e (mm, v souradnicich rodice pivotu)
  //   R: otoceni pivotu kolem ax o v * e (stupne, osa v souradnicich rodice)
  function motionPose(m, t) {
    var prog = stepProgress(m, t), out = [];
    for (var i = 0; i < m.steps.length; i++) {
      var s = m.steps[i];
      out.push({ p: s.p, op: s.op, ax: s.ax.slice(), amount: s.v * prog[i], e: prog[i] });
    }
    return out;
  }

  // Obranna kontrola spec v1. Co neodpovida, zahodi (zadny volny text se
  // nikdy nezobrazi: popisky cipu se skladaji z k+sub+n, koty jen z "t" podle
  // T_RE). Vraci {spec, warnings} nebo {spec:null} pro legacy.
  function validateSpec(raw) {
    var w = [];
    if (!raw || typeof raw !== 'object' || raw.v !== 1) return { spec: null, warnings: raw ? ['v3d: nepodporovana verze'] : [] };
    if (raw.u != null && raw.u !== 'mm') return { spec: null, warnings: ['v3d: jednotky nejsou mm'] };
    if (raw.up != null) {
      var up = isVec3(raw.up) ? norm3(raw.up) : null;
      if (!up || Math.abs(up[1] - 1) > 1e-6) w.push('v3d: up neni [0,1,0], pouzivam Y nahoru');
    }
    var front = [0, 0, 1];
    if (isVec3(raw.front)) {
      var f = norm3([raw.front[0], 0, raw.front[2]]);
      if (f) front = f; else w.push('v3d: front je svisly, pouzivam +Z');
    } else w.push('v3d: chybi front, pouzivam +Z');
    var box = null;
    if (raw.box && isVec3(raw.box.min) && isVec3(raw.box.max) &&
        raw.box.min[0] <= raw.box.max[0] && raw.box.min[1] <= raw.box.max[1] && raw.box.min[2] <= raw.box.max[2]) {
      box = { min: raw.box.min.slice(), max: raw.box.max.slice() };
    } else if (raw.box != null) w.push('v3d: neplatny box');
    var look = (raw.look === 'vd' || raw.look === 'nat') ? raw.look : 'nat';

    var dims = [];
    (Array.isArray(raw.dims) ? raw.dims : []).forEach(function (d, i) {
      if (!d || !isVec3(d.a) || !isVec3(d.b) || typeof d.t !== 'string' || !T_RE.test(d.t)) { w.push('v3d: kota ' + i + ' zahozena'); return; }
      var l = d.l === 2 ? 2 : 1;
      var p = (typeof d.p === 'string' && PIVOT_RE.test(d.p)) ? d.p : null;
      var m = isNum(d.m) ? clamp(d.m, 0, 1) : 0.5;           // poloha popisku na care kóty: 0 = u bodu a, 1 = u bodu b, 0.5 (vychozi) = uprostred
      dims.push({ a: d.a.slice(), b: d.b.slice(), o: isVec3(d.o) ? d.o.slice() : [0, 0, 0], t: d.t.trim(), l: l, p: p, m: m });
    });

    var motions = [], ids = {};
    (Array.isArray(raw.motions) ? raw.motions : []).forEach(function (m, i) {
      if (!m || typeof m.id !== 'string' || !MOTION_ID_RE.test(m.id) || ids[m.id] || !KIND_LABEL[m.k] || !Array.isArray(m.steps) || !m.steps.length) {
        w.push('v3d: pohyb ' + i + ' zahozen'); return;
      }
      var steps = [], ok = true;
      m.steps.forEach(function (s) {
        if (!s || typeof s.p !== 'string' || !PIVOT_RE.test(s.p) || (s.op !== 'T' && s.op !== 'R') || !isVec3(s.ax) || !isNum(s.v)) { ok = false; return; }
        var ax = norm3(s.ax);
        if (!ax) { ok = false; return; }
        var lim = s.op === 'T' ? 5000 : 360;
        if (Math.abs(s.v) > lim) { ok = false; return; }
        steps.push({ p: s.p, op: s.op, ax: ax, v: s.v, ms: isNum(s.ms) ? clamp(s.ms, 0, 10000) : 300 });
      });
      if (!ok || !steps.length) { w.push('v3d: pohyb ' + m.id + ' ma neplatny krok'); return; }
      var pick = (Array.isArray(m.pick) ? m.pick : []).filter(function (p) { return typeof p === 'string' && PIVOT_RE.test(p); });
      if (!pick.length) pick = steps.map(function (s) { return s.p; });
      var n = (isNum(m.n) && m.n >= 1 && m.n <= 999) ? Math.round(m.n) : (motions.length + 1);
      // sub: jen vycet a jen u boxu, cokoli jineho se zahodi (cip se pak jmenuje "Box N")
      var subk = null;
      if (m.sub != null) {
        if (m.k === 'box' && typeof m.sub === 'string' && Object.prototype.hasOwnProperty.call(SUB_LABEL, m.sub)) subk = m.sub;
        else w.push('v3d: pohyb ' + m.id + ' - neplatný druh (sub) zahozen');
      }
      var gside = (typeof m.g === 'string' && SIDE_KEYS.indexOf(m.g) >= 0) ? m.g : null;
      ids[m.id] = true;
      motions.push({ id: m.id, k: m.k, subk: subk, n: n, steps: steps, pick: pick, g: gside });
    });
    return { spec: { v: 1, u: 'mm', up: [0, 1, 0], front: front, box: box, look: look, dims: dims, motions: motions }, warnings: w };
  }

  // nazev druhu: box podle sub ("KLT box", "Multibox", "Eurobox", "Kufřík"), jinak podle k
  function kindName(m, L) {
    L = L || LABELS_DEFAULT;
    return (m.k === 'box' && m.subk) ? L['kind_' + m.subk] : L[KIND_LABEL_KEY[m.k]];
  }
  function motionLabel(m, L) { return kindName(m, L) + ' ' + m.n; }

  V3D.easeInOutCubic = easeInOutCubic;
  V3D.stepProgress = stepProgress;
  V3D.motionPose = motionPose;
  V3D.validateSpec = validateSpec;
  V3D.motionLabel = motionLabel;

  // Varianty AO = ambient occlusion (Robert 2026-10-02: "Pouzivej AO"; scena je vyblita, hlinik plochy). Ztmaveni v koutech, drazkach profilu
  // a pod policemi, jako AO hlinikoveho materialu v renderech karet (render panel: alu_ao_sila 0,4 = mix(barva, barva * AO, 0,4);
  // alu_ao_vzdalenost_mm 8 - scena renderu je v mm). r = polomer AO v mm (model je v mm), k = nejvetsi ztmaveni (linearni, "sila" jako
  // v Blenderu: nasobek 1 - k * (1 - AO)). Zakaznik (bez ladeni) ma vychozi 'vyp' = kresleni PRESNE jako bez AO (zadny pruchod navic).
  // Technika: vlastni GTAO (horizon-based, svetovy polomer v mm) nad linearni hloubkou z predpruchodu (zabalena do RGBA, 24bit depth buffer),
  // 2x bilateralni rozmazani a nasobeni zobrazeneho obrazu (blend DST_COLOR) - beauty pruchod je tedy stejny jako bez AO. Stavajici
  // SAOPass/SSAOPass z r128 se nehodi (SAOPass kresli navic cely beauty a ma polomer v pixelech, SSAOPass ma 16bit hloubku a prahy v
  // linearni hloubce 0-1 ve scene v mm) a potrebovaly by EffectComposer (ztrata MSAA, jiny tone mapping/sRGB, nutnost skriptu navic).
  // Zadna dalsi zavislost (jen jadro THREE r128), proto V3D.depsOptional = [].
  var AO_MIN_PX = 4, AO_MAX_PX = 48;         // omezeni polomeru AO na obrazovce (v CSS px; pri oddaleni se AO nevytrati, pri priblizeni nerozmaze)
  var AO_FALLOFF = 0.25;                     // cast polomeru, na ktere vliv okluzora dozniva (GTAO "falloff")
  // Kalibrace (2026-10-02, bot10 / AO-nahled): proti CPU paprskovemu AO jako Blender (kosinove vazene paprsky, zasah do vzdalenosti r) na
  // kartach 4918 a 4594: polomer GTAO = AO_RMUL * r a sila * AO_KCAL, aby soucet okluze (energie) sedel (pomer reference/viewer 1,1-1,6).
  var AO_RMUL = 2.0;                         // polomer GTAO = AO_RMUL * vzdalenost AO varianty
  var AO_KCAL = 1.3;                         // nasobek "sily" varianty (k) pri skladani
  var AO_BIAS = 0.014;                       // GTAO na rovinach vychazi ~0,986 (snapovani vzorku na pixely) -> vis se vydeli (1 - bias)
  var AO_BLUR_SIG = 0.7;                     // sigma bilateralniho rozmazani v px AO mapy (vetsi = min sumu, ale plossi tmave cary drazek)
  var AO_GAMMA = 0.5;                        // linearni nasobek -> zobrazeny (po ACES + sRGB v polotonech ~0,45-0,6)
  var AO_VARIANTS = [
    { key: 'vyp', label: 'Vyp', p: null },
    { key: 'jemne', label: 'Jemné', p: { r: 8, k: 0.25 } },
    { key: 'stredni', label: 'Střední', p: { r: 8, k: 0.4 } },
    { key: 'silne', label: 'Silné', p: { r: 24, k: 0.7 } }
  ];
  V3D.aoVariants = AO_VARIANTS.map(function (v) { return { key: v.key, label: v.label }; });
  V3D.depsOptional = [];
  function aoVariantByKey(k) { for (var i = 0; i < AO_VARIANTS.length; i++) if (AO_VARIANTS[i].key === k) return AO_VARIANTS[i]; return null; }
  // pouze prohlizec s highp ve fragment shaderu (rozbaleni hloubky); jinak se AO nenabizi
  function aoSupportedBy(THREE, renderer) {
    try {
      return !!(THREE.ShaderMaterial && THREE.WebGLRenderTarget && THREE.CustomBlending !== undefined && THREE.DstColorFactor !== undefined &&
        renderer.capabilities && renderer.capabilities.precision === 'highp');
    } catch (e) { return false; }
  }
  var AO_VERT = 'varying vec2 vUv;\nvoid main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }';
  // predpruchod hloubky: linearni -viewZ / far zabalene do RGBA (override material sceny; bez skinningu/morphu - model je staticky)
  var AO_DEPTH_VERT = 'varying float vZ;\nvoid main() { vec4 mv = modelViewMatrix * vec4(position, 1.0); vZ = -mv.z; gl_Position = projectionMatrix * mv; }';
  var AO_DEPTH_FRAG = '#include <packing>\nuniform float uFar;\nvarying float vZ;\nvoid main() { gl_FragColor = packDepthToRGBA(clamp(vZ / uFar, 0.0, 0.999999)); }';
  var AO_COMMON = [
    '#include <packing>',
    'uniform sampler2D tDepth;',
    'uniform float uNear;',
    'uniform float uFar;',
    'varying vec2 vUv;',
    // viewZ (zaporne, mm) z balene LINEARNI hloubky (-viewZ / far; presnost ~1e-3 mm); pozadi (vymazano bilou = 1.0) -> +1.0
    'float zAt(vec2 uv) {',
    '  float d = unpackRGBAToDepth(texture2D(tDepth, uv));',
    '  if (d > 0.99999) return 1.0;',
    '  return -d * uFar;',
    '}'
  ].join('\n');
  var AO_FRAG = AO_COMMON + '\n' + [
    '#define PI 3.14159265359',
    '#define HALFPI 1.57079632679',
    'uniform vec2 uRes;',
    'uniform vec2 uTan;',      // 1/proj[0][0], 1/proj[1][1]
    'uniform float uProjPx;',  // pixelu na 1 mm ve vzdalenosti 1 mm
    'uniform float uRadius;',  // mm
    'uniform float uMinPx;',
    'uniform float uMaxPx;',
    'uniform float uFalloff;', // cast polomeru, na ktere vliv okluzora dozniva
    'uniform float uBias;',
    'vec3 posAt(vec2 uv, float z) { return vec3((uv * 2.0 - 1.0) * uTan * (-z), z); }',
    'float ign(vec2 p) { return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715)))); }',
    'float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }',
    'void main() {',
    '  float z0 = zAt(vUv);',
    '  if (z0 > 0.0) { gl_FragColor = vec4(1.0); return; }',
    '  vec2 px = 1.0 / uRes;',
    '  vec3 P = posAt(vUv, z0);',
    // normala z hloubky: z dvojice sousedu vzdy ten s mensim skokem hloubky (nepada pres hrany)
    '  vec2 uvL = vUv - vec2(px.x, 0.0), uvR = vUv + vec2(px.x, 0.0), uvD = vUv - vec2(0.0, px.y), uvU = vUv + vec2(0.0, px.y);',
    '  float zl = zAt(uvL), zr = zAt(uvR), zd = zAt(uvD), zu = zAt(uvU);',
    '  vec3 dx = abs(zr - z0) < abs(zl - z0) ? posAt(uvR, zr) - P : P - posAt(uvL, zl);',
    '  vec3 dy = abs(zu - z0) < abs(zd - z0) ? posAt(uvU, zu) - P : P - posAt(uvD, zd);',
    '  float jump = 0.2 * (-z0);',
    '  if (abs(dx.z) > jump || abs(dy.z) > jump) { gl_FragColor = vec4(1.0); return; }',   // obrys: bez AO (zadny tmavy lem)
    '  vec3 cr = cross(dx, dy);',
    '  if (dot(cr, cr) < 1e-12) { gl_FragColor = vec4(1.0); return; }',
    '  vec3 N = normalize(cr);',
    '  vec3 V = normalize(-P);',
    '  float dist = -z0;',
    '  float rPx = clamp(uRadius * uProjPx / dist, uMinPx, uMaxPx);',
    '  float Rw = rPx * dist / uProjPx;',                     // polomer ve svete po omezeni na obrazovce (mm)
    '  float fR = max(uFalloff * Rw, 1e-3);',
    '  float n1 = ign(gl_FragCoord.xy);',
    '  float n2 = hash12(gl_FragCoord.xy);',
    '  float vis = 0.0;',
    '  float unocc = 0.0;',
    '  for (int s = 0; s < SLICES; s++) {',
    '    float phi = (float(s) + n1) * (PI / float(SLICES));',
    '    vec2 omega = vec2(cos(phi), sin(phi));',
    '    vec3 dirVec = vec3(omega, 0.0);',
    '    vec3 ortho = dirVec - dot(dirVec, V) * V;',
    '    vec3 axis = normalize(cross(ortho, V));',
    '    vec3 projN = N - axis * dot(N, axis);',
    '    float pnLen = length(projN);',
    '    if (pnLen < 1e-4) continue;',
    '    float sgn = sign(dot(ortho, projN));',
    '    float cosN = clamp(dot(projN, V) / pnLen, 0.0, 1.0);',
    '    float n = sgn * acos(cosN);',
    '    float low0 = cos(n + HALFPI);',
    '    float low1 = cos(n - HALFPI);',
    '    float hc0 = low0;',
    '    float hc1 = low1;',
    '    for (int j = 0; j < STEPS; j++) {',
    '      float t = (float(j) + n2) / float(STEPS);',
    '      float offPx = max(t * t * rPx, 1.0);',
    '      vec2 off = omega * offPx * px;',
    '      vec2 uvA = (floor((vUv + off) * uRes) + 0.5) * px;',
    '      float zA = zAt(uvA);',
    '      if (zA < 0.0) {',
    '        vec3 d = posAt(uvA, zA) - P;',
    '        float dl = length(d);',
    '        if (dl > 1e-4) hc0 = max(hc0, mix(low0, dot(d, V) / dl, clamp((Rw - dl) / fR, 0.0, 1.0)));',
    '      }',
    '      vec2 uvB = (floor((vUv - off) * uRes) + 0.5) * px;',
    '      float zB = zAt(uvB);',
    '      if (zB < 0.0) {',
    '        vec3 d = posAt(uvB, zB) - P;',
    '        float dl = length(d);',
    '        if (dl > 1e-4) hc1 = max(hc1, mix(low1, dot(d, V) / dl, clamp((Rw - dl) / fR, 0.0, 1.0)));',
    '      }',
    '    }',
    '    float h0 = -acos(clamp(hc1, -1.0, 1.0));',
    '    float h1 = acos(clamp(hc0, -1.0, 1.0));',
    '    h0 = n + clamp(h0 - n, -HALFPI, HALFPI);',
    '    h1 = n + clamp(h1 - n, -HALFPI, HALFPI);',
    '    float a0 = (cosN + 2.0 * h0 * sin(n) - cos(2.0 * h0 - n)) * 0.25;',
    '    float a1 = (cosN + 2.0 * h1 * sin(n) - cos(2.0 * h1 - n)) * 0.25;',
    '    vis += pnLen * (a0 + a1);',
    '    unocc += pnLen * (cosN + n * sin(n));',               // stejny integral bez okluzoru (h = n -+ pi/2)
    '  }',
    '  vis = unocc > 1e-5 ? clamp(vis / unocc, 0.0, 1.0) : 1.0;',   // pomer okludovaneho a neokludovaneho oblouku
    '  vis = clamp(vis / (1.0 - uBias), 0.0, 1.0);',
    '  gl_FragColor = vec4(vec3(vis), 1.0);',
    '}'
  ].join('\n');
  // bilateralni rozmazani (oddelene H a V): sousedi s jinou hloubkou ani pozadi se nezapocitaji
  var AO_BLUR_FRAG = AO_COMMON + '\n' + [
    'uniform sampler2D tAO;',
    'uniform vec2 uDir;',
    'uniform float uSig;',
    'void main() {',
    '  float zc = zAt(vUv);',
    '  if (zc > 0.0) { gl_FragColor = vec4(1.0); return; }',
    '  float tol = 0.006 * (-zc) + 0.5;',
    '  float sum = 0.0, wsum = 0.0;',
    '  for (int i = -BLUR_R; i <= BLUR_R; i++) {',
    '    vec2 uv = vUv + uDir * float(i);',
    '    float z = zAt(uv);',
    '    if (z > 0.0) continue;',
    '    float dz = (z - zc) / tol;',
    '    float w = exp(-0.5 * float(i * i) / (uSig * uSig)) * exp(-dz * dz);',
    '    sum += texture2D(tAO, uv).r * w; wsum += w;',
    '  }',
    '  gl_FragColor = vec4(vec3(sum / max(wsum, 1e-4)), 1.0);',
    '}'
  ].join('\n');
  // slozeni: f = (1 - k * (1 - AO)) ^ gamma (gamma ~0,5 = prepocet linearniho nasobku na zobrazenou hodnotu po ACES+sRGB); blend DST_COLOR
  // vaha AO po komponentech: tW (rtW) nese 0,5 * vaha materialu zakryvajiciho povrch (vaha 0-2), uK se pro pixel vynasobi vahou (uUseW = 0: vsude 1)
  var AO_COMP_FRAG = [
    'uniform sampler2D tAO;',
    'uniform sampler2D tW;',
    'uniform float uUseW;',
    'uniform float uK;',
    'uniform float uGamma;',
    'varying vec2 vUv;',
    'void main() {',
    '  float v = texture2D(tAO, vUv).r;',
    '  float w = uUseW > 0.5 ? texture2D(tW, vUv).r * 2.0 : 1.0;',
    '  float f = pow(max(1.0 - uK * w * (1.0 - v), 0.0), uGamma);',
    '  gl_FragColor = vec4(vec3(f), 1.0);',
    '}'
  ].join('\n');
  var AO_W_VERT = 'void main() { gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
  var AO_W_FRAG = 'uniform float uW;\nvoid main() { gl_FragColor = vec4(vec3(uW * 0.5), 1.0); }';

  V3D.ensureCss = function (href) {
    try {
      var links = document.querySelectorAll('link[rel="stylesheet"]');
      for (var i = 0; i < links.length; i++) if (links[i].getAttribute('href') === href) return;
      var l = document.createElement('link'); l.rel = 'stylesheet'; l.href = href;
      document.head.appendChild(l);
    } catch (e) { /* bez CSS bezi taky, jen osklive */ }
  };

  // ------------------------------------------------------------------
  // DOM pomucky (veskery text jen pres textContent)
  // ------------------------------------------------------------------
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function btn(cls, text, attrs) {
    var b = el('button', 'v3d-b' + (cls ? ' ' + cls : ''), text);
    b.type = 'button';
    if (attrs) Object.keys(attrs).forEach(function (k) { b.setAttribute(k, attrs[k]); });
    return b;
  }
  var ICON = {
    reset: '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square"/><path d="M4 3.5v5h5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square"/></svg>',
    plus: '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2.2" stroke-linecap="square"/></svg>',
    minus: '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M5 12h14" stroke="currentColor" stroke-width="2.2" stroke-linecap="square"/></svg>',
    fs: '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square"/></svg>',
    fsExit: '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M9 4v5H4M20 9h-5V4M15 20v-5h5M4 15h5v5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square"/></svg>'
  };
  function mq(q) { try { return !!(global.matchMedia && global.matchMedia(q).matches); } catch (e) { return false; } }
  function now() { return (global.performance && performance.now) ? performance.now() : Date.now(); }

  // ------------------------------------------------------------------
  // mount
  // ------------------------------------------------------------------
  V3D.mount = function (container, opts) {
    opts = opts || {};
    var THREE = global.THREE;
    if (!container) throw new Error('V3D.mount: chybi container');
    if (!THREE || !THREE.WebGLRenderer || !THREE.GLTFLoader || !THREE.OrbitControls) throw new Error('V3D.mount: chybi THREE r128 / GLTFLoader / OrbitControls');

    var hasCSS2D = !!THREE.CSS2DRenderer;
    var hasRoom = !!THREE.RoomEnvironment;
    var hasBlur = !!(THREE.HorizontalBlurShader && THREE.VerticalBlurShader);
    // Robert 2026-10-01: pohyby komponent vzdy plynule - systemove 'omezit animace' se ignoruje (jen kdyz stranka vyslovne preda reducedMotion:true).
    var reduced = opts.reducedMotion != null ? !!opts.reducedMotion : false;
    var coarse = mq('(pointer: coarse)');
    var trackFn = typeof opts.track === 'function' ? opts.track : null;
    var bom = null;
    // skupiny, ktere v kusovniku opravdu jsou (items[].mesh_group); bez items = vsechny
    var bomGroups = null;
    function setBom(b) {
      bom = b || null;
      bomGroups = null;
      if (bom && Array.isArray(bom.items) && bom.items.length) {
        bomGroups = new Set();
        bom.items.forEach(function (it) { var g = it && parseInt(it.mesh_group, 10); if (!isNaN(g)) bomGroups.add(g); });
      }
    }
    setBom(opts.bom);
    function bomPickable(g) { return g != null && !!bom && typeof bom.onPick === 'function' && (!bomGroups || bomGroups.has(g)); }
    var onPickFn = typeof opts.onPick === 'function' ? opts.onPick : null;   // onPick(slotId) - jen cele cislo userData.g
    var hudKoty = opts.hudKoty !== false;                                    // false = HUD bez prepinace Koty
    var hudDock = opts.hudDock === 'top';                                    // true = pruh tlacitek nad platnem (flex sloupec), platno = stage
    var L = mergeLabels(opts.labels);                                        // texty HUD (cesky vychozi, viz LABELS_DEFAULT)
    var ladeni = !!opts.ladeni;                                              // true = HUD s volbou Hliniku (kontrolni scena)

    var st = {
      ready: false, error: null, legacy: true, look: 'nat',
      mode: (opts.mode === 'wire' || opts.mode === 'real') ? opts.mode : null,
      allowReal: true,                // po nacteni: spec -> true, legacy -> !!opts.allowReal
      dims: (opts.dims === 0 || opts.dims === 1 || opts.dims === 2) ? opts.dims : null,
      // volba stranky/zakaznika (opts, HUD, v.setMode/setDims) - preziva vymenu modelu; null = vychozi podle modelu
      modePref: null, dimsPref: null,
      view: 'iso', fs: false, fsCss: false, matWrites: 0, frames: 0, interacted: false, warnings: [],
      twoSided: false,
      alu: aluVariantByKey(opts.aluVariant) ? opts.aluVariant : ((opts.ladeni && ladeniPref('v3dAlu', 'alu', aluVariantByKey)) || 'puvodni'),      // varianta hliniku (ALU_VARIANTS)
      env: envVariantByKey(opts.envVariant) ? opts.envVariant : ((opts.ladeni && ladeniUrl('env', envVariantByKey)) || 'hdri_tlumene')   // prostredi (ENV_VARIANTS); vychozi jedine nabizene = HDRI karet tlumene
    };
    st.envCfg = null;
    st.aluCfg = normAluCfg(opts.aluConfig);          // odlesky hliniku {refl, rough} od stranky (nasobky zvolene varianty hliniku)
    st.aoCfg = normAoCfg(opts.aoConfig);             // sila a dosah AO {k, r} od stranky (nasobky zvolene varianty AO)
    st.matCfg = normMatCfg(opts.matConfig);        // barvy / sytost materialu od stranky (napr. ulozene adminem v kontrolni scene)
    var _ec = normEnvCfg(opts.envConfig);       // konfigurace prostredi od stranky (napr. ulozena adminem generatoru)
    if (_ec) { st.env = 'custom'; st.envCfg = _ec; }
    function curEnv() { return (st.env === 'custom' && st.envCfg) ? envFromCfg(st.envCfg) : (envVariantByKey(st.env) || ENV_VARIANTS[0]); }
    var aluMats = [];     // materialy rozpoznane jako hlinik (po poslednim nacteni modelu)
    var colorMats = [];   // ostatni nepruhledne materialy s barvou (barvy / sytost: setMatConfig); puvodni barva v userData.__v3dBase
    var allMats = [];     // vsechny materialy modelu s envMapIntensity (po poslednim nacteni modelu)
    st.modePref = st.mode; st.dimsPref = st.dims;
    // AO: zakaznik 'vyp' (kresleni jako bez AO); ladeni bez ulozene volby 'stredni' (Robert 2026-10-02: "Pouzivej AO")
    st.ao = aoVariantByKey(opts.aoVariant) ? opts.aoVariant : ((opts.ladeni && ladeniPref('v3dAO', 'ao', aoVariantByKey)) || (opts.ladeni ? 'stredni' : 'vyp'));
    var disposed = false;
    var listeners = [];
    var hoverId = null, hoverOvs = [], hoverPtr = null, hoverTip = null, hoverTimer = 0, hoverBtn = false;     // vyzva ke kliknuti pri najeti mysi (hoverHint); hoverBtn = mys je stisknuta (tah / otaceni)
    function on(t, type, fn, o) { t.addEventListener(type, fn, o); listeners.push([t, type, fn, o]); }
    function track(key, detail) { if (trackFn) { try { trackFn(key, detail || {}); } catch (e) { /* statistiky nesmi shodit prohlizec */ } } }

    // ---------------- DOM ----------------
    var root = el('div', 'v3d-root v3d-loading v3d-mode-' + (st.mode || 'real'));
    root.setAttribute('role', 'region');
    root.setAttribute('aria-label', '3D model');
    var stage = el('div', 'v3d-stage');
    if (opts.hudDock === 'top') root.classList.add('v3d-dock-top');
    root.appendChild(stage);
    container.appendChild(root);
    var liveRec = { container: container, isFs: function () { return !disposed && (st.fsCss || fsEl() === root); } };
    live.push(liveRec);

    function sizeOf() {
      var box = hudDock ? stage : root;                      // hudDock: platno je jen stage (zbytek pod pruhem tlacitek)
      return { w: Math.max(1, box.clientWidth || root.clientWidth || container.clientWidth || 1), h: Math.max(1, box.clientHeight || root.clientHeight || container.clientHeight || 1) };
    }
    var sz = sizeOf();

    // ---------------- renderer ----------------
    var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(global.devicePixelRatio || 1, coarse ? 1.5 : 2));
    renderer.setSize(sz.w, sz.h);
    renderer.setClearColor(0x000000, 0);           // pozadi kresli CSS (prechod jako render)
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping; // AgX az v dalsi etape (CustomToneMapping)
    renderer.toneMappingExposure = 1.0;
    var canvas = renderer.domElement;
    var aoSupport = aoSupportedBy(THREE, renderer);   // AO jen s highp (rozbaleni hloubky); jinak se v HUD nenabizi a setAO vraci false
    canvas.className = 'v3d-canvas';
    stage.appendChild(canvas);

    var labelRenderer = null;
    if (hasCSS2D) {
      labelRenderer = new THREE.CSS2DRenderer();
      labelRenderer.setSize(sz.w, sz.h);
      labelRenderer.domElement.className = 'v3d-labels';
      stage.appendChild(labelRenderer.domElement);
    }

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(45, sz.w / sz.h, 1, 100000);
    camera.up.set(0, 1, 0);
    var controls = new THREE.OrbitControls(camera, canvas);
    controls.enableDamping = !reduced;
    controls.dampingFactor = 0.08;
    controls.screenSpacePanning = true;
    controls.maxPolarAngle = Math.PI / 2 + 0.35;   // trochu pod vodorovnou, ne zespodu

    var hemiLight = new THREE.HemisphereLight(0xffffff, 0x000000, 0.6); // = slunce sablony renderu (0.6, uhel 180 st.)
    scene.add(hemiLight);

    var envRT = null;
    if (hasRoom) {
      var pmrem = new THREE.PMREMGenerator(renderer);
      var room = new THREE.RoomEnvironment();
      envRT = pmrem.fromScene(room, 0.04);
      scene.environment = envRT.texture;
      room.traverse(function (n) { if (n.geometry) n.geometry.dispose(); if (n.material) n.material.dispose(); });
      pmrem.dispose();
    }
    var hdriCache = {}, hdriOrder = [], hdriLoading = {}, envSeq = 0, hdriSeed = {};
    // Velke HDRI (1-2 MB) se stahuje AZ PO prvnim zobrazenem modelu (opts.envEager = hned): na mobilni siti soutezilo o pasmo s GLB a zdrzovalo ho o ~0,8 s.
    // Do te doby osvetluje maly nahled stejneho HDRI (v.lo, 33-133 kB); brana se otevre po prvnim modelu, pri explicitni zmene prostredi, pri snapshot() a nejpozdeji po 12 s.
    var envGate = { open: !!opts.envEager, pend: false, timer: 0 };
    function hdriKey(v) { return v.file + '|' + v.rot.toFixed(4); }
    function seedOf(v) { return v.lo ? { file: v.lo, rot: v.rot } : null; }
    function loadHdriEnv(v) {
      var key = hdriKey(v);
      if (hdriCache[key]) return Promise.resolve(hdriCache[key]);
      if (hdriLoading[key]) return hdriLoading[key];
      hdriLoading[key] = ensureRgbe().then(function () { return new Promise(function (res, rej) {
        var loader = new THREE.RGBELoader();
        loader.setDataType(THREE.HalfFloatType);   // linearni filtrovani (UnsignedByte = hranate pixely)
        loader.load(envUrl(v.file), function (tex) {
          if (disposed) { tex.dispose(); rej(disposedError()); return; }
          tex.mapping = THREE.EquirectangularReflectionMapping;
          var envScene = new THREE.Scene();
          var geom = new THREE.SphereGeometry(100, 128, 64);
          geom.scale(-1, 1, 1);
          var mat = new THREE.MeshBasicMaterial({ map: tex });
          var sphere = new THREE.Mesh(geom, mat);
          sphere.rotation.y = v.rot;
          envScene.add(sphere);
          var pm = new THREE.PMREMGenerator(renderer);
          var rt = pm.fromScene(envScene, 0, 1, 1000);
          pm.dispose(); geom.dispose(); mat.dispose(); tex.dispose();
          res(rt);
        }, undefined, rej);
      }); }).then(function (rt) {
        delete hdriLoading[key]; hdriCache[key] = rt; hdriOrder.push(key);
        for (var i = 0; i < hdriOrder.length && hdriOrder.length > 3;) {   // pri hrani s natocenim a vyberem se drzi jen posledni 3 (pamet GPU), nikdy ne aktualni
          var ok = hdriOrder[i], r0 = hdriCache[ok];
          if (r0 && ok !== key && r0.texture !== scene.environment) { r0.dispose(); delete hdriCache[ok]; hdriOrder.splice(i, 1); } else i++;
        }
        return rt;
      }, function (e) { delete hdriLoading[key]; throw e; });
      return hdriLoading[key];
    }
    // envMapIntensity = zaklad (LOOK_ENV) x nasobek prostredi x nasobek varianty hliniku
    function applyMatLook() {
      var v = curEnv(), a = aluVariantByKey(st.alu) || ALU_VARIANTS[0];
      allMats.forEach(function (mat) {
        var base = mat.userData.__v3dEnvBase;
        if (typeof base !== 'number') return;
        mat.envMapIntensity = base * v.mul * (mat.userData.__v3dAluOrig ? ((a.p ? a.p.e : 1) * (st.aluCfg ? st.aluCfg.refl : 1)) : 1);
        mat.needsUpdate = true;
      });
    }
    function dropSeed(v) {              // nahled uz neni potreba (plne HDRI je pouzite): uvolnit jeho cil renderu
      var lo = seedOf(v); if (!lo) return;
      var kl = hdriKey(lo), r = hdriCache[kl];
      if (!r || r.texture === scene.environment) return;
      r.dispose(); delete hdriCache[kl]; delete hdriSeed[kl];
      var i = hdriOrder.indexOf(kl); if (i >= 0) hdriOrder.splice(i, 1);
    }
    function envGateOpen(noApply) {     // pusti stahovani plneho HDRI (noApply: volajici hned sam zavola applyEnv)
      if (envGate.open) return;
      envGate.open = true;
      if (envGate.timer) { global.clearTimeout(envGate.timer); envGate.timer = 0; }
      var pend = envGate.pend; envGate.pend = false;
      if (pend && !noApply && !disposed) applyEnv();
    }
    function envSettled(maxMs) {        // slib: plne HDRI aktualniho prostredi je pouzite (nebo se do maxMs nenacetlo / selhalo) - pro snapshot()
      if (disposed) return Promise.resolve();
      var v = curEnv();
      if (!v.file || hdriCache[hdriKey(v)]) return Promise.resolve();
      envGateOpen();
      var p = hdriLoading[hdriKey(v)];
      if (!p) return Promise.resolve();
      return Promise.race([p.then(function () {}, function () {}), new Promise(function (r) { global.setTimeout(r, maxMs); })]);
    }
    function applyEnv() {
      var v = curEnv();
      var my = ++envSeq;
      hemiLight.intensity = v.hemi;
      if (v.file) {
        var k = hdriKey(v);
        if (hdriCache[k]) scene.environment = hdriCache[k].texture;
        else if (!envGate.open) {         // pred prvnim modelem: jen maly nahled; plne HDRI az po nem (envGateOpen)
          envGate.pend = true;
          var lo = seedOf(v);
          if (lo) {
            var kl = hdriKey(lo);
            hdriSeed[kl] = true;
            if (hdriCache[kl]) scene.environment = hdriCache[kl].texture;
            else loadHdriEnv(lo).then(function (rt) {
              if (my === envSeq && !disposed && !hdriCache[k]) { scene.environment = rt.texture; requestRender(); }
            }).catch(function () { /* nahled neni nutny: plne HDRI prijde po modelu */ });
          }
        }
        else loadHdriEnv(v).then(function (rt) {
          if (my === envSeq && !disposed) { scene.environment = rt.texture; requestRender(); dropSeed(v); }
        }).catch(function (e) {
          if (disposed) return;
          st.warnings.push('HDRI prostředí se nenačetlo, použita záložní místnost: ' + ((e && e.message) || e));
          if (my === envSeq && st.env !== 'mistnost') { st.env = 'mistnost'; st.envCfg = null; applyEnv(); }
          kick(); updateHud();
        });
      } else if (envRT) scene.environment = envRT.texture;
      applyMatLook();
      requestRender();                       // kick() jen spusti smycku; bez dirty by se po zmene prostredi nic neprekreslilo
    }
    if (!envGate.open) envGate.timer = global.setTimeout(function () { envGate.timer = 0; envGateOpen(); }, 12000);     // pojistka: model nedorazil (zadny model / chyba)
    applyEnv();

    // ---------------- stav modelu ----------------
    var model = null, spec = null;
    var meshes = [];
    var origMat = new Map();          // mesh -> material z GLB
    var edgesOf = new Map();          // mesh -> LineSegments jeho skupiny hran (dratovy rezim, vytvori se jednou)
    var edgeGroups = [];              // [{obj, owner (pivot | null = staticke), meshes}]
    var groupOfMesh = new Map();      // mesh -> idx skupiny kusovniku
    var groupMeshes = new Map();      // idx -> [mesh]
    var highlightSet = new Set();
    var pivots = new Map();           // jmeno -> {node, basePos, baseQuat}
    var motions = [], motionById = {}, motionT = {}, tweens = {};
    var pickMap = {};                 // jmeno pivotu -> id pohybu
    var pickExplicit = {};            // jmeno pivotu -> true, kdyz je v motions[].pick (ne jen pivot kroku bez picku)
    var productBox = null, center = new THREE.Vector3(), radius = 1, front = new THREE.Vector3(0, 0, 1);
    var isoNorm = normalizeIsoAngles(opts.isoAngles), isoAz = isoNorm ? isoNorm.az : ISO_AZ, isoEl = isoNorm ? isoNorm.el : ISO_EL;      // uhel pohledu "3D" (1.17.0: opts.isoAngles / v.setIsoAngles)
    var dimRecs = [];                 // {obj, labels:[CSS2DObject], level, n, staticPts:[Vector3]}
    var dimsBox = null;               // obal statickych L1 kot (pro zaber kamery)
    var dimRoot = null, dimsBuilt = false;   // koty se stavi az na vyzadani (dims:0 = vubec)
    var shadow = null;
    var aoRes = null, aoMats = null;  // AO: cile renderu (jen dokud je AO zapnute) a materialy (zijou do dispose())
    var aoStat = { wPasses: 0, wMeshes: 0 };   // AO po komponentech: pocet vahovych pruchodu a meshu s vahou != 1 v poslednim (hook aoValues)
    var aoBroken = false, aoVerified = false, aoDbg = null;   // aoDbg: prepis parametru jen z ladiciho hooku (harness)
    var flight = null;
    var interacting = false;
    // ---------------- pluginy (opts.plugins) ----------------
    // opts.plugins = [function (ctx) { ...; return function dispose() {} }]: volaji se PO kazdem uspesnem postaveni modelu (prvni nacteni i
    // setModel), predchozi pluginy se pred tim ukonci (jejich dispose). ctx = { THREE, gltf (nacteny GLB: animations, scene, parser),
    // model (koren), scene, camera, controls, renderer, root, stage, container, state(), labels (slovnik textu HUD),
    // requestRender(), setAnimating(bool) (true = smycka bezi nepretrzite, dokud plugin neda false), onFrame(fn(tMs)) -> odhlaseni }.
    // Plugin smi menit scenu (pridavat/odebirat objekty, hrat animace z gltf.animations, hybat kamerou); viewer nic z toho nevi.
    // Vyjimka v pluginu nikdy nezrusi vykreslovani. Bez opts.plugins se nic nemeni.
    var pluginEnds = [], frameHooks = [], animating = false;
    function endPlugins() {
      var e = pluginEnds;
      pluginEnds = []; frameHooks = []; animating = false;
      e.forEach(function (f) { try { f(); } catch (x) { /* plugin */ } });
    }
    function runPlugins(gltf) {
      endPlugins();
      if (!Array.isArray(opts.plugins) || !opts.plugins.length || disposed) return;
      var ctx = {
        THREE: THREE, gltf: gltf, model: model, scene: scene, camera: camera, controls: controls, renderer: renderer,
        root: root, stage: stage, container: container, state: function () { return api.state(); }, labels: L,
        requestRender: function () { requestRender(); },
        setAnimating: function (b) { animating = !!b; if (animating) kick(); },
        onFrame: function (fn) {
          if (typeof fn !== 'function') return function () {};
          frameHooks.push(fn); kick();
          return function () { var i = frameHooks.indexOf(fn); if (i >= 0) frameHooks.splice(i, 1); };
        }
      };
      opts.plugins.forEach(function (pl) {
        if (typeof pl !== 'function') return;
        try { var end = pl(ctx); if (typeof end === 'function') pluginEnds.push(end); } catch (x) { st.warnings.push('plugin: ' + ((x && x.message) || x)); }
      });
    }

    var occluderMat = new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: true, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
    var highlightMat = new THREE.MeshStandardMaterial({ color: HIGHLIGHT, emissive: HIGHLIGHT, emissiveIntensity: 0.35, metalness: 0.3, roughness: 0.5 });
    highlightMat.color.convertSRGBToLinear(); highlightMat.emissive.convertSRGBToLinear();
    // podsviceni dilu pod mysi (hoverHint): pruhledna vrstva na stejne geometrii jako dil; FrontSide / DoubleSide podle materialu dilu
    var hoverMatF = new THREE.MeshBasicMaterial({ color: HIGHLIGHT, transparent: true, opacity: 0.45, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2, toneMapped: false });
    hoverMatF.color.convertSRGBToLinear();
    var hoverMatD = hoverMatF.clone(); hoverMatD.side = THREE.DoubleSide;
    var dimLineMat = new THREE.LineBasicMaterial({ color: DIM_COLOR, transparent: true, opacity: 0.9, depthTest: false, toneMapped: false });
    var dimLineMatMinor = new THREE.LineBasicMaterial({ color: DIM_COLOR, transparent: true, opacity: 0.6, depthTest: false, toneMapped: false });
    dimLineMat.color.convertSRGBToLinear(); dimLineMatMinor.color.convertSRGBToLinear();

    // ---------------- HUD ----------------
    var hud = buildHud();
    root.appendChild(hud.el);

    // ---------------- kresleni ----------------
    var rafId = 0, dirty = false;
    function requestRender() { dirty = true; kick(); }
    function kick() { if (!rafId && !disposed) rafId = global.requestAnimationFrame(frame); }
    // Kota, na kterou se divame skoro podel jeji osy (vyska pri pohledu
    // Shora), by byla jen zmet car a popisek uprostred - docasne se skryje.
    // Uroven (Vyp/Rozmery/Detail) a dimsCount() se tim nemeni.
    var _fa = new THREE.Vector3(), _fb = new THREE.Vector3(), _fc = new THREE.Vector3();
    function updateDimFacing() {
      camera.updateMatrixWorld();
      camera.getWorldDirection(_fc);
      for (var i = 0; i < dimRecs.length; i++) {
        var r = dimRecs[i];
        if (!r.obj.visible) continue;
        r.obj.updateWorldMatrix(true, false);
        _fa.copy(r.a2).applyMatrix4(r.obj.matrixWorld);
        _fb.copy(r.b2).applyMatrix4(r.obj.matrixWorld);
        var dir = _fb.sub(_fa), len = dir.length();
        // uhel mezi osou koty a smerem pohledu kamery (jako u vykresu: kota
        // rovnobezna s osou pohledu nema vypovidaci hodnotu)
        var fore = len > 1e-6 && Math.abs(dir.dot(_fc) / len) > 0.94;   // < ~20 st.
        if (fore !== r.fore) {
          r.fore = fore;
          r.obj.children.forEach(function (c) { c.visible = !fore; });
        }
      }
    }
    // Stav kamery (oficialni API cameraInfo()/onCamera(); stejna pole jako ladici hook window.__v3d.camera()).
    var cameraSubs = [];
    function cameraInfoNow() {
      camera.updateMatrixWorld(true);
      var dir = camera.position.clone().sub(controls.target).normalize();
      var sup = new THREE.Vector3(0, 1, 0).applyQuaternion(camera.quaternion);
      return { pos: camera.position.toArray(), target: controls.target.toArray(), dir: dir.toArray(), screenUp: sup.toArray(),
        up: camera.up.toArray(), dist: camera.position.distanceTo(controls.target), fov: camera.fov, aspect: camera.aspect,
        near: camera.near, far: camera.far, minDistance: controls.minDistance, maxDistance: controls.maxDistance };
    }
    function notifyCamera() {
      if (!cameraSubs.length) return;
      var info = cameraInfoNow();
      cameraSubs.slice().forEach(function (cb) { try { cb(info); } catch (e) { /* chyba odberatele nesmi shodit vykreslovani */ } });
    }
    function renderNow() {
      if (disposed) return;
      if (dimRecs.length) updateDimFacing();
      var done = false;
      if (aoActive()) {
        try { aoFrame(); done = true; } catch (e) { aoFail(e); }
      }
      if (!done) renderer.render(scene, camera);   // bez AO presne jako drive (jeden pruchod)
      if (labelRenderer) labelRenderer.render(scene, camera);
      st.frames++;
      notifyCamera();
    }
    function frame(ts) {
      rafId = 0;
      if (disposed) return;
      var t = now(), keep = false;
      if (flight) { stepFlight(t); keep = true; }
      if (stepTweens(t)) { keep = true; hoverSchedule(); }
      if (!flight && controls.enabled && controls.update()) { keep = true; dirty = true; } // dojezd (damping)
      if (interacting) keep = true;            // drzeny prst/mys: smycka bezi, kresli se jen pri zmene
      if (frameHooks.length) {
        frameHooks.slice().forEach(function (h) { try { h(t); } catch (x) { /* plugin nesmi zrusit vykreslovani */ } });
        dirty = true;                          // plugin ve snimku neco mohl zmenit
        if (animating) keep = true;
      }
      if (dirty) { renderNow(); dirty = false; }
      if (keep) kick();
    }
    controls.addEventListener('change', requestRender);
    controls.addEventListener('change', function () { hoverSchedule(); });
    controls.addEventListener('start', function () {
      interacting = true;
      if (!st.interacted) { st.interacted = true; track('interact_3d_model'); hideHint(); }
      if (st.view) { st.view = null; updateHud(); }
      kick();
    });
    controls.addEventListener('end', function () { interacting = false; kick(); });

    // ---------------- velikost ----------------
    function resize() {
      if (disposed) return;
      var s = sizeOf();
      if (s.w === sz.w && s.h === sz.h) return;
      sz = s;
      camera.aspect = s.w / s.h;
      camera.updateProjectionMatrix();
      renderer.setSize(s.w, s.h);
      if (labelRenderer) labelRenderer.setSize(s.w, s.h);
      root.classList.toggle('v3d-narrow', s.w < 640);
      if (hud) syncChipsH();
      if (st.ready && st.view && !flight) applyView(st.view, true);
      requestRender();
    }
    root.classList.toggle('v3d-narrow', sz.w < 640);
    var ro = null;
    if (global.ResizeObserver) { ro = new ResizeObserver(resize); ro.observe(root); if (hudDock) ro.observe(stage); }
    else on(global, 'resize', resize);

    // ---------------- dotyk: nepropagovat na stranku (swipe deckEl) ----------------
    ['touchstart', 'touchmove', 'touchend', 'touchcancel', 'wheel'].forEach(function (type) {
      on(root, type, function (e) { e.stopPropagation(); }, { passive: true });
    });
    // Behem preletu jsou OrbitControls vypnute - prvni dotyk prelet ukonci
    // (capture na root bezi pred listenerem OrbitControls na canvasu).
    function cancelFlight() {
      if (!flight) return;
      flight = null;
      controls.enabled = true;
      controls.update();
    }
    on(root, 'pointerdown', function (e) { if (e.target === canvas) cancelFlight(); }, true);

    // ---------------- vyber dilu (klik/klepnuti) ----------------
    var raycaster = new THREE.Raycaster();
    var ptrs = new Map(), tap = null, hoverAt = 0, tapLog = [];
    function logTap(s) { tapLog.push(s); if (tapLog.length > 8) tapLog.shift(); }
    on(canvas, 'pointerdown', function (e) {
      if (e.pointerType === 'mouse') hoverBtn = true;                  // tah / otaceni: vyzva se pocita az po uvolneni tlacitka
      if (e.isPrimary) ptrs.clear();          // primarni ukazatel = nove gesto (zahodit ztracene pointerup)
      ptrs.set(e.pointerId, true);
      if (ptrs.size > 1) { tap = null; logTap('multi'); return; }
      if (e.pointerType === 'mouse' && e.button !== 0) { tap = null; return; }
      tap = { id: e.pointerId, x: e.clientX, y: e.clientY, t: e.timeStamp || now() };
    });
    on(canvas, 'pointermove', function (e) {
      if (e.pointerType === 'mouse') hoverBtn = e.buttons > 0;
      if (tap && e.pointerId === tap.id && Math.hypot(e.clientX - tap.x, e.clientY - tap.y) > TAP_PX) { tap = null; logTap('drag'); clearHover(); }       // tah = otaceni, ne klik: vyzva zmizi
      if (e.pointerType === 'mouse' && !e.buttons && st.ready) {
        hoverPtr = { x: e.clientX, y: e.clientY };
        var t = now();
        if (t - hoverAt > 80) { hoverAt = t; hoverEval(); }
        else { if (hoverId) placeTip(e.clientX, e.clientY); hoverSchedule(true); }   // popisek jede s kurzorem i mezi vyhodnocenimi; posledni poloha se dovyhodnoti (mys se zastavila; i kurzor ruka bez hoverHint)
      }
    });
    on(canvas, 'pointerleave', function (e) { if (e.pointerType === 'mouse') { hoverPtr = null; clearHover(); } });
    on(canvas, 'pointerup', function (e) {
      if (e.pointerType === 'mouse') { hoverBtn = false; hoverPtr = { x: e.clientX, y: e.clientY }; hoverSchedule(); }      // po kliknuti i po tahu: dovyhodnotit na skutecne poloze kurzoru (po kliknuti ukaz novy stav)
      ptrs.delete(e.pointerId);
      var tp = tap;
      if (!tp || e.pointerId !== tp.id) { logTap('up-bez-down'); return; }
      tap = null;
      // doba stisku z casu udalosti (ne z casu obsluhy): na zahlcenem
      // telefonu se pointerup muze obslouzit pozde, i kdyz prst pustil hned
      var dt = (e.timeStamp || now()) - tp.t;
      if (Math.hypot(e.clientX - tp.x, e.clientY - tp.y) > TAP_PX || dt > 900) { logTap('pomale/tah ' + Math.round(dt)); return; }
      logTap('tap');
      pickAt(e.clientX, e.clientY);
    });
    on(canvas, 'pointercancel', function (e) { ptrs.delete(e.pointerId); tap = null; if (e.pointerType === 'mouse') hoverBtn = false; });

    // Slot dilu pro onPick: cele cislo userData.g nejblizsiho predka (vc. uzlu samotneho);
    // jen userData.g (ne jmeno bomgrp_N, ne zadny jiny udaj), null = uzel bez g.
    function slotOf(mesh) {
      for (var n = mesh; n && n !== model.parent; n = n.parent) {
        var g = n.userData ? n.userData.g : undefined;
        if (typeof g === 'number' && isFinite(g) && g >= 0 && Math.floor(g) === g) return g;
      }
      return null;
    }
    // pohyb, ktery klik na mesh spusti: nejblizsi pivot s pickMap rozhoduje o pohybu; "explicit" = nektery pivot nad
    // dilem (vc. nej) je v motions[].pick (a ne jen pivotem kroku bez picku)
    function motionOfMesh(o) {
      var mid = null, expl = false;
      for (var n = o; n && n !== model.parent; n = n.parent) {
        var nm = pivotNameOf(n);
        if (!nm) continue;
        if (!mid && pickMap[nm]) mid = pickMap[nm];
        if (pickExplicit[nm]) { expl = true; if (!mid) mid = pickMap[nm]; break; }
      }
      return { motion: mid, explicit: expl };
    }
    function hitAt(cx, cy) {
      if (!model) return null;
      var r = canvas.getBoundingClientRect();
      if (!r.width || !r.height) return null;
      var ndc = new THREE.Vector2(((cx - r.left) / r.width) * 2 - 1, -((cy - r.top) / r.height) * 2 + 1);
      raycaster.setFromCamera(ndc, camera);
      var hits = raycaster.intersectObjects(meshes, false);
      for (var i = 0; i < hits.length; i++) {
        var o = hits[i].object;
        if (!o.visible) continue;
        var mo = motionOfMesh(o);
        return { mesh: o, motion: mo.motion, motionExplicit: mo.explicit, group: groupOfMesh.has(o) ? groupOfMesh.get(o) : null, slot: slotOf(o) };
      }
      return null;
    }
    function pickAt(cx, cy) {
      var h = hitAt(cx, cy);
      logTap(h ? ('hit ' + (h.motion || ('g' + h.group))) : 'miss');
      if (!h) { selectMotion(null); return; }                    // klik mimo model = zrusit vyber komponentu
      // onPick aktivni: pohyb ma prednost jen u dilu z motions[].pick; dil pod pivotem kroku
      // mimo pick, ktery nese slot (g), jde do onPick
      if (h.motion && onPickFn && h.slot != null && !h.motionExplicit) h = { mesh: h.mesh, motion: null, group: h.group, slot: h.slot };
      if (h.motion) {
        // Box na zavrenem vysuvu: prvni klik jen vysune vysuv (zakaznik vidi,
        // co se deje), druhy klik box zvedne. Chip "Box N" dal dela vse naraz.
        var mm = motionById[h.motion];
        if (targetOf(h.motion) < 0.5) {
          var closedDeps = mm.deps.filter(function (d) { return targetOf(d) < 1; });
          if (closedDeps.length) { closedDeps.forEach(function (d) { play(d, 1); }); return; }
        }
        selectMotion(h.motion);
        play(h.motion, 0);
        return;
      }
      if (bomPickable(h.group)) {
        try { bom.onPick(h.group); } catch (e) { /* stranka */ }
      }
      if (onPickFn && h.slot != null) {
        try { onPickFn(h.slot); } catch (e) { /* stranka */ }
      }
    }

    // ---------------- vyzva ke kliknuti pri najeti mysi (opts.hoverHint === true; viewer 1.13.0, bot10 2026-10-07) ----------------
    // Mys (ne dotyk) nad pohyblivym dilem: dil se podsviti (pruhledna oranzova vrstva na jeho meshich - material modelu se nemeni, takze nic neprebije
    // barvy / sytost / hlinik / AO) a u kurzoru se ukaze popisek "Suplik 2 · Leva strana / Kliknutim otevrete" (po otevreni "zavrete"). Vyzva se ukaze JEN tam,
    // kde klik skutecne spusti pohyb (stejne pravidlo jako pickAt). Kurzor "ruka" je i bez hoverHint.
    function hoverMotionOf(h) {
      if (!h || !h.motion || !motionById[h.motion]) return null;
      if (onPickFn && h.slot != null && !h.motionExplicit) return null;          // klik jde do onPick stranky, ne do pohybu
      return h.motion;
    }
    function hoverTexts(id) {
      var m = motionById[id], name = motionLabel(m, L);
      if (m.g && L['side_' + m.g]) name += ' · ' + L['side_' + m.g];
      var act = L.hover_close;
      if (targetOf(id) < 0.5) {
        var dep = m.deps.filter(function (d) { return targetOf(d) < 1; })[0];                 // box na zavrenem vysuvu: prvni klik vysune vysuv (viz pickAt)
        act = dep ? (L.hover_open + ': ' + motionLabel(motionById[dep], L)) : L.hover_open;
      }
      return { name: name, act: act };
    }
    function ensureTip() {
      if (hoverTip) return hoverTip;
      hoverTip = el('div', 'v3d-tip');
      hoverTip.setAttribute('role', 'tooltip');
      hoverTip.setAttribute('aria-hidden', 'true');
      hoverTip.appendChild(el('span', 'v3d-tip__name'));
      var act = el('span', 'v3d-tip__act'), ic = el('span', 'v3d-tip__ico');
      ic.innerHTML = TIP_ICON;                                                      // pevny retezec vieweru, zadna data od stranky
      act.appendChild(ic);
      act.appendChild(el('span', 'v3d-tip__txt'));
      hoverTip.appendChild(act);
      root.appendChild(hoverTip);
      return hoverTip;
    }
    function placeTip(cx, cy) {
      if (!hoverTip) return;
      var rr = root.getBoundingClientRect(), w = hoverTip.offsetWidth, h = hoverTip.offsetHeight;
      var x = cx - rr.left + 16, y = cy - rr.top + 22;
      if (x + w > rr.width - 6) x = cx - rr.left - w - 14;                          // u praveho okraje vlevo od kurzoru
      if (y + h > rr.height - 6) y = cy - rr.top - h - 14;                          // u spodniho okraje nad kurzor
      hoverTip.style.transform = 'translate(' + Math.round(Math.max(4, x)) + 'px,' + Math.round(Math.max(4, y)) + 'px)';
    }
    function clearHoverOverlay() {
      var had = hoverOvs.length > 0;
      hoverOvs.forEach(function (ov) { if (ov.parent) ov.parent.remove(ov); });
      hoverOvs = [];
      if (had) requestRender();
    }
    function setHoverOverlay(id) {
      clearHoverOverlay();
      if (!id || st.mode !== 'real' || !model) return;
      meshes.forEach(function (o) {
        if (!o.visible || motionOfMesh(o).motion !== id) return;
        var ov = new THREE.Mesh(o.geometry, (o.material && o.material.side === THREE.DoubleSide) ? hoverMatD : hoverMatF);
        ov.raycast = function () {};                                                // vrstva nikdy neodpovida na klik ani najeti
        ov.renderOrder = 4;
        ov.matrixAutoUpdate = false;                                                // dite meshe, lokalni transformace = identita
        o.add(ov);
        hoverOvs.push(ov);
      });
      if (hoverOvs.length) requestRender();
    }
    function clearHover() {
      if (hoverTimer) { global.clearTimeout(hoverTimer); hoverTimer = 0; }
      hoverId = null;
      clearHoverOverlay();
      if (hoverTip) hoverTip.classList.remove('is-on');
    }
    function hoverShow(id) {
      if (!id) { if (hoverId) clearHover(); return; }
      var tip = ensureTip(), tx = hoverTexts(id);
      tip.firstChild.textContent = tx.name;
      tip.querySelector('.v3d-tip__txt').textContent = tx.act;
      if (id !== hoverId) { hoverId = id; setHoverOverlay(id); }
      tip.classList.add('is-on');
      if (hoverPtr) placeTip(hoverPtr.x, hoverPtr.y);
    }
    function hoverEval() {
      if (!hoverPtr || hoverBtn || !st.ready || disposed || !model) return;                                  // mys stisknuta = tah / otaceni, ne najeti
      if (opts.hoverHint === true) model.updateMatrixWorld(true);                   // po animaci / pohybu kamery muze byt svetova matice o snimek pozadu
      var h = hitAt(hoverPtr.x, hoverPtr.y);
      canvas.style.cursor = (h && (h.motion || bomPickable(h.group) || (onPickFn && h.slot != null))) ? 'pointer' : '';
      if (opts.hoverHint === true) hoverShow(hoverMotionOf(h));
    }
    function hoverSchedule(always) {                                                // dozvuky (animace pohybu, kamera, klik, posledni poloha mysi): dovyhodnotit s odstupem
      if (hoverTimer || !hoverPtr || hoverBtn || disposed || (always !== true && opts.hoverHint !== true)) return;
      hoverTimer = global.setTimeout(function () { hoverTimer = 0; hoverEval(); }, HOVER_MS);
    }

    // ---------------- nacteni / vymena modelu ----------------
    var readyResolve, readyReject;
    var ready = new Promise(function (res, rej) { readyResolve = res; readyReject = rej; });
    ready.catch(function () { /* odmitnuti resi volajici pres onError / ready.catch */ });

    var loader = new THREE.GLTFLoader();
    var loadSeq = 0;                  // cislo posledniho pozadavku na model (mount, setModel): vyhrava posledni
    var pendingLoads = [];            // nedokoncena setModel(): {reject}
    var modelSeq = 0;                 // kolikaty model je zobrazen (0 = zadny)
    var camTouched = false;           // setup uz sahl na kameru (kvuli navratu pri chybe)

    function fail(err) {
      if (disposed) return;
      // FileLoader r128 pri HTTP chybe vola onError s ProgressEventem, ne Error
      var status = err && err.target && err.target.status;
      st.error = (err && err.message) ? String(err.message) : (status ? 'GLB: HTTP ' + status : 'GLB se nepodařilo načíst');
      root.classList.remove('v3d-loading');
      root.classList.add('v3d-failed');
      hud.msg.textContent = L.load_failed;
      if (typeof opts.onError === 'function') { try { opts.onError(err); } catch (e) { /* */ } }
      readyReject(err instanceof Error ? err : new Error(st.error));
    }
    function toError(err) {
      if (err instanceof Error) return err;
      var status = err && err.target && err.target.status;
      return new Error((err && err.message) ? String(err.message) : (status ? 'GLB: HTTP ' + status : 'GLB se nepodařilo načíst'));
    }
    function supersededError() { var e = new Error('V3D: setModel nahrazeno novějším voláním'); e.superseded = true; return e; }
    function disposedError() { return new Error('V3D: disposed'); }
    function cancelPending(mk) {
      var list = pendingLoads;
      pendingLoads = [];
      list.forEach(function (r) { try { r.reject(mk()); } catch (e) { /* */ } });
    }

    // zdroj modelu: ArrayBuffer | typed array (kopie jeho okna) | URL (string)
    function asArrayBuffer(x) {
      if (!x || typeof x === 'string') return null;
      if (Object.prototype.toString.call(x) === '[object ArrayBuffer]') return x;
      if (ArrayBuffer.isView(x)) return x.buffer.slice(x.byteOffset, x.byteOffset + x.byteLength);
      return null;
    }
    function loadSource(src) {
      return new Promise(function (res, rej) {
        try {
          var ab = asArrayBuffer(src);
          if (ab) loader.parse(ab, '', res, rej);
          else if (typeof src === 'string' && src) loader.load(src, res, undefined, rej);
          else rej(new Error('V3D: chybi modelUrl/arrayBuffer'));
        } catch (e) { rej(e); }
      });
    }

    // ---- uvolneni GPU/DOM zdroju (geometrie, materialy, textury, cile renderu, popisky kot)
    var SHARED_MATS = [occluderMat, highlightMat, dimLineMat, dimLineMatMinor, hoverMatF, hoverMatD];   // zijou s prohlizecem, ne s modelem
    function collectRes(rootObj, geos, mats) {
      rootObj.traverse(function (n) {
        if (n.geometry) geos.add(n.geometry);
        if (n.material) (Array.isArray(n.material) ? n.material : [n.material]).forEach(function (m) { if (m) mats.add(m); });
        if (n.isCSS2DObject && n.element && n.element.parentNode) n.element.parentNode.removeChild(n.element);
      });
    }
    function disposeRes(geos, mats) {
      var texs = new Set();
      mats.forEach(function (m) {
        if (SHARED_MATS.indexOf(m) >= 0) return;
        Object.keys(m).forEach(function (k) { var v = m[k]; if (v && v.isTexture) texs.add(v); });
      });
      geos.forEach(function (g) { g.dispose(); });
      mats.forEach(function (m) { if (SHARED_MATS.indexOf(m) < 0) m.dispose(); });
      texs.forEach(function (t) {
        try { t.dispose(); if (t.image && typeof t.image.close === 'function') t.image.close(); } catch (e) { /* */ }
      });
    }
    // GLB, ktery se nikdy nezobrazil (zruseny/zastaraly/dispose)
    function disposeGltf(gltf) {
      try {
        var g = new Set(), m = new Set();
        if (gltf && gltf.scene) collectRes(gltf.scene, g, m);
        disposeRes(g, m);
      } catch (e) { /* */ }
    }

    // ---- stav jednoho modelu (vse, co se pri vymene modelu zahazuje / vraci pri chybe)
    function takeState() {
      return {
        model: model, spec: spec, meshes: meshes, origMat: origMat, edgesOf: edgesOf, edgeGroups: edgeGroups,
        groupOfMesh: groupOfMesh, groupMeshes: groupMeshes, highlightSet: highlightSet, pivots: pivots,
        motions: motions, motionById: motionById, motionT: motionT, tweens: tweens, pickMap: pickMap, pickExplicit: pickExplicit,
        productBox: productBox, center: center.clone(), radius: radius, front: front.clone(),
        dimRecs: dimRecs, dimsBox: dimsBox, dimRoot: dimRoot, dimsBuilt: dimsBuilt, shadow: shadow,
        legacy: st.legacy, look: st.look, warnings: st.warnings, allowReal: st.allowReal, twoSided: st.twoSided,
        blocksMs: st.blocksMs, mode: st.mode, dims: st.dims
      };
    }
    function clearState() {
      model = null; spec = null; meshes = []; origMat = new Map(); edgesOf = new Map(); edgeGroups = [];
      groupOfMesh = new Map(); groupMeshes = new Map(); highlightSet = new Set(); pivots = new Map();
      motions = []; motionById = {}; motionT = {}; tweens = {}; pickMap = {}; pickExplicit = {};
      productBox = null; center.set(0, 0, 0); radius = 1; front.set(0, 0, 1);
      dimRecs = []; dimsBox = null; dimRoot = null; dimsBuilt = false; shadow = null; selId = null; selRecs = null;
      st.warnings = []; st.twoSided = false; st.blocksMs = 0;
    }
    function putState(s) {
      model = s.model; spec = s.spec; meshes = s.meshes; origMat = s.origMat; edgesOf = s.edgesOf; edgeGroups = s.edgeGroups;
      groupOfMesh = s.groupOfMesh; groupMeshes = s.groupMeshes; highlightSet = s.highlightSet; pivots = s.pivots;
      motions = s.motions; motionById = s.motionById; motionT = s.motionT; tweens = s.tweens; pickMap = s.pickMap; pickExplicit = s.pickExplicit;
      productBox = s.productBox; center.copy(s.center); radius = s.radius; front.copy(s.front);
      dimRecs = s.dimRecs; dimsBox = s.dimsBox; dimRoot = s.dimRoot; dimsBuilt = s.dimsBuilt; shadow = s.shadow;
      st.legacy = s.legacy; st.look = s.look; st.warnings = s.warnings; st.allowReal = s.allowReal; st.twoSided = s.twoSided;
      st.blocksMs = s.blocksMs; st.mode = s.mode; st.dims = s.dims;
    }
    function detachFromScene(s) {
      [s.model, s.dimRoot, s.shadow && s.shadow.group].forEach(function (o) { if (o && o.parent) o.parent.remove(o); });
      s.edgeGroups.forEach(function (g) { if (!g.owner && g.obj.parent) g.obj.parent.remove(g.obj); });   // hrany pivotu jedou s modelem
    }
    function reattachToScene(s) {
      [s.model, s.dimRoot, s.shadow && s.shadow.group].forEach(function (o) { if (o) scene.add(o); });
      s.edgeGroups.forEach(function (g) { if (!g.owner) scene.add(g.obj); });
    }
    function disposeState(s) {
      var geos = new Set(), mats = new Set();
      detachFromScene(s);
      [s.model, s.dimRoot].forEach(function (o) { if (o) collectRes(o, geos, mats); });
      s.edgeGroups.forEach(function (g) { collectRes(g.obj, geos, mats); });
      if (s.shadow) {
        collectRes(s.shadow.group, geos, mats);
        mats.add(s.shadow.depthMat); mats.add(s.shadow.hMat); mats.add(s.shadow.vMat);
        s.shadow.rt.dispose(); s.shadow.rtBlur.dispose();
      }
      s.origMat.forEach(function (m) { (Array.isArray(m) ? m : [m]).forEach(function (x) { if (x) mats.add(x); }); });
      disposeRes(geos, mats);
    }
    function snapCamera() {
      return { pos: camera.position.clone(), tgt: controls.target.clone(), min: controls.minDistance, max: controls.maxDistance,
        near: camera.near, far: camera.far, view: st.view, flight: flight, enabled: controls.enabled };
    }
    function restoreCamera(c) {
      camera.position.copy(c.pos); controls.target.copy(c.tgt); camera.lookAt(c.tgt);
      controls.minDistance = c.min; controls.maxDistance = c.max; camera.near = c.near; camera.far = c.far;
      camera.updateProjectionMatrix();
      st.view = c.view; flight = c.flight; controls.enabled = c.enabled;
    }
    function restoreView() {
      root.classList.toggle('v3d-mode-wire', st.mode === 'wire');
      root.classList.toggle('v3d-mode-real', st.mode === 'real');
      buildChips();
      updateHud();
      requestRender();
    }

    // Nahradi zobrazeny model novym - transakcne: pri chybe zustane puvodni model, kamera i
    // stav presne jako byly, zdroje noveho se uvolni a chyba se vyhodi vyse. Vse synchronne
    // (mezi odebranim stareho a pridanim noveho se nic nekresli).
    function installModel(gltf, keepCamera) {
      if (!gltf || !gltf.scene || !gltf.scene.isObject3D) throw new Error('GLB neobsahuje scénu');
      clearHover();                                                // podsviceni a popisek patri starému modelu
      var old = model ? takeState() : null;
      var cam = old ? snapCamera() : null;
      if (old) detachFromScene(old);
      clearState();
      camTouched = false;
      try {
        setup(gltf, !!old && !!keepCamera, old ? old.front : null);
      } catch (e) {
        var partial = takeState();
        clearState();
        disposeState(partial);
        disposeGltf(gltf);
        if (old) {
          putState(old);
          reattachToScene(old);
          if (camTouched) restoreCamera(cam);
          restoreView();
        }
        throw e;
      }
      if (old) disposeState(old);
      modelSeq++;
      tap = null;           // gesto zacate nad starym modelem neni klik do noveho
      runPlugins(gltf);     // pluginy az po uspesnem postaveni (selhani vyse necha stare pluginy beze zmeny)
    }
    // model je zobrazen (poprve nebo po neuspechu mountu): stav "pripraveno"
    function markShown() {
      var first = !st.ready;
      st.ready = true; st.error = null;
      root.classList.remove('v3d-loading');
      root.classList.remove('v3d-failed');
      hud.msg.textContent = L.loading;
      updateHud();          // skryti segmentu (Vzhled u legacy, Koty bez kot) plati az po ready
      requestRender();
      if (first) {
        envGateOpen();                  // prvni model je videt: ted muze plne HDRI
        if (typeof opts.onReady === 'function') { try { opts.onReady(api); } catch (e) { /* */ } }
        readyResolve(api);
      }
    }

    function onLoaded(gltf, seq) {
      // dispose() / setModel() prisel driv nez model (ready uz je odmitnute / ceka na novejsi) - uklidit GPU zdroje
      if (disposed || seq !== loadSeq) { disposeGltf(gltf); return; }
      try { installModel(gltf, false); } catch (e) { fail(e); return; }
      markShown();
    }

    // verejne: vymena modelu za behu (viz hlavicka souboru)
    function setModel(src, o) {
      var keep = !!(o && o.keepCamera === true);
      var hasBom = !!(o && o.bom !== undefined), newBom = hasBom ? o.bom : null;
      var seq = ++loadSeq;
      cancelPending(supersededError);        // posledni vyhrava: starsi nedokoncena volani konci hned
      var p = new Promise(function (resolve, reject) {
        if (disposed) { reject(disposedError()); return; }
        var rec = { reject: reject };
        pendingLoads.push(rec);
        function unpend() { var i = pendingLoads.indexOf(rec); if (i >= 0) pendingLoads.splice(i, 1); }
        loadSource(src).then(function (gltf) {
          unpend();
          if (disposed) { disposeGltf(gltf); reject(disposedError()); return; }
          if (seq !== loadSeq) { disposeGltf(gltf); reject(supersededError()); return; }
          try { installModel(gltf, keep); }
          catch (e) { if (!st.ready) fail(e); reject(toError(e)); return; }
          if (hasBom) setBom(newBom);          // kusovnik noveho modelu (items[].mesh_group) - az kdyz se model opravdu vymenil
          markShown();
          resolve(api);
        }, function (err) {
          unpend();
          if (disposed) { reject(disposedError()); return; }
          if (seq !== loadSeq) { reject(supersededError()); return; }
          if (!st.ready) fail(err);
          reject(toError(err));
        });
      });
      p.catch(function () { /* odmitnuti resi volajici; volani bez .catch nehlasi unhandled rejection */ });
      return p;
    }

    var seq0 = ++loadSeq;
    var src0 = opts.arrayBuffer || opts.modelUrl || null;
    if (!src0) setTimeout(function () { if (seq0 === loadSeq) fail(new Error('V3D: chybi modelUrl/arrayBuffer')); }, 0);
    else loadSource(src0).then(function (gltf) { onLoaded(gltf, seq0); }, function (err) { if (seq0 === loadSeq) fail(err); });

    function pivotNameOf(n) {
      var nm = (n.userData && typeof n.userData.name === 'string') ? n.userData.name : n.name;
      return (typeof nm === 'string' && PIVOT_RE.test(nm)) ? nm : null;
    }

    function setup(gltf, keepCamera, oldFront) {
      model = gltf.scene;
      var s0 = gltf.scenes && gltf.scenes[0];
      var raw = (s0 && s0.userData && s0.userData.v3d) || (model.userData && model.userData.v3d) || null;
      var vr = validateSpec(raw);
      spec = vr.spec;
      st.warnings = vr.warnings.slice();
      st.legacy = !spec;
      st.look = spec ? spec.look : 'nat';
      front.set(0, 0, 1);
      if (spec) front.set(spec.front[0], 0, spec.front[2]).normalize();
      scene.add(model);
      model.updateMatrixWorld(true);

      model.traverse(function (n) { if (n.isMesh) meshes.push(n); });
      prepareMaterials();
      collectGroups();
      collectPivots();
      var tb = now();
      computeBlocks();
      st.blocksMs = now() - tb;

      // obal produktu: ze spec, jinak z geometrie
      var b = new THREE.Box3();
      if (spec && spec.box) b.set(new THREE.Vector3().fromArray(spec.box.min), new THREE.Vector3().fromArray(spec.box.max));
      else meshes.forEach(function (m) { b.expandByObject(m); });
      if (b.isEmpty()) b.set(new THREE.Vector3(-1, -1, -1), new THREE.Vector3(1, 1, 1));
      productBox = b;
      b.getCenter(center);
      radius = Math.max(b.getSize(new THREE.Vector3()).length() / 2, 1);

      buildShadow();
      renderShadow();      // jednou, v zavrenem stavu

      // Vzhled: GLB s v3d = opts.mode (stranka predava 'real' - Robert chce
      // materialy a svetlo jako render, Drateny zustava prepinacem); legacy GLB
      // bez v3d = jen Drateny (2026-09-14), Skutecny jen s opts.allowReal.
      // Volba stranky/zakaznika (modePref/dimsPref) preziva vymenu modelu.
      st.allowReal = !!spec || !!opts.allowReal;
      st.mode = st.modePref || (spec ? 'real' : 'wire');
      if (!st.allowReal) st.mode = 'wire';
      // Koty: bez prepinace (hudKoty:false) a bez vyslovneho dims jsou vypnute; dims:0 = vubec se
      // nestavi (ani geometrie, ani DOM popisky) - postavi se az pri zapnuti (HUD / v.setDims)
      st.dims = st.dimsPref != null ? st.dimsPref : (!hudKoty ? 0 : (spec ? 1 : 2));
      if (st.dims > 0) {
        ensureDims();
        if (st.dims === 2 && !dimRecs.some(function (d) { return d.level === 2; })) st.dims = 1;
      }
      applyMode(st.mode);
      applyDims();
      buildChips();
      updateHud();

      // limity kamery
      var fitIso = fitDistance(viewDir('iso'), FIT_PAD);
      var minD = Math.max(radius * 0.3, 20), maxD = Math.max(fitIso * 3, radius * 8);
      camTouched = true;
      if (keepCamera) {
        // kamera zustava presne, kde je: limity se jen rozsiri, aby ji (damping/update) nic neposunulo
        var dNow = camera.position.distanceTo(controls.target);
        minD = Math.min(minD, dNow); maxD = Math.max(maxD, dNow);
      }
      controls.minDistance = minD;
      controls.maxDistance = maxD;
      camera.near = Math.max(radius / 200, 0.5);
      camera.far = maxD + radius * 6;
      if (keepCamera) camera.far = Math.max(camera.far, camera.position.distanceTo(center) + radius * 4);
      camera.updateProjectionMatrix();
      if (!keepCamera) applyView('iso', true);
      else if (st.view && oldFront && front.distanceToSquared(oldFront) > 1e-9) { st.view = null; updateHud(); }   // jiny smer cela: nazev pohledu uz neplati
    }

    // Materialy z GLB se pouziji, jak jsou (Vandr build je uz vypece). Jen:
    // flatShading (render ma use_smooth=False), envMapIntensity podle look.
    // Legacy GLB (THREE.GLTFExporter r128 bez outputEncoding) ma v
    // baseColorFactor primo sRGB hodnoty -> prevod do linearnich, aby
    // pri sRGB vystupu nevysly svetlejsi (#c9cdd1 -> ~#e6e8ea).
    function applyAlu() {
      var v = aluVariantByKey(st.alu) || ALU_VARIANTS[0];
      aluMats.forEach(function (mat) {
        var o = mat.userData.__v3dAluOrig, p = v.p;
        mat.metalness = p ? p.m : o.m;
        mat.roughness = Math.min(1, Math.max(0.02, (p ? p.r : o.r) * (st.aluCfg ? st.aluCfg.rough : 1)));
        mat.color.setRGB(o.cr * (p ? p.k : 1), o.cg * (p ? p.k : 1), o.cb * (p ? p.k : 1));
        mat.userData.__v3dAoW = st.aluCfg ? st.aluCfg.ao : 1;      // AO po komponentech: vaha hlinikovych profilu
        mat.needsUpdate = true;
      });
    }
    function prepareMaterials() {
      var envI = LOOK_ENV[st.look] || 1.0, seen = new Set();
      aluMats = [];
      colorMats = [];
      allMats = [];
      meshes.forEach(function (m) {
        origMat.set(m, m.material);
        (Array.isArray(m.material) ? m.material : [m.material]).forEach(function (mat) {
          if (!mat || seen.has(mat)) return;
          seen.add(mat);
          if (st.legacy && mat.color && !mat.userData.__v3dLin) {
            mat.userData.__v3dSrgb = mat.color.getHex();
            mat.color.convertSRGBToLinear();
            if (mat.emissive) mat.emissive.convertSRGBToLinear();
            mat.userData.__v3dLin = true;
          }
          if ('flatShading' in mat) mat.flatShading = true;
          if ('envMapIntensity' in mat) { mat.envMapIntensity = envI; mat.userData.__v3dEnvBase = envI; allMats.push(mat); }
          mat.needsUpdate = true;
          if (!st.legacy && isAluMaterial(mat)) {
            mat.userData.__v3dAluOrig = { m: mat.metalness, r: mat.roughness, e: mat.envMapIntensity, cr: mat.color.r, cg: mat.color.g, cb: mat.color.b };
            aluMats.push(mat);
          } else if (mat.color && !mat.transparent && !(mat.transmission > 0)) {
            if (!mat.userData.__v3dBase) mat.userData.__v3dBase = { r: mat.color.r, g: mat.color.g, b: mat.color.b };
            if (typeof mat.roughness === 'number' && mat.userData.__v3dRough0 === undefined) mat.userData.__v3dRough0 = mat.roughness;      // puvodni drsnost (lesk: setMatConfig gloss)
            colorMats.push(mat);
          }
        });
      });
      applyAlu();
      applyMatLook();
      applyMatCfg();
    }
    // ---- barvy a sytost materialu (st.matCfg): z PUVODNI barvy (userData.__v3dBase, linearni) -> nahrada podle sRGB hexu -> sytost v HSL (sRGB) -> zpet; hlinik ma vlastni volbu (applyAlu)
    function srgbHexOfBase(b) { var c = new THREE.Color(b.r, b.g, b.b); c.convertLinearToSRGB(); return '#' + c.getHexString(); }
    function applyMatCfg() {
      var cfg = st.matCfg, hsl = { h: 0, s: 0, l: 0 };
      colorMats.forEach(function (mat) {
        var b = mat.userData.__v3dBase;
        if (!b) return;
        var c = new THREE.Color(b.r, b.g, b.b);
        if (cfg) {
          var to = cfg.colors[srgbHexOfBase(b)];
          if (to) { c.setHex(parseInt(to.slice(1), 16)); c.convertSRGBToLinear(); }
          if (cfg.sat !== 1) {
            c.convertLinearToSRGB();
            c.getHSL(hsl);
            c.setHSL(hsl.h, Math.min(1, Math.max(0, hsl.s * cfg.sat)), hsl.l);
            c.convertSRGBToLinear();
          }
        }
        mat.color.copy(c);
        var aw = cfg ? cfg.ao[srgbHexOfBase(b)] : undefined;      // AO po komponentech: vaha materialu podle puvodni barvy
        mat.userData.__v3dAoW = aw === undefined ? 1 : aw;
        var r0 = mat.userData.__v3dRough0;                     // lesk: drsnost = puvodni^lesk (1 = beze zmeny, 0 = mat, 2 = dvojnasobny)
        if (typeof r0 === 'number') {
          var gl = cfg ? cfg.gloss[srgbHexOfBase(b)] : undefined;
          mat.roughness = gl === undefined ? r0 : Math.min(1, Math.max(0.02, Math.pow(Math.max(r0, 0.02), gl)));
        }
      });
      requestRender();
    }
    function matPalette() {
      var by = {}, order = [];
      colorMats.forEach(function (mat) {
        var b = mat.userData.__v3dBase;
        if (!b) return;
        var hex = srgbHexOfBase(b);
        if (!by[hex]) { by[hex] = { hex: hex, count: 0, to: (st.matCfg && st.matCfg.colors[hex]) || null, gloss: (st.matCfg && st.matCfg.gloss[hex] !== undefined) ? st.matCfg.gloss[hex] : 1, ao: (st.matCfg && st.matCfg.ao[hex] !== undefined) ? st.matCfg.ao[hex] : 1, rough: typeof mat.userData.__v3dRough0 === 'number' ? Math.round(mat.userData.__v3dRough0 * 100) / 100 : null }; order.push(hex); }
        by[hex].count++;
      });
      return order.map(function (h) { return by[h]; }).sort(function (a, b) { return b.count - a.count || (a.hex < b.hex ? -1 : 1); });
    }


    function collectGroups() {
      // nova vetev: extras {g:int} na uzlu (dedi se na potomky);
      // legacy: jmeno bomgrp_<idx>(_n)
      meshes.forEach(function (m) {
        for (var n = m; n && n !== model.parent; n = n.parent) {
          var g = n.userData ? n.userData.g : undefined;
          if (typeof g === 'number' && g >= 0 && Math.floor(g) === g) { setGroup(m, g); return; }
          var mm = BOMGRP_RE.exec(n.name || '');
          if (mm) { setGroup(m, parseInt(mm[1], 10)); return; }
        }
      });
      function setGroup(m, g) {
        groupOfMesh.set(m, g);
        if (!groupMeshes.has(g)) groupMeshes.set(g, []);
        groupMeshes.get(g).push(m);
      }
    }

    function collectPivots() {
      if (!spec) return;
      var byName = {};
      model.traverse(function (n) { var nm = pivotNameOf(n); if (nm && !byName[nm]) byName[nm] = n; });
      spec.motions.forEach(function (m) {
        var missing = m.steps.filter(function (s) { return !byName[s.p]; });
        if (missing.length) { st.warnings.push('v3d: pohyb ' + m.id + ' - chybi pivot ' + missing[0].p); return; }
        m.steps.forEach(function (s) {
          if (!pivots.has(s.p)) {
            var nd = byName[s.p];
            pivots.set(s.p, { node: nd, basePos: nd.position.clone(), baseQuat: nd.quaternion.clone() });
          }
          s.axV = new THREE.Vector3(s.ax[0], s.ax[1], s.ax[2]);
        });
        m.total = motionTotalMs(m);
        motions.push(m);
        motionById[m.id] = m;
        motionT[m.id] = 0;
        m.pick.forEach(function (p) { if (byName[p]) { pickExplicit[p] = true; if (!pickMap[p]) pickMap[p] = m.id; } });
      });
      // dily, na ktere se nikdo neodkazuje (prazdny pick) - klik na pivot kroku
      motions.forEach(function (m) { m.steps.forEach(function (s) { if (!pickMap[s.p]) pickMap[s.p] = m.id; }); });
      // Zavislosti z hierarchie pivotu: pohyb, jehoz pivot visi pod pivotem
      // jineho pohybu (box pod vysuvem), dava smysl jen pri otevrenem rodici -
      // zdvih boxu build pocita pro vytazeny vysuv, pri zavrenem by box
      // narazil do police nad nim (integracni test 2026-10-01: 80/80 boxu na
      // vysuvu). play() proto rodice otevre driv a pred zavrenim rodice
      // zavre jeho deti. setT() zustava nizkourovnove (bez zavislosti).
      var driver = {};
      motions.forEach(function (m) { m.deps = []; m.kids = []; m.steps.forEach(function (s) { (driver[s.p] = driver[s.p] || []).push(m.id); }); });
      motions.forEach(function (m) {
        m.steps.forEach(function (s) {
          for (var n = pivots.get(s.p).node.parent; n && n !== model.parent; n = n.parent) {
            var nm = pivotNameOf(n);
            (nm && driver[nm] || []).forEach(function (d) {
              if (d === m.id || m.deps.indexOf(d) >= 0) return;
              m.deps.push(d);
              motionById[d].kids.push(m.id);
            });
          }
        });
      });
    }

    // ---------------- strany a blokujici dvojice (jednou pri nacteni) ----------------
    function meshWorldBox(m) {
      if (!m.geometry.boundingBox) m.geometry.computeBoundingBox();
      return m.geometry.boundingBox.clone().applyMatrix4(m.matrixWorld);
    }
    function overlapTol(a, b, tol) {
      return a.min.x < b.max.x - tol && b.min.x < a.max.x - tol &&
             a.min.y < b.max.y - tol && b.min.y < a.max.y - tol &&
             a.min.z < b.max.z - tol && b.min.z < a.max.z - tol;
    }
    function isAncestorOf(a, n) { for (n = n && n.parent; n && n !== model.parent; n = n.parent) if (n === a) return true; return false; }
    function unionBoxes(list) { var b = new THREE.Box3(); list.forEach(function (x) { b.union(x); }); return b; }
    // Kazdy pohyb: hlavni pivot (posledni krok - u dvirek kridlo), meshe jeho
    // podstromu, Box3 meshu zavreno / otevreno (s otevrenymi rodici, deti
    // zavrene). Podstromy dvou nesouvisejicich pohybu jsou nezavisle, takze
    // dvojice staci porovnat z techto dvou snimku.
    //  - side: +1 = otevira se podel front, -1 = proti (druha strana ulicky),
    //    0 = neurceno. Primarne z T kroku (vodorovne slozky podel front),
    //    jinak (dvirka) z posunu teziste podstromu.
    //  - blocks: pohyby, se kterymi se otevreny srazi (novy presah Box3
    //    nektere dvojice meshu, ktery v zavrenem stavu neni).
    function computeBlocks() {
      st.twoSided = false;
      if (!motions.length) return;
      var meshSet = new Set(meshes);
      motions.forEach(function (m) {
        m.root = pivots.get(m.steps[m.steps.length - 1].p).node;
        m.sub = [];
        m.root.traverse(function (n) { if (n.isMesh && meshSet.has(n)) m.sub.push(n); });
        m.blocks = []; m.side = 0;
      });
      model.updateMatrixWorld(true);
      var closed = new Map();
      meshes.forEach(function (x) { closed.set(x, meshWorldBox(x)); });
      motions.forEach(function (m) {
        m.deps.forEach(function (d) { motionT[d] = 1; });
        motionT[m.id] = 1;
        applyPoses(); model.updateMatrixWorld(true);
        m.openBoxes = m.sub.map(meshWorldBox);
        m.openAll = unionBoxes(m.openBoxes);
        m.closedBoxes = m.sub.map(function (x) { return closed.get(x); });
        m.deps.forEach(function (d) { motionT[d] = 0; });
        motionT[m.id] = 0;
      });
      applyPoses(); model.updateMatrixWorld(true);

      var c0 = new THREE.Vector3(), c1 = new THREE.Vector3();
      motions.forEach(function (m) {
        var sumT = 0;
        m.steps.forEach(function (s) { if (s.op === 'T' && Math.abs(s.ax[1]) < 0.5) sumT += s.v * (s.ax[0] * front.x + s.ax[2] * front.z); });
        if (Math.abs(sumT) >= SIDE_MIN) { m.side = sumT > 0 ? 1 : -1; return; }
        if (!m.sub.length) return;
        unionBoxes(m.closedBoxes).getCenter(c0); m.openAll.getCenter(c1);
        var d = c1.sub(c0).dot(front);
        if (Math.abs(d) >= SIDE_MIN) m.side = d > 0 ? 1 : -1;
      });
      motions.forEach(function (m) {      // cisty zdvih (box na vysuvu): strana rodice
        if (!m.side) m.deps.some(function (d) { var s = motionById[d].side; if (s) { m.side = s; return true; } return false; });
      });
      st.twoSided = motions.some(function (m) { return m.side > 0; }) && motions.some(function (m) { return m.side < 0; });

      for (var i = 0; i < motions.length; i++) {
        for (var j = i + 1; j < motions.length; j++) {
          var a = motions[i], b = motions[j];
          if (a.root === b.root || isAncestorOf(a.root, b.root) || isAncestorOf(b.root, a.root)) continue;
          if (!a.sub.length || !b.sub.length || !overlapTol(a.openAll, b.openAll, BLOCK_TOL)) continue;
          var hit = false;
          for (var p = 0; p < a.sub.length && !hit; p++) {
            for (var q = 0; q < b.sub.length && !hit; q++) {
              if (overlapTol(a.openBoxes[p], b.openBoxes[q], BLOCK_TOL) && !overlapTol(a.closedBoxes[p], b.closedBoxes[q], BLOCK_TOL)) hit = true;
            }
          }
          if (hit) { a.blocks.push(b.id); b.blocks.push(a.id); }
        }
      }
    }

    // ---------------- material: JEDEN stav ----------------
    function wantMaterial(m) {
      if (highlightSet.size && groupOfMesh.has(m) && highlightSet.has(groupOfMesh.get(m))) return highlightMat;
      if (st.mode === 'wire') return Array.isArray(origMat.get(m)) ? origMat.get(m).map(function () { return occluderMat; }) : occluderMat;
      return origMat.get(m);
    }
    function sameMat(a, b) {
      if (a === b) return true;
      if (Array.isArray(a) && Array.isArray(b) && a.length === b.length) { for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) return false; return true; }
      return false;
    }
    function refreshMeshMaterial(m) {
      var want = wantMaterial(m);
      if (!sameMat(m.material, want)) { m.material = want; st.matWrites++; }
    }
    function edgeColorLinear(m) {
      var om = origMat.get(m);
      var mat0 = Array.isArray(om) ? om[0] : om;
      // barva hrany = to, co by dily ukazovaly (sRGB), prilis svetle -> tmava (jako dnes)
      var disp = new THREE.Color(WIRE_DARK);
      if (mat0 && mat0.color) {
        if (mat0.userData.__v3dSrgb != null) disp = new THREE.Color(mat0.userData.__v3dSrgb);
        else disp = mat0.color.clone().convertLinearToSRGB();
      }
      // legacy: presne dnesni prah (soucet > 2.2); nova vetev prisneji, aby
      // vypeceny hlinik Vandr (#BBBAB3, soucet 2.16) nemel svetle sede hrany
      if (disp.r + disp.g + disp.b > (st.legacy ? 2.2 : 1.8)) disp = new THREE.Color(WIRE_DARK);
      return disp.convertSRGBToLinear();
    }
    // nejblizsi pivot pohybu nad meshem nebo mesh sam (null = staticky dil)
    function edgeOwnerOf(m) {
      for (var n = m; n && n !== model.parent; n = n.parent) {
        var nm = pivotNameOf(n);
        if (nm && pivots.has(nm) && pivots.get(nm).node === n) return n;
      }
      return null;
    }
    // Hrany: JEDEN LineSegments na skupinu meshi se stejnym nejblizsim pivotem
    // (v jeho souradnicich, visi pod nim a jede s nim) + jeden pro vsechny
    // staticke dily (ve svete); barva v kazdem vrcholu. Drateny rezim mel
    // driv 2 draw cally na kazdy mesh (kontrola 2026-10-01: 4918 199 proti 102).
    function ensureEdges() {
      if (edgeGroups.length) return;
      model.updateMatrixWorld(true);
      var byOwner = new Map(), inv = new THREE.Matrix4(), mtx = new THREE.Matrix4();
      meshes.forEach(function (m) {
        var owner = edgeOwnerOf(m);
        var g = byOwner.get(owner);
        if (!g) { g = { owner: owner, parts: [], total: 0, meshes: [] }; byOwner.set(owner, g); }
        var eg = new THREE.EdgesGeometry(m.geometry, 1);
        // mesh -> vlastnik: mezi nimi neni zadny pivot, takze vztah je pevny
        // i kdyz je pohyb zrovna otevreny
        mtx.copy(m.matrixWorld);
        if (owner) mtx.premultiply(inv.copy(owner.matrixWorld).invert());
        eg.applyMatrix4(mtx);
        g.parts.push({ pos: eg.attributes.position.array, col: edgeColorLinear(m) });
        g.total += eg.attributes.position.count;
        eg.dispose();
        g.meshes.push(m);
      });
      byOwner.forEach(function (g) {
        if (!g.total) return;
        var pos = new Float32Array(g.total * 3), cols = new Float32Array(g.total * 3), o = 0;
        g.parts.forEach(function (pt) {
          pos.set(pt.pos, o);
          for (var i = 0; i < pt.pos.length; i += 3) { cols[o + i] = pt.col.r; cols[o + i + 1] = pt.col.g; cols[o + i + 2] = pt.col.b; }
          o += pt.pos.length;
        });
        var geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        geo.setAttribute('color', new THREE.BufferAttribute(cols, 3));
        var ls = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ vertexColors: true, toneMapped: false }));
        ls.userData.__v3dHelper = true;
        ls.renderOrder = 1;
        ls.raycast = function () {};
        (g.owner || scene).add(ls);
        edgeGroups.push({ obj: ls, owner: g.owner, meshes: g.meshes });
        g.meshes.forEach(function (m) { edgesOf.set(m, ls); });
      });
    }
    function applyMode(mode) {
      clearHover();
      st.mode = mode === 'wire' ? 'wire' : 'real';
      if (st.mode === 'real' && !st.allowReal) st.mode = 'wire';
      if (st.mode === 'wire') ensureEdges();
      meshes.forEach(refreshMeshMaterial);
      edgeGroups.forEach(function (g) { g.obj.visible = st.mode === 'wire'; });
      if (shadow) shadow.group.visible = st.mode === 'real' && shadow.ok;
      root.classList.toggle('v3d-mode-wire', st.mode === 'wire');
      root.classList.toggle('v3d-mode-real', st.mode === 'real');
      updateHud();
      requestRender();
    }
    function applyHighlight(set) {
      highlightSet = new Set();
      (set ? Array.from(set) : []).forEach(function (g) { var n = parseInt(g, 10); if (!isNaN(n)) highlightSet.add(n); });
      meshes.forEach(refreshMeshMaterial);
      requestRender();
    }

    // ---------------- kontaktni stin ----------------
    function buildShadow() {
      if (!hasBlur) return;
      var size = productBox.getSize(new THREE.Vector3());
      var W = size.x + 2 * SHADOW_PAD, D = size.z + 2 * SHADOW_PAD;
      var camH = clamp(size.y * 0.35, 120, 900);
      var g = new THREE.Group();
      g.userData.__v3dHelper = true;
      g.position.set(center.x, productBox.min.y - 0.5, center.z);
      var rt = new THREE.WebGLRenderTarget(512, 512); rt.texture.generateMipmaps = false;
      var rtBlur = new THREE.WebGLRenderTarget(512, 512); rtBlur.texture.generateMipmaps = false;
      var planeGeo = new THREE.PlaneGeometry(W, D).rotateX(Math.PI / 2);
      var plane = new THREE.Mesh(planeGeo, new THREE.MeshBasicMaterial({ map: rt.texture, opacity: SHADOW_OPACITY, transparent: true, depthWrite: false, toneMapped: false }));
      plane.renderOrder = -1;
      plane.scale.y = -1;           // textura je kreslena zespodu (vzor webgl_shadow_contact)
      plane.raycast = function () {};
      g.add(plane);
      var blurPlane = new THREE.Mesh(planeGeo);
      blurPlane.visible = false;
      g.add(blurPlane);
      var cam = new THREE.OrthographicCamera(-W / 2, W / 2, D / 2, -D / 2, 0, camH);
      cam.rotation.x = Math.PI / 2; // kouka nahoru
      g.add(cam);
      var depthMat = new THREE.MeshDepthMaterial();
      depthMat.side = THREE.DoubleSide;
      depthMat.onBeforeCompile = function (sh) {
        sh.fragmentShader = sh.fragmentShader.replace(
          'gl_FragColor = vec4( vec3( 1.0 - fragCoordZ ), opacity );',
          'gl_FragColor = vec4( vec3( 0.0 ), ( 1.0 - fragCoordZ ) * 1.15 );'
        );
      };
      function sm(S) { return new THREE.ShaderMaterial({ uniforms: THREE.UniformsUtils.clone(S.uniforms), vertexShader: S.vertexShader, fragmentShader: S.fragmentShader, depthTest: false }); }
      shadow = { group: g, rt: rt, rtBlur: rtBlur, plane: plane, blurPlane: blurPlane, cam: cam, depthMat: depthMat,
        hMat: sm(THREE.HorizontalBlurShader), vMat: sm(THREE.VerticalBlurShader), ok: false };
      g.visible = false;
      scene.add(g);
    }
    function renderShadow() {
      if (!shadow) return;
      var hidden = [];
      scene.traverse(function (n) {
        if (n.visible && (n.isLine || n.isLineSegments || n.isPoints || n.isSprite || n === shadow.plane)) { hidden.push(n); n.visible = false; }
      });
      var prevGroupVis = shadow.group.visible;
      shadow.group.visible = true;
      var prevClear = renderer.getClearColor(new THREE.Color()), prevAlpha = renderer.getClearAlpha();
      renderer.setClearColor(0x000000, 0);
      scene.overrideMaterial = shadow.depthMat;
      renderer.setRenderTarget(shadow.rt);
      renderer.clear();
      renderer.render(scene, shadow.cam);
      scene.overrideMaterial = null;
      blur(2.2); blur(0.9);
      renderer.setRenderTarget(null);
      renderer.setClearColor(prevClear, prevAlpha);
      hidden.forEach(function (n) { n.visible = true; });
      shadow.group.visible = prevGroupVis;
      shadow.ok = true;
      function blur(amount) {
        var bp = shadow.blurPlane;
        bp.visible = true;
        bp.material = shadow.hMat;
        shadow.hMat.uniforms.tDiffuse.value = shadow.rt.texture;
        shadow.hMat.uniforms.h.value = amount / 256;
        renderer.setRenderTarget(shadow.rtBlur);
        renderer.render(bp, shadow.cam);
        bp.material = shadow.vMat;
        shadow.vMat.uniforms.tDiffuse.value = shadow.rtBlur.texture;
        shadow.vMat.uniforms.v.value = amount / 256;
        renderer.setRenderTarget(shadow.rt);
        renderer.render(bp, shadow.cam);
        bp.visible = false;
      }
    }

    // ---------------- AO (viz AO_VARIANTS nahore) ----------------
    // Prubeh jednoho snimku: 1) beauty bez car (presne jako bez AO) 2) hloubka sceny do RT (bez car, kontaktniho stinu a pruhlednych dilu)
    // 3) GTAO 4) 2x bilateralni rozmazani 5) nasobeni obrazu (DST_COLOR, alfa beze zmeny = pruhledne pozadi zustane) 6) cary a kóty nad AO.
    // Kresli se jen v renderNow() (na vyzadani) - AO nevyvolava zadnou smycku rAF. Cile renderu se vytvori az pri zapnuti a uvolni pri 'vyp'.
    var _aoV2 = new THREE.Vector2(), _aoColor = new THREE.Color();
    function aoActive() { var v = aoVariantByKey(st.ao); return aoSupport && !aoBroken && st.ready && st.mode === 'real' && !!(v && v.p); }
    function aoEff() { var v = aoVariantByKey(st.ao), p = v && v.p; return p ? { k: p.k * (st.aoCfg ? st.aoCfg.k : 1), r: p.r * (st.aoCfg ? st.aoCfg.r : 1) } : null; }       // sila a dosah AO = varianta x posuvniky (jedno misto pro vykresleni i hook aoValues)
    function setVis(list, vis) { for (var i = 0; i < list.length; i++) list[i].visible = vis; }
    // pruhledne dily a kontaktni stin do hloubky nepatri (AO pocita s tim, co je skutecne videt jako povrch)
    function aoSkipMesh(n) {
      if (shadow && n === shadow.plane) return true;
      var ms = Array.isArray(n.material) ? n.material : [n.material];
      for (var i = 0; i < ms.length; i++) { var m = ms[i]; if (m && ((m.transparent && m.opacity < 0.98) || m.transmission > 0)) return true; }
      return false;
    }
    // rozliseni AO: nejvyse CSS rozliseni (jako pixelRatio 1, na retine se AO natahne bilinearne), na dotykovych displejich polovicni
    function aoSize() {
      var cs = renderer.getSize(_aoV2);
      var k = coarse ? 0.5 : 1;
      return { w: Math.max(8, Math.round(cs.x * k)), h: Math.max(8, Math.round(cs.y * k)), k: k };
    }
    function aoFreeRT() {
      if (!aoRes) return;
      aoRes.rtD.dispose(); aoRes.rtA.dispose(); aoRes.rtB.dispose();
      if (aoRes.rtW) aoRes.rtW.dispose();
      aoRes = null;
    }
    function aoEnsure() {
      var z = aoSize();
      if (!aoMats) {
        var geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3));
        geo.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 2, 0, 0, 2], 2));
        var quad = new THREE.Mesh(geo, null);
        quad.frustumCulled = false;
        var qscene = new THREE.Scene(); qscene.add(quad);
        var sm = function (frag, uniforms, defines, extra) {
          var o = { vertexShader: AO_VERT, fragmentShader: frag, uniforms: uniforms, defines: defines || {}, depthTest: false, depthWrite: false, toneMapped: false };
          if (extra) Object.keys(extra).forEach(function (k) { o[k] = extra[k]; });
          return new THREE.ShaderMaterial(o);
        };
        var depthU = function () { return { tDepth: { value: null }, uNear: { value: 1 }, uFar: { value: 1000 } }; };
        var aoU = depthU();
        aoU.uRes = { value: new THREE.Vector2(1, 1) }; aoU.uTan = { value: new THREE.Vector2(1, 1) }; aoU.uProjPx = { value: 1 };
        aoU.uRadius = { value: 8 }; aoU.uMinPx = { value: 4 }; aoU.uMaxPx = { value: 48 }; aoU.uFalloff = { value: AO_FALLOFF }; aoU.uBias = { value: AO_BIAS };
        var bU = function () { var u = depthU(); u.tAO = { value: null }; u.uDir = { value: new THREE.Vector2(1, 0) }; u.uSig = { value: AO_BLUR_SIG }; return u; };
        aoMats = {
          quad: quad, qscene: qscene, qcam: new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1), wmats: {},
          depth: new THREE.ShaderMaterial({ vertexShader: AO_DEPTH_VERT, fragmentShader: AO_DEPTH_FRAG, uniforms: { uFar: { value: 1000 } }, side: THREE.DoubleSide, blending: THREE.NoBlending, toneMapped: false }),
          ao: sm(AO_FRAG, aoU, { SLICES: coarse ? 2 : 3, STEPS: 3 }, { blending: THREE.NoBlending }),
          blurH: sm(AO_BLUR_FRAG, bU(), { BLUR_R: 3 }, { blending: THREE.NoBlending }),
          blurV: sm(AO_BLUR_FRAG, bU(), { BLUR_R: 3 }, { blending: THREE.NoBlending }),
          comp: sm(AO_COMP_FRAG, { tAO: { value: null }, tW: { value: null }, uUseW: { value: 0 }, uK: { value: 0.4 }, uGamma: { value: AO_GAMMA } }, null, {
            transparent: true, blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.DstColorFactor, blendDst: THREE.ZeroFactor,
            blendEquationAlpha: THREE.AddEquation, blendSrcAlpha: THREE.ZeroFactor, blendDstAlpha: THREE.OneFactor
          })
        };
      }
      if (!aoRes) {
        var rt = function (depth, linear) {
          var f = linear ? THREE.LinearFilter : THREE.NearestFilter;
          return new THREE.WebGLRenderTarget(z.w, z.h, { minFilter: f, magFilter: f, format: THREE.RGBAFormat, depthBuffer: !!depth, stencilBuffer: !!depth });   // depth+stencil = 24bit hloubka (jinak 16bit z-fighting)
        };
        aoRes = { w: z.w, h: z.h, k: z.k, rtD: rt(true, false), rtA: rt(false, true), rtB: rt(false, true) };
      } else if (aoRes.w !== z.w || aoRes.h !== z.h) {
        aoRes.rtD.setSize(z.w, z.h); aoRes.rtA.setSize(z.w, z.h); aoRes.rtB.setSize(z.w, z.h); if (aoRes.rtW) aoRes.rtW.setSize(z.w, z.h);
        aoRes.w = z.w; aoRes.h = z.h; aoRes.k = z.k;
      }
      return aoRes;
    }
    // AO po komponentech: vaha materialu meshe (matConfig.ao podle puvodni barvy / aluConfig.ao pro hlinik; userData.__v3dAoW nastavuje applyMatCfg / applyAlu), 1 = beze zmeny
    function aoWeightOf(n) {
      var m = Array.isArray(n.material) ? n.material[0] : n.material, w = m && m.userData && m.userData.__v3dAoW;
      return typeof w === 'number' ? w : 1;
    }
    function aoWeightMat(w) {
      var key = Math.round(w * 100), c = aoMats.wmats;
      if (!c[key]) c[key] = new THREE.ShaderMaterial({ vertexShader: AO_W_VERT, fragmentShader: AO_W_FRAG, uniforms: { uW: { value: key / 100 } }, side: THREE.DoubleSide, blending: THREE.NoBlending, toneMapped: false });
      return c[key];
    }
    // extra pruchod sceny (stejna viditelnost jako hloubka): kazdy mesh se vykresli barvou 0,5 * vaha do rtW; vraci true, kdyz se kreslilo (nejaky mesh ma vahu != 1)
    function aoWeightPass(res, meshesVis, skip) {
      var skipSet = new Set(skip), list = [], any = 0;
      for (var i = 0; i < meshesVis.length; i++) {
        var n = meshesVis[i];
        if (skipSet.has(n)) continue;
        var w = aoWeightOf(n);
        if (w !== 1) any++;
        list.push([n, w]);
      }
      aoStat.wMeshes = any;
      if (!any) return false;
      if (!res.rtW) res.rtW = new THREE.WebGLRenderTarget(res.w, res.h, { minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, format: THREE.RGBAFormat, depthBuffer: true, stencilBuffer: false });
      renderer.setRenderTarget(res.rtW);
      renderer.setClearColor(0x000000, 1);                  // pozadi = vaha 0 (AO tam stejne neni: hloubka = 1.0)
      renderer.clear(true, true, true);
      var orig = list.map(function (e) { return e[0].material; });
      try {
        for (var j = 0; j < list.length; j++) list[j][0].material = aoWeightMat(list[j][1]);
        renderer.render(scene, camera);
      } finally {
        for (var k = 0; k < list.length; k++) list[k][0].material = orig[k];
      }
      aoStat.wPasses++;
      return true;
    }
    function aoDraw(mat, target) {
      aoMats.quad.material = mat;
      renderer.setRenderTarget(target);
      renderer.render(aoMats.qscene, aoMats.qcam);
    }
    function aoCheck() {
      var ms = [aoMats.depth, aoMats.ao, aoMats.blurH, aoMats.comp];
      for (var i = 0; i < ms.length; i++) {
        var pr = renderer.properties.get(ms[i]).currentProgram;
        if (!pr || (pr.diagnostics && pr.diagnostics.runnable === false)) return false;
      }
      return true;
    }
    function aoFail(e) {
      aoBroken = true;
      st.warnings.push('AO se nepodařilo spustit: ' + ((e && e.message) || e));
      aoFreeRT();
      updateHud();
    }
    function aoFrame() {
      var res = aoEnsure(), p = aoVariantByKey(st.ao).p, D = aoDbg || {};
      var overlay = [], meshesVis = [], skip = [];
      scene.traverse(function (n) {
        if (!n.visible) return;
        if (n.isLine || n.isPoints || n.isSprite) overlay.push(n);
        else if (n.isMesh) { meshesVis.push(n); if (aoSkipMesh(n)) skip.push(n); }
      });
      var autoClear0 = renderer.autoClear, alpha0 = renderer.getClearAlpha();
      renderer.getClearColor(_aoColor);
      try {
        setVis(overlay, false);
        renderer.render(scene, camera);                       // 1) beauty bez car, stejne jako bez AO (vc. antialiasingu a pruhledneho pozadi)
        renderer.autoClear = false;
        setVis(skip, false);
        renderer.setRenderTarget(res.rtD);                    // 2) hloubka (RGBA balena; pozadi = bila = 1.0)
        renderer.setClearColor(0xffffff, 1);
        renderer.clear(true, true, true);
        aoMats.depth.uniforms.uFar.value = camera.far;
        scene.overrideMaterial = aoMats.depth;
        renderer.render(scene, camera);
        scene.overrideMaterial = null;
        var useW = aoWeightPass(res, meshesVis, skip);        // 2b) vahy AO po komponentech do rtW (jen kdyz ma nejaky material vahu != 1)
        setVis(skip, true);
        renderer.setClearColor(_aoColor, alpha0);
        var pm = camera.projectionMatrix.elements, unit = radius < 30 ? radius / 800 : 1;   // model v metrech (ne v mm): polomer se prepocte
        var U = aoMats.ao.uniforms, df = aoMats.ao.defines;
        if (D.slices && (df.SLICES !== D.slices || df.STEPS !== (D.steps || df.STEPS))) { df.SLICES = D.slices; df.STEPS = D.steps || df.STEPS; aoMats.ao.needsUpdate = true; }
        U.tDepth.value = res.rtD.texture; U.uNear.value = camera.near; U.uFar.value = camera.far;
        U.uRes.value.set(res.w, res.h); U.uTan.value.set(1 / pm[0], 1 / pm[5]); U.uProjPx.value = 0.5 * res.h * pm[5];
        U.uBias.value = D.bias != null ? D.bias : AO_BIAS;
        U.uRadius.value = (D.r != null ? D.r : aoEff().r) * (D.rmul != null ? D.rmul : AO_RMUL) * unit; U.uMinPx.value = (D.minPx != null ? D.minPx : AO_MIN_PX) * res.k;
        U.uMaxPx.value = (D.maxPx != null ? D.maxPx : AO_MAX_PX) * res.k; U.uFalloff.value = D.falloff != null ? D.falloff : AO_FALLOFF;
        aoDraw(aoMats.ao, res.rtA);                           // 3) GTAO -> rtA
        [[aoMats.blurH, res.rtA, res.rtB, 1, 0], [aoMats.blurV, res.rtB, res.rtA, 0, 1]].forEach(function (b) {   // 4) bilateralni rozmazani H, V
          var u = b[0].uniforms;
          u.tDepth.value = res.rtD.texture; u.uNear.value = camera.near; u.uFar.value = camera.far;
          u.tAO.value = b[1].texture; u.uDir.value.set(b[3] / res.w, b[4] / res.h); u.uSig.value = D.sig != null ? D.sig : AO_BLUR_SIG;
          aoDraw(b[0], b[2]);
        });
        var C = aoMats.comp.uniforms;                         // 5) nasobeni obrazu (DST_COLOR), alfa beze zmeny
        C.tW.value = useW ? res.rtW.texture : res.rtA.texture; C.uUseW.value = useW ? 1 : 0;
        C.tAO.value = res.rtA.texture; C.uK.value = (D.k != null ? D.k : aoEff().k) * (D.kcal != null ? D.kcal : AO_KCAL); C.uGamma.value = D.gamma != null ? D.gamma : AO_GAMMA;
        aoDraw(aoMats.comp, null);
        if (overlay.length) {                                 // 6) cary a kóty nad AO (AO je neztmavuje)
          setVis(meshesVis, false); setVis(overlay, true);
          renderer.render(scene, camera);
        }
        if (!aoVerified) {
          if (!aoCheck()) throw new Error('shader AO se nezkompiloval');
          aoVerified = true;
        }
      } finally {
        scene.overrideMaterial = null;
        setVis(overlay, true); setVis(meshesVis, true);
        renderer.setRenderTarget(null);
        renderer.setClearColor(_aoColor, alpha0);
        renderer.autoClear = autoClear0;
      }
    }

    // ---------------- koty ----------------
    function fmtMm(v) { return Math.round(v).toLocaleString('cs-CZ').replace(/\s/g, ' ') + ' mm'; }
    function makeDim(a, b, o, text, level, minor, m) {
      var A = a.clone(), B = b.clone(), O = o.clone();
      var A2 = A.clone().add(O), B2 = B.clone().add(O);
      var len = A2.distanceTo(B2);
      var dir = B2.clone().sub(A2);
      if (dir.lengthSq() < 1e-9) dir.set(1, 0, 0); dir.normalize();
      var on = O.lengthSq() > 1e-9 ? O.clone().normalize() : new THREE.Vector3(0, 1, 0);
      var ext = on.clone().multiplyScalar(Math.min(Math.max(len * 0.02, 6), 30));
      var tick = dir.clone().add(on).normalize().multiplyScalar(clamp(len * 0.03, 8, 40) * (minor ? 0.6 : 1));
      var pts = [];
      function seg(p, q) { pts.push(p.x, p.y, p.z, q.x, q.y, q.z); }
      if (O.lengthSq() > 1e-9) { seg(A, A2.clone().add(ext)); seg(B, B2.clone().add(ext)); }
      seg(A2, B2);
      seg(A2.clone().sub(tick), A2.clone().add(tick));
      seg(B2.clone().sub(tick), B2.clone().add(tick));
      var geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
      var g = new THREE.Group();
      g.userData.__v3dHelper = true;
      var line = new THREE.LineSegments(geo, minor ? dimLineMatMinor : dimLineMat);
      line.renderOrder = 998;
      line.raycast = function () {};
      g.add(line);
      var labels = [];
      if (labelRenderer) {
        var div = el('div', 'v3d-dim' + (minor ? ' v3d-dim--minor' : ''), text);
        var lab = new THREE.CSS2DObject(div);
        lab.position.copy(A2).lerp(B2, m == null ? 0.5 : m);          // popisek uprostred cary, nebo u jednoho konce (spec dims[].m: sloupec vysek od podlahy)
        g.add(lab);
        labels.push(lab);
      }
      var rec = { obj: g, labels: labels, level: level, text: text, staticPts: [A, B, A2, B2], a2: A2.clone(), b2: B2.clone(), fore: false };
      dimRecs.push(rec);
      return rec;
    }

    // L1 z obalu produktu v ramu cela: sirka podel right, hloubka podel
    // front, vyska podel up. Koty vytazene "ven a dolu", aby byly videt
    // zepredu i ve 3D pohledu (kamera vpravo zepredu).
    function boxDimsInFrontFrame(box) {
      var U = new THREE.Vector3(0, 1, 0), F = front.clone(), R = new THREE.Vector3().crossVectors(U, F).normalize();
      var c = [], mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
      for (var i = 0; i < 8; i++) {
        var p = new THREE.Vector3(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, i & 4 ? box.max.z : box.min.z);
        var q = [p.dot(R), p.dot(U), p.dot(F)];
        for (var k = 0; k < 3; k++) { mn[k] = Math.min(mn[k], q[k]); mx[k] = Math.max(mx[k], q[k]); }
      }
      function P(r, u, f) { return R.clone().multiplyScalar(r).addScaledVector(U, u).addScaledVector(F, f); }
      var size = [mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]];
      var OFF = Math.max(Math.max(size[0], size[1], size[2], 1) * 0.12, 100);
      var k7 = 0.7071;
      return [
        { a: P(mn[0], mn[1], mx[2]), b: P(mx[0], mn[1], mx[2]), o: F.clone().multiplyScalar(OFF * k7).addScaledVector(U, -OFF * k7), v: size[0] },
        { a: P(mx[0], mn[1], mn[2]), b: P(mx[0], mn[1], mx[2]), o: R.clone().multiplyScalar(OFF * k7).addScaledVector(U, -OFF * k7), v: size[2] },
        { a: P(mn[0], mn[1], mx[2]), b: P(mn[0], mx[1], mx[2]), o: R.clone().multiplyScalar(-OFF * k7).addScaledVector(F, OFF * k7), v: size[1] }
      ];
    }

    function buildDims() {
      dimRoot = new THREE.Group();
      dimRoot.userData.__v3dHelper = true;
      scene.add(dimRoot);
      if (spec) {
        var hasL1 = spec.dims.some(function (d) { return d.l === 1; });
        if (!hasL1) boxDimsInFrontFrame(productBox).forEach(function (d) { dimRoot.add(makeDim(d.a, d.b, d.o, fmtMm(d.v), 1, false).obj); });
        spec.dims.forEach(function (d) {
          var text = /mm$/.test(d.t) ? d.t : d.t + ' mm';
          var rec = makeDim(new THREE.Vector3().fromArray(d.a), new THREE.Vector3().fromArray(d.b), new THREE.Vector3().fromArray(d.o), text, d.l, d.l === 2, d.m);
          var pv = d.p ? pivots.get(d.p) : null;
          if (pv) { model.updateMatrixWorld(true); pv.node.attach(rec.obj); rec.staticPts = null; }
          else dimRoot.add(rec.obj);
        });
      } else {
        legacyOverall(productBox).forEach(function (d) { dimRoot.add(makeDim(d.a, d.b, d.o, fmtMm(d.v), 1, false).obj); });
        legacyProfiles().forEach(function (d) { dimRoot.add(makeDim(d.a, d.b, d.o, fmtMm(d.v), 2, true).obj); });
      }
      var b = new THREE.Box3();
      dimRecs.forEach(function (r) { if (r.level === 1 && r.staticPts) r.staticPts.forEach(function (p) { b.expandByPoint(p); }); });
      dimsBox = b.isEmpty() ? null : b;
    }

    // dnesni buildOverallDimensions (nabidka-online.html:2012) - stejne body a odsazeni
    function legacyOverall(box) {
      var min = box.min, max = box.max, size = box.getSize(new THREE.Vector3());
      var OFF = Math.max(Math.max(size.x, size.y, size.z, 1) * 0.12, 100);
      var V = function (x, y, z) { return new THREE.Vector3(x, y, z); };
      return [
        { a: V(min.x, min.y, min.z), b: V(max.x, min.y, min.z), o: V(0, -OFF, -OFF), v: size.x },
        { a: V(min.x, min.y, min.z), b: V(min.x, min.y, max.z), o: V(-OFF, -OFF, 0), v: size.z },
        { a: V(min.x, min.y, min.z), b: V(min.x, max.y, min.z), o: V(-OFF, 0, -OFF), v: size.y }
      ];
    }
    // dnesni buildProfileDimensions (nabidka-online.html:2092) - jeden zastupce na skupinu
    function legacyProfiles() {
      var out = [], keys = ['x', 'y', 'z'];
      groupMeshes.forEach(function (ms) {
        var mesh = ms && ms[0];
        if (!mesh) return;
        var box = new THREE.Box3().setFromObject(mesh);
        var size = box.getSize(new THREE.Vector3());
        var dims = [size.x, size.y, size.z];
        var dom = dims.indexOf(Math.max(dims[0], dims[1], dims[2]));
        var others = [0, 1, 2].filter(function (i) { return i !== dom; });
        var second = Math.max(dims[others[0]], dims[others[1]]);
        if (dims[dom] < 40 || dims[dom] < 2.2 * Math.max(second, 1)) return;
        var c = box.getCenter(new THREE.Vector3()), half = dims[dom] / 2;
        var p1 = c.clone(); p1[keys[dom]] -= half;
        var p2 = c.clone(); p2[keys[dom]] += half;
        var offIdx = dims[others[0]] <= dims[others[1]] ? others[0] : others[1];
        var off = Math.max(dims[offIdx] / 2 + 10, 100);
        var o = new THREE.Vector3(); o[keys[offIdx]] = off;
        out.push({ a: p1, b: p2, o: o, v: dims[dom] });
      });
      return out;
    }
    // Koty se stavi az pri prvnim zapnuti (dims:0 + hudKoty:false = nikdy: zadna geometrie,
    // zadne DOM popisky, nic se nepocita). Stavi se v zavrenem stavu pohybu (kota na pivotu
    // se pripoji k pivotu a nese ho s sebou).
    function ensureDims() {
      if (dimsBuilt || !model) return;
      var saved = null;
      if (motions.some(function (m) { return motionT[m.id] > 0; })) {
        saved = {};
        Object.keys(motionT).forEach(function (k) { saved[k] = motionT[k]; motionT[k] = 0; });
        applyPoses(); model.updateMatrixWorld(true);
      }
      buildDims();
      dimsBuilt = true;
      if (saved) { Object.keys(saved).forEach(function (k) { motionT[k] = saved[k]; }); applyPoses(); model.updateMatrixWorld(true); }
    }
    function applyDims() {
      if (st.dims > 0) ensureDims();
      dimRecs.forEach(function (r) {
        var vis = st.dims > 0 && r.level <= st.dims;
        r.obj.visible = vis;
        r.fore = false;
        r.obj.children.forEach(function (c) { c.visible = vis; });   // vc. popisku (CSS2D nehlida viditelnost rodice)
      });
      updateHud();
      requestRender();
    }
    function dimsVisibleCount() { var n = 0; dimRecs.forEach(function (r) { if (r.obj.visible) n++; }); return n; }

    // ---------------- vyber komponentu: jeho vlastni rozmery (Robert 2026-10-06) ----------------
    // Klik na dil / cip pohybu vybere komponent (cip dostane is-sel) a ukaze jeho 3 rozmery (sirka, vyska, hloubka v ramu cela) bez ohledu na uroven Koty (i "Vyp");
    // koty se pocitaji z obalky dilu v ZAVRENEM stavu a nesou se s pivotem (vyjedou se suplikem). Zrusi se kliknutim mimo model, Vychozim pohledem nebo vyberem jineho dilu.
    var selId = null, selRecs = null;
    function clearSelDims() {
      if (!selRecs) return;
      selRecs.forEach(function (r) {
        if (r.obj.parent) r.obj.parent.remove(r.obj);
        r.obj.traverse(function (n) {
          if (n.isCSS2DObject && n.element && n.element.parentNode) n.element.parentNode.removeChild(n.element);
          if (n.geometry) n.geometry.dispose();
        });
        var i = dimRecs.indexOf(r); if (i >= 0) dimRecs.splice(i, 1);
      });
      selRecs = null;
    }
    function buildSelDims(m) {
      var saved = {}, any = false;
      Object.keys(motionT).forEach(function (k) { saved[k] = motionT[k]; if (motionT[k] > 0) any = true; });
      if (any) { Object.keys(saved).forEach(function (k) { motionT[k] = 0; }); applyPoses(); }
      model.updateMatrixWorld(true);
      var box = new THREE.Box3(), first = null;
      m.steps.forEach(function (s) {
        var pv = pivots.get(s.p);
        if (!pv) return;
        if (!first) first = pv;
        box.union(meshBox(pv.node));
      });
      var recs = [];
      if (first && !box.isEmpty()) {
        boxDimsInFrontFrame(box).forEach(function (d) {
          var rec = makeDim(d.a, d.b, d.o, fmtMm(d.v), 1, false);
          dimRecs.splice(dimRecs.indexOf(rec), 1);            // vyber se neridi urovni Koty (Vyp / Rozmery / Detail) ani se nepocita do dimsCount
          rec.sel = true; rec.staticPts = null;
          rec.obj.visible = true;
          rec.obj.children.forEach(function (c) { c.visible = true; });
          rec.labels.forEach(function (l) { l.element.classList.add('v3d-dim--sel'); });
          first.node.attach(rec.obj);                         // vyjede s dilem (pivot je ted v zavrenem stavu)
          recs.push(rec);
        });
      }
      if (any) { Object.keys(saved).forEach(function (k) { motionT[k] = saved[k]; }); applyPoses(); model.updateMatrixWorld(true); }
      return recs.length ? recs : null;
    }
    function selectMotion(id) {
      id = (id && motionById[id]) ? id : null;
      if (id === selId && (id === null || selRecs)) return;
      clearSelDims();
      selId = id;
      if (id && st.ready && model && opts.selDims === true) selRecs = buildSelDims(motionById[id]);          // rozmery vybraneho dilu jen kdyz o ne stranka rekne (nabidky, kontrolni scena)
      updateChips();
      requestRender();
    }

    // ---------------- pohledy ----------------
    function rotAboutUp(v, deg) {
      var c = Math.cos(deg * DEG), s = Math.sin(deg * DEG);
      return new THREE.Vector3(v.x * c + v.z * s, v.y, -v.x * s + v.z * c);
    }
    function viewDir(k) {
      if (k === 'front') return front.clone();
      if (k === 'side') return rotAboutUp(front, 90);
      // Shora: up kamery zustava (0,1,0), smer je o 1e-4 nakloneny k celu ->
      // lookAt da stejny obraz jako camera.up = -front (celo dole, vzadu
      // nahore) a OrbitControls (r128 si orbit osu cachuje z camera.up pri
      // vytvoreni) neprepina na zvrhly stav.
      if (k === 'top') return new THREE.Vector3(0, 1, 0).addScaledVector(front, 1e-4).normalize();
      var d = rotAboutUp(front, isoAz).multiplyScalar(Math.cos(isoEl * DEG));
      d.y = Math.sin(isoEl * DEG);
      return d.normalize();
    }
    // Presny zaber: rohy obalu promitnute do baze kamery (stejna baze jako
    // Matrix4.lookAt), vzdalenost tak, aby se vesel s rezervou FIT_PAD.
    function fitDistance(dir, pad) {
      var box = productBox.clone();
      if (dimsBox && st.dims > 0) box.union(dimsBox);
      var z = dir.clone().normalize();
      var x = new THREE.Vector3().crossVectors(camera.up, z);
      if (x.lengthSq() < 1e-20) x.set(1, 0, 0);
      x.normalize();
      var y = new THREE.Vector3().crossVectors(z, x);
      var tanY = Math.tan(camera.fov * DEG / 2), tanX = tanY * camera.aspect, d = 0;
      for (var i = 0; i < 8; i++) {
        var p = new THREE.Vector3(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, i & 4 ? box.max.z : box.min.z).sub(center);
        var px = Math.abs(p.dot(x)), py = Math.abs(p.dot(y)), pz = p.dot(z);
        d = Math.max(d, pz + px * pad / tanX, pz + py * pad / tanY);
      }
      return Math.max(d, radius * 0.5);
    }
    function settleDamping() {
      // zbytkovou setrvacnost OrbitControls aplikovat hned (jinak by po
      // preletu kamera jeste "doklouzala")
      var d = controls.enableDamping;
      controls.enableDamping = false; controls.update(); controls.enableDamping = d;
    }
    function flyTo(pos, target, ms) {
      settleDamping();
      if (reduced || !ms) {
        flight = null;
        camera.position.copy(pos); controls.target.copy(target); camera.lookAt(target);
        controls.enabled = true; controls.update();
        requestRender();
        return;
      }
      var p0 = camera.position.clone(), t0 = controls.target.clone();
      var d0 = p0.clone().sub(t0), d1 = pos.clone().sub(target);
      var dist0 = Math.max(d0.length(), 1e-3), dist1 = Math.max(d1.length(), 1e-3);
      var u0 = d0.normalize(), u1 = d1.normalize();
      flight = { t0: t0, t1: target.clone(), dist0: dist0, dist1: dist1, u0: u0, q: new THREE.Quaternion().setFromUnitVectors(u0, u1), start: now(), dur: ms };
      controls.enabled = false;
      kick();
    }
    function stepFlight(t) {
      var f = flight, s = clamp01((t - f.start) / f.dur), e = easeInOutCubic(s);
      var tgt = f.t0.clone().lerp(f.t1, e);
      var dir = f.u0.clone().applyQuaternion(new THREE.Quaternion().slerp(f.q, e));
      camera.position.copy(tgt).addScaledVector(dir, f.dist0 + (f.dist1 - f.dist0) * e);
      camera.lookAt(tgt);
      controls.target.copy(tgt);
      if (s >= 1) { flight = null; controls.enabled = true; controls.update(); }
      dirty = true;
    }
    function applyView(k, instant) {
      if (VIEWS.indexOf(k) < 0) k = 'iso';
      var dir = viewDir(k);
      var dist = fitDistance(dir, FIT_PAD);
      dist = clamp(dist, controls.minDistance || 0, controls.maxDistance || Infinity);
      st.view = k;
      flyTo(center.clone().addScaledVector(dir, dist), center.clone(), instant ? 0 : FLIGHT_MS);
      updateHud();
    }
    function zoom(sign) {
      var tgt = controls.target.clone();
      var off = camera.position.clone().sub(tgt);
      var dist = clamp(off.length() * (sign > 0 ? 0.8 : 1.25), controls.minDistance, controls.maxDistance);
      if (st.view) { st.view = null; updateHud(); }  // uz to neni cisty pohled (resize ho nesmi vratit)
      flyTo(tgt.clone().addScaledVector(off.normalize(), dist), tgt, ZOOM_MS);
    }

    // ---------------- animace ----------------
    function applyPoses() {
      pivots.forEach(function (pv) { pv.node.position.copy(pv.basePos); pv.node.quaternion.copy(pv.baseQuat); });
      var q = new THREE.Quaternion();
      motions.forEach(function (m) {
        var t = motionT[m.id];
        if (!(t > 0)) return;
        motionPose(m, t).forEach(function (c, i) {
          if (!(c.e > 0)) return;
          var pv = pivots.get(c.p), s = m.steps[i];
          if (!pv) return;
          if (c.op === 'T') pv.node.position.addScaledVector(s.axV, c.amount);
          else { q.setFromAxisAngle(s.axV, c.amount * DEG); pv.node.quaternion.premultiply(q); } // osa v souradnicich rodice
        });
      });
    }
    function stepTweens(t) {
      var ids = Object.keys(tweens);
      if (!ids.length) return false;
      var changed = false;
      ids.forEach(function (id) {
        var tw = tweens[id];
        if (t < tw.start) return;
        var s = clamp01((t - tw.start) / tw.dur);
        motionT[id] = tw.from + (tw.to - tw.from) * s;
        changed = true;
        if (s >= 1) { motionT[id] = tw.to; delete tweens[id]; }
      });
      if (changed) { applyPoses(); dirty = true; }
      updateChips();
      return true;
    }
    function targetOf(id) { return tweens[id] ? tweens[id].to : motionT[id]; }
    function setT(id, t) {
      if (!motionById[id]) return false;
      delete tweens[id];
      motionT[id] = clamp01(+t || 0);
      applyPoses(); updateChips(); requestRender();
      return true;
    }
    function finishAt(id) { var tw = tweens[id]; return tw ? tw.start + tw.dur : 0; }
    function play(id, dir, delay, silent, chain) {
      var m = motionById[id];
      if (!m) return false;
      chain = chain || {};
      if (chain[id]) return false;           // pojistka proti cyklu zavislosti
      chain[id] = true;
      var cur = motionT[id] || 0;
      var to = dir > 0 ? 1 : (dir < 0 ? 0 : (targetOf(id) >= 0.5 ? 0 : 1));
      if (!silent) track('v3d_anim', { id: id, k: m.k, dir: to ? 'open' : 'close' });
      if (!st.interacted) { st.interacted = true; hideHint(); }
      // otevrit = nejdriv zavrit, co blokuje misto (vysuv nad zvednutym
      // boxem, sklopena dvirka, box z druhe strany ulicky), a otevrit rodice
      // (vysuv pod boxem); zavrit = nejdriv deti
      var start = now() + (delay || 0);
      if (to === 1) {
        (m.blocks || []).forEach(function (b) {
          if (targetOf(b) > 0 || motionT[b] > 0) play(b, -1, delay, true, chain);
          start = Math.max(start, finishAt(b));
        });
      }
      (to === 1 ? m.deps : m.kids).forEach(function (d) {
        if (targetOf(d) !== to) play(d, to === 1 ? 1 : -1, delay, true, chain);
        start = Math.max(start, finishAt(d));
      });
      var dur = m.total * Math.abs(to - cur);
      if (reduced || dur < 1) {
        if (!reduced && start > now() + 0.5) { tweens[id] = { from: cur, to: to, start: start, dur: Math.max(dur, 1) }; kick(); }
        else setT(id, to);
        updateChips();
        return true;
      }
      tweens[id] = { from: cur, to: to, start: start, dur: dur };
      updateChips();
      kick();
      return true;
    }
    // Strana privracena ke kamere (oboustranna sestava): +1 = kamera na strane
    // front, -1 = na opacne; skoro kolmo (+-10 st.) nebo shora = front.
    function cameraSide() {
      var d = flight ? flight.u0.clone().applyQuaternion(flight.q) : camera.position.clone().sub(controls.target);
      var l = Math.hypot(d.x, d.z);
      if (l < 1e-6) return 1;
      return (d.x * front.x + d.z * front.z) / l >= -CAM_SIDE_EPS ? 1 : -1;
    }
    // Co otevira "Otevrit vse": supliky, vysuvy, dvirka (boxy jen jednotlive -
    // zvednute boxy by narazely do vysuvu/dvirek nad sebou); u oboustranne
    // sestavy jen strana ke kamere; pojistka: nic, co by narazilo do uz
    // vybraneho pohybu.
    function openAllSet(gk) {
      var side = (st.twoSided && !gk) ? cameraSide() : 0, chosen = [];       // tlacitko radku strany (gk) otevira VZDY celou tu stranu, bez ohledu na kameru
      motions.forEach(function (m) {
        if (m.k === 'box') return;
        if (gk && m.g !== gk) return;
        if (side && m.side && m.side !== side) return;
        if (chosen.some(function (c) { return (m.blocks || []).indexOf(c.id) >= 0; })) return;
        chosen.push(m);
      });
      return chosen;
    }
    function playAll(dir, gk) {
      if (!motions.length) return false;
      var set = openAllSet(gk);
      var to = dir > 0 ? 1 : (dir < 0 ? 0 : (set.some(function (m) { return targetOf(m.id) < 0.5; }) ? 1 : 0));
      if (to === 1 && !set.length) return false;
      track('v3d_anim', { id: 'all', dir: to ? 'open' : 'close' });
      var i = 0;
      // zavrit = vsechno (i boxy a druhou stranu)
      (to ? set : motions.filter(function (m) { return !gk || m.g === gk; })).forEach(function (m) {
        // uz miri k cili (i jako zavislost drivejsiho pohybu) - znovu
        // nespoustet, jinak by se posunul jeho start a dite by vyjelo driv
        if (targetOf(m.id) === to) return;
        play(m.id, to ? 1 : -1, reduced ? 0 : (i++) * STAGGER_MS, true);
      });
      return true;
    }

    // ---------------- fullscreen ----------------
    var fsPlaceholder = null;
    function fsEl() { return document.fullscreenElement || document.webkitFullscreenElement || null; }
    function cssFs(onFlag) {
      if (onFlag && !st.fsCss) {
        fsPlaceholder = document.createComment('v3d');
        root.parentNode.insertBefore(fsPlaceholder, root);
        document.body.appendChild(root);       // fixed uvnitr transformovaneho .slide by nebyl pres celou obrazovku
        root.classList.add('v3d-fs-css');
        st.fsCss = true;
      } else if (!onFlag && st.fsCss) {
        root.classList.remove('v3d-fs-css');
        if (fsPlaceholder && fsPlaceholder.parentNode) { fsPlaceholder.parentNode.insertBefore(root, fsPlaceholder); fsPlaceholder.parentNode.removeChild(fsPlaceholder); }
        else container.appendChild(root);
        fsPlaceholder = null;
        st.fsCss = false;
      }
      syncFs();
    }
    function syncFs() {
      st.fs = st.fsCss || fsEl() === root;
      root.classList.toggle('v3d-is-fs', st.fs);
      updateHud();
      resize();
    }
    function setFullscreen(want) {
      if (want == null) want = !st.fs;
      if (want === st.fs) return;
      if (want) {
        track('v3d_view', { k: 'fullscreen' });
        var req = root.requestFullscreen || root.webkitRequestFullscreen;
        var enabled = document.fullscreenEnabled || document.webkitFullscreenEnabled;
        if (req && enabled) {
          try {
            var p = req.call(root);
            if (p && p.catch) p.catch(function () { cssFs(true); });
          } catch (e) { cssFs(true); }
        } else cssFs(true);
      } else {
        if (st.fsCss) cssFs(false);
        else if (fsEl() === root) { var ex = document.exitFullscreen || document.webkitExitFullscreen; if (ex) { try { var r = ex.call(document); if (r && r.catch) r.catch(function () {}); } catch (e) { /* */ } } }
      }
    }
    on(document, 'fullscreenchange', syncFs);
    on(document, 'webkitfullscreenchange', syncFs);
    on(document, 'keydown', function (e) { if (e.key === 'Escape' && st.fsCss) cssFs(false); });

    // ---------------- HUD ----------------
    function buildHud() {
      var h = { el: el('div', 'v3d-hud') };
      // vlevo nahore: Koty + Vzhled
      var tl = el('div', 'v3d-tl');
      h.dims = seg(L.dims_cap, 'dims', [['0', L.dims_off], ['1', L.dims_1], ['2', L.dims_2]], true);
      h.mode = seg(L.mode_cap, 'mode', [['real', L.mode_real], ['wire', L.mode_wire]], true);
      if (hudKoty) tl.appendChild(h.dims.el);     // hudKoty:false = verejna stranka bez prepinace kot
      tl.appendChild(h.mode.el);
      if (ladeni) {
        h.alu = seg(L.alu_cap, 'alu', ALU_VARIANTS.map(function (v) { return [v.key, v.label]; }), true);
        h.alu.el.classList.add('v3d-seg--ladeni');
        tl.appendChild(h.alu.el);
        root.classList.add('v3d-ladeni');
      }
      // vpravo nahore: pohledy + reset
      var tr = el('div', 'v3d-tr');
      h.view = seg(null, 'view', VIEWS.map(function (k) { return [k, L['view_' + k]]; }), false);
      h.view.el.classList.add('v3d-seg--views');
      h.reset = btn('v3d-ico', null, { 'data-act': 'reset', 'aria-label': L.reset, title: L.reset });
      h.reset.innerHTML = ICON.reset;
      tr.appendChild(h.view.el); tr.appendChild(h.reset);
      // vpravo dole: zoom + fullscreen
      var br = el('div', 'v3d-br');
      h.zin = btn('v3d-ico', null, { 'data-act': 'zin', 'aria-label': L.zoom_in, title: L.zoom_in }); h.zin.innerHTML = ICON.plus;
      h.zout = btn('v3d-ico', null, { 'data-act': 'zout', 'aria-label': L.zoom_out, title: L.zoom_out }); h.zout.innerHTML = ICON.minus;
      h.fs = btn('v3d-ico', null, { 'data-act': 'fs', 'aria-label': L.fullscreen, title: L.fullscreen }); h.fs.innerHTML = ICON.fs;
      br.appendChild(h.zin); br.appendChild(h.zout); br.appendChild(h.fs);
      // dole: napoveda + cipy pohybu
      var bottom = el('div', 'v3d-bottom');
      h.hint = el('div', 'v3d-hint');
      h.chips = el('div', 'v3d-chips');
      h.chips.setAttribute('role', 'toolbar');
      h.chips.setAttribute('aria-label', L.chips_aria);
      bottom.appendChild(h.hint); bottom.appendChild(h.chips);
      h.msg = el('div', 'v3d-msg', L.loading);
      h.msg.setAttribute('aria-live', 'polite');
      [tl, tr, br, bottom, h.msg].forEach(function (x) { h.el.appendChild(x); });
      if (ladeni) {       // radek AO (kontrolni scena) - posledni v levem sloupci
        h.ao = seg('AO', 'ao', AO_VARIANTS.map(function (v) { return [v.key, v.label]; }), true);
        h.ao.el.classList.add('v3d-seg--ladeni');
        tl.appendChild(h.ao.el);
      }

      on(h.el, 'click', function (e) {
        var b = e.target.closest ? e.target.closest('button') : null;
        if (!b || !h.el.contains(b) || !st.ready) return;
        var act = b.getAttribute('data-act');
        if (act === 'reset') { selectMotion(null); applyView('iso'); track('v3d_view', { k: 'reset' }); return; }
        if (act === 'zin') { zoom(1); return; }
        if (act === 'zout') { zoom(-1); return; }
        if (act === 'fs') { setFullscreen(); return; }
        if (act === 'openall') { playAll(1, b.getAttribute('data-g') || null); return; }
        if (act === 'closeall') { playAll(-1, b.getAttribute('data-g') || null); return; }
        var mid = b.getAttribute('data-motion');
        if (mid) { selectMotion(mid); play(mid, 0); return; }
        var grp = b.getAttribute('data-grp'), val = b.getAttribute('data-v');
        if (!grp) return;
        var segObj = h[grp];
        // uzky displej: segment Koty/Vzhled ukazuje jen aktivni volbu, klik prepne na dalsi
        if (segObj.cycle && root.classList.contains('v3d-narrow')) val = segObj.next();
        if (grp === 'view') { applyView(val); track('v3d_view', { k: val }); }
        else if (grp === 'dims') { st.dims = parseInt(val, 10) || 0; st.dimsPref = st.dims; applyDims(); track('v3d_dims', { l: st.dims }); }
        else if (grp === 'mode') { if (val === 'real' && !st.allowReal) return; applyMode(val); st.modePref = st.mode; track('v3d_mode', { m: st.mode }); }
        else if (grp === 'ao') { api.setAO(val); }
        else if (grp === 'alu') { api.setAluminium(val); }
      });
      return h;

      function seg(cap, grp, items, cycle) {
        var s = { el: el('div', 'v3d-seg' + (cycle ? ' v3d-seg--cycle' : '')), btns: {}, cycle: cycle, cur: null };
        s.el.setAttribute('role', 'group');
        if (cap) { s.el.setAttribute('aria-label', cap); s.el.appendChild(el('span', 'v3d-seg__cap', cap)); }
        items.forEach(function (it) {
          var b = btn(null, it[1], { 'data-grp': grp, 'data-v': it[0], 'aria-pressed': 'false' });
          s.btns[it[0]] = b;
          s.el.appendChild(b);
        });
        s.set = function (v) {
          s.cur = v == null ? null : String(v);
          Object.keys(s.btns).forEach(function (k) {
            var onFlag = k === s.cur;
            s.btns[k].classList.toggle('is-on', onFlag);
            s.btns[k].setAttribute('aria-pressed', onFlag ? 'true' : 'false');
          });
        };
        s.next = function () {
          var keys = Object.keys(s.btns).filter(function (k) { return !s.btns[k].hidden; });
          var i = keys.indexOf(s.cur);
          return keys[(i + 1) % keys.length];
        };
        return s;
      }
    }
    function updateHud() {
      if (!hud) return;
      hud.view.set(st.view);
      hud.dims.set(st.dims);
      hud.mode.set(st.mode);
      if (hud.ao) { hud.ao.set(aoSupport ? st.ao : 'vyp'); hud.ao.el.hidden = !aoSupport || aoBroken; }   // bez podpory (highp) se volba AO nenabizi
      if (hud.alu) hud.alu.set(st.alu);
      // koty nemusi byt postavene (dims:0): Detail nabidnout, kdyz je (spec) / muze byt (legacy: profily)
      hud.dims.btns['2'].hidden = dimsBuilt ? !dimRecs.some(function (d) { return d.level === 2; }) : (spec ? !spec.dims.some(function (d) { return d.l === 2; }) : false);
      hud.dims.el.hidden = !hudKoty || (st.ready && dimsBuilt && !dimRecs.length);
      hud.mode.el.hidden = st.ready && !st.allowReal;     // legacy 103: jen Drateny, prepinac nenabizet
      hud.fs.innerHTML = st.fs ? ICON.fsExit : ICON.fs;
      hud.fs.setAttribute('aria-label', st.fs ? L.fullscreen_exit : L.fullscreen);
      hud.fs.title = hud.fs.getAttribute('aria-label');
    }
    function chipGroupsOf(list) {      // skupiny podle druhu (k, u boxu i sub) v poradi prvniho vyskytu; uvnitr poradi ze spec
      var groups = [], byKey = {};
      list.forEach(function (m) {
        var key = m.k + '|' + (m.subk || '');
        if (!byKey[key]) { byKey[key] = { name: kindName(m, L), list: [] }; groups.push(byKey[key]); }
        byKey[key].list.push(m);
      });
      return groups;
    }
    function appendChipGroups(parent, list) {
      chipGroupsOf(list).forEach(function (g) {
        var ge = el('div', 'v3d-chipgrp');
        ge.setAttribute('role', 'group');
        ge.setAttribute('aria-label', g.name);
        g.list.forEach(function (m) {
          var t = motionLabel(m, L);
          ge.appendChild(btn('v3d-chip', t, { 'data-motion': m.id, 'aria-pressed': 'false', title: t, 'aria-label': t }));
        });
        parent.appendChild(ge);
      });
    }
    function chipAllButtons(list, gk) {  // "Otevrit/Zavrit vse"; u radku strany jen pro tu stranu (data-g)
      var all = el('div', 'v3d-chipall');
      if (list.some(function (m) { return m.k !== 'box'; })) {
        var a1 = { 'data-act': 'openall', title: (st.twoSided && !gk) ? L.open_all_title_two_sided : L.open_all_title };
        if (gk) a1['data-g'] = gk;
        all.appendChild(btn('v3d-chip v3d-chip--all', L.open_all, a1));
      }
      var a2 = { 'data-act': 'closeall' };
      if (gk) a2['data-g'] = gk;
      all.appendChild(btn('v3d-chip v3d-chip--all', L.close_all, a2));
      return all;
    }
    function syncChipsH() {              // vyska panelu cipu (vic radku) -> zoom tlacitka vpravo nad nim
      if (!hud || !hud.chips) return;
      if (!hud.chips.classList.contains('v3d-chips--rows')) { root.style.removeProperty('--v3d-chips-h'); return; }      // jedna rada = dosavadni vychozi 52 px
      var h = hud.chips.offsetHeight;
      root.style.setProperty('--v3d-chips-h', h > 0 ? (h + 8) + 'px' : '52px');
    }
    function buildChips() {
      hud.chips.textContent = '';
      var sided = motions.some(function (m) { return m.g; });
      hud.chips.classList.toggle('v3d-chips--rows', sided);
      if (sided) {
        // spolecna nabidka: radek pro kazdou stranu (Leva / Prava / Prepazka; pohyby bez strany naposled), popisek strany + cipy jeji strany + Otevrit/Zavrit vse JEN pro stranu
        SIDE_KEYS.concat([null]).forEach(function (gk) {
          var list = motions.filter(function (m) { return (m.g || null) === gk; });
          if (!list.length) return;
          var row = el('div', 'v3d-chiprow' + (gk ? ' v3d-chiprow--' + gk : ''));
          row.setAttribute('role', 'group');
          row.setAttribute('aria-label', gk ? L['side_' + gk] : L.chips_aria);
          if (gk) row.appendChild(el('span', 'v3d-chiprow__lbl', L['side_' + gk]));
          appendChipGroups(row, list);
          if (list.length > 1) row.appendChild(chipAllButtons(list, gk));
          hud.chips.appendChild(row);
        });
      } else {
        appendChipGroups(hud.chips, motions);
        // "Otevrit vse" jen kdyz je co otevrit (boxy se jim neotviraji); pri dlouhe liste cipu zustavaji u praveho okraje
        if (motions.length > 1) hud.chips.appendChild(chipAllButtons(motions, null));
      }
      root.classList.toggle('v3d-has-chips', motions.length > 0);
      var touchHint = coarse ? L.hint_touch : L.hint_mouse;
      hud.hint.textContent = touchHint + (motions.length ? (coarse ? L.hint_tap_tail : L.hint_click_tail) : '');
      updateChips();
      syncChipsH();
      global.requestAnimationFrame(syncChipsH);          // po rozlozeni (fonty, zalomeni)
    }
    function updateChips() {
      if (!hud) return;
      var bs = hud.chips.querySelectorAll('[data-motion]');
      for (var i = 0; i < bs.length; i++) {
        var id = bs[i].getAttribute('data-motion'), open = targetOf(id) >= 0.5;
        bs[i].classList.toggle('is-open', open);
        bs[i].classList.toggle('is-sel', id === selId);
        bs[i].setAttribute('aria-pressed', open ? 'true' : 'false');
      }
    }
    function hideHint() { if (hud) hud.hint.classList.add('is-gone'); }

    // ---------------- dispose ----------------
    function dispose() {
      if (disposed) return;
      try { if (st.fsCss) cssFs(false); else if (fsEl() === root) setFullscreen(false); } catch (e) { /* */ }
      disposed = true;
      clearHover();
      if (hoverTip && hoverTip.parentNode) hoverTip.parentNode.removeChild(hoverTip);
      var li = live.indexOf(liveRec);
      if (li >= 0) live.splice(li, 1);
      // dispose pred dokoncenim nacteni: ready se jinak nikdy nevyridi (nalez 9)
      if (!st.ready && !st.error) { st.error = 'disposed'; readyReject(new Error('V3D: disposed')); }
      if (rafId) global.cancelAnimationFrame(rafId);
      if (envGate.timer) { global.clearTimeout(envGate.timer); envGate.timer = 0; }
      rafId = 0; tweens = {}; flight = null;
      if (ro) ro.disconnect();
      listeners.forEach(function (l) { l[0].removeEventListener(l[1], l[2], l[3]); });
      listeners = [];
      controls.dispose();
      cancelPending(disposedError);                    // nedokoncena setModel() se nesmi nechat viset
      disposeState(takeState());                       // model, koty, stin, hrany (vc. DOM popisku)
      // zbytek sceny (kdyby neco zustalo) + materialy sdilene s prohlizecem
      var geos = new Set(), mats = new Set();
      collectRes(scene, geos, mats);
      SHARED_MATS.forEach(function (m) { mats.add(m); });
      geos.forEach(function (g) { g.dispose(); });
      mats.forEach(function (m) { m.dispose(); });
      cameraSubs = [];
      endPlugins();
      if (envRT) envRT.dispose();
      Object.keys(hdriCache).forEach(function (k) { hdriCache[k].dispose(); });
      aoFreeRT();
      if (aoMats) {
        [aoMats.depth, aoMats.ao, aoMats.blurH, aoMats.blurV, aoMats.comp].forEach(function (m) { m.dispose(); });
        Object.keys(aoMats.wmats).forEach(function (k) { aoMats.wmats[k].dispose(); });
        aoMats.quad.geometry.dispose();
        aoMats = null;
      }
      renderer.dispose();
      if (renderer.forceContextLoss) { try { renderer.forceContextLoss(); } catch (e) { /* */ } }
      if (root.parentNode) root.parentNode.removeChild(root);
      if (global.__v3d === hook) global.__v3d = null;
    }

    // ---------------- verejne API ----------------
    function state() {
      var t = {}, labels = {};
      motions.forEach(function (m) { t[m.id] = motionT[m.id]; labels[m.id] = motionLabel(m, L); });
      return {
        ready: st.ready, error: st.error, legacy: st.legacy, look: st.look, mode: st.mode, dims: st.dims, alu: st.alu, aluMaterials: aluMats.length, env: st.env, envCfg: st.envCfg ? { hdri: st.envCfg.hdri, strength: st.envCfg.strength, rot_deg: st.envCfg.rot_deg, hemi: st.envCfg.hemi } : null, envHdriLoaded: Object.keys(hdriCache).some(function (k) { return !hdriSeed[k]; }), envSeed: Object.keys(hdriSeed).some(function (k) { return hdriCache[k] && hdriCache[k].texture === scene.environment; }),
        ao: aoSupport ? st.ao : 'vyp', aoActive: aoActive(), aoSupported: aoSupport && !aoBroken,
        allowReal: st.allowReal, twoSided: st.twoSided,
        loading: pendingLoads.length > 0 || (!st.ready && !st.error), modelSeq: modelSeq, hudKoty: hudKoty, onPick: !!onPickFn,
        view: st.view, isoAngles: { az: isoAz, el: isoEl }, flying: !!flight, animating: Object.keys(tweens).length > 0, fullscreen: st.fs,
        t: t, motions: motions.map(function (m) { return { id: m.id, k: m.k, sub: m.subk || null, n: m.n, label: labels[m.id], deps: (m.deps || []).slice(), side: m.side || 0, blocks: (m.blocks || []).slice() }; }),
        openAllSet: st.ready ? openAllSet().map(function (m) { return m.id; }) : [],
        groups: Array.from(groupMeshes.keys()).sort(function (a, b) { return a - b; }),
        highlighted: Array.from(highlightSet), front: front.toArray(), warnings: st.warnings.slice()
      };
    }
    var api = {
      ready: ready,
      setModel: setModel,
      selectMotion: function (id) { if (!st.ready) return false; selectMotion(id); return true; },
      // barvy a sytost materialu: setMatConfig({sat, colors:{"#puvodni":"#nova"}}) -> normalizovana konfigurace | null (vychozi); null/neplatne = vychozi
      setMatConfig: function (c) { st.matCfg = normMatCfg(c); if (st.ready) applyMatCfg(); return api.getMatConfig(); },
      getMatConfig: function () { return st.matCfg ? { sat: st.matCfg.sat, colors: JSON.parse(JSON.stringify(st.matCfg.colors)), gloss: JSON.parse(JSON.stringify(st.matCfg.gloss)), ao: JSON.parse(JSON.stringify(st.matCfg.ao)) } : { sat: 1, colors: {}, gloss: {}, ao: {} }; },
      resetMatConfig: function () { st.matCfg = null; if (st.ready) applyMatCfg(); },
      materialPalette: function () { return matPalette(); },
      // odlesky hliniku {refl: 0-1,5, rough: 0,5-2} (nasobky zvolene varianty) a AO {k: 0-2, r: 0,25-3}; null / neplatne = vychozi
      setAluConfig: function (c) { st.aluCfg = normAluCfg(c); if (st.ready) { applyAlu(); applyMatLook(); kick(); } return api.getAluConfig(); },
      getAluConfig: function () { return st.aluCfg ? { refl: st.aluCfg.refl, rough: st.aluCfg.rough, ao: st.aluCfg.ao } : { refl: 1, rough: 1, ao: 1 }; },
      resetAluConfig: function () { api.setAluConfig(null); },
      setAoConfig: function (c) { st.aoCfg = normAoCfg(c); requestRender(); return api.getAoConfig(); },
      getAoConfig: function () { return st.aoCfg ? { k: st.aoCfg.k, r: st.aoCfg.r } : { k: 1, r: 1 }; },
      resetAoConfig: function () { api.setAoConfig(null); },
      setView: function (k) { if (!st.ready) return false; if (k === 'reset') k = 'iso'; applyView(k); return true; },
      // vychozi 3D pohled (1.17.0): setIsoAngles({az, el} | null, fly) zmeni uhel pohledu "3D" (null = puvodnich 35 / 25; fly=true kameru tam preleti); currentAngles() = {az, el} aktualni kamery vuci celu modelu
      setIsoAngles: function (a, fly) {
        var n = (a === null || a === undefined) ? { az: ISO_AZ, el: ISO_EL } : normalizeIsoAngles(a);
        if (!n) return false;
        isoAz = n.az; isoEl = n.el;
        if (st.ready && fly) applyView('iso');
        return true;
      },
      currentAngles: function () {
        if (!st.ready || disposed) return null;
        var off = camera.position.clone().sub(controls.target), len = off.length();
        if (!(len > 1e-6)) return null;
        var az = -(Math.atan2(off.z, off.x) - Math.atan2(front.z, front.x)) / DEG;           // opak rotAboutUp(front, az)
        az = ((az + 180) % 360 + 360) % 360 - 180; if (az === -180) az = 180;
        return { az: Math.round(az * 10) / 10, el: Math.round(Math.asin(Math.max(-1, Math.min(1, off.y / len))) / DEG * 10) / 10 };
      },
      setDims: function (l) { st.dims = (l === 1 || l === 2) ? l : 0; st.dimsPref = st.dims; if (st.ready) applyDims(); return true; },
      setMode: function (m) {
        if (m !== 'wire' && m !== 'real') return false;
        if (!st.ready) { st.mode = m; st.modePref = m; return true; }
        if (m === 'real' && !st.allowReal) return false;     // legacy bez allowReal: jen Drateny
        applyMode(m); st.modePref = st.mode; return true;
      },
      play: function (id, dir) { return play(id, dir || 0); },
      playAll: function (dir) { return playAll(dir || 0); },
      setT: setT,
      highlight: function (set) { applyHighlight(set); return true; },
      zoom: function (s) { if (st.ready) zoom(s); },
      fullscreen: function (want) { setFullscreen(want); },
      // kamera: cameraInfo() = aktualni stav ({pos,target,dir,screenUp,up,dist,fov,aspect,near,far,minDistance,maxDistance}, mm, three osy),
      // onCamera(cb) = cb(info) po kazdem vykresleni snimku (zmena kamery, tazeni, preletu, resize); vraci funkci pro odhlaseni
      cameraInfo: cameraInfoNow,
      // snimek plateno -> Promise<dataURL>: v.snapshot({ width, type:'image/png'|'image/jpeg', quality, background }). Vykresli cerstvy snimek
      // a precte ho ve stejnem JS tasku (platno nema preserveDrawingBuffer). Velikost = pixely platna (nejvyse; width jen zmensi, pomer stran
      // zustava); cervene kota-cary jsou v obraze, TEXTY kot (DOM popisky) ne; pruhledne pozadi se vyplni `background` (JPEG bez nej = bila).
      snapshot: function (o) {
        o = o || {};
        return envSettled(4000).then(function () { return new Promise(function (res, rej) {          // snimek ma mit plne HDRI (nahled se lisi jen minimalne; cekani nejvyse 4 s)
          try {
            if (disposed || !st.ready) { rej(new Error('V3D: snimek neni mozny (neni pripraveno nebo uvolneno)')); return; }
            clearHover();                                                                              // snimek bez podsviceni dilu pod mysi
            renderNow();
            var src = renderer.domElement, w = src.width, h = src.height;
            if (!(w > 0 && h > 0)) { rej(new Error('V3D: prazdne platno')); return; }
            var tw = (typeof o.width === 'number' && o.width >= 16) ? Math.min(Math.round(o.width), w) : w;
            var th = Math.max(1, Math.round(h * tw / w));
            var type = o.type === 'image/jpeg' ? 'image/jpeg' : 'image/png';
            var bg = typeof o.background === 'string' && /^#[0-9a-fA-F]{3,8}$|^rgba?\([0-9 ,.%]+\)$/.test(o.background) ? o.background : (type === 'image/jpeg' ? '#ffffff' : null);
            var c = document.createElement('canvas'); c.width = tw; c.height = th;
            var g = c.getContext('2d');
            if (bg) { g.fillStyle = bg; g.fillRect(0, 0, tw, th); }
            g.drawImage(src, 0, 0, tw, th);
            res(c.toDataURL(type, typeof o.quality === 'number' ? Math.min(1, Math.max(0.1, o.quality)) : 0.92));
          } catch (e) { rej(e); }
        }); });
      },
      onCamera: function (cb) {
        if (typeof cb !== 'function' || disposed) return function () {};
        cameraSubs.push(cb);
        return function () { var i = cameraSubs.indexOf(cb); if (i >= 0) cameraSubs.splice(i, 1); };
      },
      setAluminium: function (k) {
        if (!aluVariantByKey(k)) return false;
        st.alu = k;
        if (st.ready) { applyAlu(); applyMatLook(); kick(); }
        if (ladeni) ladeniUloz('v3dAlu', k);
        updateHud();
        return true;
      },
      setEnvironment: function (k) {
        var v = envVariantByKey(k);
        if (!v) return false;
        st.env = k;
        envGateOpen(true);
        applyEnv(); kick();
        updateHud();
        return true;
      },
      // Konfigurace prostredi (V3D.envLibrary, admin generatoru): setEnvConfig({hdri, strength, rot_deg, hemi}) -> normalizovana konfigurace | false (neznamy hdri)
      setEnvConfig: function (c) {
        var n = normEnvCfg(c);
        if (!n) return false;
        st.env = 'custom'; st.envCfg = n;
        envGateOpen(true);
        applyEnv(); kick(); updateHud();
        return { hdri: n.hdri, strength: n.strength, rot_deg: n.rot_deg, hemi: n.hemi };
      },
      getEnvConfig: function () {
        var c = (st.env === 'custom' && st.envCfg) ? st.envCfg : cfgOfVariant(st.env);
        return { hdri: c.hdri, strength: c.strength, rot_deg: c.rot_deg, hemi: c.hemi };
      },
      resetEnvConfig: function () {
        st.env = 'hdri_tlumene'; st.envCfg = null;
        envGateOpen(true);
        applyEnv(); kick(); updateHud();
        return true;
      },
      // AO (ambient occlusion): 'vyp' | 'jemne' | 'stredni' | 'silne' (V3D.aoVariants); false = neznama volba nebo prohlizec AO neumi
      setAO: function (k) {
        var v = aoVariantByKey(k);
        if (!v) return false;
        if (v.p && (!aoSupport || aoBroken)) return false;
        st.ao = k;
        if (!v.p) aoFreeRT();                    // 'vyp': uvolnit cile renderu (zkompilovane materialy zustavaji)
        if (st.ready) requestRender();
        if (ladeni) ladeniUloz('v3dAO', k);
        updateHud();
        return true;
      },
      state: state,
      dispose: dispose
    };

    // ---------------- ladici hook (harness) ----------------
    function meshBox(node) {
      var b = new THREE.Box3();
      node.updateWorldMatrix(true, true);   // i rodice (vnorene pivoty pred prvnim vykreslenim)
      node.traverse(function (n) { if (n.isMesh && !n.userData.__v3dHelper && meshes.indexOf(n) >= 0) b.expandByObject(n); });
      return b;
    }
    function findNode(name) {
      if (!model) return null;
      if (pivots.has(name)) return pivots.get(name).node;
      var f = null;
      model.traverse(function (n) { if (!f && (n.name === name || (n.userData && n.userData.name === name))) f = n; });
      return f;
    }
    var hook = {
      state: state,
      setAO: function (k) { return api.setAO(k); },
      aoParams: function (o) { aoDbg = o || null; requestRender(); },   // {r, k, gamma, minPx, maxPx, falloff} prepise varianta; null = zpet
      setT: setT,
      play: function (id, dir) { return play(id, dir || 0); },
      worldBox: function (name) {
        var n = findNode(name);
        if (!n) return null;
        var b = meshBox(n);
        if (b.isEmpty()) return null;
        return { min: b.min.toArray(), max: b.max.toArray(), center: b.getCenter(new THREE.Vector3()).toArray(), size: b.getSize(new THREE.Vector3()).toArray() };
      },
      pivot: function (name) {
        var pv = pivots.get(name);
        if (!pv) return null;
        var dq = pv.baseQuat.clone().invert().multiply(pv.node.quaternion);
        return { pos: pv.node.position.toArray(), basePos: pv.basePos.toArray(), angleDeg: 2 * Math.acos(clamp(Math.abs(dq.w), 0, 1)) / DEG,
          world: pv.node.getWorldPosition(new THREE.Vector3()).toArray() };
      },
      screenOf: function (name) {
        var n = findNode(name);
        if (!n) return null;
        var c = meshBox(n).getCenter(new THREE.Vector3()).project(camera);
        var r = canvas.getBoundingClientRect();
        return { x: r.left + (c.x + 1) / 2 * r.width, y: r.top + (1 - c.y) / 2 * r.height };
      },
      camera: cameraInfoNow,
      envInfo: function () { var m = allMats.length ? allMats[0].envMapIntensity : null; return { hasEnv: !!scene.environment, texId: scene.environment ? scene.environment.uuid : null, hemi: hemiLight.intensity, matIntensity: m, cached: Object.keys(hdriCache).length, gate: envGate.open, seed: Object.keys(hdriSeed).some(function (k) { return hdriCache[k] && hdriCache[k].texture === scene.environment; }) }; },
      // jak velkou cast okna zabira obal produktu (max |NDC| rohu; <=1 = cely v zaberu)
      fitCheck: function () {
        camera.updateMatrixWorld(true);
        var mx = 0, my = 0, b = productBox;
        if (!b) return null;
        for (var i = 0; i < 8; i++) {
          var p = new THREE.Vector3(i & 1 ? b.max.x : b.min.x, i & 2 ? b.max.y : b.min.y, i & 4 ? b.max.z : b.min.z).project(camera);
          mx = Math.max(mx, Math.abs(p.x)); my = Math.max(my, Math.abs(p.y));
        }
        return { x: mx, y: my };
      },
      dimsCount: dimsVisibleCount,
      selectedMotion: function () { return selId; },
      matInfo: function () { return colorMats.map(function (m) { var b = m.userData.__v3dBase, c = m.color.clone(); c.convertLinearToSRGB(); return { orig: srgbHexOfBase(b), now: '#' + c.getHexString(), rough: typeof m.roughness === 'number' ? Math.round(m.roughness * 1000) / 1000 : null, rough0: m.userData.__v3dRough0 === undefined ? null : m.userData.__v3dRough0, aoW: typeof m.userData.__v3dAoW === 'number' ? m.userData.__v3dAoW : 1 }; }); },
      aluInfo: function () { return aluMats.map(function (m) { var o = m.userData.__v3dAluOrig; return { rough: Math.round(m.roughness * 1000) / 1000, metal: m.metalness, env: Math.round(m.envMapIntensity * 1000) / 1000, rough0: o.r, metal0: o.m, aoW: typeof m.userData.__v3dAoW === 'number' ? m.userData.__v3dAoW : 1 }; }); },
      aoValues: function () { var e = aoEff(); return e ? { variant: st.ao, k: Math.round(e.k * 1000) / 1000, r: Math.round(e.r * 1000) / 1000, cfg: st.aoCfg, wPasses: aoStat.wPasses, wMeshes: aoStat.wMeshes } : { variant: st.ao, k: 0, r: 0, cfg: st.aoCfg, wPasses: aoStat.wPasses, wMeshes: aoStat.wMeshes }; },
      hoverInfo: function () {
        var on_ = !!(hoverTip && hoverTip.classList.contains('is-on'));
        return { id: hoverId, overlays: hoverOvs.length, on: on_, name: hoverTip ? hoverTip.firstChild.textContent : null, act: hoverTip ? hoverTip.querySelector('.v3d-tip__txt').textContent : null,
          cursor: canvas.style.cursor, tip: on_ ? hoverTip.getBoundingClientRect().toJSON() : null };
      },
      selDimsLabels: function () { return selRecs ? selRecs.map(function (r) { return r.text; }) : []; },
      dimsLabels: function () { var a = []; dimRecs.forEach(function (r) { if (r.obj.visible) a.push(r.text); }); return a; },
      info: function () {
        renderNow();
        var i = renderer.info;
        return { calls: i.render.calls, triangles: i.render.triangles, lines: i.render.lines, geometries: i.memory.geometries, textures: i.memory.textures,
          programs: i.programs ? i.programs.length : null, meshes: meshes.length, pivots: pivots.size, motions: motions.length, dims: dimRecs.length,
          matWrites: st.matWrites, frames: st.frames, pixelRatio: renderer.getPixelRatio(), toneMapping: renderer.toneMapping, outputEncoding: renderer.outputEncoding,
          shadow: !!(shadow && shadow.ok), env: !!scene.environment, hasCSS2D: hasCSS2D, blocksMs: st.blocksMs || 0 };
      },
      materialAudit: function () {
        var wrong = 0;
        meshes.forEach(function (m) { if (!sameMat(m.material, wantMaterial(m))) wrong++; });
        var wireOcc = meshes.filter(function (m) { return m.material === occluderMat; }).length;
        // meshe, jejichz skupina hran je videt
        var edgesVis = meshes.filter(function (m) { return edgesOf.has(m) && edgesOf.get(m).visible; }).length;
        var statG = edgeGroups.filter(function (g) { return !g.owner; })[0];
        return { mode: st.mode, total: meshes.length, wrong: wrong, occluders: wireOcc, edgesVisible: edgesVis, highlighted: meshes.filter(function (m) { return m.material === highlightMat; }).length, matWrites: st.matWrites,
          edgeObjects: edgeGroups.length, staticEdgeMeshes: statG ? statG.meshes.length : 0 };
      },
      renderNow: renderNow,
      // AO (harness): stav, rozliseni cilu, pamet; hodnoty AO mapy (po rozmazani, 0..1) v bodech [x, y] v CSS px od leveho horniho rohu (kalibrace)
      aoInfo: function () {
        return { supported: aoSupport, broken: aoBroken, active: aoActive(), variant: st.ao, webgl2: !!renderer.capabilities.isWebGL2, res: aoRes ? { w: aoRes.w, h: aoRes.h, k: aoRes.k } : null,
          programs: renderer.info.programs ? renderer.info.programs.length : null, memory: { geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures } };
      },
      aoSample: function (pts) {
        if (!aoRes) return null;
        var buf = new Uint8Array(aoRes.w * aoRes.h * 4), cs = renderer.getSize(new THREE.Vector2());
        renderer.readRenderTargetPixels(aoRes.rtA, 0, 0, aoRes.w, aoRes.h, buf);
        return pts.map(function (q) {
          var ix = clamp(Math.floor(q[0] / cs.x * aoRes.w), 0, aoRes.w - 1), iy = clamp(Math.floor((1 - q[1] / cs.y) * aoRes.h), 0, aoRes.h - 1);
          return buf[(iy * aoRes.w + ix) * 4] / 255;
        });
      },
      // smycka kresleni stoji (zadny prelet/animace/dojezd ovladani) - harness ceka na dojezd setrvacnosti
      idle: function () { return !rafId && !flight && Object.keys(tweens).length === 0; },
      tapLog: function () { return tapLog.slice(); },
      // co by trefil klik v bode obrazovky (harness: je box videt, nezakryva ho vysuv?)
      pickInfo: function (x, y) { var h = hitAt(x, y); return h ? { motion: h.motion, motionExplicit: h.motionExplicit, group: h.group, slot: h.slot } : null; },
      // zdroje, ktere prohlizec drzi (harness: unik pri vymenach modelu)
      resources: function () {
        var geos = new Set(), mats = new Set(), texs = new Set();
        scene.traverse(function (n) {
          if (n.geometry) geos.add(n.geometry);
          if (n.material) (Array.isArray(n.material) ? n.material : [n.material]).forEach(function (m) { if (m) mats.add(m); });
        });
        origMat.forEach(function (m) { (Array.isArray(m) ? m : [m]).forEach(function (x) { if (x) mats.add(x); }); });
        mats.forEach(function (m) { Object.keys(m).forEach(function (k) { if (m[k] && m[k].isTexture) texs.add(m[k]); }); });
        return { geos: geos.size, mats: mats.size, texs: texs.size, sceneChildren: scene.children.length,
          modelGroups: scene.children.filter(function (c) { return !c.isLight && !c.userData.__v3dHelper; }).length,
          currentInScene: !!model && model.parent === scene, labelsDom: labelRenderer ? labelRenderer.domElement.children.length : 0,
          dimRecs: dimRecs.length, dimsBuilt: dimsBuilt, edgeGroups: edgeGroups.length, pending: pendingLoads.length, modelSeq: modelSeq };
      },
      // sedi slouzene hrany na svych dilech? Pro kazdou skupinu: o kolik obal
      // jejich hran (ve svete) vycniva z presneho obalu vrcholu jejich meshi
      // (hrany nejedou s pivotem -> stovky mm) a jak presne sedi rohy.
      edgeAudit: function () {
        var outside = 0, corner = 0, v = new THREE.Vector3();
        edgeGroups.forEach(function (g) {
          // presne obaly z vrcholu (obal geometrie po natoceni o obecny uhel je volnejsi)
          function exact(obj, box) {
            obj.updateWorldMatrix(true, false);
            var pa = obj.geometry.attributes.position;
            for (var i = 0; i < pa.count; i++) box.expandByPoint(v.fromBufferAttribute(pa, i).applyMatrix4(obj.matrixWorld));
          }
          var eb = new THREE.Box3(), mb = new THREE.Box3();
          exact(g.obj, eb);
          g.meshes.forEach(function (m) { exact(m, mb); });
          outside = Math.max(outside, mb.min.x - eb.min.x, mb.min.y - eb.min.y, mb.min.z - eb.min.z, eb.max.x - mb.max.x, eb.max.y - mb.max.y, eb.max.z - mb.max.z);
          corner = Math.max(corner, eb.min.distanceTo(mb.min), eb.max.distanceTo(mb.max));
        });
        return { groups: edgeGroups.length, outsideMm: Math.max(outside, 0), cornerMm: corner };
      },
      // bod na obrazovce, kde klik trefi dany pohyb (mrizka v promitnutem obalu
      // jeho podstromu, od stredu ven); null = neni videt
      pickPoint: function (id) {
        var m = motionById[id];
        if (!m || !m.root) return null;
        var b = meshBox(m.root);
        if (b.isEmpty()) return null;
        camera.updateMatrixWorld(true);
        var r = canvas.getBoundingClientRect(), x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
        for (var i = 0; i < 8; i++) {
          var p = new THREE.Vector3(i & 1 ? b.max.x : b.min.x, i & 2 ? b.max.y : b.min.y, i & 4 ? b.max.z : b.min.z).project(camera);
          var sx = r.left + (p.x + 1) / 2 * r.width, sy = r.top + (1 - p.y) / 2 * r.height;
          x0 = Math.min(x0, sx); x1 = Math.max(x1, sx); y0 = Math.min(y0, sy); y1 = Math.max(y1, sy);
        }
        x0 = Math.max(x0, r.left + 1); x1 = Math.min(x1, r.right - 1); y0 = Math.max(y0, r.top + 1); y1 = Math.min(y1, r.bottom - 1);
        var cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, pts = [], N = 12;
        for (var a = 0; a <= N; a++) for (var c = 0; c <= N; c++) pts.push([x0 + (x1 - x0) * a / N, y0 + (y1 - y0) * c / N]);
        pts.sort(function (u, v) { return Math.hypot(u[0] - cx, u[1] - cy) - Math.hypot(v[0] - cx, v[1] - cy); });
        for (var k = 0; k < pts.length; k++) { var h = hitAt(pts[k][0], pts[k][1]); if (h && h.motion === id) return { x: pts[k][0], y: pts[k][1] }; }
        return null;
      },
      // kamera okamzite z daneho smeru (harness: oboustranna sestava z druhe strany)
      lookFrom: function (dir) {
        var d = new THREE.Vector3().fromArray(dir).normalize();
        var dist = clamp(fitDistance(d, FIT_PAD), controls.minDistance || 0, controls.maxDistance || Infinity);
        st.view = null;
        flyTo(center.clone().addScaledVector(d, dist), center.clone(), 0);
        updateHud();
      },
      cameraSide: function () { return cameraSide(); },
      // nastavit stav vsech pohybu najednou {id: t} (chybejici = 0), bez zavislosti
      setAll: function (tmap) {
        tmap = tmap || {};
        Object.keys(motionT).forEach(function (id) { delete tweens[id]; motionT[id] = clamp01(+tmap[id] || 0); });
        applyPoses(); updateChips(); requestRender();
        return true;
      },
      // Box3 podstromu pohybu ve svetovych souradnicich v aktualnim stavu
      motionBox: function (id) {
        var m = motionById[id];
        if (!m || !m.root) return null;
        var b = meshBox(m.root);
        return b.isEmpty() ? null : { min: b.min.toArray(), max: b.max.toArray() };
      },
      model: function () { return model; }
    };
    global.__v3d = hook;
    api.debug = hook;
    return api;
  };
})(window);
