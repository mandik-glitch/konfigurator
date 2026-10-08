// Path-traceovane 3D nahledy pro nabidku (Robert 2026-08-10) -
// vyclenene z app-script (bot14, 2026-09-03,
// PLAN_ROZDELENI_FRONTENDU.md). 1:1 presun, beze zmeny chovani.
// Klasicky script (ne modul), sdili globalni scope s app-script - musi
// se nacist PRED nim (viz <script src> v scene.html).
//
// Skutecne hranice bloku SIRSI nez plan (22725-25593) - obsahuje navic
// popout-panelu sekci (renderPanelPopout/queryRenderPanelMode/
// popoutRenderPanel, puvodne fyzicky daleko, r. ~14594-14700), protoze
// je pouzivana VYHRADNE timhle blokem (potvrzeno gremem pred presunem)
// a jeji oddeleni by zpusobilo dopredou referenci (queryRenderPanelMode
// by nebyla definovana v okamziku volani ze zbytku bloku - odhaleno
// e2e testem, schvaleno bot3 pred timhle presunem). Poradi uvnitr
// souboru zachovava puvodni poradi v app-script (popout sekce byla
// FYZICKY DRIV nez hlavni path-traced blok).
//
// addRenderPopoutButton byla puvodne self-invoking IIFE spustena hned
// na miste - #fwRenderWindow ale vytvari az `initFloatingShapesWindow(
// {winId:"fwRenderWindow",...})` volani, ktere ZUSTAVA v app-script
// (jadro, sdileny helper pro vsechny plovouci panely). Prevedeno na
// pojmenovanou funkci + explicitni `addRenderPopoutButton();` volani
// ponechane v app-script HNED PO puvodnim miste (za `const
// renderPanelWin = initFloatingShapesWindow(...)`), aby poradi
// provedeni zustalo presne stejne jako pred extrakci.
// ============================================================
// Robert 2026-08-11 ("start render - dej to vyjimatelne na plochu a
// zpet"): panel Render jde VYJMOUT ze sceny do SAMOSTATNEHO okna
// prohlizece (jde pretahnout na druhy monitor / volne misto na plose) a
// zavrenim toho okna se vrati zpatky do plovouciho panelu ve scene.
//
// Technicky: cely <div id="renderPanelSection"> se i s posluchaci
// presune (document.adoptNode) do noveho okna - NEklonuje se, takze
// vsechny posuvniky/checkboxy zustavaji TYTEZ elementy a jejich stav i
// nastaveni renderu funguji beze zmeny. Aby je nasel i zbytek aplikace
// (readBlenderOptions atd. hledaji pres document.getElementById),
// getElementById ma nize fallback do vyjmuteho okna.
let renderPanelPopout = null;

const _origGetElementById = document.getElementById.bind(document);
document.getElementById = function (id) {
  const el = _origGetElementById(id);
  if (el) return el;
  if (renderPanelPopout && !renderPanelPopout.closed) {
    try { return renderPanelPopout.document.getElementById(id); } catch (e) { return null; }
  }
  return null;
};

// Stejny fallback pro radia rezimu renderu (name=, ne id=).
function queryRenderPanelMode() {
  let el = document.querySelector('input[name="renderPanelMode"]:checked');
  if (!el && renderPanelPopout && !renderPanelPopout.closed) {
    try { el = renderPanelPopout.document.querySelector('input[name="renderPanelMode"]:checked'); } catch (e) {}
  }
  return el;
}

function popoutRenderPanel() {
  if (renderPanelPopout && !renderPanelPopout.closed) { renderPanelPopout.focus(); return; }
  const section = _origGetElementById("renderPanelSection");
  if (!section) return;
  let w;
  try {
    w = window.open("", "logimanRenderPanel", "width=460,height=880,scrollbars=yes,resizable=yes");
  } catch (e) { w = null; }
  if (!w) { showJoinToast("Prohlížeč zablokoval nové okno - povol vyskakovací okna pro tuhle stránku."); return; }

  const fwWin = _origGetElementById("fwRenderWindow");
  const fwBody = fwWin ? fwWin.querySelector(".fw-shapes-body") : section.parentNode;

  w.document.open();
  w.document.write('<!doctype html><html lang="cs"><head><meta charset="utf-8"><title>Render – nastavení (Logiman)</title></head>'
    + '<body><div id="rpPopoutBar"><span>🎨 Render – nastavení</span>'
    + '<button id="rpPopoutBack" type="button">⇤ Vrátit do scény</button></div>'
    + '<div id="rpPopoutHost"></div></body></html>');
  w.document.close();
  // Prevzit CSS hlavni stranky (promenne, posuvniky, sbalovaci skupiny) -
  // kopie <style> bloku + tridy/atributy na <html>, at plati dark theme.
  try {
    w.document.documentElement.className = document.documentElement.className;
    for (const a of document.documentElement.attributes) {
      if (a.name.startsWith("data-")) w.document.documentElement.setAttribute(a.name, a.value);
    }
    document.querySelectorAll("style").forEach(st => {
      const c = w.document.createElement("style");
      c.textContent = st.textContent;
      w.document.head.appendChild(c);
    });
    const extra = w.document.createElement("style");
    extra.textContent = "body{margin:0;background:var(--bg,#141821);color:var(--text,#c9d1d9);font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif;}"
      + "#rpPopoutBar{position:sticky;top:0;z-index:5;display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 12px;background:var(--panel,#1b1f27);border-bottom:1px solid var(--border-soft2,#333a45);font-size:13px;}"
      + "#rpPopoutBack{background:var(--panel2,#232a35);color:var(--text,#c9d1d9);border:1px solid var(--border-soft2,#3a4453);border-radius:5px;padding:4px 10px;font-size:12px;cursor:pointer;font-family:inherit;}"
      + "#rpPopoutBack:hover{background:var(--panel3,#2b3340);}"
      + "#rpPopoutHost{padding:10px 12px;}";
    w.document.head.appendChild(extra);
  } catch (e) { /* horsi vzhled neni duvod nefungovat */ }

  w.document.getElementById("rpPopoutHost").appendChild(w.document.adoptNode(section));
  if (fwWin) fwWin.style.display = "none";

  const dockBack = () => {
    renderPanelPopout = null;
    try {
      if (section.ownerDocument !== document && fwBody) {
        fwBody.appendChild(document.adoptNode(section));
        if (fwWin) fwWin.style.display = "flex";
      }
    } catch (e) { /* okno uz je pryc a element s nim - nic vic nezmuzeme */ }
  };
  w.document.getElementById("rpPopoutBack").onclick = () => w.close();
  // pagehide misto beforeunload - spolehlivejsi pri zavreni okna krizkem
  w.addEventListener("pagehide", dockBack);
  renderPanelPopout = w;
  w.focus();
}

// Tlacitko "⧉" v titulku plovouciho okna Render (vedle ⟲ a ✕).
//
// POZOR (bot14, 2026-09-03, PLAN_ROZDELENI_FRONTENDU.md extrakce):
// puvodne self-invoking IIFE spustena hned tady. #fwRenderWindow ale
// NENI staticke HTML - vytvari ho az `initFloatingShapesWindow({winId:
// "fwRenderWindow", ...})` volani v app-script (puvodne o par radku
// VYS ve stejnem souboru, ted uz v JINEM souboru nacitanem DRIV).
// Kdyby tahle funkce zustala samospustna IIFE tady, bezela by PRED
// tim, nez #fwRenderWindow vubec existuje (element by se tise
// nenasel, tlacitko by se nikdy nepridalo). Reseno prevodem na
// pojmenovanou funkci + explicitni volani `addRenderPopoutButton();`
// v app-script, HNED PO puvodnim miste (za `const renderPanelWin =
// initFloatingShapesWindow(...)`) - presne zachovava puvodni poradi
// provedeni, jen misto IIFE je to volani pojmenovane funkce odsud.
function addRenderPopoutButton() {
  const fwWin = _origGetElementById("fwRenderWindow");
  if (!fwWin) return; // uzky displej - plovouci okna se nestavi
  const grp = fwWin.querySelector(".fw-shapes-titlebar span");
  const btnGroup = fwWin.querySelectorAll(".fw-shapes-titlebar span")[1] || grp;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "fw-shapes-reset-btn";
  btn.title = "Vyjmout panel do samostatného okna (na plochu) - zavřením okna se vrátí zpět";
  btn.textContent = "⧉";
  btn.addEventListener("mousedown", (e) => e.stopPropagation()); // nezacinat tazeni okna
  btn.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); popoutRenderPanel(); });
  btnGroup.insertBefore(btn, btnGroup.firstChild);
}

// ==================== Path-traceovane 3D nahledy pro nabidku ====================
// Robert 2026-08-10 ("chci to delat metodou ray tracing, plnohodnotny
// render" - "to co jsem přiložil je kvalita kterou chci pro nabídky",
// "Pro nabídky by se mohlo využít GPU mého počítače"): view3d_a/view3d_b v
// generateSceneOffer() misto obycejneho rasterizovaneho screenshotu
// (captureRaw3d) POUZIJI skutecny path tracer (three-gpu-pathtracer) -
// skutecne odrazy/mekke stiny/AO mezi dily, ne jen aproximovany PBR
// material. Bezi CELE v prohlizeci na GPU prihlaseneho admina (WebGL2),
// zadny server na to netreba.
//
// Hlavni scena bezi na PINNED three.js r128 (klasicke "script" tagy, ne ES
// moduly) - three-gpu-pathtracer vyzaduje modernejsi three.js (r150+, ES
// moduly). Aby nedoslo k rozbiti zive editovatelne sceny (r128 zustava
// ZCELA nedotcena), bezi path tracer v ODDELENE, docasne vytvorene
// instanci moderniho three.js (viz import map v <head>), ktera nacte
// STEJNOU geometrii pres uz existujici exportSceneAsGlb() (GLB export
// zachovava world-space pozice/rotace/meritko presne jak jsou ve scene).
//
// Failure-safe zamerne na kazde urovni (network blokovana/pomala, WebGL2
// nedostupne, GLB parse chyba, cokoli) - pri jakekoli chybe funkce vrati
// null pro dany snimek a volajici (generateSceneOffer) tise spadne zpet na
// uz driv spocitany rasterizovany captureRaw3d() vysledek pro tenhle
// pohled, takze cely proces generovani nabidky NIKDY nespadne kvuli
// tomuto vylepseni.
const PATHTRACE_TIME_BUDGET_MS = 9000; // na 1 pohled (mimo nacitani GLB/HDRI)
let _ptModulesPromise = null;

// bot6 2026-08-10 - dulezita oprava: Promise, jednou USTALENY (at uz
// splneny nebo ZAMITNUTY), uz nikdy nezmeni vysledek - kdyby prvni pokus
// o nacteni modulu (napr. prechodny vypadek site k unpkg.com CDN,
// docasne zablokovany pozadavek) selhal, `_ptModulesPromise` by zustal
// navzdy ukazovat na tenhle JEDEN zamitnuty Promise a VSECHNY dalsi
// pokusy behem cele session (dokud se stranka znovu nenacte) by hned
// selhaly se stejnou chybou, bez jakehokoli noveho pokusu o import -
// i kdyby se site mezitim uzdravila. Presne tenhle vzor by vysvetloval
// "poprve to fungovalo (testovaci Playwright relace bota), pak uz ne
// (Robertova samostatna relace v prohlizeci)" - kazda relace ma svou
// vlastni cache, ale UVNITR jedne relace staci jedno prechodne selhani a
// je "rozbito" natrvalo. Oprava: cache se drzi jen PRI USPECHU - pri
// selhani se `_ptModulesPromise` vynuluje, aby dalsi volani zkusilo
// import znovu od nuly.
function _ptLoadModules() {
  if (!_ptModulesPromise) {
    _ptModulesPromise = Promise.all([
      import("three"),
      import("three/addons/loaders/GLTFLoader.js"),
      import("three/addons/loaders/RGBELoader.js"),
      import("three/addons/loaders/EXRLoader.js"),
      import("three-gpu-pathtracer"),
    ]).catch(err => {
      _ptModulesPromise = null;
      throw err;
    });
  }
  return _ptModulesPromise;
}

// Robert 2026-08-10 ("vymen misto pathtracing chci ray tracing" - po
// upresnujici otazce zvolil "klasicky ray tracing - ostre odrazy, bez
// zrneni, rychly"): SSRPass = screen-space ray tracing. Paprsky se
// skutecne trasuji (ray marching v prostoru obrazovky) pro odrazy, ale
// jednim pruchodem a DETERMINISTICKY - zadne vzorkovani, zadne zrneni,
// vysledek prakticky okamzite. Oproti path traceru nema fyzikalne
// presnou globalni iluminaci a odrazi jen to, co je videt na obrazovce
// (vedomy kompromis, viz AskUserQuestion 2026-08-10).
// Nacita se ZVLAST od path traceru (ten zustava nedotceny pro rendery
// nabidek), aby se zbytecne netahal three-gpu-pathtracer, kdyz uzivatel
// chce jen rychly SSR render.
let _ssrModulesPromise = null;
function _ssrLoadModules() {
  if (!_ssrModulesPromise) {
    _ssrModulesPromise = Promise.all([
      import("three/addons/postprocessing/EffectComposer.js"),
      import("three/addons/postprocessing/RenderPass.js"),
      import("three/addons/postprocessing/SSRPass.js"),
    ]).catch(err => {
      _ssrModulesPromise = null; // stejny duvod jako u _ptLoadModules vyse
      throw err;
    });
  }
  return _ssrModulesPromise;
}

// Snimky: pole {pos:{x,y,z}, target:{x,y,z}} (obycejne cisla, NE r128
// THREE.Vector3 - vyhne se krizeni dvou ruznych instanci THREE tridy mezi
// hlavni scenou (r128) a touhle docasnou modernejsi instanci). Vraci pole
// stejne delky, kazda polozka je bud data:image/jpeg;base64,... nebo null
// (selhani jen tohoto snimku).
// Robert 2026-08-10 ("za chodu myslím toto: čerpat hdri i PBR pro 3D scenu
// v nabídce ve sdíleném disku slozka rendering") - HDRI i PBR textura
// hliniku se ctou VZDY ZIVE z prave aktivni slozky na Sdilenem disku (viz
// api/rendering_settings.py), zadne pevne zadratovane cesty - zmena
// aktivni slozky v adminu se projevi hned pri pristim generovani nabidky,
// bez jakehokoli redeploy/zmeny kodu.
async function _fetchActiveRenderingHdri() {
  try {
    const r = await fetch("/api/public/rendering/hdri");
    if (!r.ok) return null;
    const data = await r.json();
    return data.file || null;
  } catch (e) { return null; }
}

async function _fetchActiveRenderingPbr() {
  try {
    const r = await fetch("/api/public/rendering/pbr");
    if (!r.ok) return null;
    const data = await r.json();
    return (data.roles && Object.keys(data.roles).length) ? data.roles : null;
  } catch (e) { return null; }
}

// GLTFLoader prejmenovava duplicitni uzly (N kusu stejneho dilu = N uzlu se
// STEJNYM puvodnim jmenem "bomgrp_<idx>") na bomgrp_<idx>, bomgrp_<idx>_1,
// bomgrp_<idx>_2... (stejny jev, stejne reseno jako v nabidka-online.html).
const BOMGRP_NAME_RE = /^bomgrp_(\d+)(?:_\d+)*$/;

// Sdilena pomocna funkce (bot3, 2026-08-10) - nacte aktivni PBR sadu
// hliniku ze Sdileneho disku a aplikuje ji na vsechny mesh potomky
// root uzlu `modelRoot.children`, pro ktere `isAluRootName(node.name)`
// vrati true. Puvodne jen uvnitr capturePathTracedOfferViews (predikat
// tam byl natvrdo BOMGRP_NAME_RE + aluGroupIndices), vytazeno ven, aby
// stejnou logiku (vc. dlazdicovani/uv2 pro AO mapu) mohl pouzit i
// samostatny panel "Render (test)" (viz renderCurrentViewStandalone)
// bez kopie 40 radku kodu, ktera by se casem rozjela do dvou verzi.
// Robert 2026-08-10 ("porad tam neni ta textura zapecena, ty nevis jak to
// udelat?") - SKUTECNA PRICINA konecne nalezena: katalogove GLB modely
// profilu NEMAJI ZADNE UV SOURADNICE. Overeno primo v souborech
// (rozparsovana GLB JSON hlavicka `webapp/katalog/profil_*.glb`):
// kazdy primitiv ma jen atributy POSITION a NORMAL, TEXCOORD_0 chybi
// UPLNE. Bez UV nema three.js kam texturu "nalepit" - shader vzorkuje
// porad jeden a tentyz texel, takze cely dil vypada jako PLOCHA BARVA a
// budi presne dojem "textura se neaplikovala", i kdyz je kod spravne a
// textury se nactou v poradku. Ziva scena si toho nikdy nevsimla,
// protoze pouziva jen jednobarevne materialy bez textur.
//
// Reseni bez prekopavani vsech katalogovych modelu: UV se DOPOCITAJI za
// behu boxovou (planarni podle dominantni osy normaly) projekci - pro
// hranate hlinikove profily je to prakticky idealni mapovani, protoze
// kazda stena je rovina kolma na nekterou osu. Vysledne UV jsou rovnou
// ve "dlazdicich" (delka/TILE_MM), takze texture.repeat zustava 1:1.
function ensureBoxUVs(THREE2, geometry, tileMm) {
  if (geometry.attributes.uv) return false; // uz ma vlastni UV - nesahat
  const pos = geometry.attributes.position;
  if (!pos) return false;
  const nor = geometry.attributes.normal;
  const uv = new Float32Array(pos.count * 2);
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
    let nx = 0, ny = 1, nz = 0;
    if (nor) { nx = Math.abs(nor.getX(i)); ny = Math.abs(nor.getY(i)); nz = Math.abs(nor.getZ(i)); }
    let u, v;
    if (nx >= ny && nx >= nz) { u = z; v = y; }        // stena kolma na X
    else if (ny >= nx && ny >= nz) { u = x; v = z; }   // kolma na Y
    else { u = x; v = y; }                              // kolma na Z
    uv[i * 2] = u / tileMm;
    uv[i * 2 + 1] = v / tileMm;
  }
  geometry.setAttribute("uv", new THREE2.BufferAttribute(uv, 2));
  return true;
}

// Robert 2026-08-10 ("porad neni zapecena textura" - poctvrte): misto
// dalsiho hadani vraci funkce ted DIAGNOSTIKU (kolik uzlu odpovidalo
// predikatu, kolik meshu dostalo material, kolika se dopocitalo UV,
// ktere mapy se skutecne nacetly) - panel Render ji vypise, takze je
// hned videt, JESTLI se PBR vubec aplikuje, nebo se jen vizualne
// neprojevuje (napr. prilis velka dlazdice = extremni priblizeni
// textury, viz tileMm parametr).
async function applyAluPbrTextures(THREE2, modelRoot, isAluRootName, tileMm) {
  const stats = { matchedNodes: 0, meshes: 0, uvGenerated: 0, maps: [], error: null };
  let pbrRoles;
  try {
    pbrRoles = await _fetchActiveRenderingPbr();
  } catch (err) {
    stats.error = "načtení seznamu PBR souborů selhalo: " + (err.message || err);
    return stats;
  }
  if (!pbrRoles) { stats.error = "v adminu není nastavená aktivní PBR sada"; return stats; }
  try {
    const texLoader = new THREE2.TextureLoader();
    const [baseColorTex, normalTex, roughTex, metalTex, aoTex] = await Promise.all([
      pbrRoles.baseColor ? texLoader.loadAsync(pbrRoles.baseColor.url) : null,
      pbrRoles.normal ? texLoader.loadAsync(pbrRoles.normal.url) : null,
      pbrRoles.roughness ? texLoader.loadAsync(pbrRoles.roughness.url) : null,
      pbrRoles.metallic ? texLoader.loadAsync(pbrRoles.metallic.url) : null,
      pbrRoles.ambientOcclusion ? texLoader.loadAsync(pbrRoles.ambientOcclusion.url) : null,
    ]);
    // Velikost jedne "dlazdice" textury na dilu (mm). UV se dopocitavaji
    // primo v techto jednotkach (viz ensureBoxUVs), takze repeat zustava
    // 1:1 - drivejsi `repeat.set(1000/TILE_MM, 80/TILE_MM)` predpokladal
    // UV v rozsahu 0-1 od exporteru, ktere ale v katalogovych modelech
    // vubec nejsou (viz komentar u ensureBoxUVs).
    // POZOR na velikost dlazdice: pri 150mm zabere jedna dlazdice na
    // 40mm sirokem profilu jen ~27 % obrazku - takove priblizeni z
    // jemneho kartacovaneho hliniku udela hladkou plochu a vypada to,
    // ze "textura tam neni". Proto je ted nastavitelna posuvnikem
    // (viz renderOpts.textureTileMm v panelu Render).
    // Vychozi 40mm (drive 150mm - viz komentar o extremnim priblizeni
    // vyse). Plati i pro produkcni render nabidky, ktery vlastni hodnotu
    // nepredava.
    const TILE_MM = (tileMm && tileMm > 0) ? tileMm : 40;
    [baseColorTex, normalTex, roughTex, metalTex, aoTex].forEach(t => {
      if (!t) return;
      t.wrapS = t.wrapT = THREE2.RepeatWrapping;
      t.repeat.set(1, 1);
    });
    if (baseColorTex) baseColorTex.colorSpace = THREE2.SRGBColorSpace;
    if (baseColorTex) stats.maps.push("baseColor");
    if (normalTex) stats.maps.push("normal");
    if (roughTex) stats.maps.push("roughness");
    if (metalTex) stats.maps.push("metallic");
    if (aoTex) stats.maps.push("AO");

    modelRoot.children.forEach(node => {
      if (!isAluRootName(node.name || "")) return;
      stats.matchedNodes++;
      node.traverse(n => {
        if (!n.isMesh) return;
        stats.meshes++;
        if (ensureBoxUVs(THREE2, n.geometry, TILE_MM)) stats.uvGenerated++;
        n.material = new THREE2.MeshStandardMaterial({
          map: baseColorTex || undefined, normalMap: normalTex || undefined,
          roughnessMap: roughTex || undefined, metalnessMap: metalTex || undefined,
          aoMap: aoTex || undefined, aoMapIntensity: 1.0,
          metalness: metalTex ? 1.0 : 0.6, roughness: roughTex ? 1.0 : 0.4,
          // flatShading VYPNUTO - u textrovaneho povrchu vypadaji tvrde
          // fasety hure nez hladke stinovani z normal mapy.
          flatShading: false,
          // Robert ("udelej kod podle tohoto" - realisticke-renderovani
          // navod): envMapIntensity zesiluje odlesky z HDRI prostredi
          // (ptScene.environment), side:FrontSide je vychozi hodnota
          // MeshStandardMaterial, nastaveno explicitne pro jistotu/
          // shodu s navodem.
          envMapIntensity: 1.2,
          side: THREE2.FrontSide,
        });
        // AO mapa potrebuje DRUHOU UV sadu. V three.js r152+ se druha sada
        // jmenuje "uv1" (drive "uv2") - stary nazev by se tise ignoroval.
        if (aoTex && n.geometry.attributes.uv && !n.geometry.attributes.uv1) {
          n.geometry.setAttribute("uv1", n.geometry.attributes.uv);
        }
      });
    });
    return stats;
  } catch (err) {
    console.warn("PBR textura hliníku se nepodařila načíst, dílům zůstává původní materiál.", err);
    stats.error = (err && (err.message || err)) + "";
    return stats;
  }
}

// Robert 2026-08-10 ("udelej kod podle tohoto" -
// https://jirkasa.github.io/threejs-navod/tutorial/realisticke-renderovani/):
// zakladni "realisticke" nastaveni rendereru podle navodu, prevedeno na
// nazvy API aktualni verze three.js (r169 - "outputEncoding"/
// "physicallyCorrectLights" z navodu uz v teto verzi neexistuji,
// nahrazeny "outputColorSpace" a fyzikalne spravnym chovanim jako
// vychozim). toneMappingExposure=0.5 tlumi prepalene svetla/odlesky z
// HDRI, shadowMap.enabled zapina promitani stinu (bez tohohle by
// castShadow/receiveShadow priznaky na mesich/svetlech nemely zadny
// efekt - presne stejne jako uz ma hlavni ziva scena, viz `renderer.
// shadowMap.enabled` vyse v souboru).
function applyRealisticRendererDefaults(ptRenderer, THREE2) {
  ptRenderer.toneMapping = THREE2.ACESFilmicToneMapping;
  ptRenderer.toneMappingExposure = 0.5;
  ptRenderer.outputColorSpace = THREE2.SRGBColorSpace;
  ptRenderer.shadowMap.enabled = true;
  ptRenderer.shadowMap.type = THREE2.PCFSoftShadowMap;
}

// Stinove smerove svetlo (podle navodu) - VZDY pridano, bez ohledu na
// to, jestli je aktivni HDRI (environment mapa dava odlesky/ambientni
// osvetleni, ale ZADNY jasne smerovany stin) - jinak by PBR (rychly,
// ne-path-tracovany) rezim nemel zadny kontaktni stin pod sestavou.
// Shadow-camera frustum se skaluje podle skutecne velikosti sestavy
// (maxDim z bounding boxu), aby stin pokryl celou sestavu bez ohledu
// na to, jak velky/maly kus se prave renderuje (navod pouziva pevne
// cislo 1.2, to ale plati jen pro jejich metrovou scenu - nase je v mm).
function addShadowCastingLight(THREE2, ptScene, maxDim, intensity) {
  const dir = new THREE2.DirectionalLight(0xffffff, intensity != null ? intensity : 1.5);
  dir.position.set(maxDim * 0.6, maxDim * 0.9, maxDim * 0.7);
  dir.castShadow = true;
  const frustum = maxDim * 0.75;
  dir.shadow.mapSize.width = 1024;
  dir.shadow.mapSize.height = 1024;
  dir.shadow.camera.left = -frustum;
  dir.shadow.camera.right = frustum;
  dir.shadow.camera.top = frustum;
  dir.shadow.camera.bottom = -frustum;
  dir.shadow.camera.near = 1;
  dir.shadow.camera.far = maxDim * 4;
  dir.shadow.bias = -0.0005;
  dir.shadow.camera.updateProjectionMatrix();
  ptScene.add(dir);
  ptScene.add(dir.target);
}

// Robert 2026-08-10 (test panelu "Render": "objekt je moc daleko" +
// "nejak to chce urcovat pred renderem nastaveni kamery"): slepe
// kopirovani zive kamery/pohledu koncilo se sestavou vyplnujici jen
// malou cast zaberu (zavisi na tom, jak byla zrovna zive priblizena/
// oddalena, coz pro fotorealisticky close-up neni to prave nastaveni).
// Tahle funkce misto toho prepocita VZDALENOST od stredu bounding boxu
// CELE sestavy tak, aby sestava zabrala rozumnou cast zaberu, PRI
// ZACHOVANI smeru pohledu (uhlu), ktery uz kamera/shot ma - jen se
// "posune po stejne primce" na spravnou vzdalenost. Vraci {pos, target}
// jako obycejne {x,y,z} objekty (stejna konvence jako shots pouzivane
// v capturePathTracedOfferViews).
function fitCameraToScene(pos, target, fovDeg, marginFactor) {
  const box = bboxOfEntries(placed);
  if (box.isEmpty()) return { pos, target };
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z) || 1000;
  const dir = new THREE.Vector3(pos.x - target.x, pos.y - target.y, pos.z - target.z);
  if (dir.lengthSq() < 1e-6) dir.set(0, 0.4, 1); // pojistka - shodny bod, vezmi vychozi smer
  dir.normalize();
  const fovRad = (fovDeg || 45) * Math.PI / 180;
  // marginFactor = okraj kolem sestavy (posuvnik "Priblizeni" v panelu
  // Render; 1.6 = puvodni pevna hodnota, pouzita i kdyz volajici nic
  // nepreda - napr. produkcni render nabidky).
  const fitDistance = (maxDim / 2) / Math.tan(fovRad / 2) * (marginFactor || 1.6);
  const newPos = center.clone().addScaledVector(dir, fitDistance);
  return {
    pos: { x: newPos.x, y: newPos.y, z: newPos.z },
    target: { x: center.x, y: center.y, z: center.z },
  };
}

// Robert 2026-08-10 ("podivej se na tu nabidku je ulozena" -> zjisteno v
// nginx logu, ze /views-3d se vubec nezkusilo zavolat - path tracer
// selhal CELY, driv nez cokoli poslal): ray tracing bezi cely v
// prohlizeci, takze jeho JS chyby server normalne vubec nevidi -
// diagnostika dosud vyzadovala rucni otevreni konzole. Best-effort
// (nikdy nesmi shodit zbytek toku) hlaseni na novy endpoint
// /path-trace-error, at je pripadne dalsi selhani hned videt v
// `journalctl -u konfigurator`, ne jen v konzoli admina.
function _reportPathTraceError(offerId, stage, err) {
  try {
    fetch(`/api/admin/scene-offers/${offerId}/path-trace-error`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage, message: (err && (err.stack || err.message)) || String(err) }),
    }).catch(() => {});
  } catch (e) { /* ignoruj - hlaseni chyby nesmi samo zpusobit dalsi chybu */ }
}

async function capturePathTracedOfferViews(glbBuffer, shots, aluGroupIndices, onProgress, offerId) {
  let THREE2, GLTFLoader2, RGBELoader2, EXRLoader2, WebGLPathTracer;
  try {
    [THREE2, { GLTFLoader: GLTFLoader2 }, { RGBELoader: RGBELoader2 }, { EXRLoader: EXRLoader2 }, { WebGLPathTracer }] = await _ptLoadModules();
  } catch (err) {
    console.warn("Path tracer: načtení modulů selhalo, používám běžný snímek.", err);
    if (offerId) _reportPathTraceError(offerId, "load-modules", err);
    return shots.map(() => null);
  }

  const w = renderer.domElement.width, h = renderer.domElement.height;
  const canvas = document.createElement("canvas");
  canvas.width = w; canvas.height = h;
  let ptRenderer, pathTracer;
  const results = [];
  try {
    ptRenderer = new THREE2.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
    ptRenderer.setSize(w, h, false);
    applyRealisticRendererDefaults(ptRenderer, THREE2);

    const ptScene = new THREE2.Scene();
    const loader = new GLTFLoader2();
    const gltf = await loader.parseAsync(glbBuffer, "");
    const modelRoot = gltf.scene;
    modelRoot.traverse(n => { if (n.isMesh) { n.castShadow = true; n.receiveShadow = true; } });
    const sceneBboxSize = bboxOfEntries(placed).getSize(new THREE.Vector3());
    const sceneMaxDim = Math.max(sceneBboxSize.x, sceneBboxSize.y, sceneBboxSize.z, 100); // min. 100mm - pojistka proti 0/prazdne scene

    // PBR textura hliniku (aktivni sada na Sdilenem disku) - aplikuje se
    // JEN na meshe uvnitr bomgrp_<idx> uzlu, kde idx patri "alu" vrstve
    // (viz aluGroupIndices, sestaveno v generateSceneOffer). Ostatni dily
    // (desky, prislusenstvi) si necháváji svuj puvodni material z GLB.
    // Sdilena implementace viz applyAluPbrTextures() vyse.
    if (aluGroupIndices && aluGroupIndices.size) {
      await applyAluPbrTextures(THREE2, modelRoot, (name) => {
        const m = BOMGRP_NAME_RE.exec(name);
        return !!m && aluGroupIndices.has(parseInt(m[1], 10));
      });
    }
    ptScene.add(modelRoot);

    // Stejna podlaha jako ma zivá scéna vizuálně navozovat (jen jednoduchá
    // rovina pro kontaktní stín, presna barva neni kriticka).
    const groundGeo = new THREE2.PlaneGeometry(2000, 2000);
    const groundMat = new THREE2.MeshStandardMaterial({ color: 0x9a9a9a, roughness: 0.95, metalness: 0 });
    const ground = new THREE2.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.5;
    ground.receiveShadow = true;
    ptScene.add(ground);
    addShadowCastingLight(THREE2, ptScene, sceneMaxDim);

    // HDRI - aktivni sada na Sdilenem disku (viz vyse), NE aktivni HDRI
    // zive interaktivni sceny (activeHdriFile) - ty dva systemy jsou
    // zamerne oddelene (Robert: "Ve 3D scéně budem používat to co máme
    // pbr"). Bez aktivni HDRI padneme na obycejna svetla (WebGLPathTracer
    // umi prevzit THREE.DirectionalLight/HemisphereLight primo ze sceny).
    // Robert ("pozadi nesmi byt aktivni, hdri mapa skryta"): HDRI se
    // pouziva JEN pro odlesky/osvetleni (environment), NIKDY jako
    // viditelne pozadi za sestavou - realna fotka v HDRI mape jinak
    // vizualne "spolkla" mensi/vzdalenejsi vypadajici sestavu a
    // zavadela dojmem, ze kamera je spatne nastavena. Pozadi je proto
    // VZDY neutralni barva, bez ohledu na to, jestli HDRI existuje.
    let envLoaded = false;
    ptScene.background = new THREE2.Color(0xd8dadd);
    try {
      const hdriFile = await _fetchActiveRenderingHdri();
      if (hdriFile) {
        const HdriLoaderCls2 = hdriFile.ext === "exr" ? EXRLoader2 : RGBELoader2;
        const hdriTex = await new HdriLoaderCls2().loadAsync(hdriFile.url);
        hdriTex.mapping = THREE2.EquirectangularReflectionMapping;
        ptScene.environment = hdriTex;
        envLoaded = true;
      }
    } catch (err) {
      console.warn("Path tracer: HDRI se nepodařilo načíst, používám základní světla.", err);
    }
    if (!envLoaded) {
      // OPRAVA: puvodni pevna pozice (4,6,5) byla v jednotkach metru z
      // puvodniho navodu/priklad - nase scena je v MM, takze svetlo
      // skoncilo prakticky uvnitr dilu misto nad nim. Skalovano stejne
      // jako addShadowCastingLight vyse.
      const hemi = new THREE2.HemisphereLight(0xffffff, 0x444444, 1.2);
      ptScene.add(hemi);
      const dir = new THREE2.DirectionalLight(0xffffff, 2.5);
      dir.position.set(sceneMaxDim * 0.4, sceneMaxDim * 0.6, sceneMaxDim * 0.5);
      ptScene.add(dir);
    }

    const ptCamera = new THREE2.PerspectiveCamera(camera.fov, w / h, camera.near, camera.far);
    pathTracer = new WebGLPathTracer(ptRenderer);
    pathTracer.filterGlossyFactor = 0.5;

    for (let i = 0; i < shots.length; i++) {
      const shot = fitCameraToScene(shots[i].pos, shots[i].target, camera.fov);
      ptCamera.position.set(shot.pos.x, shot.pos.y, shot.pos.z);
      ptCamera.lookAt(shot.target.x, shot.target.y, shot.target.z);
      ptCamera.updateProjectionMatrix();
      pathTracer.setScene(ptScene, ptCamera);

      const t0 = performance.now();
      let samples = 0;
      while (performance.now() - t0 < PATHTRACE_TIME_BUDGET_MS) {
        pathTracer.renderSample();
        samples++;
        // Robert ("na nekolik desitek sekund mi to rozbilo/znepristupnilo
        // scenu po vytvoreni nabidky") - OPRAVA: drive se hlavni vlakno
        // uvolnovalo (await setTimeout) jen kazdy 6. vzorek, takze mezi
        // uvolnenimi bezelo 6x renderSample() za sebou synchronne -
        // dost dlouho, aby to citelne "zamrzlo" zbytek stranky (vc.
        // hlavni 3D sceny, kterou uz uzivatel po zobrazeni "Nabidka
        // ulozena" muze chtit hned dal pouzivat, viz runPathTraceUpgrade -
        // ray tracing uz od te zmeny bezi NA POZADI, ne jako blokujici
        // krok pred zobrazenim nabidky, takze tenhle problem je ted
        // konecne VIDET). Uvolneni je ted po KAZDEM vzorku - nakladny
        // onProgress preview snimek (toDataURL) se ale porad dela jen
        // kazdy 6. vzorek, at neni sam o sobe zbytecnou zateze navic.
        if (samples % 6 === 0 && onProgress) {
          // Robert ("chci v malem okne videt ray tracing než se vytvoří
          // nabídka") - onProgress dostava ZIVY renderer, ne jen cisla,
          // aby volajici mohl obcas snapshotnout aktualni (jeste
          // konvergujici) obraz do maleho nahledoveho okna. Levnejsi
          // kvalita (0.6) nez finalni ulozeny snimek (0.9) - je to jen
          // docasny, rychle se prepisujici nahled.
          onProgress(i, shots.length, samples, ptRenderer);
        }
        await new Promise(r => setTimeout(r, 0)); // uvolni hlavni vlakno po KAZDEM vzorku
      }
      // Robert ("3D pohled 2: neplatný formát obrázku") - toDataURL() umi
      // za urcitych okolnosti (ztraceny/degradovany WebGL kontext, napr.
      // po vycerpani GPU pameti behem predchoziho snimku) VRATIT "data:,"
      // (zadna skutecna obrazova data) MISTO vyhozeni vyjimky - takovy
      // retezec je porad "pravdivy" (truthy), takze by prosel kolem
      // `if (ptB) view3d_b = ptB;` v generateSceneOffer() a prepsal
      // funkcni rastrovany fallback timhle nevalidnim datovym URI, ktery
      // pak backend odmitl. Explicitni kontrola tvaru retezce - nevalidni
      // vysledek se posle jako null (stejne jako skutecna vyjimka), aby
      // volajici spolehlivě spadl zpet na puvodni rastrovany snimek.
      const dataUrl = ptRenderer.domElement.toDataURL("image/jpeg", 0.9);
      results.push(/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/=]+$/.test(dataUrl) ? dataUrl : null);
    }
  } catch (err) {
    console.warn("Path tracer: renderování selhalo, používám běžný snímek.", err);
    if (offerId) _reportPathTraceError(offerId, "render", err);
    while (results.length < shots.length) results.push(null);
  } finally {
    // bot6 2026-08-10 - dulezity dodatek: WebGLRenderer.dispose() uvolni
    // jen interni cache (textury/geometrie), NE samotny WebGL kontext.
    // Kazde volani teto funkce vytvari NOVY <canvas> + NOVY WebGL2
    // kontext (viz vyse) - bez explicitniho forceContextLoss() by
    // prohlizec pri OPAKOVANEM generovani nabidky ve stejnem tabu
    // postupne vycerpal svuj limit soucasnych WebGL kontextu (typicky
    // 8-16), coz by po nekolika pokusech zpusobilo selhani vytvoreni
    // DALSIHO kontextu (throw v konstruktoru WebGLRenderer) - navenek by
    // to vypadalo jako "nahodne prestalo fungovat po pár nabídkách".
    try { if (pathTracer) pathTracer.dispose(); } catch (e) { /* ignoruj */ }
    try { if (ptRenderer) ptRenderer.dispose(); } catch (e) { /* ignoruj */ }
    try { if (ptRenderer) ptRenderer.forceContextLoss(); } catch (e) { /* ignoruj */ }
  }
  while (results.length < shots.length) results.push(null); // pojistka pri castecnem selhani
  return results;
}

// Zivy 3D model pro online nabidku (Robert: "3D model ne jako nahledy
// ale rovnou jako zivy model") - export SKUTECNE geometrie (ne
// screenshot). GLTFExporter.parse() v teto pinned verzi NEMA onError
// callback (jen onDone) - selhani/zaseknuti se proto hlida rucnim
// timeoutem, ne jen try/catch. placed[].object3d se posila PRIMO jako
// pole (GLTFExporter to podporuje, NEPREPARENTUJE vstupni objekty -
// bez vedlejsich ucinku na zivou scenu). Volat vzdy AZ PO
// setTechnicalDrawingMode(false) (stejne misto jako snimky view3d_a/b
// o par radku niz) - tou dobou uz maji vsechny dily normalni
// MeshStandardMaterial bez textur, zadne exotictve shadery.
function exportSceneAsGlb() {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("GLTFExporter timeout")), 20000);
    try {
      new THREE.GLTFExporter().parse(
        placed.map(e => e.object3d),
        (result) => { clearTimeout(timer); resolve(result); },
        { binary: true, onlyVisible: true }
      );
    } catch (err) {
      clearTimeout(timer);
      reject(err);
    }
  });
}

// Robert 2026-08-10 ("navrhuji nejdrive vygenerovat nabidku s okny pro
// rendery (abych vedel kde to cekat kdyby to nevyslo) a teprve pote
// vytvorit rendery a ty tam vlozit"): dobehnouci krok PO uspesnem
// vytvoreni nabidky (viz generateSceneOffer nize, volani BEZ await) -
// nabidka uz existuje a je pouzitelna s rastrovymi 3D nahledy, tahle
// funkce jen zkusi fotorealisticky (ray-traced) render a kdyz uspeje,
// dodatecne ho ulozi pres PATCH-like endpoint /views-3d. Selhani v
// jakekoli fazi nema vliv na uz existujici/zobrazenou nabidku - jen se
// o nem napise samostatny radek do statusEl, at je vzdy jasne VIDET
// vysledek (uspech/castecny uspech/selhani s duvodem), ne jen v konzoli
// (presne to Robert driv nahlasil: "V nabídce jsem ovšem neviděl žádný
// nový render").
let lastOfferNumber = null; // posledni nabidka vytvorena v teto relaci - vychozi cil pro "Pridat do nabidky"

// Robert 2026-08-11 ("ty dva automaticke pohledy nastavim... podivam se
// kamerou na objekt a pri stisku nejakych klaves se to ulozi jako pozice
// pro kameru"): Ctrl+Shift+1 a Ctrl+Shift+2 ulozi AKTUALNI smer pohledu
// kamery jako zaber 1/2 pro automaticke rendery nabidky, Ctrl+Shift+0
// oba smaze (vrati automatiku: aktualni pohled + 120 stupnu). Uklada se
// jen SMER (azimut + vyska) - render pak vzdy miri na stred sestavy s
// automatickym odstupem, takze na presne pozici/zoomu nezalezi.
// localStorage = plati pro tenhle prohlizec, prezije obnoveni stranky.
const OFFER_RENDER_SHOTS_KEY = "logimanOfferRenderShots";

// ---------------------------------------------------------------------------------------------------------------
// ONLINE NABIDKA = vzhled jako u karet (bot4 2026-10-01, Robert: "renderovani v online nabidce musi mit i stejne
// pozadi jako automat na karty", "materialy stejne jako na Vandru"): k renderu se posila i ZAPIS DILU sceny (to, co
// uklada sestava). Server z nej postavi stejny job jako u karty (sablona X30-02, pozadi, HDRI, materialy z panelu
// Rendering - viz api/nabidka_kartova_cesta.py). Kdyz to nejde - at server (zadny volny GPU stroj, dil mimo katalog)
// nebo render (chyba Blenderu, stroj se neozval) - zkusi se AUTOMATICKY stara cesta (GLB ze sceny), takze nabidka o
// rendery neprijde. Uzivatel, ktery render zastavil, se nikdy nevraci. Test: scripts/2026-10-01_nabidka_kartova_cesta_testy/.
function buildRenderRecipe() {
  try {
    if (typeof serializeEntryForSave !== "function") return null;
    // nahled rozpracovaneho importu (tmpimport_*) do zapisu nepatri - server ty dily nezna (rada bot8, invariant skillu import-fbx-scena)
    const dily = placed.filter(e => !(typeof isImportPreviewEntry === "function" && isImportPreviewEntry(e)));
    if (!dily.length) return null;
    const text = JSON.stringify(dily.map(e => serializeEntryForSave(e)));
    return text.length <= 1900000 ? text : null;
  } catch (e) { return null; }
}

async function renderViewWithFallback(glb, settings, recipe, opt) {
  const cesty = recipe ? ["karta", "stara"] : ["stara"];
  for (let k = 0; k < cesty.length; k++) {
    const cesta = cesty[k];
    const fd = new FormData();
    fd.append("model", new Blob([glb], { type: "model/gltf-binary" }), "model.glb");
    fd.append("settings", JSON.stringify(settings));
    if (cesta === "karta") fd.append("recipe", recipe);
    try {
      const r0 = await fetch("/api/admin/blender-render", { method: "POST", body: fd });
      const d0 = await r0.json().catch(() => ({}));
      if (!r0.ok || !d0.job_id) throw new Error(d0.error || ("HTTP " + r0.status));
      const jakKarta = d0.cesta === "karta";
      if (opt.onJob) opt.onJob(d0.job_id, jakKarta);
      const t0 = Date.now();
      let lastPrev = "";
      while (true) {
        await new Promise(r => setTimeout(r, 3000));
        if (Date.now() - t0 > opt.timeoutMs) throw new Error("render trvá přes " + Math.round(opt.timeoutMs / 60000) + " minut");
        const sr = await fetch(`/api/admin/blender-render/${d0.job_id}` + (opt.progressive ? `?have=${encodeURIComponent(lastPrev)}` : ""));
        const sd = await sr.json().catch(() => ({}));
        if (!sr.ok) throw new Error(sd.error || ("HTTP " + sr.status));
        if (sd.preview && opt.onPreview) { opt.onPreview(sd.preview); lastPrev = String(sd.preview_mtime || ""); }
        if (sd.state === "done") return { image: sd.image, sd, jakKarta, jobId: d0.job_id };
        if (sd.state === "cancelled") { const e = new Error(sd.error || "Render byl zrušen."); e.zruseno = true; e.sd = sd; throw e; }
        if (sd.state === "error") throw new Error(sd.error || "Render selhal.");
        if (opt.onWait) opt.onWait(sd, Math.round((Date.now() - t0) / 1000), jakKarta);
      }
    } catch (err) {
      if (err && err.zruseno) throw err;
      if (cesta === "karta" && k + 1 < cesty.length) { if (opt.onFallback) opt.onFallback((err && err.message) || String(err)); continue; }
      throw err;
    }
  }
}

function cameraDirToAzEl() {
  const dx = camera.position.x - controls.target.x;
  const dy = camera.position.y - controls.target.y;
  const dz = camera.position.z - controls.target.z;
  const r = Math.hypot(dx, dy, dz) || 1;
  return {
    az: Math.atan2(-dz, dx) * 180 / Math.PI,             // three.js Y-up -> Blender azimut
    el: Math.asin(Math.max(-1, Math.min(1, dy / r))) * 180 / Math.PI,
  };
}

function loadOfferRenderShots() {
  try {
    const d = JSON.parse(localStorage.getItem(OFFER_RENDER_SHOTS_KEY) || "{}");
    const ok = (s) => s && isFinite(s.az) && isFinite(s.el);
    return { shot1: ok(d.shot1) ? d.shot1 : null, shot2: ok(d.shot2) ? d.shot2 : null };
  } catch (e) { return { shot1: null, shot2: null }; }
}

function saveOfferRenderShot(slot) {
  const d = loadOfferRenderShots();
  const v = cameraDirToAzEl();
  d["shot" + slot] = { az: Math.round(v.az * 10) / 10, el: Math.round(v.el * 10) / 10 };
  try { localStorage.setItem(OFFER_RENDER_SHOTS_KEY, JSON.stringify(d)); } catch (e) {}
  showJoinToast(`📷 Pohled ${slot} pro automatické rendery nabídky uložen (azimut ${Math.round(v.az)}°, výška ${Math.round(v.el)}°).`);
}

window.addEventListener("keydown", (ev) => {
  if (!ev.ctrlKey || !ev.shiftKey || ev.altKey) return;
  // Robert 2026-08-11 ("ctrl shift 1 nic nezahlasilo"): funguje i
  // jednicka na numericke klavesnici (code Numpad1), ne jen v horni rade.
  const code = ev.code.replace("Numpad", "Digit");
  if (code !== "Digit1" && code !== "Digit2" && code !== "Digit0") return;
  const tag = (ev.target && ev.target.tagName) || "";
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
  ev.preventDefault();
  if (code === "Digit0") {
    try { localStorage.removeItem(OFFER_RENDER_SHOTS_KEY); } catch (e) {}
    showJoinToast("📷 Uložené pohledy pro rendery nabídky smazány - zpět na automatiku (aktuální pohled + 120°).");
    return;
  }
  saveOfferRenderShot(code === "Digit1" ? 1 : 2);
});

// Robert 2026-08-11 ("urcite chci nastavit napr 2 pohledy kamery
// (rendery) automaticke, a pripadne si nejaky dodelam rucne"): po
// vytvoreni nabidky se AUTOMATICKY vyrenderuji oba zabery (A/B) pres
// Blender/Cycles - stejna cesta jako panel Render, jen s kamerou
// prenesenou ze sceny (camera_position/camera_target/camera_fov_deg).
// Hotove obrazky prepisi rastrove nahledy nabidky pres /views-3d, uplne
// stejne jako driv path tracer. Kdyz Blender selze (server i notebook
// nedostupne, chyba exportu...), spadne to zpet na puvodni prohlizecovy
// path tracer (runPathTraceUpgrade nize) - nabidka NIKDY nezustane bez
// 3D nahledu. Rucni rendery si Robert dela v panelu Render a pripojuje
// tlacitkem "Pridat do nabidky" (galerie Vizualizace).
async function runOfferRenderUpgrade(modelGlb, shotA, shotB, aluGroupIndices, offerId, offerNumber) {
  const statusEl = document.getElementById("offerStatus");
  const note = (text) => {
    if (!statusEl) return;
    const el = document.createElement("div");
    el.style.cssText = "margin-top:4px;font-size:12px;";
    el.textContent = text;
    statusEl.appendChild(el);
  };
  try {
    const settings = readBlenderOptions();
    settings.progressive_preview = false; // nahledy tu nikdo nesleduje, jen by render zdrzely
    // bot4 2026-10-01 (Robert: "Online nabidky se musi renderovat na Omen"): ucel renderu; stroj vybira server
    // (api/render_worker.py::stroj_pro_ucel) a kdyz Omen nejde pouzit, jde render na GPU stanici jako dosud.
    settings.ucel = "nabidka";
    // Robert 2026-08-11 ("automaticke rendery musi mit ruzne uhly
    // pohledu" + "na stred os, tam vzdy umistim objekt"): neprebira se
    // presna pozice kamery (ta muze byt prilis blizko/daleko), ale jen
    // SMER pohledu - render miri vzdy na stred objektu s automatickym
    // odstupem (camera_distance_factor), takze se sestava vzdy vejde
    // cela do zaberu. Zaber 1 = ze smeru, kterym se zrovna divas;
    // zaber 2 = otoceny o 120 stupnu a z vetsiho nadhledu.
    const dir = {
      x: shotA.pos.x - shotA.target.x,
      y: shotA.pos.y - shotA.target.y,
      z: shotA.pos.z - shotA.target.z,
    };
    const rDist = Math.hypot(dir.x, dir.y, dir.z) || 1;
    // three.js (Y nahoru) -> Blender (Z nahoru): azimut v pudorysu XZ
    const azDeg = Math.atan2(-dir.z, dir.x) * 180 / Math.PI;
    const elDeg = Math.asin(Math.max(-1, Math.min(1, dir.y / rDist))) * 180 / Math.PI;
    // Pohledy ulozene klavesami Ctrl+Shift+1/2 maji prednost; bez nich
    // automatika = aktualni pohled + otoceni o 120 stupnu s nadhledem.
    const saved = loadOfferRenderShots();
    const shots = [
      saved.shot1 || { az: azDeg, el: Math.max(8, Math.min(70, elDeg)) },
      saved.shot2 || { az: azDeg + 120, el: Math.max(30, Math.min(70, elDeg + 25)) },
    ];
    const images = [];
    const recipe = buildRenderRecipe();     // zapis dilu pro vzhled jako u karet (null = jen stara cesta)
    let kartou = 0;
    for (let i = 0; i < 2; i++) {
      const s = Object.assign({}, settings, {
        camera_azimuth_deg: shots[i].az,
        camera_elevation_deg: shots[i].el,
      });
      const vysl = await renderViewWithFallback(modelGlb, s, recipe, {
        timeoutMs: 10 * 60 * 1000,
        onWait: (sd, el, jakKarta) => {
          if (statusEl) statusEl.textContent = `Fotorealistický render nabídky (Blender${jakKarta ? ", vzhled jako u karet" : ""}, pohled ${i + 1}/2)… ${el} s`;
        },
        onFallback: (duvod) => note(`ℹ Pohled ${i + 1}: vzhled jako u karet nešel (${duvod}), renderuji starou cestou.`),
      });
      images.push(vysl.image);
      if (vysl.jakKarta) kartou++;
    }
    // Robert 2026-08-11 ("napsalo se, ale neni to tam"): rendery se driv
    // ukladaly JEN do dvou pevnych 3D nahledu (view_3d_a/b) - jenze ty
    // jsou v online nabidce prakticky neviditelne (na strance 3D pohledu
    // se zobrazuje zivy model, obrazky jsou jen zaloha). Hlavni cil je
    // proto GALERIE na strance "Vizualizace" (a tim i slozka Rendery
    // nabidek/<cislo> na Sdilenem disku); pevne nahledy se aktualizuji
    // navic (hodi se pro PDF a jako zaloha, kdyz se zivy model nenacte).
    for (let i = 0; i < images.length; i++) {
      const gr = await fetch(`/api/admin/scene-offers/${offerId}/renders`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: images[i], caption: `Pohled ${i + 1}` }),
      });
      if (!gr.ok) {
        const gd = await gr.json().catch(() => ({}));
        throw new Error("uložení do galerie nabídky selhalo: " + (gd.error || ("HTTP " + gr.status)));
      }
    }
    const r = await fetch(`/api/admin/scene-offers/${offerId}/views-3d`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ view3d_a: images[0], view3d_b: images[1] }),
    });
    if (!r.ok) console.warn("Aktualizace pevných 3D náhledů selhala (galerie už je uložená).");
    note(`✓ Fotorealistický render (Blender/Cycles) doplněn do nabídky ${offerNumber} - stránka „Vizualizace" (2 pohledy) + Sdílený disk / Rendery nabídek.${kartou === images.length ? " Vzhled jako u karet." : ""}`);
  } catch (err) {
    console.warn("Blender render nabídky selhal, zkouším prohlížečový path tracer:", err);
    note(`⚠ Blender render nabídky se nezdařil (${err.message || err}) - zkouším záložní ray tracing v prohlížeči…`);
    await runPathTraceUpgrade(modelGlb, shotA, shotB, aluGroupIndices, offerId, offerNumber);
  }
}

async function runPathTraceUpgrade(modelGlb, shotA, shotB, aluGroupIndices, offerId, offerNumber) {
  const ptPreviewEl = document.getElementById("offerPathTracePreview");
  const statusEl = document.getElementById("offerStatus");
  if (ptPreviewEl) ptPreviewEl.style.display = "";
  let pathTraceNote;
  try {
    const [ptA, ptB] = await capturePathTracedOfferViews(modelGlb, [shotA, shotB], aluGroupIndices, (i, total, samples, liveRenderer) => {
      if (ptPreviewEl && liveRenderer) {
        const liveDataUrl = liveRenderer.domElement.toDataURL("image/jpeg", 0.6);
        if (/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/=]+$/.test(liveDataUrl)) ptPreviewEl.src = liveDataUrl;
      }
    }, offerId);
    if (ptA || ptB) {
      // Robert 2026-08-11 ("nejak se v tom ztracis"): JEDNO pravidlo pro
      // vsechny cesty - kazdy render nabidky (i tenhle zalozni) konci v
      // galerii Vizualizace + na Sdilenem disku. Zadne obrazky, ktere
      // jsou "ulozene, ale nikde nejsou videt".
      const pts = [ptA, ptB];
      for (let i = 0; i < pts.length; i++) {
        if (!pts[i]) continue;
        await fetch(`/api/admin/scene-offers/${offerId}/renders`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image: pts[i], caption: `Pohled ${i + 1}` }),
        }).catch(() => {});
      }
      const body = {};
      if (ptA) body.view3d_a = ptA;
      if (ptB) body.view3d_b = ptB;
      const r = await fetch(`/api/admin/scene-offers/${offerId}/views-3d`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        pathTraceNote = `⚠ Fotorealistický render nabídky ${offerNumber} se vygeneroval, ale nepodařilo se ho uložit.`;
      } else if (ptA && ptB) {
        pathTraceNote = `✓ Fotorealistický render (ray tracing) doplněn do nabídky ${offerNumber} (oba 3D náhledy).`;
      } else {
        pathTraceNote = `⚠ Fotorealistický render doplněn jen pro 1 ze 2 3D náhledů nabídky ${offerNumber}, druhý zůstal běžný snímek.`;
      }
    } else {
      pathTraceNote = `⚠ Fotorealistický render (ray tracing) se pro nabídku ${offerNumber} nepodařilo vygenerovat, zůstává s běžnými 3D náhledy.`;
    }
  } catch (err) {
    console.warn("Path tracer selhal (nabídka zůstává s běžnými 3D náhledy):", err);
    pathTraceNote = `⚠ Fotorealistický render (ray tracing) nabídky ${offerNumber} se nezdařil (${err.message || err}).`;
  } finally {
    if (ptPreviewEl) { ptPreviewEl.style.display = "none"; ptPreviewEl.removeAttribute("src"); }
  }
  if (statusEl) {
    const noteEl = document.createElement("div");
    noteEl.style.cssText = "margin-top:4px;font-size:12px;";
    noteEl.textContent = pathTraceNote;
    statusEl.appendChild(noteEl);
  }
}

// Robert 2026-08-10 ("navrhuji nejdrive vychytat to renderování bokem" +
// "chce to nove tlacitko render, po stisknuti se otevre natahovaci panel
// do sceny, a vyrenderuje presne to co vidim, muj pohled kamerou"):
// SAMOSTATNY diagnosticky/pouzitelny nastroj, uplne nezavisly na
// generateSceneOffer()/nabidce - zadny GLB upload, zadne ukladani na
// server, jen presny aktualni pohled kamerou (camera.position/
// controls.target primo, ZADNY druhy otoceny uhel jako u nabidky)
// vyrenderovany ray tracingem. NA ROZDIL od capturePathTracedOfferViews
// (ktera chyby zamerne polyka a vraci jen null, aby nikdy nerozbila
// generovani nabidky) tahle funkce chybu VZDY zobrazi rovnou v panelu
// jako citelny text - ucel je prave DIAGNOSTIKA/rychle vyzkouseni, ne
// tichy fallback.
// Robert 2026-08-10 ("udelej ruzna dulezita nastaveni... formou
// posuvniku at si to muzu nastavit"): zive nastavitelne parametry
// renderu (viz #renderPanelSection v HTML). Vychozi hodnoty odpovidaji
// tomu, co bylo drive natvrdo v kodu (expozice 0.5 a envMapIntensity
// 1.2 primo z navodu jirkasa.github.io, zbytek stavajici chovani), takze
// "Vychozi hodnoty" vrati presne dosavadni vzhled.
const RENDER_OPT_DEFAULTS = {
  exposure: 0.5, envIntensity: 1.2, lightIntensity: 1.5,
  roughness: 1, textureTileMm: 40, zoom: 1.6, ssrDistance: 2,
  hdriBackground: false, ground: true,
};
const RENDER_OPT_STORAGE_KEY = "sceneRenderPanelOptions";
const RENDER_OPT_SLIDERS = [
  { key: "exposure", id: "renderOptExposure", digits: 2 },
  { key: "envIntensity", id: "renderOptEnvIntensity", digits: 1 },
  { key: "lightIntensity", id: "renderOptLightIntensity", digits: 1 },
  { key: "roughness", id: "renderOptRoughness", digits: 2 },
  { key: "textureTileMm", id: "renderOptTextureTile", digits: 0 },
  { key: "zoom", id: "renderOptZoom", digits: 2 },
  { key: "ssrDistance", id: "renderOptSsrDistance", digits: 1 },
];

// Robert 2026-08-10 ("chci tam mit plne nastavovani jako v blenderu" +
// screenshot Render Properties): nastaveni serveroveho Blender/Cycles
// renderu. Klice odpovidaji 1:1 tomu, co ocekava POST
// /api/admin/blender-render (api/blender_render.py -> NUM_LIMITS), aby
// slo pridat dalsi parametr jen na tehle dvou mistech. Popisky v UI
// zamerne pouzivaji ORIGINALNI blenderovske nazvy (Max Samples, Noise
// Threshold, Light Paths...), at je to dohledatelne v dokumentaci
// Blenderu.
const BLENDER_OPT_SLIDERS = [
  { key: "samples", id: "blOptSamples", digits: 0 },
  { key: "min_samples", id: "blOptMinSamples", digits: 0 },
  { key: "noise_threshold", id: "blOptNoiseThreshold", digits: 3 },
  { key: "time_limit_s", id: "blOptTimeLimit", digits: 0 },
  { key: "max_bounces", id: "blOptMaxBounces", digits: 0 },
  { key: "diffuse_bounces", id: "blOptDiffuseBounces", digits: 0 },
  { key: "glossy_bounces", id: "blOptGlossyBounces", digits: 0 },
  { key: "transmission_bounces", id: "blOptTransmissionBounces", digits: 0 },
  { key: "volume_bounces", id: "blOptVolumeBounces", digits: 0 },
  { key: "transparent_bounces", id: "blOptTransparentBounces", digits: 0 },
  { key: "clamp_direct", id: "blOptClampDirect", digits: 1 },
  { key: "clamp_indirect", id: "blOptClamp", digits: 1 },
  { key: "exposure", id: "blOptExposure", digits: 1 },
  { key: "gamma", id: "blOptGamma", digits: 2 },
  { key: "hdri_strength", id: "blOptHdriStrength", digits: 1 },
  { key: "hdri_rotation_deg", id: "blOptHdriRotation", digits: 0 },
  { key: "sun_energy", id: "blOptSunEnergy", digits: 1 },
  { key: "sun_softness_deg", id: "blOptSunSoftness", digits: 1 },
  { key: "sun_azimuth_deg", id: "blOptSunAzimuth", digits: 0 },
  { key: "sun_elevation_deg", id: "blOptSunElevation", digits: 0 },
  { key: "camera_lens_mm", id: "blOptLens", digits: 0 },
  { key: "camera_distance_factor", id: "blOptCamDist", digits: 1 },
  { key: "camera_azimuth_deg", id: "blOptCamAzimuth", digits: 0 },
  { key: "camera_elevation_deg", id: "blOptCamElevation", digits: 0 },
  { key: "dof_fstop", id: "blOptFstop", digits: 1 },
  { key: "texture_tile_mm", id: "blOptTile", digits: 0 },
  { key: "normal_strength", id: "blOptNormalStrength", digits: 1 },
  { key: "metallic", id: "blOptMetallic", digits: 2 },
  { key: "roughness_mat", id: "blOptRoughnessMat", digits: 2 },
  { key: "coat_weight", id: "blOptCoat", digits: 2 },
  { key: "resolution_x", id: "blOptResX", digits: 0 },
  { key: "resolution_y", id: "blOptResY", digits: 0 },
];
const BLENDER_OPT_CHECKBOXES = [
  { key: "adaptive_sampling", id: "blOptAdaptive" },
  { key: "sun_enabled", id: "blOptSun" },
  { key: "hdri_as_background", id: "blOptHdriBg" },
  { key: "floor_enabled", id: "blOptFloor" },
  { key: "floor_dots", id: "blOptFloorDots" },
  { key: "transparent_background", id: "blOptTransparentBg" },
  { key: "dof_enabled", id: "blOptDof" },
  { key: "shade_smooth", id: "blOptSmooth" },
  { key: "use_pbr_textures", id: "blOptUseTextures" },
  { key: "use_normal_map", id: "blOptUseNormalMap" },
  { key: "progressive_preview", id: "blOptProgressive" },
  { key: "use_denoising", id: "blOptDenoise" },
];
// Vyber textury/HDRI a barva materialu (Robert 2026-08-11: "chci mit
// moznost zmenit texturu a shading nodes") - jine typy vstupu nez
// posuvnik/zatrzitko, proto vlastni seznamy.
const BLENDER_OPT_SELECTS_VALUE = [
  { key: "pbr_folder_id", id: "blOptPbrSet" },
  { key: "hdri_file_id", id: "blOptHdriFile" },
];
const BLENDER_OPT_SELECTS = [
  { key: "view_transform", id: "blOptViewTransform" },
  { key: "floor_pattern", id: "blOptFloorPattern" },
  { key: "look", id: "blOptLook" },
];
const BLENDER_OPT_STORAGE_KEY = "sceneBlenderRenderOptions";

function readBlenderOptions() {
  const o = {};
  BLENDER_OPT_SLIDERS.forEach(s => {
    const el = document.getElementById(s.id);
    if (el) o[s.key] = parseFloat(el.value);
  });
  BLENDER_OPT_CHECKBOXES.forEach(c => {
    const el = document.getElementById(c.id);
    if (el) o[c.key] = el.checked;
  });
  BLENDER_OPT_SELECTS.forEach(s => {
    const el = document.getElementById(s.id);
    if (el) o[s.key] = el.value;
  });
  BLENDER_OPT_SELECTS_VALUE.forEach(s => {
    const el = document.getElementById(s.id);
    if (el && el.value) o[s.key] = el.value;
  });
  const colorEl = document.getElementById("blOptBaseColor");
  if (colorEl) {
    // #rrggbb -> [r,g,b] 0..1 (Blender pracuje s linearnimi 0-1 slozkami)
    const hex = colorEl.value.replace("#", "");
    o.base_color = [0, 2, 4].map(i => parseInt(hex.substr(i, 2), 16) / 255);
    o.base_color_hex = colorEl.value;
  }
  // roughness_mat je v UI zvlast (aby nekolidoval s prohlizecovym
  // "Drsnost hliniku"), server ale ceka klic "material_roughness"
  if (o.roughness_mat != null) o.material_roughness = o.roughness_mat;
  if (o.metallic != null) o.material_metallic = o.metallic;
  return o;
}

function applyBlenderOptionsToUi(o) {
  BLENDER_OPT_SLIDERS.forEach(s => {
    const el = document.getElementById(s.id);
    const valEl = document.getElementById(s.id + "Val");
    if (el && o[s.key] != null) el.value = o[s.key];
    if (el && valEl) valEl.textContent = parseFloat(el.value).toFixed(s.digits);
  });
  BLENDER_OPT_CHECKBOXES.forEach(c => {
    const el = document.getElementById(c.id);
    if (el && o[c.key] != null) el.checked = !!o[c.key];
  });
  BLENDER_OPT_SELECTS.forEach(s => {
    const el = document.getElementById(s.id);
    if (el && o[s.key]) el.value = o[s.key];
  });
  BLENDER_OPT_SELECTS_VALUE.forEach(s => {
    const el = document.getElementById(s.id);
    if (el && o[s.key]) el.value = o[s.key];
  });
  const colorEl = document.getElementById("blOptBaseColor");
  if (colorEl && o.base_color_hex) colorEl.value = o.base_color_hex;
}

function persistBlenderOptions() {
  try {
    const o = readBlenderOptions();
    o._defaults_version = BLENDER_OPT_DEFAULTS_VERSION; // viz initBlenderOptionsUi
    localStorage.setItem(BLENDER_OPT_STORAGE_KEY, JSON.stringify(o));
  } catch (e) { /* ignoruj */ }
}

// Robert 2026-09-09 ("vespod je zpet na výchozí, přidej i tabulku
// ulozených nastavení, aby se dalo mezi nimi prepinat") - "Vychozi
// hodnoty" resetovalo jen na PEVNE tovarni cisla; tohle jsou navic
// JMENOVANA ulozena nastaveni (vlastni "profily"), mezi kterymi
// prehlizi/prepina prostou tabulkou radku v panelu. localStorage,
// per prohlizec - stejne jako "posledni pouzite" (BLENDER_OPT_STORAGE_KEY).
const BLENDER_OPT_PRESETS_KEY = "sceneBlenderRenderPresets";

function resetBlenderOptionsToDefaults() {
  // el.defaultValue/defaultChecked = puvodni HTML atribut value="…"/
  // checked, nezavisle na tom, co uzivatel od te doby nastavil - takze
  // "vychozi" jsou vzdy presne ty, co vidi kdokoli s cistym prohlizecem,
  // beze nutnosti duplikovat cisla znovu tady v JS.
  BLENDER_OPT_SLIDERS.forEach(s => {
    const el = document.getElementById(s.id);
    const valEl = document.getElementById(s.id + "Val");
    if (!el) return;
    el.value = el.defaultValue;
    if (valEl) valEl.textContent = parseFloat(el.value).toFixed(s.digits);
  });
  BLENDER_OPT_CHECKBOXES.forEach(c => {
    const el = document.getElementById(c.id);
    if (el) el.checked = el.defaultChecked;
  });
  BLENDER_OPT_SELECTS.forEach(s => {
    const el = document.getElementById(s.id);
    if (!el || !el.options.length) return;
    const def = Array.prototype.find.call(el.options, o => o.defaultSelected);
    el.value = (def || el.options[0]).value;
  });
  const colorEl = document.getElementById("blOptBaseColor");
  if (colorEl) colorEl.value = colorEl.defaultValue;
  persistBlenderOptions();
}

function loadBlOptPresets() {
  try { return JSON.parse(localStorage.getItem(BLENDER_OPT_PRESETS_KEY) || "{}") || {}; }
  catch (e) { return {}; }
}

function saveBlOptPresets(presets) {
  try { localStorage.setItem(BLENDER_OPT_PRESETS_KEY, JSON.stringify(presets)); } catch (e) { /* ignoruj */ }
}

function renderBlOptPresetsList() {
  const list = document.getElementById("blOptPresetsList");
  if (!list) return;
  const presets = loadBlOptPresets();
  const names = Object.keys(presets).sort((a, b) => a.localeCompare(b, "cs"));
  list.innerHTML = "";
  if (!names.length) {
    const empty = document.createElement("div");
    empty.style.cssText = "font-size:11px;color:var(--text-muted);";
    empty.textContent = "Zatím žádná uložená nastavení.";
    list.appendChild(empty);
    return;
  }
  names.forEach(name => {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;align-items:center;gap:6px;font-size:12px;";
    const nameBtn = document.createElement("button");
    nameBtn.type = "button";
    nameBtn.className = "linklike-btn";
    nameBtn.style.cssText = "flex:1;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;";
    nameBtn.textContent = "▸ " + name;
    nameBtn.title = "Načíst toto nastavení";
    nameBtn.addEventListener("click", () => {
      applyBlenderOptionsToUi(presets[name]);
      persistBlenderOptions();
      showJoinToast(`Nastavení „${name}“ načteno.`);
    });
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "linklike-btn";
    delBtn.style.cssText = "flex:none;color:var(--error);";
    delBtn.title = "Smazat";
    delBtn.textContent = "✕";
    delBtn.addEventListener("click", () => {
      if (!confirm(`Smazat uložené nastavení „${name}“?`)) return;
      const p = loadBlOptPresets();
      delete p[name];
      saveBlOptPresets(p);
      renderBlOptPresetsList();
    });
    row.appendChild(nameBtn);
    row.appendChild(delBtn);
    list.appendChild(row);
  });
}

(function initBlOptPresetsUi() {
  renderBlOptPresetsList();
  const saveBtn = document.getElementById("btnBlOptSaveAsPreset");
  if (!saveBtn) return;
  saveBtn.addEventListener("click", () => {
    const name = (prompt("Název nového uloženého nastavení:") || "").trim();
    if (!name) return;
    const presets = loadBlOptPresets();
    if (presets[name] && !confirm(`Nastavení „${name}“ už existuje. Přepsat?`)) return;
    presets[name] = readBlenderOptions();
    saveBlOptPresets(presets);
    renderBlOptPresetsList();
    showJoinToast(`Nastavení „${name}“ uloženo.`);
  });
})();

// Robert 2026-08-11 ("bílé... to není hliník"): panel si pamatuje
// hodnoty v localStorage, takze kdyz zmenime VYCHOZI hodnoty (novy
// hlinikovejsi material, AgX, mekci slunce), stare ulozene hodnoty je
// prebiji a uzivatel zmenu nikdy neuvidi. Verze niz rika, ke kterym
// defaultum ulozene hodnoty patri - pri zvyseni verze se ulozene
// hodnoty JEDNOU zahodi a nactou se nove vychozi.
const BLENDER_OPT_DEFAULTS_VERSION = 4;

(function initBlenderOptionsUi() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(BLENDER_OPT_STORAGE_KEY) || "{}") || {}; } catch (e) { saved = {}; }
  if (saved._defaults_version !== BLENDER_OPT_DEFAULTS_VERSION) {
    saved = {};
    try {
      localStorage.removeItem(BLENDER_OPT_STORAGE_KEY);
      localStorage.setItem(BLENDER_OPT_STORAGE_KEY, JSON.stringify({ _defaults_version: BLENDER_OPT_DEFAULTS_VERSION }));
    } catch (e) { /* ignoruj */ }
  }
  if (Object.keys(saved).length) applyBlenderOptionsToUi(saved);
  // Firefox pri obnoveni stranky obnovuje stav formularovych prvku ze
  // session (nezavisle na localStorage i HTML) - Robert 2026-08-11 tak
  // videl "Pouzit PBR textury" vypnute, i kdyz je vychozi zapnute.
  // autocomplete="off" (v HTML vyse) tomu brani; tohle je druha pojistka:
  // co neni ulozene, vratit na HTML default.
  BLENDER_OPT_CHECKBOXES.forEach(c => {
    const el = document.getElementById(c.id);
    if (el && saved[c.key] == null) el.checked = el.defaultChecked;
  });
  BLENDER_OPT_SLIDERS.forEach(sl => {
    const el = document.getElementById(sl.id);
    if (el && saved[sl.key] == null) el.value = el.defaultValue;
  });
  BLENDER_OPT_SLIDERS.forEach(s => {
    const el = document.getElementById(s.id);
    const valEl = document.getElementById(s.id + "Val");
    if (!el) return;
    el.addEventListener("input", () => {
      if (valEl) valEl.textContent = parseFloat(el.value).toFixed(s.digits);
      persistBlenderOptions();
    });
  });
  [...BLENDER_OPT_CHECKBOXES, ...BLENDER_OPT_SELECTS, ...BLENDER_OPT_SELECTS_VALUE,
   { id: "blOptBaseColor" }].forEach(c => {
    const el = document.getElementById(c.id);
    if (el) el.addEventListener("change", persistBlenderOptions);
  });
  // Robert 2026-08-11 ("rozdel to na kategorie a udelej je sbalovaci"):
  // sekce se prepinaji podle rezimu - blenderove volby jen pro Blender,
  // prohlizecove jen pro PBR/SSR. Drive visely v panelu VSECHNY naraz,
  // takze v Blender rezimu byly videt i nefunkcni prohlizecove posuvniky
  // (a "Meritko textury" dokonce 2x - viz Robertuv screenshot).
  function syncBlenderOptsVisibility() {
    const mode = queryRenderPanelMode();
    // Robert 2026-09-09 ("dej tam jen 2 možnosti blender/cycles a ten
    // Luxcore"): LuxCore jede stejnou cestou jako Blender/Cycles (export
    // GLB + POST na server, viz nize) - jen jiny engine (blender_render_
    // scene.py::renderer) - sdili tedy i stejne UI sekce (kamera/
    // sampling/material), i kdyz cast poli (Cycles-specificky sampling)
    // LuxCore renderu nema vliv.
    const isBlender = !!mode && (mode.value === "blender" || mode.value === "luxcore");
    const blWrap = document.getElementById("blenderOptsWrap");
    if (blWrap) blWrap.style.display = isBlender ? "flex" : "none";
    const matWrap = document.getElementById("blenderMaterialWrap");
    if (matWrap) matWrap.style.display = isBlender ? "" : "none";
    const brWrap = document.getElementById("browserOptsWrap");
    if (brWrap) brWrap.style.display = isBlender ? "none" : "";
    const presetsWrap = document.getElementById("blOptPresetsWrap");
    if (presetsWrap) presetsWrap.style.display = isBlender ? "flex" : "none";
  }
  document.querySelectorAll('input[name="renderPanelMode"]').forEach(r => {
    r.addEventListener("change", syncBlenderOptsVisibility);
  });
  syncBlenderOptsVisibility();

  // Robert 2026-08-11 ("proc je tam toto, kdyz jsme v cycles?"):
  // Base Color / Metallic / Roughness JSOU regulerni vstupy Principled
  // BSDF (Cycles je pouziva uplne stejne jako prohlizecovy render), ale
  // pri zapnutych PBR texturach je textura PREBIJI - posuvniky pak
  // nemaji zadny ucinek. Nechavat je aktivni je matouci, takze se
  // zasedi a doplni se vysvetlujici popisek podle aktualniho stavu.
  // Robert 2026-08-11 ("zamceli se posuvniky, to je spatne"): posuvniky
  // uz se NEZAMYKAJI. Puvodni predpoklad "textura prebiji vsechny tri"
  // byl navic vecne spatny - zalezi, ktere mapy vybrana sada obsahuje
  // (napr. Hlinik_1 nema metallic mapu, takze posuvnik Metallic PLATI).
  // Misto zamykani se jen zesvetli popisek u kanalu, ktery textura
  // opravdu prebiji, a popisek presne rekne, co plati.
  const PBR_ROLE_TO_ROW = { baseColor: "blOptBaseColor", roughness: "blOptRoughnessMat", metallic: "blOptMetallic" };
  let pbrRolesBySet = {};   // folder_id -> [role], + "" pro vychozi sadu
  function syncMaterialPlainState() {
    const useTex = document.getElementById("blOptUseTextures");
    const on = !useTex || useTex.checked;
    const setSel = document.getElementById("blOptPbrSet");
    const roles = on ? (pbrRolesBySet[(setSel && setSel.value) || ""] || null) : [];
    const overridden = [];
    Object.entries(PBR_ROLE_TO_ROW).forEach(([role, inputId]) => {
      const inp = document.getElementById(inputId);
      const row = inp && inp.closest(".render-opt-row");
      if (!inp || !row) return;
      inp.disabled = false;                       // nikdy nezamykat
      // roles === null = sadu zatim neznáme (nenacetla se) -> nic nesedime
      const isOver = roles ? roles.indexOf(role) >= 0 : false;
      row.classList.toggle("is-inactive", isOver);
      if (isOver) overridden.push(row.querySelector("label") ? row.querySelector("label").textContent : role);
    });
    const note = document.getElementById("materialPlainNote");
    if (note) {
      if (!on) note.textContent = "Textury vypnuté – hliník se vykreslí podle hodnot výše (hladký kov).";
      else if (!roles) note.textContent = "Zapnuté PBR textury přebíjejí ty kanály, pro které má vybraná sada mapu; ostatní posuvníky platí.";
      else if (overridden.length) note.textContent = `Vybraná sada přebíjí: ${overridden.join(", ")}. Ostatní posuvníky se použijí normálně.`;
      else note.textContent = "Vybraná sada nemá žádnou z těchto map – všechny posuvníky se použijí.";
    }
  }
  const useTexEl = document.getElementById("blOptUseTextures");
  if (useTexEl) useTexEl.addEventListener("change", syncMaterialPlainState);
  const pbrSetEl = document.getElementById("blOptPbrSet");
  if (pbrSetEl) pbrSetEl.addEventListener("change", syncMaterialPlainState);
  syncMaterialPlainState();

  // Zapamatovat, ktere sbalovaci sekce si uzivatel nechal otevrene.
  try {
    const openState = JSON.parse(localStorage.getItem("sceneRenderGroupsOpen") || "{}") || {};
    document.querySelectorAll("#renderPanelSection details.render-group").forEach((d, i) => {
      const key = d.id || ("g" + i);
      if (openState[key] != null) d.open = !!openState[key];
      d.addEventListener("toggle", () => {
        try {
          const st = JSON.parse(localStorage.getItem("sceneRenderGroupsOpen") || "{}") || {};
          st[key] = d.open;
          localStorage.setItem("sceneRenderGroupsOpen", JSON.stringify(st));
        } catch (e) { /* ignoruj */ }
      });
    });
  } catch (e) { /* ignoruj - sbalovani funguje i bez pameti */ }

  // Naplnit nabidku PBR sad a HDRI map ze Sdileneho disku (viz
  // GET /api/admin/blender-render/assets). Selhani je nekriticke -
  // zustane volba "vychozi z administrace".
  fetch("/api/admin/blender-render/assets")
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data) return;
      pbrRolesBySet = { "": data.default_pbr_roles || [] };
      (data.pbr_sets || []).forEach(s => { pbrRolesBySet[String(s.folder_id)] = s.roles || []; });
      const pbrSel = document.getElementById("blOptPbrSet");
      if (pbrSel) (data.pbr_sets || []).forEach(s => {
        const o = document.createElement("option");
        o.value = s.folder_id;
        o.textContent = `${s.name} (${(s.roles || []).length} map)`;
        pbrSel.appendChild(o);
      });
      const hdriSel = document.getElementById("blOptHdriFile");
      if (hdriSel) (data.hdri || []).forEach(h => {
        const o = document.createElement("option");
        o.value = h.id;
        o.textContent = h.name;
        hdriSel.appendChild(o);
      });
      // obnovit drive vybrane hodnoty (ulozeny stav se aplikoval driv,
      // nez v <select> vubec existovaly polozky)
      try {
        const saved = JSON.parse(localStorage.getItem(BLENDER_OPT_STORAGE_KEY) || "{}") || {};
        if (pbrSel && saved.pbr_folder_id) pbrSel.value = saved.pbr_folder_id;
        if (hdriSel && saved.hdri_file_id) hdriSel.value = saved.hdri_file_id;
      } catch (e) { /* ignoruj */ }
      syncMaterialPlainState();   // ted uz vime, ktere mapy sady maji
    })
    .catch(() => {});
})();

function readRenderOptions() {
  const opts = Object.assign({}, RENDER_OPT_DEFAULTS);
  RENDER_OPT_SLIDERS.forEach(s => {
    const el = document.getElementById(s.id);
    if (el) opts[s.key] = parseFloat(el.value);
  });
  const bgEl = document.getElementById("renderOptHdriBackground");
  if (bgEl) opts.hdriBackground = bgEl.checked;
  const groundEl = document.getElementById("renderOptGround");
  if (groundEl) opts.ground = groundEl.checked;
  return opts;
}

function applyRenderOptionsToUi(opts) {
  RENDER_OPT_SLIDERS.forEach(s => {
    const el = document.getElementById(s.id);
    const valEl = document.getElementById(s.id + "Val");
    if (el && opts[s.key] != null) el.value = opts[s.key];
    if (el && valEl) valEl.textContent = parseFloat(el.value).toFixed(s.digits);
  });
  const bgEl = document.getElementById("renderOptHdriBackground");
  if (bgEl) bgEl.checked = !!opts.hdriBackground;
  const groundEl = document.getElementById("renderOptGround");
  if (groundEl) groundEl.checked = opts.ground !== false;
}

function persistRenderOptions() {
  try { localStorage.setItem(RENDER_OPT_STORAGE_KEY, JSON.stringify(readRenderOptions())); } catch (e) { /* ignoruj */ }
}

(function initRenderOptionsUi() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(RENDER_OPT_STORAGE_KEY) || "{}") || {}; } catch (e) { saved = {}; }
  applyRenderOptionsToUi(Object.assign({}, RENDER_OPT_DEFAULTS, saved));
  RENDER_OPT_SLIDERS.forEach(s => {
    const el = document.getElementById(s.id);
    const valEl = document.getElementById(s.id + "Val");
    if (!el) return;
    el.addEventListener("input", () => {
      if (valEl) valEl.textContent = parseFloat(el.value).toFixed(s.digits);
      persistRenderOptions();
    });
  });
  ["renderOptHdriBackground", "renderOptGround"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", persistRenderOptions);
  });
  const resetBtn = document.getElementById("btnRenderOptReset");
  // Robert 2026-09-09: tlacitko je SDILENE pro oba rezimy (viz HTML - je
  // az PO obou <details> sekcich), ale resetovalo VZDY jen prohlizecove
  // "renderOpt*" hodnoty - v rezimu Blender/LuxCore tedy tise nedelalo
  // nic viditelneho (resetovalo skryte posuvniky). Vetveno podle
  // aktualniho rezimu, viz resetBlenderOptionsToDefaults() nize.
  if (resetBtn) resetBtn.addEventListener("click", () => {
    const mode = queryRenderPanelMode();
    if (mode && (mode.value === "blender" || mode.value === "luxcore")) {
      resetBlenderOptionsToDefaults();
    } else {
      applyRenderOptionsToUi(RENDER_OPT_DEFAULTS);
      persistRenderOptions();
    }
  });
})();

// Robert 2026-08-10 ("to tlacitko render nechej jen nastaveni, ale
// samotny render chci v extra novem okne protoze na obrazovce uz neni
// misto"): vysledek uz se nezobrazuje v panelu (ten zustava jen
// nastavenim), ale ve SKUTECNEM samostatnem okne prohlizece - da se
// odsunout na druhy monitor, zvetsit pres celou obrazovku a nezabira
// misto ve scene.
//
// DULEZITE: okno se musi otevrit SYNCHRONNE hned pri kliku (uvnitr
// uzivatelskeho gesta), jinak ho prohlizec zablokuje jako pop-up -
// proto se otevre PRAZDNE hned na zacatku a obsah se do nej doplnuje
// prubezne, misto aby se otviralo az s hotovym obrazkem.
function openRenderResultWindow() {
  let w;
  try {
    w = window.open("", "logimanRenderVysledek", "width=1200,height=900,scrollbars=yes,resizable=yes");
  } catch (e) { return null; }
  if (!w) return null;
  try {
    if (!w.document.getElementById("renderWinImg")) {
      w.document.open();
      w.document.write(
        '<!doctype html><html lang="cs"><head><meta charset="utf-8"><title>Render – Logiman</title>' +
        '<style>' +
        'html,body{margin:0;height:100%;}' +
        'body{background:#1b1f27;color:#c9d1d9;font-family:-apple-system,"Segoe UI",Roboto,Arial,sans-serif;display:flex;flex-direction:column;}' +
        '#bar{padding:8px 12px;font-size:13px;line-height:1.4;display:flex;gap:14px;align-items:center;border-bottom:1px solid #333a45;flex:none;}' +
        '#renderWinStatus{flex:1;}' +
        '#renderWinDl{color:#9fd0ff;text-decoration:none;border:1px solid #3a4453;border-radius:5px;padding:4px 10px;font-size:12px;white-space:nowrap;}' +
        '#renderWinDl:hover{background:#232a35;}' +
        '#renderWinStop{background:#4a2b2b;color:#ffb4b4;border:1px solid #6b3a3a;border-radius:5px;padding:4px 10px;font-size:12px;cursor:pointer;white-space:nowrap;font-family:inherit;}' +
        '#renderWinStop:hover{background:#5c3434;}' +
        '#renderWinStop:disabled{opacity:.5;cursor:default;}' +
        '#renderWinAttach{background:#1e3a2a;color:#8fe0b0;border:1px solid #2e5c40;border-radius:5px;padding:4px 10px;font-size:12px;cursor:pointer;white-space:nowrap;font-family:inherit;}' +
        '#renderWinAttach:hover{background:#25482f;}' +
        '#renderWinAttach:disabled{opacity:.5;cursor:default;}' +
        '#wrap{flex:1;overflow:auto;display:flex;align-items:center;justify-content:center;padding:12px;box-sizing:border-box;}' +
        'img{max-width:100%;max-height:100%;box-shadow:0 4px 24px rgba(0,0,0,.55);border-radius:4px;}' +
        '</style></head><body>' +
        '<div id="bar" title="Klik na obrázek = 100 % / přizpůsobit oknu, Ctrl+kolečko myši = plynulý zoom"><span id="renderWinStatus">Spouštím render…</span>' +
        '<button id="renderWinStop" style="display:none;">⏹ Zastavit render</button>' +
        '<button id="renderWinAttach" style="display:none;">✚ Přidat do nabídky</button>' +
        '<a id="renderWinDl" download="render.png" style="display:none;">⬇ Stáhnout PNG</a></div>' +
        '<div id="wrap"><img id="renderWinImg" alt="Render"></div>' +
        // Robert 2026-08-11 ("dej mi do okna renderu zooming"): klik na
        // obrazek prepina prizpusobit/100 %, Ctrl+kolecko plynuly zoom.
        // Skript zije primo v okne, takze funguje i pro obrazky pridane
        // pozdeji (testovaci rendery, pohled 1/2).
        '<script>(function(){' +
        'var zoom=0;var wrap=document.getElementById("wrap");' +
        'function apply(){wrap.querySelectorAll("img").forEach(function(img){' +
        'if(zoom<=0){img.style.width="";img.style.maxWidth="100%";img.style.maxHeight="100%";img.style.cursor="zoom-in";}' +
        'else{img.style.maxWidth="none";img.style.maxHeight="none";img.style.width=(img.naturalWidth*zoom)+"px";img.style.cursor="zoom-out";}});' +
        'if(zoom>0){wrap.style.alignItems="flex-start";wrap.style.justifyContent="flex-start";}' +
        'else if(wrap.style.flexDirection!=="column"){wrap.style.alignItems="center";wrap.style.justifyContent="center";}}' +
        'wrap.addEventListener("click",function(e){if(e.target.tagName!=="IMG")return;zoom=zoom?0:1;apply();});' +
        'wrap.addEventListener("wheel",function(e){if(!e.ctrlKey)return;e.preventDefault();' +
        'zoom=Math.min(6,Math.max(0.1,(zoom||0.6)*(e.deltaY<0?1.15:0.87)));apply();},{passive:false});' +
        'new MutationObserver(function(){apply();}).observe(wrap,{childList:true});' +
        '})();<\/script></body></html>'
      );
      w.document.close();
    } else {
      // Znovupouzite okno z predchoziho renderu - vycistit stary vysledek.
      const img = w.document.getElementById("renderWinImg");
      const dl = w.document.getElementById("renderWinDl");
      const at = w.document.getElementById("renderWinAttach");
      if (img) { img.removeAttribute("src"); img.style.display = ""; }
      if (dl) dl.style.display = "none";
      if (at) { at.style.display = "none"; at.onclick = null; }
      // sloty z testovacich renderu (pohled 1/2) z minula
      w.document.querySelectorAll('[id^="renderWinImg"]').forEach(el => {
        if (el.id !== "renderWinImg") el.remove();
      });
    }
    w.focus();
  } catch (e) { /* okno existuje, jen se do nej nepodarilo zapsat */ }
  return w;
}

function renderWinStatus(win, text, isError) {
  if (!win) return;
  try {
    const el = win.document.getElementById("renderWinStatus");
    if (el) { el.textContent = text; el.style.color = isError ? "#ff6b6b" : ""; }
  } catch (e) { /* okno mezitim zavrene */ }
}

// Robert 2026-08-10 ("v blenderu byva tlacitko stop (killer) u cycles
// behem renderovani"): tlacitko Stop primo v okne vysledku. Zobrazuje se
// jen po dobu, kdy render skutecne bezi; klik posle POST na
// /api/admin/blender-render/<job>/cancel (viz api/blender_render.py),
// ktery Blender proces zabije - dotazovaci smycka pak uvidi stav
// "cancelled" a skonci.
function renderWinSetStop(win, onStop) {
  if (!win) return;
  try {
    const btn = win.document.getElementById("renderWinStop");
    if (!btn) return;
    if (!onStop) { btn.style.display = "none"; btn.onclick = null; return; }
    btn.style.display = "";
    btn.disabled = false;
    btn.textContent = "⏹ Zastavit render";
    btn.onclick = () => {
      btn.disabled = true;
      btn.textContent = "Zastavuji…";
      onStop();
    };
  } catch (e) { /* okno mezitim zavrene */ }
}

// Robert 2026-08-11 ("kdyz se mi budou libit chci nekde odkliknout ano
// maji byt soucasti nabidky"): zelene tlacitko primo v okne vysledku.
// Ukazuje se az kdyz je render HOTOVY; klik projde "koleckem" -
// vyber nabidky + volitelny popisek - a posle obrazek na
// POST /api/admin/scene-offers/<id>/renders (galerie "Vizualizace").
function renderWinSetAttach(win, onAttach) {
  if (!win) return;
  try {
    const btn = win.document.getElementById("renderWinAttach");
    if (!btn) return;
    if (!onAttach) { btn.style.display = "none"; btn.onclick = null; return; }
    btn.style.display = "";
    btn.disabled = false;
    btn.textContent = "✚ Přidat do nabídky";
    btn.onclick = () => onAttach(btn, win);
  } catch (e) { /* okno mezitim zavrene */ }
}

// Kolecko schvaleni (viz renderWinSetAttach): dialogy se ptaji v OKNE
// vysledku (ne v hlavni scene, ktera muze byt schovana pod nim).
async function attachRenderToOffer(dataUrl, btn, win) {
  try {
    btn.disabled = true;
    btn.textContent = "Načítám nabídky…";
    const r = await fetch("/api/admin/scene-offers");
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || ("HTTP " + r.status));
    const offers = d.offers || [];
    if (!offers.length) throw new Error("Žádná platná nabídka - nejdřív nabídku vygeneruj.");
    // Vychozi = nabidka vytvorena naposledy v teto relaci, jinak nejnovejsi.
    const dflt = (lastOfferNumber && offers.some(o => o.offer_number === lastOfferNumber))
      ? lastOfferNumber : offers[0].offer_number;
    const nabidky = offers.slice(0, 10).map(o =>
      `${o.offer_number}${o.customer_name ? " – " + o.customer_name : ""}`).join("\n");
    const answer = win.prompt("Do které nabídky render přidat?\n\n" + nabidky + "\n\nZadej číslo nabídky:", dflt);
    if (answer === null) { btn.disabled = false; btn.textContent = "✚ Přidat do nabídky"; return; }
    const chosen = offers.find(o => o.offer_number.toLowerCase() === answer.trim().toLowerCase());
    if (!chosen) throw new Error(`Nabídka "${answer.trim()}" v seznamu není.`);
    const caption = win.prompt("Popisek pod obrázkem (nepovinné):", "") || "";
    btn.textContent = "Ukládám…";
    const ar = await fetch(`/api/admin/scene-offers/${chosen.id}/renders`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: dataUrl, caption: caption.trim() || null }),
    });
    const ad = await ar.json().catch(() => ({}));
    if (!ar.ok) throw new Error(ad.error || ("HTTP " + ar.status));
    btn.textContent = `✓ Přidáno do ${chosen.offer_number}`;
    // Tlacitko zustava aktivni - stejny render jde pridat i do dalsi nabidky.
    setTimeout(() => { try { btn.disabled = false; btn.textContent = "✚ Přidat do nabídky"; } catch (e) {} }, 2500);
  } catch (err) {
    try { win.alert("Render se nepodařilo přidat: " + (err.message || err)); } catch (e) {}
    try { btn.disabled = false; btn.textContent = "✚ Přidat do nabídky"; } catch (e) {}
  }
}

function renderWinShowImage(win, dataUrl, filename, slot) {
  if (!win) return false;
  try {
    const doc = win.document;
    let img;
    if (slot != null) {
      // Vice obrazku pod sebou (testovaci rendery: pohled 1 + pohled 2).
      img = doc.getElementById("renderWinImg" + slot);
      if (!img) {
        const wrap = doc.getElementById("wrap");
        wrap.style.flexDirection = "column";
        wrap.style.justifyContent = "flex-start";
        const base = doc.getElementById("renderWinImg");
        if (base) base.style.display = "none";
        img = doc.createElement("img");
        img.id = "renderWinImg" + slot;
        img.alt = "Render " + (slot + 1);
        img.style.marginBottom = "10px";
        wrap.appendChild(img);
      }
    } else {
      img = doc.getElementById("renderWinImg");
    }
    const dl = doc.getElementById("renderWinDl");
    if (img) img.src = dataUrl;
    if (dl) { dl.href = dataUrl; dl.download = filename || "render.png"; dl.style.display = ""; }
    return true;
  } catch (e) { return false; }
}

async function renderCurrentViewStandalone() {
  const btn = document.getElementById("btnRenderCurrentView");
  const statusEl = document.getElementById("renderPanelStatus");
  const imgEl = document.getElementById("renderPanelImg");
  // Musi byt hned tady (synchronne v ramci kliku) - viz komentar vyse.
  const resultWin = openRenderResultWindow();
  if (!resultWin && statusEl) {
    statusEl.style.color = "#ffb454";
    statusEl.textContent = "Prohlížeč zablokoval nové okno - povol vyskakovací okna pro tuhle stránku (výsledek se zatím zobrazí zde v panelu).";
  }
  const modeInput = queryRenderPanelMode();
  const renderMode = modeInput ? modeInput.value : "blender";
  const renderOpts = readRenderOptions();
  if (!placed.length) {
    if (statusEl) { statusEl.style.color = "#ff6b6b"; statusEl.textContent = "Scéna je prázdná."; }
    return;
  }
  if (btn) btn.disabled = true;
  if (imgEl) imgEl.style.display = "none";
  if (statusEl) { statusEl.style.color = ""; statusEl.textContent = "Exportuji 3D data…"; }

  // Robert 2026-08-10 ("zapoj to do sceny" - Blender/Cycles na serveru):
  // uplne jina cesta nez PBR/SSR vyse - nic se nerenderuje v prohlizeci,
  // jen se posle GLB + nastaveni na server, ktery spusti Blender
  // headless (viz api/blender_render.py) a vrati hotovy PNG.
  if (renderMode === "blender" || renderMode === "luxcore") {
    try {
      const glb = await exportSceneAsGlb();
      const settings = readBlenderOptions();
      // Robert 2026-09-09: LuxCore jako 2. volba vedle Blender/Cycles -
      // stejny export/endpoint, jen jiny vypocetni engine na serveru
      // (viz api/blender_render_scene.py "renderer").
      settings.renderer = renderMode === "luxcore" ? "luxcore" : "cycles";
      const engineLabel = renderMode === "luxcore" ? "LuxCore" : "Blender/Cycles";
      if (statusEl) statusEl.textContent = `Renderuji na serveru (${engineLabel}, ${settings.samples} vzorků)… může to trvat desítky sekund.`;
      const fd = new FormData();
      fd.append("model", new Blob([glb], { type: "model/gltf-binary" }), "model.glb");
      fd.append("settings", JSON.stringify(settings));
      renderWinStatus(resultWin, `Renderuji na serveru (${engineLabel}, ${settings.samples} vzorků)… může to trvat desítky sekund.`);
      // Robert 2026-08-10 ("CHYBA (Blender): HTTP 504"): render UZ
      // NEBEZI uvnitr HTTP pozadavku - server ho jen nastartuje a vrati
      // job_id (gunicorn ma --timeout 60 a nginx proxy_read_timeout 60s,
      // takze cekat na dlouhy render primo v odpovedi znamenalo
      // zabiteho workera + 504, viz api/blender_render.py). Klient se
      // proto ptá na stav, dokud neni hotovo.
      const startResp = await fetch("/api/admin/blender-render", { method: "POST", body: fd });
      const startData = await startResp.json().catch(() => ({}));
      if (!startResp.ok) throw new Error(startData.error || ("HTTP " + startResp.status));
      const jobId = startData.job_id;
      if (!jobId) throw new Error("Server nevrátil ID úlohy.");
      let stoppedByUser = false;
      renderWinSetStop(resultWin, () => {
        stoppedByUser = true;
        fetch(`/api/admin/blender-render/${jobId}/cancel`, { method: "POST" }).catch(() => {});
      });

      // Robert 2026-08-10 ("chci to videt prubezne obraz kazdych 5 sec"):
      // dotaz na stav kazdych 5 s; server pri nem vraci i posledni hotovy
      // PRUCHOD progresivniho renderu (viz blender_render_scene.py -
      // render bezi v nekolika pruchodech 8, 16, 32... vzorku). Aby se
      // stejny nahled netahal porad dokola, posila se zpet jeho
      // `preview_mtime` jako ?have= a server obrazek vynecha, pokud se
      // nezmenil.
      const POLL_MS = 5000;
      const MAX_WAIT_MS = 20 * 60 * 1000; // 20 min - tvrdy strop na strane klienta
      const startedAt = Date.now();
      let data = null;
      let lastPreviewMtime = "";
      while (true) {
        await new Promise(r => setTimeout(r, POLL_MS));
        if (Date.now() - startedAt > MAX_WAIT_MS) {
          throw new Error("Render trvá neúměrně dlouho - přestávám čekat (na serveru možná stále běží).");
        }
        const sr = await fetch(`/api/admin/blender-render/${jobId}?have=${encodeURIComponent(lastPreviewMtime)}`);
        const sd = await sr.json().catch(() => ({}));
        if (!sr.ok) throw new Error(sd.error || ("HTTP " + sr.status));
        const elapsed = Math.round((Date.now() - startedAt) / 1000);
        if (sd.preview) {
          renderWinShowImage(resultWin, sd.preview, "render-blender-nahled.png");
          lastPreviewMtime = String(sd.preview_mtime || "");
        }
        const previewNote = lastPreviewMtime ? " (průběžný náhled)" : "";
        if (sd.state === "queued") {
          renderWinStatus(resultWin, `Čekám ve frontě (jiný render právě běží)… ${elapsed} s`);
        } else if (sd.state === "running") {
          renderWinStatus(resultWin, `Renderuji na serveru (Blender/Cycles, cíl ${settings.samples} vzorků)… ${elapsed} s${previewNote}`);
          if (statusEl) statusEl.textContent = `Renderuji na serveru… ${elapsed} s`;
        } else if (sd.state === "cancelled") {
          // Zastaveni TLACITKEM Stop neni chyba - jen klidna hlaska
          // (na rozdil od zruseni novejsim renderem nebo skutecneho padu).
          if (stoppedByUser || sd.stopped_by_user) {
            renderWinSetStop(resultWin, null);
            const note = "⏹ Render zastaven." + (lastPreviewMtime ? " Zobrazen poslední průběžný náhled." : "");
            renderWinStatus(resultWin, note);
            if (statusEl) { statusEl.style.color = ""; statusEl.textContent = note; }
            return;
          }
          throw new Error(sd.error || "Render byl zrušen novějším renderem.");
        } else if (sd.state === "error") {
          throw new Error((sd.error || "Render selhal.") + (sd.detail ? " — " + sd.detail.slice(-300) : ""));
        } else if (sd.state === "done") {
          data = sd;
          break;
        }
      }
      // Robert 2026-08-11 ("prakticky jsem nepostrehl rozdil ani v kvalite
      // ani v case oproti serveru") - protoze ZADNY jeho render na GPU ve
      // skutecnosti nedobehl (agent behem renderu "mizel", viz oprava v
      // api/render_worker.py). Aby to priste bylo videt na prvni pohled,
      // hlaska rovnou rika, KDE se renderovalo.
      const kde = data.worker_name ? `⚡ ${data.worker_name} (GPU)` : "server (CPU)";
      const info = `✓ Blender hotovo za ${data.render_seconds} s na ${kde}`
        + (data.queue_wait_seconds > 1 ? ` (+ ${data.queue_wait_seconds} s ve frontě)` : "")
        + `, ${settings.resolution_x}×${settings.resolution_y}, ${data.size_kb} kB`
        + `, HDRI: ${data.hdri_used || "žádná"}, textury: ${(data.textures_used || []).join("+") || "žádné"}`;
      const shown = renderWinShowImage(resultWin, data.image, "render-blender.png");
      renderWinStatus(resultWin, info);
      renderWinSetAttach(resultWin, (btn, win) => attachRenderToOffer(data.image, btn, win));
      if (!shown && imgEl) { imgEl.src = data.image; imgEl.style.display = ""; } // okno zavrene/blokovane
      if (statusEl) { statusEl.style.color = ""; statusEl.textContent = info; }
    } catch (err) {
      console.error("Blender render selhal:", err);
      const msg = "✗ CHYBA (Blender): " + ((err && err.message) || String(err));
      renderWinStatus(resultWin, msg, true);
      if (statusEl) {
        statusEl.style.color = "#ff6b6b";
        statusEl.textContent = msg;
      }
    } finally {
      renderWinSetStop(resultWin, null); // render skoncil (jakkoli) - Stop uz nedava smysl
      if (btn) btn.disabled = false;
    }
    return;
  }

  // Robert 2026-08-10 ("malý obrázek a trvá dlouho takže bud je v super
  // rozlišeni, nebo mame nekde kostrbaty prubeh"): presne tak - drivejsi
  // verze renderovala na PLNE rozliseni hlavniho 3D viewportu (vc.
  // devicePixelRatio, na beznem monitoru klidne 3000+ px na delsi hrane),
  // i kdyz se vysledek zobrazuje jen v malem panelu (~300px). Ray tracing
  // (WebGLPathTracer) stoji cas primo umerne poctu pixelu - stejny
  // 9sekundovy casovy rozpocet (PATHTRACE_TIME_BUDGET_MS) tak stihl jen
  // zlomek vzorku na pixel, nez kdyby renderoval v rozliseni, ve kterem se
  // stejne zobrazuje. Rozliseni proto omezeno na RENDER_PANEL_MAX_EDGE na
  // delsi hrane (pomer stran zachovan) - stejny casovy rozpocet dá VIC
  // vzorku na pixel = citelne mene zrnity/hezci vysledek, ne jen rychlejsi.
  const RENDER_PANEL_MAX_EDGE = 900;
  let THREE2, GLTFLoader2, RGBELoader2, EXRLoader2, WebGLPathTracer;
  // ssrComposer MUSI byt deklarovany tady (ne uvnitr try) - uklizi se ve
  // finally bloku, kam by promenna z vnitrniho bloku nebyla videt.
  let ptRenderer, pathTracer, ssrComposer;
  // Docasne oznaceni hlinikovych dilu pred exportem (viz nize, PBR textura) -
  // jmeno se po exportu vzdy vrati zpet, aby "diagnosticky" panel nemel
  // zadny trvaly vedlejsi ucinek na zivou scenu/kusovnik.
  const renamedEntries = [];
  try {
    placed.forEach((e, i) => {
      if (e.part && e.part.layer === "alu") {
        renamedEntries.push({ obj: e.object3d, origName: e.object3d.name });
        e.object3d.name = `renderpreview_alu_${i}`;
      }
    });
    const glbBuffer = await exportSceneAsGlb();
    renamedEntries.forEach(r => { r.obj.name = r.origName; });

    if (statusEl) statusEl.textContent = "Načítám moduly path traceru (CDN)…";
    [THREE2, { GLTFLoader: GLTFLoader2 }, { RGBELoader: RGBELoader2 }, { EXRLoader: EXRLoader2 }, { WebGLPathTracer }] = await _ptLoadModules();

    if (statusEl) statusEl.textContent = "Sestavuji scénu…";
    const liveW = renderer.domElement.width, liveH = renderer.domElement.height;
    const edgeScale = Math.min(1, RENDER_PANEL_MAX_EDGE / Math.max(liveW, liveH));
    const w = Math.round(liveW * edgeScale), h = Math.round(liveH * edgeScale);
    const canvas = document.createElement("canvas");
    canvas.width = w; canvas.height = h;
    ptRenderer = new THREE2.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
    ptRenderer.setSize(w, h, false);
    applyRealisticRendererDefaults(ptRenderer, THREE2);
    ptRenderer.toneMappingExposure = renderOpts.exposure; // posuvnik "Expozice"

    const ptScene = new THREE2.Scene();
    const loader = new GLTFLoader2();
    const gltf = await loader.parseAsync(glbBuffer, "");
    gltf.scene.traverse(n => { if (n.isMesh) { n.castShadow = true; n.receiveShadow = true; } });
    // PBR textura hliniku - stejna sdilena logika/sada jako u oficialnich
    // nabidkovych renderu (viz applyAluPbrTextures vyse), jen dily
    // pozname podle docasneho "renderpreview_alu_*" jmena mista bomgrp_.
    const pbrStats = await applyAluPbrTextures(THREE2, gltf.scene, (name) => name.startsWith("renderpreview_alu_"), renderOpts.textureTileMm);
    // Posuvniky "Odlesky prostredi"/"Drsnost hliniku" - aplikuji se az
    // TED, na hotove materialy (at plati i pro dily bez PBR sady, ktere
    // si nechaly puvodni material z GLB).
    gltf.scene.traverse(n => {
      if (!n.isMesh || !n.material) return;
      const mats = Array.isArray(n.material) ? n.material : [n.material];
      mats.forEach(m => {
        if (m.envMapIntensity !== undefined) m.envMapIntensity = renderOpts.envIntensity;
        if (m.roughness !== undefined) m.roughness = renderOpts.roughness;
        m.needsUpdate = true;
      });
    });
    ptScene.add(gltf.scene);

    // Robert ("vysledek je horsi nez samotna scena"): panel dosud NEMEL
    // zadnou podlahu ani stinove svetlo (na rozdil od capturePathTracedOfferViews,
    // ktera obe ma) - sestava tak "plavala" bez kontaktniho stinu/opory,
    // coz vypadalo hur nez ziva scena s vlastnim gridem/stiny. Doplneno
    // stejne jako u nabidky, ted volitelne pres zatrzitko "Podlaha + stin".
    const sceneBboxSize = bboxOfEntries(placed).getSize(new THREE.Vector3());
    const sceneMaxDim = Math.max(sceneBboxSize.x, sceneBboxSize.y, sceneBboxSize.z, 100);
    if (renderOpts.ground) {
      const groundGeo = new THREE2.PlaneGeometry(sceneMaxDim * 6, sceneMaxDim * 6);
      const groundMat = new THREE2.MeshStandardMaterial({ color: 0x9a9a9a, roughness: 0.95, metalness: 0 });
      const ground = new THREE2.Mesh(groundGeo, groundMat);
      ground.rotation.x = -Math.PI / 2;
      ground.position.y = -0.5;
      ground.receiveShadow = true;
      ptScene.add(ground);
    }
    addShadowCastingLight(THREE2, ptScene, sceneMaxDim, renderOpts.lightIntensity);

    // HDRI jen pro odlesky/osvetleni (environment); jako viditelne pozadi
    // jen kdyz si to uzivatel vyslovne zapne zatrzitkem "HDRI jako pozadi"
    // (Robert puvodne 2026-08-10: "pozadi nesmi byt aktivni, hdri mapa
    // skryta" - proto vychozi stav VYPNUTO, ale at je to zkusitelne).
    let envLoaded = false;
    ptScene.background = new THREE2.Color(0xd8dadd);
    try {
      const hdriFile = await _fetchActiveRenderingHdri();
      if (hdriFile) {
        const HdriLoaderCls2 = hdriFile.ext === "exr" ? EXRLoader2 : RGBELoader2;
        const hdriTex = await new HdriLoaderCls2().loadAsync(hdriFile.url);
        hdriTex.mapping = THREE2.EquirectangularReflectionMapping;
        ptScene.environment = hdriTex;
        if (renderOpts.hdriBackground) ptScene.background = hdriTex;
        envLoaded = true;
      }
    } catch (e) { /* padne na zakladni svetla nize */ }
    if (!envLoaded) {
      const hemi = new THREE2.HemisphereLight(0xffffff, 0x444444, 1.2);
      ptScene.add(hemi);
      const dir = new THREE2.DirectionalLight(0xffffff, 2.5);
      dir.position.set(sceneMaxDim * 0.4, sceneMaxDim * 0.6, sceneMaxDim * 0.5);
      ptScene.add(dir);
    }

    // Smer pohledu (uhel) presne jako aktualni kamera, ale VZDALENOST
    // dopoctena podle bounding boxu sestavy (viz fitCameraToScene vyse -
    // Robert: "objekt je moc daleko" + "nejak to chce urcovat pred
    // renderem nastaveni kamery"). Posuvnik "Priblizeni" meni prave tenhle
    // odstup (nizsi cislo = bliz).
    const fitted = fitCameraToScene(
      { x: camera.position.x, y: camera.position.y, z: camera.position.z },
      { x: controls.target.x, y: controls.target.y, z: controls.target.z },
      camera.fov,
      renderOpts.zoom
    );
    const ptCamera = new THREE2.PerspectiveCamera(camera.fov || 45, w / h, camera.near, camera.far);
    ptCamera.position.set(fitted.pos.x, fitted.pos.y, fitted.pos.z);
    ptCamera.lookAt(fitted.target.x, fitted.target.y, fitted.target.z);
    ptCamera.updateProjectionMatrix();

    let samples = 0;
    if (renderMode === "raytrace") {
      // Robert 2026-08-10 ("vymen misto pathtracing chci ray tracing" ->
      // zvolil "klasicky ray tracing - ostre odrazy, bez zrneni, rychly"):
      // path tracer (WebGLPathTracer, vzorkovaci smycka) VYMENEN za
      // SSRPass - screen-space ray tracing. Paprsky se trasuji pro odrazy,
      // ale jednim deterministickym pruchodem: zadne vzorky, zadne
      // zrneni, hotovo prakticky okamzite. Posuvnik "Pocet vzorku" se v
      // tomhle rezimu uz nepouziva (viz jeho popisek v panelu).
      if (statusEl) statusEl.textContent = "Načítám ray tracing (SSR) moduly…";
      const [{ EffectComposer }, { RenderPass }, { SSRPass }] = await _ssrLoadModules();
      if (statusEl) statusEl.textContent = "Renderuji (ray tracing)…";
      ssrComposer = new EffectComposer(ptRenderer);
      // Odrazive plochy: hlinikove dily + podlaha (SSRPass potrebuje
      // vyslovny seznam meshu, do kterych se ma odrazet).
      const selects = [];
      ptScene.traverse(n => { if (n.isMesh) selects.push(n); });
      const ssrPass = new SSRPass({
        renderer: ptRenderer, scene: ptScene, camera: ptCamera,
        width: w, height: h, groundReflector: null, selects,
      });
      ssrPass.thickness = 0.5;
      ssrPass.maxDistance = sceneMaxDim * renderOpts.ssrDistance; // posuvnik "Dosah odrazu"
      ssrPass.opacity = 1;
      ssrComposer.addPass(new RenderPass(ptScene, ptCamera));
      ssrComposer.addPass(ssrPass);
      ssrComposer.render();
      samples = 1;
    } else {
      // PBR - 1 obycejny rastrovany snimek stejnou scenou/kamerou/PBR
      // texturou/HDRI odlesky jako ray tracing vyse, jen BEZ odrazu
      // okolnich dilu (SSR pruchod).
      if (statusEl) statusEl.textContent = "Renderuji (PBR)…";
      ptRenderer.render(ptScene, ptCamera);
      samples = 1;
    }

    const finalUrl = ptRenderer.domElement.toDataURL("image/jpeg", 0.9);
    if (!/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/=]+$/.test(finalUrl)) {
      throw new Error("toDataURL() vrátil neplatný obrázek (ztracený/degradovaný WebGL kontext?).");
    }
    // Robert ("porad neni zapecena textura"): k vysledku se VZDY vypise,
    // co presne PBR krok udelal - kolik dilu/meshu dostalo texturovany
    // material a kolika se dopocitalo UV. Kdyz tu bude "0 dílů", je
    // problem v rozpoznani dilu; kdyz tu budou cisla a textura presto
    // neni videt, je problem ve VZHLEDU (meritko/expozice), ne v tom,
    // ze by se textura neaplikovala - poprve tak pujde tyhle dve
    // uplne odlisne priciny rozlisit bez hadani.
    const pbrNote = pbrStats && !pbrStats.error
      ? `PBR: ${pbrStats.matchedNodes} dílů / ${pbrStats.meshes} meshů, UV dopočítáno ${pbrStats.uvGenerated}×, mapy: ${pbrStats.maps.join("+") || "žádné"}, dlaždice ${renderOpts.textureTileMm} mm`
      : `PBR NEAPLIKOVÁNO (${(pbrStats && pbrStats.error) || "neznámý důvod"})`;
    const doneNote = (renderMode === "raytrace" ? "✓ Hotovo (ray tracing, ostré odrazy). " : "✓ Hotovo (PBR). ") + pbrNote;
    const shown = renderWinShowImage(resultWin, finalUrl, "render-" + renderMode + ".jpg");
    renderWinSetAttach(resultWin, (btn, win) => attachRenderToOffer(finalUrl, btn, win));
    renderWinStatus(resultWin, doneNote);
    if (!shown && imgEl) { imgEl.src = finalUrl; imgEl.style.display = ""; } // okno zavrene/blokovane
    if (statusEl) { statusEl.style.color = ""; statusEl.textContent = doneNote; }
  } catch (err) {
    console.error("Render aktuálního pohledu selhal:", err);
    const msg = "✗ CHYBA: " + ((err && (err.message || err.stack)) || String(err));
    renderWinStatus(resultWin, msg, true);
    if (statusEl) {
      statusEl.style.color = "#ff6b6b";
      statusEl.textContent = msg;
    }
  } finally {
    try { if (pathTracer) pathTracer.dispose(); } catch (e) { /* ignoruj */ }
    try { if (ssrComposer) ssrComposer.dispose(); } catch (e) { /* ignoruj */ }
    try { if (ptRenderer) ptRenderer.dispose(); } catch (e) { /* ignoruj */ }
    try { if (ptRenderer) ptRenderer.forceContextLoss(); } catch (e) { /* ignoruj */ }
    if (btn) btn.disabled = false;
  }
}
document.getElementById("btnRenderCurrentView").addEventListener("click", renderCurrentViewStandalone);
// Robert 2026-08-10 ("teprve uvnitr okna renderovani bude tlacitko
// start"): tlacitko v hlavnim panelu uz render NESPOUSTI - jen otevre
// okno, at je cas si nejdriv nastavit posuvniky. Samotny render
// spousti az "▶ Start renderu" uvnitr okna.
document.getElementById("btnOpenRenderPanel").addEventListener("click", () => {
  // Panel je zrovna vyjmuty na plose (samostatne okno) - jen ho vytahnout
  // do popredi, ne otevirat prazdny plovouci panel ve scene.
  if (renderPanelPopout && !renderPanelPopout.closed) { renderPanelPopout.focus(); return; }
  if (renderPanelWin) renderPanelWin.show();
});

// Balne v nabidce (Robert 2026-10-01: "nevidim v nabidce cenu za montaz a balne"): souhrn sceny (refreshSummary) pocita Cenu celkem
// vcetne balneho (app_settings.packaging_pct = procento ze souctu vsech uz zaokrouhlenych polozek, POSLEDNI krok), ale nabidka
// ho nikdy neobsahovala - zakaznik dostaval cenu o balne nizsi nez ve scene. Vraci radek kusovniku "Balne (X %)" (jako Cena rezu /
// Cena spoju: bez ceny za kus, bez dilu) nebo null, kdyz je procento 0. Pocita se z VSECH dosavadnich radku, proto se vola az po
// nich a pred souctem total_price. Existujici (drive vytvorene) nabidky se nemeni - jejich ulozena cena balne neobsahuje.
function offerPackagingItem(items) {
  const pct = Number((typeof PRICING_CONFIG !== "undefined" && PRICING_CONFIG && PRICING_CONFIG.packaging_pct) || 0);
  if (!(pct > 0)) return null;
  const subtotal = (items || []).reduce((s, it) => s + (it.total || 0), 0);
  const czk = Math.round(subtotal * pct / 100);
  return czk > 0 ? { name: `Balné (${pct} %)`, dim: "-", qty: "-", unit_price: null, total: czk } : null;
}

// Robert 2026-10-01 ("montaz v online nabidce chci pred vytvorenim nabidky zvolit jako % castku"): sazba montaze PRO TUTO nabidku.
// Cislo 0-100 (0 = bez montaze), prazdne/neplatne = null (= plati vychozi sazba z nastaveni, ziva). Carka i tecka jako desetinny oddelovac.
function offerMontazPctValue(raw) {
  if (raw === null || raw === undefined || raw === "") return null;
  const n = typeof raw === "number" ? raw : parseFloat(String(raw).replace(",", "."));
  return Number.isFinite(n) && n >= 0 && n <= 100 ? Math.round(n * 100) / 100 : null;
}
// Volby nabidky v podobe, v jake je uklada backend (offer_options, api/scene_offers.py::_sanitize_offer_options) - samostatna funkce,
// aby se dala overit bez snimani vykresu. POZOR: montaz_pct 0 je platna volba ("bez montaze"), proto zadne `|| null`.
function offerOptionsPayload(offerOptions) {
  offerOptions = offerOptions || {};
  return {
    show_qr: offerOptions.showQr !== false,
    delivery_term: offerOptions.deliveryTerm || null,
    hidden_payment_method: offerOptions.hiddenPaymentMethod || null,
    hidden_delivery_state: offerOptions.hiddenDeliveryState || null,
    fixed_deposit_pct: offerOptions.fixedDepositPct || null,
    hide_bom_prices: !!offerOptions.hideBomPrices,
    montaz_pct: offerMontazPctValue(offerOptions.montazPct),
  };
}

async function generateSceneOffer(offerOptions) {
  offerOptions = offerOptions || {};
  const btn = document.getElementById("btnGenerateOffer");
  const statusEl = document.getElementById("offerStatus");
  if (!placed.length) {
    statusEl.textContent = "Scéna je prázdná - nejdřív do ní vlož nějaké díly.";
    statusEl.className = "err";
    return;
  }
  if (typeof isImportPreviewEntry === "function" && placed.some(isImportPreviewEntry)) {
    statusEl.textContent = "Ve scéně je náhled rozpracovaného importu - nejdřív import dokonči (Sestavit tvar) nebo zruš.";
    statusEl.className = "err";
    return;
  }
  btn.disabled = true;
  statusEl.className = "";
  statusEl.textContent = "Snímám pohledy a generuji PDF…";

  // Ulozeni aktualniho stavu kamery/pohledu, aby se uzivateli po
  // vygenerovani nabidky vratil presne tam, kde byl (Robert nebyl
  // pozadan, aby cokoli oznacoval - "plati to pro vsechny objekty ve
  // sceně", takze zadny vyber se nemeni, jen docasne prepinani kamery).
  const prevMode = (typeof viewModeSelectEl !== "undefined" && viewModeSelectEl) ? viewModeSelectEl.value : "3d";
  const prevPos = camera.position.clone();
  const prevUp = camera.up.clone();
  const prevTarget = controls.target.clone();
  const prevZoom = camera.zoom;
  const dimsCheckbox = document.getElementById("toggleDims");
  const dimsWereOn = dimsCheckbox ? dimsCheckbox.checked : false;

  try {
    // Robert 2026-08-07 ("vlož odklikávání správnosti rovnou tam do
    // sceny"): styl kotovani odklikany v "Náhled kótování" (viz
    // #dimStyleModalBox/fetchApprovedDimensionStyle) se ulozil na
    // server - skutecna nabidka ho ted pouziva misto natvrdo daneho
    // DEFAULT_DIM_STYLE. Selhani nacteni (offline/chyba) tise spadne
    // zpet na DEFAULT_DIM_STYLE, at generovani nabidky nikdy neshodi.
    const dimStyle = await fetchApprovedDimensionStyle();
    setHelperMarkersVisible(false);

    // --- Kusovnik: slucovaci skupiny se pocitaji PRED snimky vykresu
    // (posunuto sem 2026-08-08 kvuli computeGroupPixelBboxes nize - ta
    // potrebuje g.objects/groupIdx uz hotove, dokud kamera jeste
    // odpovida prave snimanemu pohledu) i PRED GLB exportem, protoze
    // kazdy object3d dostane name "bomgrp_<index skupiny>" - GLTFExporter
    // jmena uzlu zachova, takze online nabidka pak umi kliknutim na
    // radek kusovniku najit a zvyraznit vsechny patrici 3D uzly (Robert:
    // "klikatelny kusovnik ktery obarvuje/odbarvuje komponenty v 3D
    // modelu nabidky"). Bez pojmenovani neexistuje ZADNA vazba
    // kusovnik<->mesh (exportuji se anonymni uzly) - overeno pruzkumem,
    // zadny objekt name nikde nedostava.
    const rows = placed.map(currentWeightPrice);
    // Robert: "stejne polozky kusovniku slucovat" - dva dily se stejnym
    // katalogovym dilem + stejnou (zaokrouhlenou) delkou maji VZDY
    // identickou jednotkovou cenu (currentWeightPrice je cistá funkce
    // part+delka, zadny sleva/prepis na jednotlivou instanci nikde
    // neexistuje) - sloucit je do 1 radku s poctem ks je proto cenove
    // bezpecne. customColor (rucni "Obarvit dil") je soucasti klice, aby
    // vizualne odlisny kus nezmizel ve slucenem radku s ostatnimi.
    const itemGroups = new Map();
    placed.forEach((e, i) => {
      const lenRounded = rows[i].lengthMm != null ? Math.round(rows[i].lengthMm) : null;
      // Robert 2026-08-07 ("u deskových materiálů se cena zadává za 1m2"):
      // deska nema lenRounded (null jako u prislusenstvi) - bez rozmeru v
      // klici by se RUZNE VELKE desky stejneho produktu chybne slouzily do
      // jednoho radku se spolecnou (prvni nalezenou) cenou.
      const boardDimKey = rows[i].widthMm != null ? `${Math.round(rows[i].widthMm)}x${Math.round(rows[i].heightMm)}` : null;
      const key = `${e.part.id}|${lenRounded}|${boardDimKey}|${e.customColor || ""}`;
      const unit = rows[i].price != null ? Math.round(rows[i].price) : 0;
      let g = itemGroups.get(key);
      if (g) {
        g.qty += 1;
      } else {
        g = {
          name: `${partDisplayName(e.part)} (${e.part.layer})`,
          dim: lenRounded != null ? lenRounded + " mm" : (boardDimKey ? Math.round(rows[i].widthMm) + " × " + Math.round(rows[i].heightMm) + " mm" : "-"),
          unit_price: unit,
          // Robert ("stisk toptransu... vypsat živou cenu") - hmotnost na
          // kus (kg), potreba pro dopocet ceny dopravy Toptrans v online
          // nabidce podle PSC (viz _resolve_toptrans_price, api/orders.py).
          weight_kg: rows[i].weight || 0,
          qty: 1,
          // Robert: "aktivni linky kusovniku na eshop" - null kdyz dil
          // neni navazan na zadny aktivni produkt, kusovnik ho pak
          // vykresli jako obycejny text.
          product_id: e.part.shop_product_id || null,
          groupIdx: itemGroups.size,
          // bot6 2026-08-10 (PBR textura hliniku v nabidce) - urcuje, na
          // ktere bomgrp_<idx> uzly v exportovanem GLB se ma pri
          // fotorealistickem nahledu/zivem modelu aplikovat PBR textura
          // hliniku (jen "alu" vrstva, ne desky/prislusenstvi/plasty).
          layer: e.part.layer || null,
          // Robert 2026-08-08 ("profily v řezu s aktivní prolinkovou
          // vazbou do výkresu") - prurez profilu (napr. [20,40]) pro
          // vykresleni maleho obdelniku v nabidce, viz objects nize.
          cross_section_mm: e.part.cross_section_mm || null,
          // bot6 2026-08-09 ("levé ikony profilů ve výkresu nabídky musí
          // převzít skutečné obrázky stejné jako ve scéně vlevo dole") -
          // stejny zdroj jako refreshCrossSectionPanel() nize (realny
          // technicky nakres z Dogusu), jen exportovany do ulozene nabidky,
          // aby ho nabidka-online.html mohla oriznout stejnym zpusobem
          // (computeDogusCrossSectionCrop, zkopirovano tam).
          dogus_image_schema_url: e.part.dogus_image_schema_url || null,
          objects: [],
        };
        itemGroups.set(key, g);
      }
      // VSECHNY instance skupiny (i pri slouceni do 1 radku kusovniku) -
      // potreba pro sjednoceny pixelovy bounding box pres kazdy pohled
      // (computeGroupPixelBboxes nize), aby zvyrazneni v narysu/bokorysu/
      // pudorysu pokrylo uplne vsechny umistene kusy, ne jen prvni.
      g.objects.push(e.object3d);
      e.object3d.name = `bomgrp_${g.groupIdx}`;
    });

    // bot6 2026-08-10 - ktere bomgrp_<idx> skupiny jsou hlinikove profily
    // (layer "alu") - jen na ne se pri fotorealistickem nahledu aplikuje
    // PBR textura hliniku (viz capturePathTracedOfferViews nize), ne na
    // desky/prislusenstvi/plasty.
    const aluGroupIndices = new Set(
      [...itemGroups.values()].filter(g => g.layer === "alu").map(g => g.groupIdx)
    );

    setTechnicalDrawingMode(true);
    const narys = captureOrthoWithDims("front", dimStyle);
    const narysBboxes = computeGroupPixelBboxes(itemGroups, renderer.domElement.width, renderer.domElement.height);
    const bokorys = captureOrthoWithDims("side", dimStyle);
    const bokorysBboxes = computeGroupPixelBboxes(itemGroups, renderer.domElement.width, renderer.domElement.height);
    const pudorys = captureOrthoWithDims("top", dimStyle);
    const pudorysBboxes = computeGroupPixelBboxes(itemGroups, renderer.domElement.width, renderer.domElement.height);
    setTechnicalDrawingMode(false);

    // Robert ("2D pohledy nech maji 2 rezimy zobrazeni, drateny a
    // ghosted, nikoli v roletce ale vedle sebe tlacitka prepinatka") -
    // druha sada snimku STEJNYCH pohledu (stejna kamera/ramovani) v
    // "ghost" stylu (polopruhledne dily, viz applyPartMaterial), aby
    // zakaznik v online nabidce mohl prepinat. Kotovaci bboxy jsou
    // shodne s drivejsimi (stejny pohled), neni potreba je pocitat
    // znovu.
    setTechnicalDrawingMode(true, "ghost");
    const narysGhost = captureOrthoWithDims("front", dimStyle);
    const bokorysGhost = captureOrthoWithDims("side", dimStyle);
    const pudorysGhost = captureOrthoWithDims("top", dimStyle);
    setTechnicalDrawingMode(false);

    // Zivy 3D model (nepovinny krok - selhani/timeout se jen zaloguje,
    // zbytek generovani PDF/obrazku pokracuje uplne stejne jako drive).
    // Robert ("V nabídce jsem ovšem neviděl žádný nový render") -
    // predchozi verze pri selhani jen tise zalogovala do konzole, takze
    // uzivatel nemel zadnou zpravu o tom, ze/proc ray tracing nedopadl -
    // pathTraceNote se od tohodle bodu naplni a na konci pripoji k
    // vysledne hlasce o vytvorene nabidce (viz nize), at je vysledek
    // (uspech i selhani s duvodem) vzdy viditelny, ne jen v konzoli.
    let pathTraceNote = null;
    let modelGlb = null;
    try {
      modelGlb = await exportSceneAsGlb();
    } catch (err) {
      console.warn("Export 3D modelu selhal (nabídka bude bez živého modelu):", err);
      pathTraceNote = `⚠ Živý 3D model se nepodařilo exportovat (${err.message || err}) - nabídka neobsahuje ray tracing ani živý model.`;
    }

    setViewMode("3d");
    renderer.render(scene, camera);
    let view3d_a = captureRaw3d();
    const shotA = {
      pos: { x: camera.position.x, y: camera.position.y, z: camera.position.z },
      target: { x: controls.target.x, y: controls.target.y, z: controls.target.z },
    };

    // 2. uhel - otoceni kamery o pevny krok kolem stejneho stredu (target),
    // at je vizualne odlisny od prvniho (vychoziho) pohledu.
    const offsetVec = camera.position.clone().sub(controls.target);
    const angle = Math.PI * 0.55;
    const cosA = Math.cos(angle), sinA = Math.sin(angle);
    const rotated = new THREE.Vector3(
      offsetVec.x * cosA - offsetVec.z * sinA,
      offsetVec.y,
      offsetVec.x * sinA + offsetVec.z * cosA
    );
    camera.position.copy(controls.target).add(rotated);
    camera.lookAt(controls.target);
    let view3d_b = captureRaw3d();
    const shotB = {
      pos: { x: camera.position.x, y: camera.position.y, z: camera.position.z },
      target: { x: controls.target.x, y: controls.target.y, z: controls.target.z },
    };

    // Robert 2026-08-10 ("navrhuji nejdrive vygenerovat nabidku s okny pro
    // rendery (abych vedel kde to cekat kdyby to nevyslo) a teprve pote
    // vytvorit rendery a ty tam vlozit"): puvodne tenhle blok BLOKOVAL
    // samotne vytvoreni nabidky - cely POST cekal na dokonceni obou
    // path-tracovanych snimku (2x9s+), takze pri selhani/pomalosti
    // uzivatel nemel ani hotovou nabidku, ani zpravu, kde presne to
    // uvizlo. Ray tracing se ted spousti AZ PO uspesnem vytvoreni
    // nabidky (view3d_a/b nize jeste zustavaji rastrove - "okna" jsou
    // uz hotova a viditelna hned) - viz runPathTraceUpgrade() nize,
    // volana az po ulozeni nabidky, jako samostatny "dobehnouci" krok,
    // ktery uz existujici nabidku jen dodatecne vylepsi (PATCH pres
    // /views-3d), nikdy ji neblokuje ani nerozbije.

    // --- Kusovnik + celkova cena - stejny zaklad jako refreshSummary()
    // (itemGroups spocitane VYSE, pred GLB exportem - viz komentar tam).
    // mesh_group = index skupiny, odpovida "bomgrp_<idx>" jmenum uzlu v
    // exportovanem GLB - online nabidka pres nej paruje radek kusovniku
    // s 3D objekty. Souhrnne radky (rezy/pausal/spoje) mesh_group
    // nemaji - nejsou to fyzicke dily.
    const items = [...itemGroups.values()].map(g => ({
      name: g.name, dim: g.dim, qty: `${g.qty} ks`,
      unit_price: g.unit_price, total: g.unit_price * g.qty,
      product_id: g.product_id,
      mesh_group: g.groupIdx,
      // Robert ("stisk toptransu... vypsat živou cenu") - celkova
      // hmotnost radku (kg), soucet pres vsechny radky = hmotnost cele
      // sestavy pro dopocet ceny dopravy Toptrans (api/scene_offers.py
      // ::public_offer_toptrans_price).
      weight_kg_total: Math.round((g.weight_kg || 0) * g.qty * 1000) / 1000,
      // Robert 2026-08-08 ("profily v řezu s aktivní prolinkovou vazbou
      // do výkresu") - viz computeGroupPixelBboxes vyse; x0/y0/x1/y1 jsou
      // zlomky [0,1] pozice v danem obrazku (stejna konvence jako
      // scene_offer_markups), null kdyz dil nema prurez (prislusenstvi)
      // nebo se do zaberu pohledu vubec nevesel.
      cross_section_mm: g.cross_section_mm,
      dogus_image_schema_url: g.dogus_image_schema_url,
      layer: g.layer,
      drawing_bbox: {
        narys: narysBboxes[g.groupIdx] || null,
        bokorys: bokorysBboxes[g.groupIdx] || null,
        pudorys: pudorysBboxes[g.groupIdx] || null,
      },
    }));
    const totalCut = placed.reduce((s, e) => s + (e.part.price_per_cut_czk || 0), 0);
    const totalProfiles = placed.reduce((s, e) => s + (isProfilePart(e.part) ? 1 : 0), 0);
    const totalProfileFlatFee = totalProfiles * (PRICING_CONFIG.profile_flat_fee_czk || 0);
    const totalJoints = placed.reduce((s, e) => s + (e.jointCount || 0), 0);
    const totalJointPrice = totalJoints * (PRICING_CONFIG.joint_price_czk || 0);
    const totalAccessoryHardware = (PRICING_CONFIG.accessories || []).reduce(
      (s, a) => s + (a.qty_per_joint || 0) * totalJoints * (a.price_czk || 0), 0
    );
    if (totalCut) items.push({ name: "Cena řezů", dim: "-", qty: `${totalProfiles} ks`, unit_price: null, total: Math.round(totalCut) });
    if (totalProfileFlatFee) items.push({ name: "Manipulační tarif (paušál za profil)", dim: "-", qty: `${totalProfiles} ks`, unit_price: null, total: Math.round(totalProfileFlatFee) });
    if (totalJointPrice) items.push({ name: "Cena spojů", dim: "-", qty: `${totalJoints} ks`, unit_price: null, total: Math.round(totalJointPrice) });
    if (totalAccessoryHardware) items.push({ name: "Příslušenství (spojovací materiál)", dim: "-", qty: "-", unit_price: null, total: Math.round(totalAccessoryHardware) });
    const balneItem = offerPackagingItem(items);   // POSLEDNI radek - procento ze vsech predchozich (viz offerPackagingItem)
    if (balneItem) items.push(balneItem);
    // "kusovnik bez cen... vlozeni individualni ceny" (Robert) - items
    // se pocitaji VZDY normalne (kusovnik existuje dal, jen se
    // zakaznikovi nezobrazi, viz hide_bom_prices na nabidka-online.html),
    // rucne zadana cena je JEN pro total_price, kdyz je vyplnena.
    const computedTotalPrice = items.reduce((s, it) => s + (it.total || 0), 0);
    const totalPrice = (offerOptions.hideBomPrices && offerOptions.customTotal != null)
      ? offerOptions.customTotal
      : computedTotalPrice;

    const customerName = offerOptions.customerName || "";
    const customerEmail = offerOptions.customerEmail || "";

    // HDRI odlesky (Robert 2026-08-06: "zapec") - snapshot aktualniho
    // nastaveni ze sceny, at klient vidi model stejne nablyskany.
    let hdriSnapshot = null;
    try {
      if (typeof activeHdriFile !== "undefined" && activeHdriFile) {
        hdriSnapshot = {
          file: activeHdriFile,
          rotation: (typeof hdriRotation !== "undefined") ? hdriRotation : 0,
          intensity: (typeof hdriReflIntensity !== "undefined") ? hdriReflIntensity : 1,
          roughness: (typeof hdriReflRoughness !== "undefined") ? hdriReflRoughness : null,
          metalness: (typeof hdriReflMetalness !== "undefined") ? hdriReflMetalness : null,
          base_color: (typeof hdriReflBaseColor !== "undefined") ? hdriReflBaseColor : null,
        };
      }
    } catch (e) { /* nabidka funguje i bez HDRI */ }
    const resp = await fetch("/api/admin/scene-offers", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items, total_price: totalPrice,
        views: { narys, bokorys, pudorys, narys_ghost: narysGhost, bokorys_ghost: bokorysGhost, pudorys_ghost: pudorysGhost, view3d_a, view3d_b },
        customer: { name: customerName, email: customerEmail },
        hdri: hdriSnapshot,
        offer_options: offerOptionsPayload(offerOptions),
      }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      statusEl.className = "err";
      statusEl.textContent = data.error || "Nabídku se nepodařilo vygenerovat.";
    } else {
      statusEl.className = "ok";
      const onlineUrl = data.online_url ? new URL(data.online_url, window.location.origin).href : "";
      // Automaticke PDF zruseno (Robert 2026-08-06) - nabidka zije jen
      // online, klient si ji z prohlizece vytiskne/ulozi sam.
      statusEl.innerHTML = `Nabídka ${data.offer_number} uložena.`
        + (onlineUrl ? ` <a href="${onlineUrl}" target="_blank">Zobrazit online</a>`
          + ` · <a href="#" id="btnCopyOnlineOfferLink">🔗 Zkopírovat odkaz pro klienta</a>` : "")
        // pathTraceNote v tomhle miste uz hlasi jen pripadne selhani
        // EXPORTU GLB (viz vyse) - samotny vysledek ray tracingu uz
        // neni soucasti teto (rychle zobrazene) hlasky, viz
        // runPathTraceUpgrade() nize, ktera pripoji VLASTNI radek az
        // po dobehnuti.
        + (pathTraceNote ? `<div style="margin-top:4px;font-size:12px;">${pathTraceNote.replace(/[<>&]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]))}</div>` : "");
      const copyBtn = document.getElementById("btnCopyOnlineOfferLink");
      if (copyBtn) {
        copyBtn.onclick = (e) => {
          e.preventDefault();
          navigator.clipboard.writeText(onlineUrl).then(() => {
            copyBtn.textContent = "✓ Odkaz zkopírován";
          }).catch(() => {
            window.prompt("Odkaz pro klienta:", onlineUrl);
          });
        };
      }
      // Zivy 3D model - samostatny nezavisly upload AZ PO uspesnem
      // zalozeni nabidky (nginx client_max_body_size, viz plan) - jeho
      // selhani se jen zaloguje a NIKDY nemeni uz zobrazenou uspesnou
      // hlasku vyse (nabidka/PDF/obrazky uz existuji bez ohledu na to).
      if (data.offer_number) lastOfferNumber = data.offer_number;
      if (modelGlb && data.offer_id) {
        try {
          const fd = new FormData();
          fd.append("model", new Blob([modelGlb], { type: "model/gltf-binary" }), "model.glb");
          const mr = await fetch(`/api/admin/scene-offers/${data.offer_id}/model`, { method: "POST", body: fd });
          if (!mr.ok) console.warn("Nahrání 3D modelu selhalo, nabídka zůstává jen s plochými náhledy.");
        } catch (err) {
          console.warn("Nahrání 3D modelu selhalo:", err);
        }
        // Robert 2026-08-10 ("nejdriv vygenerovat nabidku... teprve pote
        // vytvorit rendery a ty tam vlozit"): ZAMERNE BEZ await - nabidka
        // uz je hotova/zobrazena vyse, ray tracing dobehne na pozadi a
        // sam se dopoji do statusEl az bude hotovy (viz
        // runPathTraceUpgrade). Kdyby se cekalo tady, btn/kamera by se
        // vratily do puvodniho stavu (finally nize) az za dalsich 9-18s.
        if (offerOptions.withRenders) {
          runOfferRenderUpgrade(modelGlb, shotA, shotB, aluGroupIndices, data.offer_id, data.offer_number);
        }
      }
    }
  } catch (err) {
    statusEl.className = "err";
    statusEl.textContent = "Chyba spojení - nabídku se nepodařilo vygenerovat.";
  } finally {
    // Pojistka - kdyby nekde mezi zapnutim/vypnutim rezimu vykresu (napr.
    // pri chybe snimani) doslo k vyjimce, tohle zajisti navrat na puvodni
    // renderMode/pozadi i tak (no-op, pokud uz bylo vypnuto normalne vyse).
    setTechnicalDrawingMode(false);
    setHelperMarkersVisible(true);
    // Navrat kamery presne tam, kde uzivatel byl pred kliknutim.
    setViewMode(prevMode);
    // Viz stejny fix v previewDimensionStyle - drzi dropdown v souladu se skutecnou kamerou.
    if (typeof viewModeSelectEl !== "undefined" && viewModeSelectEl) viewModeSelectEl.value = prevMode;
    camera.position.copy(prevPos);
    camera.up.copy(prevUp);
    if (camera.isOrthographicCamera) { camera.zoom = prevZoom; camera.updateProjectionMatrix(); }
    controls.target.copy(prevTarget);
    camera.lookAt(controls.target);
    controls.update();
    renderer.render(scene, camera);
    btn.disabled = false;
  }
}
// Robert 2026-08-09 ("při její tvorbě konkretniho cisla, chci mit
// moznsot vzdy nektere prvky odebrat, napr QR kod, nebo naopak doplnit:
// Termín dodání") - misto rovnou volaneho generateSceneOffer() (drive
// jen s window.prompt() na jmeno zakaznika) se ted nejdriv otevre
// maly modal se sadou voleb; teprve jeho "Vytvořit nabídku" spusti
// samotne generovani. Jmeno zakaznika presunuto ze zvlastniho prompt()
// do stejneho formulare.
function openOfferOptionsModal() {
  if (!placed.length) {
    document.getElementById("offerStatus").className = "err";
    document.getElementById("offerStatus").textContent = "Scéna je prázdná - nejdřív do ní vlož nějaké díly.";
    return;
  }
  if (typeof isImportPreviewEntry === "function" && placed.some(isImportPreviewEntry)) {
    document.getElementById("offerStatus").className = "err";
    document.getElementById("offerStatus").textContent = "Ve scéně je náhled rozpracovaného importu - nejdřív import dokonči (Sestavit tvar) nebo zruš.";
    return;
  }
  document.getElementById("offerOptCustomerName").value = "";
  document.getElementById("offerOptCustomerEmail").value = "";
  document.getElementById("offerOptShowQr").checked = true;
  document.getElementById("offerOptDeliveryTerm").value = "";
  document.getElementById("offerOptHiddenPayment").value = "";
  document.getElementById("offerOptHiddenDeliveryState").value = "";
  document.getElementById("offerOptFixedDepositOn").checked = false;
  document.getElementById("offerOptFixedDepositPct").value = 70;
  document.getElementById("offerOptHideBomPrices").checked = false;
  document.getElementById("offerOptCustomTotal").value = "";
  // Montaz: predvyplnena vychozi sazba z nastaveni, Robert ji pro tuhle nabidku muze zmenit (0 = bez montaze)
  document.getElementById("offerOptMontazPct").value =
    Number((typeof PRICING_CONFIG !== "undefined" && PRICING_CONFIG && PRICING_CONFIG.montaz_pct) || 0);
  offerOptSyncFixedDepositUI();
  offerOptSyncHideBomPricesUI();
  offerOptSyncMontazUI();
  document.getElementById("offerOptionsModalOverlay").classList.add("open");
}
function closeOfferOptionsModal() {
  document.getElementById("offerOptionsModalOverlay").classList.remove("open");
}
// Stejny "seed z aktualniho stavu + zvlast viditelnost" vzor jako
// offerEditSyncFixedDepositUI/offerEditSyncHideBomPricesUI v
// admin/js/crm-nabidky.js (editace JIZ ZALOZENE nabidky) - tady jde o
// PRVOTNI zalozeni, proto zadny "seed od predchozi hodnoty".
function offerOptSyncFixedDepositUI() {
  document.getElementById("offerOptFixedDepositWrap").style.display =
    document.getElementById("offerOptFixedDepositOn").checked ? "" : "none";
}
document.getElementById("offerOptFixedDepositOn").onchange = offerOptSyncFixedDepositUI;
function offerOptSyncHideBomPricesUI() {
  document.getElementById("offerOptCustomTotalWrap").style.display =
    document.getElementById("offerOptHideBomPrices").checked ? "" : "none";
}
document.getElementById("offerOptHideBomPrices").onchange = offerOptSyncHideBomPricesUI;
// Orientacni castka montaze bez DPH vedle pole: % z ceny sestavy ve scene (pri "individualni cene" z ni). Skutecna castka v online
// nabidce je % z celkove ceny nabidky - po zaokrouhleni polozek se muze o nekolik Kc lisit, proto "≈".
function offerOptMontazBaseCzk() {
  const hide = document.getElementById("offerOptHideBomPrices").checked;
  const custom = parseFloat(document.getElementById("offerOptCustomTotal").value);
  if (hide && Number.isFinite(custom) && custom >= 0) return custom;
  const el = document.getElementById("statTotalPrice");
  const n = el ? Number(String(el.textContent).replace(/\s/g, "")) : 0;
  return Number.isFinite(n) ? n : 0;
}
function offerOptSyncMontazUI() {
  const info = document.getElementById("offerOptMontazInfo");
  if (!info) return;
  const pct = offerMontazPctValue(document.getElementById("offerOptMontazPct").value);
  const base = offerOptMontazBaseCzk();
  info.textContent = (pct !== null && pct > 0 && base > 0)
    ? `≈ ${Math.round(base * pct / 100).toLocaleString("cs-CZ")} Kč bez DPH` : "";
}
document.getElementById("offerOptMontazPct").addEventListener("input", offerOptSyncMontazUI);
document.getElementById("offerOptCustomTotal").addEventListener("input", offerOptSyncMontazUI);
document.getElementById("offerOptHideBomPrices").addEventListener("change", offerOptSyncMontazUI);
let offerWithRenders = false; // kterou variantou byl otevren formular nabidky
document.getElementById("btnGenerateOffer").addEventListener("click", () => {
  offerWithRenders = false;
  openOfferOptionsModal();
});
// Agenta budime HNED pri kliku (ne az po exportu/vytvoreni nabidky) -
// nez se pripravi data, agent stihne nabehnout a poslat heartbeat,
// takze prvni render uz jde na GPU. Kdyz protokol neni nainstalovany
// (INSTALACE_PROTOKOLU.reg), prohlizec odkaz tise zahodi a render
// jde na server.
//
// bot4 2026-10-01 (Robert 2026-09-30: po stisku "+ rendery" naskocilo cerne okno
// "RenderAgent - C:\Temp\render..." s nekonecnou smyckou "Agent skoncil, restartuji za
// 3s..."): budit JEN kdyz GPU stanice (vychozi worker) nehlasi tep ("offline"). Bezi-li, je
// to na Logiman2 sluzba (NAINSTALOVAT_SLUZBU.bat), render jde na ni a zbytecny pokus o start
// na TOMHLE PC jen otevrel okno stareho spoustece (u "stuck" start dalsi kopie nepomuze).
// Stav nezname (chyba site, 403 bez prava GPU monitoru) = nebudit. Test:
// scripts/2026-10-01_render_agent_testy/test_wake_render_agent.js
async function wakeRenderAgent() {
  try {
    const r = await fetch("/api/admin/render-worker/status");
    if (!r.ok) return;
    const info = await r.json();
    if (!info || info.state !== "offline") return;
    const fr = document.createElement("iframe");
    fr.style.display = "none";
    fr.src = "logimanrender://start";
    document.body.appendChild(fr);
    setTimeout(() => fr.remove(), 4000);
  } catch (e) { /* neinstalovany protokol / stav nezname nevadi */ }
}
document.getElementById("btnGenerateOfferRenders").addEventListener("click", () => {
  offerWithRenders = true;
  wakeRenderAgent();
  openOfferOptionsModal();
});
document.getElementById("btnTestRenders").addEventListener("click", () => {
  wakeRenderAgent();
  runTestRenders();
});

// Robert 2026-08-11 ("dej tam jeste jedno tlacitko treti, at nemusim
// delat nabidku kvuli testovani renderu"): vyrenderuje oba ulozene
// pohledy (Ctrl+Shift+1/2, jinak automatika) pres Blender/Cycles a
// ukaze je v okne renderu POD SEBOU. Zadna nabidka, zadne ukladani -
// jen na obrazovku. Stejna renderovaci cesta ale poslouzi i pro
// budouci rendery produktovych sestav pro e-shop.
function computeAutoRenderShots() {
  const v = cameraDirToAzEl();
  const saved = loadOfferRenderShots();
  return [
    saved.shot1 || { az: v.az, el: Math.max(8, Math.min(70, v.el)) },
    saved.shot2 || { az: v.az + 120, el: Math.max(30, Math.min(70, v.el + 25)) },
  ];
}

async function runTestRenders() {
  const btn = document.getElementById("btnTestRenders");
  const resultWin = openRenderResultWindow(); // synchronne v ramci kliku
  if (!placed.length) { renderWinStatus(resultWin, "Scéna je prázdná - nejdřív do ní vlož nějaké díly.", true); return; }
  if (btn) btn.disabled = true;
  try {
    renderWinStatus(resultWin, "Exportuji 3D data…");
    const glb = await exportSceneAsGlb();
    const settings = readBlenderOptions();
    const shots = computeAutoRenderShots();
    const recipe = buildRenderRecipe();     // zapis dilu pro vzhled jako u karet (null = jen stara cesta)
    for (let i = 0; i < 2; i++) {
      const st = Object.assign({}, settings, {
        camera_azimuth_deg: shots[i].az,
        camera_elevation_deg: shots[i].el,
        ucel: "nabidka",   // viz rendery nabidek vyse: server posle render na Omen, kdyz je pouzitelny
      });
      let stopped = false;
      let vysl;
      try {
        vysl = await renderViewWithFallback(glb, st, recipe, {
          timeoutMs: 15 * 60 * 1000, progressive: true,
          onJob: (jobId) => renderWinSetStop(resultWin, () => {
            stopped = true;
            fetch(`/api/admin/blender-render/${jobId}/cancel`, { method: "POST" }).catch(() => {});
          }),
          onPreview: (img) => renderWinShowImage(resultWin, img, `test-pohled-${i + 1}-nahled.png`, i),
          onWait: (sd, el, jakKarta) => {
            const jak = jakKarta ? " (vzhled jako u karet)" : "";
            if (sd.state === "queued" || sd.state === "waiting_worker") {
              renderWinStatus(resultWin, `Test: pohled ${i + 1}/2 čeká ve frontě${jak}… ${el} s`);
            } else if (sd.state === "running") {
              renderWinStatus(resultWin, `Test: renderuji pohled ${i + 1}/2${jak}… ${el} s`);
            }
          },
          onFallback: (duvod) => renderWinStatus(resultWin, `Test: pohled ${i + 1}/2 - vzhled jako u karet nešel (${duvod}), zkouším starou cestu…`),
        });
      } catch (err) {
        if (err && err.zruseno) {
          if (stopped || (err.sd && err.sd.stopped_by_user)) { renderWinStatus(resultWin, "⏹ Test render zastaven."); return; }
          throw new Error(err.message || "Render byl zrušen novějším renderem.");
        }
        throw err;
      }
      const sd = vysl.sd;
      const kde = sd.worker_name ? `⚡ ${sd.worker_name} (GPU)` : "server (CPU)";
      renderWinShowImage(resultWin, vysl.image, `test-pohled-${i + 1}.png`, i);
      renderWinStatus(resultWin, `✓ Pohled ${i + 1}/2 hotový za ${sd.render_seconds} s na ${kde}${vysl.jakKarta ? " - vzhled jako u karet" : ""}`);
    }
    renderWinStatus(resultWin, "✓ Testovací rendery hotové (oba pohledy níže). Nic se neukládalo - nabídka nevznikla.");
  } catch (err) {
    renderWinStatus(resultWin, "✗ CHYBA (test render): " + ((err && err.message) || err), true);
  } finally {
    renderWinSetStop(resultWin, null);
    if (btn) btn.disabled = false;
  }
}
document.getElementById("offerOptionsModalClose").addEventListener("click", closeOfferOptionsModal);
document.getElementById("offerOptCancel").addEventListener("click", closeOfferOptionsModal);
document.getElementById("offerOptionsModalOverlay").addEventListener("click", (e) => {
  if (e.target.id === "offerOptionsModalOverlay") closeOfferOptionsModal();
});
document.getElementById("offerOptSubmit").addEventListener("click", async () => {
  const submitBtn = document.getElementById("offerOptSubmit");
  const customerEmailVal = document.getElementById("offerOptCustomerEmail").value.trim();
  // Rychle overeni FORMATU pred spustenim cele (pomale) generace
  // nahledu/PDF - lepe selhat hned, nez az po vyrenderovani vsech
  // pohledu (viz generateSceneOffer nize, ktery by stejnou chybu vratil
  // az z backendu na konci).
  if (customerEmailVal && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(customerEmailVal)) {
    document.getElementById("offerOptionsModalOverlay").classList.add("open");
    alert("E-mail zákazníka není ve správném formátu.");
    return;
  }
  // Montaz: prazdne pole = vychozi sazba z nastaveni (null), jinak cislo 0-100 %
  const montazRaw = document.getElementById("offerOptMontazPct").value.trim();
  const montazPctVal = offerMontazPctValue(montazRaw);
  if (montazRaw !== "" && montazPctVal === null) {
    document.getElementById("offerOptionsModalOverlay").classList.add("open");
    alert("Montáž musí být číslo od 0 do 100 %.");
    return;
  }
  submitBtn.disabled = true;
  try {
    closeOfferOptionsModal();
    await generateSceneOffer({
      customerName: document.getElementById("offerOptCustomerName").value.trim(),
      customerEmail: customerEmailVal,
      showQr: document.getElementById("offerOptShowQr").checked,
      deliveryTerm: document.getElementById("offerOptDeliveryTerm").value.trim(),
      hiddenPaymentMethod: document.getElementById("offerOptHiddenPayment").value || null,
      hiddenDeliveryState: document.getElementById("offerOptHiddenDeliveryState").value || null,
      fixedDepositPct: document.getElementById("offerOptFixedDepositOn").checked
        ? (parseInt(document.getElementById("offerOptFixedDepositPct").value, 10) || 70)
        : null,
      hideBomPrices: document.getElementById("offerOptHideBomPrices").checked,
      customTotal: document.getElementById("offerOptCustomTotal").value.trim()
        ? (parseFloat(document.getElementById("offerOptCustomTotal").value) || null)
        : null,
      montazPct: montazPctVal,
      withRenders: offerWithRenders,
    });
  } finally {
    submitBtn.disabled = false;
  }
});
