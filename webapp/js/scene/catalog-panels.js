if (typeof THREE === "undefined") {
  document.body.innerHTML = '<div style="padding:40px;font-family:sans-serif;color:#e8eaed;background:#1b1e24;height:100%;">' +
    '<h2>Nepodařilo se načíst Three.js z CDN.</h2>' +
    '<p>Tento prototyp potřebuje internetové připojení (načítá knihovnu z cdn.jsdelivr.net).</p></div>';
  throw new Error("THREE.js se nenačetlo");
}
// bot8 2026-08-22 (Robert: "je to nepresne" - kolizni rezim karoserie,
// viz checkCarBodyCollisions): globalni patch THREE.Mesh.raycast na
// BVH-akcelerovanou variantu (js/three-mesh-bvh.js) - BEZPECNE pro
// VSECHNY ostatni existujici raycasty v aplikaci (klikani/vyber/hover),
// protoze acceleratedRaycast interne kontroluje "geometry.boundsTree
// existuje?" a kdyz ne, zavola presne puvodni THREE chovani beze
// zmeny (overeno primo ve zdroji knihovny). BVH strom se pocita jen
// pro geometrie, kde na to nekdo explicitne zavola computeBoundsTree()
// (viz ensureWallBoundsTree nize) - u vsech ostatnich dilu (profily,
// prislusenstvi...) se nic nemeni. NEPOVINNE - kdyby se lokalni soubor
// z nejakeho duvodu nenacetl, kolizni rezim jen nebude fungovat
// (zachyceno primo v checkCarBodyCollisions), zbytek appky bezi dal.
if (typeof MeshBVHLib !== "undefined") {
  THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
  THREE.BufferGeometry.prototype.disposeBoundsTree = MeshBVHLib.disposeBoundsTree;
  THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
}

// Robert 2026-08-12 ("cela scena cerna"): musi byt DEFINOVANO uplne na
// zacatku skriptu - viz dlouhy komentar u zbytku zamku pozic plovoucich
// ikon (hledej FLOATING_LOCK_KEY nize). Pouziva se uz behem pocatecniho
// nacteni stranky, dlouho pred tim, nez se skript dostane k sekci, kde
// puvodne bylo (o tisice radku niz) - tam byla ona pozdni deklarace
// pricinou TDZ ReferenceError, ktera shodila celou zbylou inicializaci
// sceny.
let floatingIconsLocked = false;

const CATALOG_URL = "/api/katalog";
// Barvy pro badge v katalogu (jen UI akcent, nesouvisí s materiálem v 3D scéně)
const badgeColor = { alu: "#3a5a7a", black: "#444444", zinc: "#5a5a3a", guma: "#3a3a3a", plast_svetly: "#5a6a7a" };
function badgeClass(layer){ return "b-" + (layer in badgeColor ? layer : "alu"); }
// Skutečné barvy materiálů pro 3D scénu - hliník musí vypadat jako hliník, ne jako UI motiv.
// Robert 2026-09-08 ("musí tam byt nody pro vsechny materiály/objekty ve
// sceně") - katalog přislušenství (spojky/konzole/patky/kluzáky/gumy...)
// dřív skoro celý spadal na generický fallback "#9aa0a6" (žádné cfg_dily/
// shop_products.layer NEBYLO nic jiného než "alu"), takže zinkové/plastové/
// pryžové díly vypadaly stejně jako broušený hliník. "zinc"/"black" tu byly
// definované už dřív, ale v DB nikdy nebyly použité - doplněno "guma"
// (pryžová těsnění/pásky) a "plast_svetly" (eurobox - světlejší než "black").
const partMaterialColor = {
  alu: "#c9cdd1", black: "#242424", zinc: "#b7bcc0",
  // Robert 2026-09-10: zesvetleni x1.2 na #7a828a se ukazalo jako PRILIS
  // ("boxy a uhelniky jsou moc svetle, chtel jsem jen o 20%, tak to vratit
  // na stredni sedou") - vraceno na puvodni #666c73. Nasobeni kanalu x1.2
  // znamena vic nez 20 % ve VNIMANE svetlosti, proto to bilo do oci.
  // Oddelena polozka "mdf" tim ztratila duvod (existovala jen proto, aby
  // MDF zesvetleni plastu neodneslo s sebou) a je zrusena - MDF se opet
  // ridi plast_svetly, presne jako pred touhle zmenou.
  // POZOR: "plast_svetly" jsou UZ JEN euroboxy. Uhelnikove spojky
  // (shop_products 3045/3207/3216) tu drive omylem visely taky - Robert
  // 2026-09-10: "uhelnik je odlitek, ne plast !" - a byly prepsany na
  // "zinc" (#b7bcc0), viz backups/2026-09-10_uhelniky_plast_na_zinek.json.
  // Nekoliduje to s drivejsim "uhelniky nejsou ze stejneho materialu jako
  // profily" ani "uhelniky nejsou leskle": zinek ma metalness 0.45 vs alu
  // 0.6 a roughness 0.55 vs alu 0.35, takze je matnejsi nez profil.
  guma: "#1c1c1e", plast_svetly: "#666c73",
  // Robert 2026-09-10 "mdf chci zvlast" - MDF ma vlastni polozku, aby se
  // dala ladit nezavisle na euroboxech. VLASTNI ODSTIN je
  // nutnost, ne kosmetika: material se pozna PODLE BARVY, takze dva
  // materialy se stejnym hexem od sebe rozlisit nejdou. Lehce do
  // antracitu (Robert driv: "mdf seda antracit lehce").
  mdf: "#5c626a",
};
// Kovovost podle vrstvy - viz materialForLayer() (hdri-panels-ui.js).
// Zinkovy odlitek je dost kovovy, plast/pryz prakticky vubec ne (predtim
// VSECHNO krom "alu" dostavalo plocho stejnych 0.35). Zinek DRZ POD 0.5,
// aby ho api/blender_render_scene.py (_keeps_own_color, pasmo 0.35-0.55)
// rozpoznalo jako samostatnou "odlitek" vetev, ne stejny kos jako "alu"
// (0.6) - viz Robert 2026-09-08 ("tohle stavění GUI nemusíme delat kdyz
// to umi z blenderu" - prefabrikovana textura zinku procedurálně v
// Blenderu shader nodes, ne nová fotka nahraná přes Sdílený disk).
const partMaterialMetalness = { alu: 0.6, zinc: 0.45, black: 0.1, guma: 0.05, plast_svetly: 0.1, mdf: 0.1 };
// Produktove dily (shop_products) maji layer VZDY natvrdo "produkt"
// (api/app.py fetch_katalog_parts) - nemuzou tedy nikdy nest realnou
// vrstvu, jen vlastni color_hex. Aby i ONY dostaly spravnou kovovost (ne
// plochych 0.35 pro vsechno), obratime tabulku barev na kovovost podle
// KONKRETNI barvy - kdyz produkt ma color_hex presne z tehle palety
// (nastavene hromadne pri klasifikaci pripoju, viz AGENTS_LOG.md
// 2026-09-08), pozna se tak jeho material i bez vlastniho pole "layer".
const HEX_TO_METALNESS = {};
for (const k in partMaterialColor) HEX_TO_METALNESS[partMaterialColor[k].toLowerCase()] = partMaterialMetalness[k];

// Drsnost podle vrstvy (Robert 2026-09-08 "projdi nejake materialy a
// zjisti co je treba") - do teto chvile mela VSECHNO jednu spolecnou
// hodnotu 0.4 bez ohledu na material. Podle odborných zdrojů (PBR
// referencni databaze, viz AGENTS_LOG.md pro presne odkazy): tvrdy
// vstrikovany plast (ABS/POM - spojky, kluzáky, madla) ma ostre, jasne
// odlesky (0.05-0.2), gumove tesneni je naopak hodne matne (0.7+),
// odlitek (zinek) je zrnitejsi nez brouseny hlinik.
const partMaterialRoughness = { alu: 0.35, zinc: 0.55, black: 0.15, guma: 0.75, plast_svetly: 0.3, mdf: 0.4 };
const HEX_TO_ROUGHNESS = {};
for (const k in partMaterialColor) HEX_TO_ROUGHNESS[partMaterialColor[k].toLowerCase()] = partMaterialRoughness[k];

// Logo ochrany LOGIMAN.CZ ma vlastni barvu (Robert 2026-09-11, pres bot3:
// "lehce oranzovou"), mimo standardni alu paletu vyse. PYTHON PROTEJSEK:
// razitkovac.LOGO_BARVA_HEX/LOGO_METALNESS/LOGO_ROUGHNESS + stejny zaznam
// v HEX_TO_METALNESS/ROUGHNESS ve scripts/2026-09-09_turntable_job.py -
// meni se OBA najednou. cfg_dily.color_hex pro tenhle dil dostal stejnou
// hodnotu (scripts/2026-09-11_logo_barva_katalog.py), jinak by se
// oranzova v katalogu (/api/katalog, odkud CATALOG_URL cte) neobjevila.
// 2026-09-11: Robert po prvnim snimku rozhodl "vyraznejsi" - zmeneno z
// kandidata A (#c97a3d) na kandidata C (#d4863f, "jasnejsi ambra").
HEX_TO_METALNESS["#d4863f"] = 0.65;
HEX_TO_ROUGHNESS["#d4863f"] = 0.30;

let CATALOG = [];
// Koeficient konfiguratoru (scene_price_coefficient) je uz v cenach dilu z
// /api/katalog - v prehledu ceny se neuvadi (Robert 2026-09-30).
// Cache-buster - donutit prohlizec vzdy stahnout cerstve GLB soubory misto
// stare cachovane verze. Bez tohoto muze prohlizec po nasazeni opravene
// geometrie na server porad zobrazovat starou verzi dilu z mezipameti, i po
// obnoveni stranky - presne tohle zpusobilo zmatek s "porad oblym" 45x45.
const CACHE_BUST = Date.now();

// Viditelnost dilu ve 3D scene (bot1, 2026-07-27) - drive pevne zadratovany
// seznam ID tady v kodu (5 profilu, ktere Robert osobne zkontroloval a
// potvrdil jako spravne), ted nahrazeno databazovym priznakem
// cfg_dily.visible_in_scene (viz fetch_katalog_parts() v app.py). Puvodnich
// 5 potvrzenych profilu bylo pri migraci prevedeno na visible_in_scene=1,
// takze chovani se nemeni. Robert: "jakmile se fbx modely nahrajou supni je
// do sceny do katalogu" - admin FBX upload ted po uspesnem prevodu na GLB
// nastavi visible_in_scene=1 automaticky, bez nutnosti upravovat tenhle
// soubor pro kazdy novy profil.

// --- Prihlaseni (session cookie) - cely konfigurator je za loginem
// (rozhodnuti 2026-07-23). Katalog je prvni skutecna data, co appka
// potrebuje - pokud API vrati 401, znamena to "neprihlaseno" a presmerujeme
// na login misto zobrazeni prazdne/rozbite appky. Ostatni endpointy jsou
// na serveru chranene stejne (@login_required/@admin_required), takze i
// kdyby se tenhle redirect nekde neprovedl, data se stejne neprozradi.
function redirectToLogin() {
  window.location.href = "/login.html?next=" + encodeURIComponent(location.pathname + location.search);
}

fetch(CATALOG_URL)
  .then(r => {
    if (r.status === 401) { redirectToLogin(); throw new Error("neprihlaseno"); }
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  })
  .then(data => {
    // ceny v data.parts uz jsou navysene na serveru (viz /api/katalog)
    // ⭐ NEfiltrovat podle visible_in_scene tady (bot8 2026-09-11, nasel
    // Robert po vlozeni sestavy: "Nepodařilo se vložit tvar... neznámý díl
    // vypln_drazky_30 v katalogu"). CATALOG je JEDINY zdroj, ze ktereho
    // katalogPartById() resolvuje kazdy dil VCETNE tech, co uz sestava
    // NESE (nacitani ulozenych sestav, ekvalizer, vkladani do sceny) - ne
    // jen picker "vloz novy dil". `visible_in_scene=0` ma znamenat "nenabizi
    // se k rucnimu vlozeni", ne "neni nacitatelny" - ty dva vyznamy driv
    // splynuly, protoze filtr sedel tady misto v buildCatalogList() nize,
    // ktera skutecne staví ten browsable seznam. Razitkove dily
    // (logo_logiman_cz, vypln_drazky_30) maji visible_in_scene=0 zamerne
    // (nemaji jit vlozit rucne), ale MUSI jit nacist, kdyz uz jsou v datech
    // orazitkovane sestavy - presne to tenhle radek rozbil pro vsech 8
    // dnes orazitkovanych sestav.
    CATALOG = (data.parts || [])
      .map(p => ({
        id: p.id, name: p.name, layer: p.layer,
        material_label: p.material_label, dims_mm: p.dims_mm,
        length_mm: p.length_mm, cross_section_mm: p.cross_section_mm,
        weight_kg: p.weight_kg_approx, price_czk: p.price_czk_approx_PLACEHOLDER,
        price_per_cut_czk: p.price_per_cut_czk,
        file: "katalog/" + p.file + "?v=" + CACHE_BUST,
        // Skryto z picker/browse seznamu (buildCatalogList), ale porad
        // resolvovatelne katalogPartById() - viz komentar u CATALOG vyse.
        visible_in_scene: !!p.visible_in_scene,
        // bot2, 2026-07-28: produkty (shop_products s nahranym FBX) maji
        // source:"product" + category_id navazany na content_categories,
        // aby je slo v katalogu razit do stromu kategorii misto ploche
        // "layer" skupiny (viz buildCatalogList nize).
        source: p.source || "profil",
        category_id: p.category_id != null ? p.category_id : null,
        // Robert: "aktivni linky kusovniku na eshop" - null kdyz dil neni
        // navazan na zadny aktivni produkt (bezne u pomocnych/internich
        // profilu) - kusovnik pak polozku vykresli jako obycejny text.
        shop_product_id: p.shop_product_id != null ? p.shop_product_id : null,
        // Robert 2026-08-05 ("necht se u produktu ve scene zobrazuje pocet
        // ks skladem"): null u dilu bez navazane shop_products karty (viz
        // api/app.py fetch_katalog_parts) - makePartButton() takove proste
        // nezobrazi (nema smysl u internich/pomocnych profilu).
        stock_qty: p.stock_qty != null ? p.stock_qty : null,
        // bot1 2026-08-01 OPRAVA ("oznacovani ploch je ok, jen se
        // neuklada"): tohle pole se tu drive VUBEC nekopirovalo ze
        // serverove odpovedi (fetch_katalog_parts uz ho vraci spravne,
        // /api/products/<id>/connector-flags ho i spravne uklada do DB -
        // overeno primo v databazi), takze KAZDY dil polozeny z katalogu
        // (i po obnoveni stranky) mel accessory_conn_enabled=undefined a
        // choval se, jako by jeste nikdy nebyl zkontrolovan (vsech 6
        // ploch nabizeno znovu) - ulozene rozhodnuti z Kontroly ploch se
        // tak nikdy nepouzilo pro nove/znovunactene kusy.
        accessory_conn_enabled: Array.isArray(p.accessory_conn_enabled) ? p.accessory_conn_enabled : null,
        // bot1 2026-08-04: naucena poloha uhelniku (UhelnikAut) - ze
        // serveru, sdilena pro vsechny uzivatele (viz uhelnik_pose v api/app.py).
        uhelnik_pose: p.uhelnik_pose || null,
        // bot1 2026-08-04: SKU produktu - zobrazuje se v Kusovniku u
        // vsech produktu jednotne (drive ho nektere mely jen v nazvu).
        sku: p.sku || null,
        // bot7, 2026-08-07 OPRAVA ("kde to vázne?" - barva ani 2D
        // protahovani desky nefungovaly): STEJNA trida bugu jako uz drive
        // u accessory_conn_enabled vyse - CATALOG se tu staví přes .map()
        // s pevným výčtem polí, takže nové backendové pole samo o sobě
        // NESTAČÍ (fetch_katalog_parts uz color_hex/is_board_material
        // vraci spravne, ale sem se nikdy nezkopirovaly) - "Obarvit dil"
        // pri vlozeni z katalogu i zelene sipky desky proto tise
        // nefungovaly u VŠECH produktu, ne jen u PR10.
        color_hex: p.color_hex || null,
        // Robert 2026-08-12 ("klikaci prostredi pro odklikavani spravnych
        // postupu, jak vse spravne napojovat"): explicitni rezim Place
        // All - 'corner' | 'endcap' | 'none' | null (nenauceno).
        attach_mode: p.attach_mode || null,
        // Robert 2026-08-15 ("pozice se mela ulozit vuci tem dvema
        // profilum"): plna naucena poza pro rezim corner_side - pozice
        // + rotace RELATIVNE k ramu rohu 2 profilu (cornerSideFrame).
        attach_pose: p.attach_pose || null,
        // Robert 2026-08-12 ("cep potrebuje byt zanoreny castecne do
        // profilu") - signed odsazeni (mm) podel osy pripojeni, aplikuje
        // se v runZaslepkaAut az PO standardnim "naplocho" osazeni.
        attach_offset_mm: p.attach_offset_mm != null ? Number(p.attach_offset_mm) : 0,
        // Robert 2026-08-12 ("oznaci plochy objektu podle geometrie, ja
        // to levym klikem jen potvrdim") - skutecne rovinne plochy z mesh
        // geometrie (viz detectGeometricFaces), null = zadne ulozene,
        // pouziva se puvodnich 6 box-connectoru.
        geo_faces: Array.isArray(p.geo_faces) ? p.geo_faces : null,
        is_board_material: !!p.is_board_material,
        // Jednotka ceny a informace, jak k ni backend dosel. U desek posila
        // /api/katalog cenu VZDY prepoctenou na Kc/m2 (viz fetch_katalog_parts)
        // - `price_basis` rika, jestli tak byla zadana ("m2"), nebo se
        // dopocitala z ceny tabule ("m2_z_tabule"), pripadne ze prepocet
        // nesel ("neznamy_prepocet_nelze"). Stejna trida bugu jako u
        // color_hex/is_board_material vyse: bez techhle radku by pole tise
        // zmizela mezi backendem a CATALOG.
        unit: p.unit || null,
        price_basis: p.price_basis || null,
        // Robert 2026-08-08 ("obrazky jako tlacitka" - novy obrazkovy panel
        // katalogu): auto-generovany 3D nahled, viz generateCatalogThumbnails
        // nize. Stejna trida bugu jako color_hex/accessory_conn_enabled vyse -
        // pridano rovnou pri zavedeni pole, nikoli az po nahlasenem "nefunguje".
        thumbnail_file: p.thumbnail_file ? ("katalog/" + p.thumbnail_file + "?v=" + CACHE_BUST) : null,
        // bot7, 2026-08-08 ("toto neni realny rez, ale zjednoduseny model,
        // realne fotky jsou přece stažené z Dogusu"): STEJNA trida bugu jako
        // color_hex/accessory_conn_enabled vyse - fetch_katalog_parts uz pole
        // vraci, bez teto radky by tise chybelo v CATALOG a panel realnych
        // prurezu by tise spadl na GLB fallback u UPLNE VSECH profilu.
        dogus_image_schema_url: p.dogus_image_schema_url || null,
        // Robert 2026-08-09 ("toto bych potreboval natocit kulatinou
        // nahoru") - vychozi orientace pri vlozeni (placeAtOrigin) byla
        // vzdy "horizontal" (lezi na zemi); nektere drobne dily (paticky,
        // sroubovaci patky) davaji vic smysl "svisle", jak byly puvodne
        // exportovane z CAD. Nastavitelne per-produkt v adminu.
        place_vertical: !!p.place_vertical,
      }));
    buildCatalogList();
    renderWizardStep1();
    if (typeof renderCatalogImagePanel === "function") renderCatalogImagePanel();
  })
  .catch(err => {
    if (err.message === "neprihlaseno") return;
    document.getElementById("catalogList").innerHTML =
      '<div style="color:#e07070;font-size:12px;">Nepodařilo se načíst katalog (' + err.message + '). ' +
      'Zkontroluj, že API /api/katalog běží a je dostupné.</div>';
  });

// bot2, 2026-07-28: strom kategorii pro produkty v Katalogu dilu (Robert:
// "ten tam musime zaroven s tim zacit rozvetvovat do kategorii at je v
// tom prehled") - stejny strom, ktery uz pouziva eshop/admin
// (content_categories pres /api/categories), znovupouzity tady jen pro
// razeni produktovych 3D modelu. Verejny endpoint, ale appka je stejne
// cela za loginem.
let CATEGORY_TREE = [];
fetch("/api/categories")
  .then(r => r.ok ? r.json() : { tree: [] })
  .then(data => { CATEGORY_TREE = data.tree || []; buildCatalogList(); })
  .catch(() => {});

// --- Cena spoju + prislusenstvi (rozhodnuti 2026-07-23) - sazba za 1 spoj a
// seznam prislusenstvi (kazde ma cenu/ks a kolik ks pripada na 1 spoj) se
// nacitaji jednou pri startu; samotny vypocet celkove ceny pro AKTUALNI
// sestavu (kolik spoju + kolik kterym prislusenstvim to vychazi) resi
// refreshSummary() nize, protoze potrebuje zivou geometrii/pripojeni.
let PRICING_CONFIG = { joint_price_czk: 0, profile_flat_fee_czk: 0, packaging_pct: 0, montaz_pct: 0, scene_price_coefficient: 1, accessories: [] };
fetch("/api/pricing-config")
  .then(r => r.ok ? r.json() : null)
  .then(data => {
    if (!data) return;
    PRICING_CONFIG = data;
    refreshSummary();
  })
  .catch(() => {});

// --- Uzivatelsky box (jmeno/role + odhlaseni) v hornim panelu ---
let CURRENT_USER = null;

// Snadne prepinani mezi Eshop/3D scena/Administrace (Robert 2026-08-06:
// "potřebuju snadné přepínání mezi eshopem, administrací a scénou, vpravo
// nahoře") - stejna funkce zkopirovana do index/category/product/
// realizace/scene.html (projekt nema sdileny JS soubor mezi strankami).
function renderAreaSwitch(role, current) {
  const items = [
    { key: "eshop", href: "/index.html", label: "Eshop" },
    { key: "scene", href: "/scene.html", label: "3D scéna" },
  ];
  if (role === "admin") items.push({ key: "admin", href: "/admin.html", label: "Administrace" });
  if (role === "admin") items.push({ key: "remeslo", href: "/remeslo.html", label: "Řemeslo" });
  return items.map(it => it.key === current
    ? `<span class="as-item active">${it.label}</span>`
    : `<a class="as-item" href="${it.href}">${it.label}</a>`
  ).join("");
}

fetch("/api/auth/me")
  .then(r => r.ok ? r.json() : { user: null })
  .then(data => {
    CURRENT_USER = data.user;
    // Robert 2026-09-03 ("zakaznikum pristup do sceny neumoznime, neni to
    // vhodne") - scena je od tehle chvile jen pro staff. Backendova API
    // (katalog, custom-shapes, product-assemblies, connector-flags/...)
    // uz jsou @staff_required (api/app.py) - bez tehle kontroly by
    // prihlaseny zakaznik (role='user') videl jen rozbitou stranku plnou
    // 403 chybovych hlasek misto cisteho presmerovani. STAFF_ROLES tady
    // natvrdo = PERMISSION_ROLES v api/app.py (JS nema pristup k Python
    // konstante).
    const STAFF_ROLES = ["admin", "manager", "skladnik", "ucetni", "monter", "sklad"];
    if (CURRENT_USER && !STAFF_ROLES.includes(CURRENT_USER.role)) {
      window.location.href = "/index.html";
      return;
    }
    if (CURRENT_USER) {
      initSupportWidget();
      const currentThemeGuess = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
      applyShopTheme(CURRENT_USER.theme_shop || currentThemeGuess, { persist: false });
    }
    // "Kontrola ploch" (odklikavani funkcnich konektoru prislusenstvi -
    // uklada se trvale do accessory_conn_enabled) je nastroj na SPRAVU
    // katalogu, ne neco pro bezneho zakaznika - Robert 2026-08-01:
    // "tlacitko kontrola ploch je v podstate jen pro admina".
    const btnConnectorReviewEl = document.getElementById("btnConnectorReview");
    if (btnConnectorReviewEl) {
      btnConnectorReviewEl.style.display = (CURRENT_USER && CURRENT_USER.role === "admin") ? "" : "none";
    }
    // bot8 2026-09-15: "Uložit opravu" (přeuložení otevřené sestavy pod
    // stejným ID) - stejny admin-only vzor jako btnConnectorReview vyse,
    // navic gatovano na openedAssemblyId (viz syncResaveOpenedButton ve
    // scene.html - CURRENT_USER se muze naplnit AZ PO mvOpenFromUrl, proto
    // se kontrola dela na obou mistech).
    if (typeof syncResaveOpenedButton === "function") syncResaveOpenedButton();
    // HDRI prostredi - CELA funkce jen pro admina (Robert 2026-08-06:
    // "tu funkci HDRi nechme jen pro admina", pripomenuto znovu po
    // predchozim incidentu "cela scena se rozbila" - pri revertu se
    // gatovani cele sekce ztratilo, zustalo jen na upload/mazani radku;
    // backend api/hdri.py je "@admin_required" na VSECH endpointech
    // vc. GET, takze nemelo smysl UI ukazovat nikomu jinemu).
    const hdriWrapEl = document.getElementById("hdriWrap");
    const isAdminUser = CURRENT_USER && CURRENT_USER.role === "admin";
    if (hdriWrapEl) hdriWrapEl.style.display = isAdminUser ? "flex" : "none";
    const hdriAdminRowEl = document.getElementById("hdriAdminRow");
    if (hdriAdminRowEl) hdriAdminRowEl.style.display = isAdminUser ? "flex" : "none";
    // Robert 2026-08-03 ("zkus pouzit stejny typ nastroje ve scene"): novy
    // debug panel "Kontrola pozic spoje" (viz nize) - stejne admin-only
    // gatovani jako Kontrola ploch, ze stejneho duvodu (diagnosticky
    // nastroj, ne neco pro beznou objednavku).
    const btnJointPositionReviewEl = document.getElementById("btnJointPositionReview");
    if (btnJointPositionReviewEl) {
      btnJointPositionReviewEl.style.display = (CURRENT_USER && CURRENT_USER.role === "admin") ? "" : "none";
    }
    // Nabidka (Robert 2026-08-04) - generuje PDF a uklada na Sdileny disk,
    // backend endpoint /api/admin/scene-offers vyzaduje opravneni
    // sdileny_disk/zobrazit (admin ho ma vzdy - viz has_permission() v
    // app.py) - stejne admin-only gatovani tlacitka jako u vyse uvedenych
    // diagnostickych nastroju, at se neukazuje nekomu, komu by stejne
    // backend odmitl pozadavek.
    const btnGenerateOfferEl = document.getElementById("btnGenerateOffer");
    const btnGenerateOfferRendersEl = document.getElementById("btnGenerateOfferRenders");
    if (btnGenerateOfferRendersEl) btnGenerateOfferRendersEl.style.display = (CURRENT_USER && CURRENT_USER.role === "admin") ? "" : "none";
    const btnTestRendersEl = document.getElementById("btnTestRenders");
    if (btnTestRendersEl) btnTestRendersEl.style.display = (CURRENT_USER && CURRENT_USER.role === "admin") ? "" : "none";
    if (btnGenerateOfferEl) {
      btnGenerateOfferEl.style.display = (CURRENT_USER && CURRENT_USER.role === "admin") ? "" : "none";
    }
    const btnOpenRenderPanelEl = document.getElementById("btnOpenRenderPanel");
    if (btnOpenRenderPanelEl) {
      btnOpenRenderPanelEl.style.display = (CURRENT_USER && CURRENT_USER.role === "admin") ? "" : "none";
    }
    const btnDimStylePreviewEl = document.getElementById("btnDimStylePreview");
    if (btnDimStylePreviewEl) {
      btnDimStylePreviewEl.style.display = (CURRENT_USER && CURRENT_USER.role === "admin") ? "" : "none";
    }
    const btnGenerateCatalogThumbnailsEl = document.getElementById("btnGenerateCatalogThumbnails");
    if (btnGenerateCatalogThumbnailsEl) {
      btnGenerateCatalogThumbnailsEl.style.display = (CURRENT_USER && CURRENT_USER.role === "admin") ? "" : "none";
      btnGenerateCatalogThumbnailsEl.onclick = generateCatalogThumbnails;
    }
    const btnStopCatalogThumbnailsEl = document.getElementById("btnStopCatalogThumbnails");
    if (btnStopCatalogThumbnailsEl) {
      btnStopCatalogThumbnailsEl.onclick = () => { CATALOG_THUMB_CANCEL = true; };
    }
    // Vlastni tvary uz mohly byt nactene drive (custom-shapes fetch nezavisi
    // na poradi) - prekresli, at tlacitko "smazat" spravne zohledni roli
    // (admin smaze cokoli), ne jen "mine" z prvniho vykresleni bez CURRENT_USER.
    //
    // POZOR - PRICINA JE ZAVOD, NE JEN CHYBEJICI FUNKCE (bot3/Robert,
    // 2026-09-11, "jedno nacteni ze dvou" spadalo): `renderCustomShapesTree`
    // je definovana jako FUNCTION DECLARATION uvnitr <script id="app-script">
    // (scene.html) - hoistuje se hned na zacatek TOHOTO bloku, jakmile
    // prohlizec zacne blok spoustet, ne az kdyz parser fyzicky dojde na
    // radek definice. Jenze tenhle soubor (catalog-panels.js) se nacita
    // JAKO <script src> DRIV nez app-script (2 dalsi externi <script src>
    // mezi nimi - hdri-panels-ui.js, material-panel.js) a `fetch("/api/auth/me")`
    // o par radku vys je asynchronni: kdyz server odpovi driv, nez
    // prohlizec vubec ZACNE stahovat/spoustet app-script (napr. behem
    // cekani na tech 5 predchozich externich <script>), .then() nize
    // dobehne s `renderCustomShapesTree` jeste NEDEFINOVANOU - hoisting
    // se totiz tyka jen bloku, ktery uz bezi, ne bloku, ktery se jeste
    // ani nezacal stahovat. Pri pomalejsi odpovedi /api/auth/me (napr.
    // studeny cache) uz app-script mezitim dobehne a funkce existuje -
    // odtud "zhruba jedno nacteni ze dvou", ne stoprocentni chyba.
    //
    // PUVODNI historie: puvodni `refreshCustomShapesPanel()` zanikla pri
    // prestavbe na stromove menu (commit dbfc98c [remove-fn]) - tenhle
    // posledni odkaz na ni prezil a vyjimka "not defined" utnula CELY
    // zbytek callbacku (userBox, logout tlacitko...), presne Robertovo
    // "ctrl+s ve scene nefunguje" 2026-08-06. Nazev uz je od te doby
    // opraveny na existujici `renderCustomShapesTree`, ale to samo
    // neresi ZAVOD popsany vyse - proto navic guard + try/catch: kdyz
    // funkce jeste neexistuje (nebo cokoli uvnitr sama spadne), presne
    // TATO cast se preskoci, ale zbytek callbacku (userBox, odhlaseni)
    // pobezi dal - strom se stejne spravne prekresli o chvili pozdeji
    // samostatnym `csReloadCategoriesAndShapes()` (spusteno primo v
    // app-script), ktery uz CURRENT_USER precte aktualni.
    try {
      if (typeof renderCustomShapesTree === "function") renderCustomShapesTree();
    } catch (e) {
      console.error("renderCustomShapesTree (obnova po přihlášení) selhalo:", e);
    }
    const box = document.getElementById("userBox");
    if (!CURRENT_USER) { box.innerHTML = ""; document.getElementById("areaSwitch").innerHTML = ""; return; }
    document.getElementById("areaSwitch").innerHTML = renderAreaSwitch(CURRENT_USER.role, "scene");
    const roleLabel = { admin: "admin", manager: "manager", user: "uživatel", skladnik: "mistr", ucetni: "asistent", monter: "montér", sklad: "skladník" }[CURRENT_USER.role] || CURRENT_USER.role;
    box.innerHTML = `<span>${CURRENT_USER.name || CURRENT_USER.email} (${roleLabel})</span>` +
      '<button id="btnLogout">Odhlásit se</button>';
    document.getElementById("btnLogout").onclick = () => {
      fetch("/api/auth/logout", { method: "POST" }).then(redirectToLogin);
    };
  });

// --- Podpora (zivy chat) - bot1, 2026-07-25. Faze 1 z SUPPORT_SYSTEM_NAVRH.md.
// Cely konfigurator je za loginem, takze CURRENT_USER je vzdy vyplneny, jakmile
// se widget muze pouzit - napojeni na /api/support/* (viz api/support.py).
let supportChatOpen = false;
let supportChatPollTimer = null;
let supportChatLastMessageId = 0;

function supportChatFormatTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("cs-CZ", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function supportChatRender(data) {
  const log = document.getElementById("supportChatLog");
  const messages = data.messages || [];
  if (!messages.length) {
    log.innerHTML = '<div class="support-msg-empty">Napište nám, poradíme s výběrem profilu i sestavením tvaru.</div>';
    supportChatLastMessageId = 0;
    return;
  }
  log.innerHTML = messages.map(m => {
    const cls = m.sender_type === "customer" ? "customer" : (m.sender_type === "ai" ? "ai" : "operator");
    const who = m.sender_type === "ai" ? "🤖 3Dbot" : (m.sender_type === "operator" ? (m.sender_name || "Podpora") : "Vy");
    const esc = (m.body || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return `<div class="support-msg ${cls}">${esc}<span class="support-msg-meta">${who} · ${supportChatFormatTime(m.created_at)}</span></div>`;
  }).join("");
  log.scrollTop = log.scrollHeight;
  supportChatLastMessageId = messages[messages.length - 1].id;
}

function supportChatUpdateBadge(data) {
  const badge = document.getElementById("supportChatBadge");
  const hasUnread = !!(data.conversation && data.conversation.unread_by_customer) && !supportChatOpen;
  badge.style.display = hasUnread ? "block" : "none";
}

function supportChatLoad() {
  fetch("/api/support/conversation")
    .then(r => r.ok ? r.json() : { conversation: null, messages: [] })
    .then(data => {
      supportChatUpdateBadge(data);
      if (supportChatOpen) supportChatRender(data);
    })
    .catch(() => {});
}

function supportChatSend() {
  const input = document.getElementById("supportChatInput");
  const body = input.value.trim();
  if (!body) return;
  const btn = document.getElementById("btnSupportChatSend");
  btn.disabled = true;
  fetch("/api/support/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  })
    .then(r => r.json())
    .then(() => {
      input.value = "";
      supportChatLoad();
    })
    .finally(() => { btn.disabled = false; });
}

function supportChatSetOpen(open) {
  supportChatOpen = open;
  document.getElementById("supportChatPanel").classList.toggle("open", open);
  if (open) {
    supportChatLoad();
    document.getElementById("supportChatBadge").style.display = "none";
  }
}

function initSupportWidget() {
  document.getElementById("supportChatTab").onclick = () => supportChatSetOpen(!supportChatOpen);
  document.getElementById("supportChatCloseBtn").onclick = () => supportChatSetOpen(false);
  document.getElementById("btnSupportChatSend").onclick = supportChatSend;
  document.getElementById("supportChatInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); supportChatSend(); }
  });
  supportChatLoad();
  supportChatPollTimer = setInterval(supportChatLoad, 4000);
}


// ---------------------------------------------------------------------
// MAZACI IKONA KATALOGU - JEDNO MISTO PRO VSECHNY POLOZKY (Robert 2026-10-03: "neco chci smazat z katalogu z obrazku, ale chybi mazaci ikona -
// udelej script, ktery pohlida, aby se udelala mazaci ikona u kazde nove polozky")
//
// Predtim: seznam (makePartButton) mel ikonu u kazdeho dilu, obrazkovy katalog (makeCatalogImgBtn) JEN u produktu (shop_products) - dily z cfg_dily
// (testovaci/kontrolni polozky "(kontrola)", "(TEST ...)") ikonu nemely a nesly smazat. Ted jsou obe cesty jen volani attachCatalogRemoveButton() a
// ensureCatalogRemoveButtons() hlida (po kazdem vykresleni a pres MutationObserver), ze zadna dlazdice ani radek katalogu ikonu NEPOSTRADA, at ji vytvoril
// jakykoli kod. Staticka kontrola: scripts/qa/catalog_delete_icons.js (spousti ji scripts/qa/static.sh).
//   produkt (shop_products)  -> nedestruktivne vypne "Pro scenu" (karta v obchode zustava)
//   dil z cfg_dily           -> SKUTECNE smazani (DELETE /api/admin/profily/<id>, nevratne, s potvrzenim)
// Jen pro admina (stejne jako drive).
// ---------------------------------------------------------------------
function attachCatalogRemoveButton(btn, p, cls) {
  if (!btn || !p || !CURRENT_USER || CURRENT_USER.role !== "admin") return null;
  if (btn.querySelector(":scope > [data-catalog-remove]")) return null;          // uz ma
  const isProduct = p.source === "product" && p.shop_product_id != null;
  const removeBtn = document.createElement("span");
  removeBtn.className = cls;
  removeBtn.dataset.catalogRemove = isProduct ? "hide" : "delete";
  removeBtn.textContent = "🗑";
  removeBtn.title = isProduct ? "Zrušit \"Pro scénu\" - odebrat z katalogu scény" : "Smazat katalogový díl (nevratné)";
  removeBtn.addEventListener("mousedown", (ev) => { ev.stopPropagation(); });
  removeBtn.addEventListener("click", async (ev) => {
    ev.stopPropagation();
    if (isProduct) {
      if (!confirm(`Zrušit "${p.name}" z katalogu scény (vypne "Pro scénu")?`)) return;
      try {
        const r = await fetch(`/api/shop/products/${p.shop_product_id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ visible_in_scene: false }),
        });
        if (!r.ok) { alert("Nepodařilo se odebrat z katalogu."); return; }
      } catch (err) {
        alert("Chyba: " + err.message);
        return;
      }
    } else {
      if (!confirm(`Trvale smazat katalogový díl "${p.name}"? Tuhle akci nejde vrátit.`)) return;
      try {
        const r = await fetch(`/api/admin/profily/${encodeURIComponent(p.id)}`, { method: "DELETE" });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) { alert(data.error || "Nepodařilo se smazat díl."); return; }
      } catch (err) {
        alert("Chyba: " + err.message);
        return;
      }
    }
    CATALOG = CATALOG.filter(x => x.id !== p.id);
    if (typeof buildCatalogList === "function") buildCatalogList();
    if (typeof renderCatalogImagePanel === "function") renderCatalogImagePanel();
  });
  btn.appendChild(removeBtn);
  return removeBtn;
}

// Hlidac: kazda dlazdice obrazkoveho katalogu (.catalog-img-btn) a kazdy radek seznamu (.part-btn) s data-part-id, ktery ikonu nema, ji dostane.
function ensureCatalogRemoveButtons() {
  if (!CURRENT_USER || CURRENT_USER.role !== "admin" || !Array.isArray(CATALOG)) return 0;
  let doplneno = 0;
  document.querySelectorAll(".catalog-img-btn[data-part-id], #catalogList .part-btn[data-part-id]").forEach(btn => {
    if (btn.querySelector(":scope > [data-catalog-remove]")) return;
    const p = CATALOG.find(x => String(x.id) === btn.dataset.partId);
    if (!p) return;
    if (attachCatalogRemoveButton(btn, p, btn.classList.contains("catalog-img-btn") ? "catalog-img-btn-remove" : "part-btn-remove")) doplneno++;
  });
  return doplneno;
}
let catalogRemoveGuardTimer = null;
function scheduleCatalogRemoveGuard() {
  if (catalogRemoveGuardTimer) return;
  catalogRemoveGuardTimer = requestAnimationFrame(() => { catalogRemoveGuardTimer = null; ensureCatalogRemoveButtons(); });
}
function installCatalogRemoveGuard() {
  ["catalogImgPanelBody", "catalogList", "viewport"].forEach(id => {
    const el = document.getElementById(id);
    if (!el || el._catalogRemoveGuard) return;
    el._catalogRemoveGuard = true;
    new MutationObserver(scheduleCatalogRemoveGuard).observe(el, { childList: true, subtree: id !== "viewport" });
  });
  scheduleCatalogRemoveGuard();
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", installCatalogRemoveGuard); else installCatalogRemoveGuard();

// ---------------------------------------------------------------------
// VZPERA 45 STUPNU S NASTAVITELNOU DELKOU (Robert 2026-10-03: "sikme rozpery = konkretni delka profilu + sikma spojka zrcadlove na obou koncich ... ideálně
// nastavitelné 100-1000 mm" a "kde ty vzpery najdu ve scene v katalogu"). Virtualni polozka katalogu (neni karta v DB, nema vlastni SKU): kliknuti se zepta na delku
// profilu (100-1000 mm) a vlozi hotovy tvar = profil teto delky + sikma spojka na OBOU koncich (zrcadlove). Cena a kusovnik se pocitaji z dilu (profil + 2x spojka).
// Polohy jsou OVERENE na skutecne siti (scripts/2026-10-03_sikma_spojka_30_na_profilu_30.py = tvar #580, #178 = Robertuv vzor pro system 40): spojka lezi svym celem na
// konci profilu (zasunuta 1.5 mm), seznuti vede nahoru a ven, spojka na kladnem konci je zrcadlo prvni (stejny dil, otoceny).
// ---------------------------------------------------------------------
const BRACE_MIN_MM = 100, BRACE_MAX_MM = 1000, BRACE_DEFAULT_MM = 300;
const BRACE_DEFS = {
  "30": { label: "Vzpěra 45° 30×30", profile: "Object_7", connector: "product_3254", yMid: 15, yConn: 30, zOff: 0,
          qA: [0.5, 0.5, -0.5, -0.5], qB: [0.5, 0.5, 0.5, 0.5] },
  "40": { label: "Vzpěra 45° 40×40", profile: "Object_11", connector: "product_3220", yMid: 20, yConn: 19.983817645190204, zOff: 0.16556756019605,
          qA: [-0.7071067811865476, 0, 0, 0.7071067811865475], qB: [0, 0.7071067811865476, 0.7071067811865476, 0] },
};
const BRACE_Q_PROFILE = [-0.7071067811865476, 0, 0, 0.7071067811865476];     // nativni delka profilu (Y) -> -Z

function buildBraceShape(sys, lengthMm) {
  const d = BRACE_DEFS[sys];
  if (!d) return null;
  const L = Math.round(Number(lengthMm));
  if (!(L >= BRACE_MIN_MM && L <= BRACE_MAX_MM)) return null;
  const half = L / 2;
  return {
    id: null, name: `${d.label}, délka ${L} mm`, is_public: false,
    parts: [
      { part_id: d.profile, position: [0, d.yMid, 0], quaternion: BRACE_Q_PROFILE.slice(), scale: [1, L / 1000, 1] },
      { part_id: d.connector, position: [0, d.yConn, -half - d.zOff], quaternion: d.qA.slice(), scale: [1, 1, 1] },
      { part_id: d.connector, position: [0, d.yConn, half + d.zOff], quaternion: d.qB.slice(), scale: [1, 1, 1] },
    ],
    join_groups: [], frame_groups: [], text_labels: [],
  };
}

function insertBraceFromCatalog(sys) {
  const d = BRACE_DEFS[sys];
  if (!d) return;
  const raw = prompt(`${d.label}: délka profilu v mm (${BRACE_MIN_MM}–${BRACE_MAX_MM}).\nNa oba konce se připnou šikmé spojky.`, String(BRACE_DEFAULT_MM));
  if (raw == null) return;
  const L = Number(String(raw).replace(",", ".").replace(/\s|mm/gi, ""));
  const shape = buildBraceShape(sys, L);
  if (!shape) { alert(`Délka musí být celé číslo od ${BRACE_MIN_MM} do ${BRACE_MAX_MM} mm.`); return; }
  if (typeof insertCustomShape === "function") insertCustomShape(shape);
}

// ikona dlazdice: profil se sikmymi konci (SVG data URI, bez souboru)
const BRACE_TILE_ICON = "data:image/svg+xml;utf8," + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 90"><rect width="120" height="90" fill="#2b3340"/>' +
  '<polygon points="14,56 22,40 98,40 106,56 98,50 22,50" fill="#c9ced6" stroke="#8d96a3"/>' +
  '<rect x="22" y="40" width="76" height="10" fill="#dfe3e8" stroke="#8d96a3"/>' +
  '<polygon points="22,40 14,56 22,50" fill="#ff8a2b"/><polygon points="98,40 106,56 98,50" fill="#ff8a2b"/>' +
  '<text x="60" y="76" font-family="sans-serif" font-size="11" fill="#e6e9ee" text-anchor="middle">45°</text></svg>');

function makeBraceTile(sys) {
  const d = BRACE_DEFS[sys];
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "catalog-img-btn";
  btn.dataset.virtualBrace = sys;
  btn.title = `${d.label} – nastavitelná délka ${BRACE_MIN_MM}–${BRACE_MAX_MM} mm\nProfil + šikmá spojka na obou koncích (zrcadlově). Délku zadáš po kliknutí.`;
  const img = document.createElement("img");
  img.src = BRACE_TILE_ICON; img.alt = d.label;
  const label = document.createElement("span");
  label.textContent = d.label + " (délka 100–1000)";
  btn.appendChild(img);
  btn.appendChild(label);
  btn.addEventListener("click", () => insertBraceFromCatalog(sys));
  return btn;
}

function makeBraceListButton(sys) {
  const d = BRACE_DEFS[sys];
  const btn = document.createElement("button");
  btn.className = "part-btn";
  btn.dataset.virtualBrace = sys;
  btn.innerHTML = `${d.label} <span class="badge b-produkt">sestava</span><small>profil nastavitelné délky ${BRACE_MIN_MM}–${BRACE_MAX_MM} mm + 2× šikmá spojka (zrcadlově)</small>`;
  btn.onclick = () => insertBraceFromCatalog(sys);
  return btn;
}

function makePartButton(p, badgeHtml, dimTxt){
  const btn = document.createElement("button");
  btn.className = "part-btn";
  btn.dataset.partId = String(p.id);   // podsviceni oznaceneho dilu, viz highlightCatalogPart
  const w = p.weight_kg != null ? p.weight_kg.toFixed(3) + " kg" : "?";
  const pr = p.price_czk != null ? Math.round(p.price_czk) + " Kč" : "?";
  // Robert 2026-08-05 ("necht se u produktu ve scene zobrazuje pocet ks
  // skladem"): jen u dilu navazanych na skutecnou shop_products kartu -
  // interni/pomocne profily bez skladove evidence (stock_qty null) tenhle
  // udaj proste nemaji, nezobrazuje se u nich vubec.
  const stockTxt = p.stock_qty != null
    ? ` · sklad: ${p.stock_qty} ks${p.stock_qty <= 0 ? " ⚠️" : ""}`
    : "";
  // Robert 2026-08-11 ("katalogove polozky leve menu, ztratili SKU?"):
  // SKU se ze serveru posilalo uz drive, ale zobrazovalo se jen v
  // kusovniku sceny (partDisplayName) - v katalogu chybelo. Ted je na
  // zacatku spodniho radku; kdyz uz ho nazev obsahuje, nepridava se
  // podruhe (stejne pravidlo jako partDisplayName).
  const skuTxt = (p.sku && !String(p.name || "").includes(p.sku))
    ? `<span class="part-btn-sku">${p.sku}</span> · ` : "";
  btn.innerHTML = `${p.name} ${badgeHtml}
    <small>${skuTxt}${dimTxt ? dimTxt + " · " : ""}${w} · ~${pr}${stockTxt}</small>`;
  btn.onclick = () => placeAtOrigin(p);
  // Mazaci ikona: jedno misto pro VSECHNY katalogove dlazdice/radky (attachCatalogRemoveButton nize), viz tez ensureCatalogRemoveButtons.
  attachCatalogRemoveButton(btn, p, "part-btn-remove");
  return btn;
}

// bot2, 2026-07-28: rekurzivne vykresli vetev stromu kategorii (jen ty,
// ktere obsahuji aspon jeden produkt s modelem - drtiva vetsina
// content_categories jinak zustava skryta, aby seznam nebyl zahlcen
// prazdnymi kategoriemi).
function categorySubtreeHasProducts(node, byCategory) {
  if ((byCategory[node.id] || []).length) return true;
  return (node.children || []).some(c => categorySubtreeHasProducts(c, byCategory));
}

// Sbalovani skupin katalogu (Robert 2026-08-12) - jedno misto pro levy
// strom i obrazkovy panel. Klic musi byt stabilni napric prekreslenim
// seznamu, proto se odvozuje od nazvu skupiny / id kategorie.
const CATALOG_GROUPS_OPEN_KEY = "konfCatalogGroupsOpen";
function catalogGroupsOpenState() {
  try { return JSON.parse(localStorage.getItem(CATALOG_GROUPS_OPEN_KEY) || "{}") || {}; }
  catch (e) { return {}; }
}
function catalogGroupIsOpen(key) {
  const st = catalogGroupsOpenState();
  return st[key] === true;   // vychozi = sbaleno (Robert, 2026-08-26 - pri prvnim nacteni
                              // maji byt vsechny polozky katalogu sbalene; jakmile uzivatel
                              // nejakou skupinu rucne rozbali, jeji stav se ulozi a prezije)
}
function catalogGroupSetOpen(key, open) {
  const st = catalogGroupsOpenState();
  st[key] = open;
  try { localStorage.setItem(CATALOG_GROUPS_OPEN_KEY, JSON.stringify(st)); } catch (e) { /* ignoruj */ }
}
// Napoji nadpis + telo skupiny na prepinac. `titleEl` dostane sipku,
// `bodyEls` je jeden nebo vic prvku, ktere se schovavaji.
function wireCatalogGroupToggle(key, titleEl, bodyEls, labelText) {
  const arrow = document.createElement("span");
  arrow.className = "cat-arrow";
  arrow.textContent = "▾";
  titleEl.textContent = "";
  titleEl.appendChild(arrow);
  titleEl.appendChild(document.createTextNode(labelText));
  const bodies = Array.isArray(bodyEls) ? bodyEls : [bodyEls];
  const apply = (open) => {
    titleEl.classList.toggle("is-collapsed", !open);
    bodies.forEach(el => el && el.classList.toggle("is-collapsed", !open));
  };
  apply(catalogGroupIsOpen(key));
  titleEl.addEventListener("click", () => {
    const open = titleEl.classList.contains("is-collapsed");   // prave se rozbaluje
    catalogGroupSetOpen(key, open);
    apply(open);
  });
}

function renderCategoryNode(node, byCategory, container, depth) {
  if (!categorySubtreeHasProducts(node, byCategory)) return;
  const ownParts = byCategory[node.id] || [];
  const h = document.createElement("div");
  h.className = "cat-group-title";
  container.appendChild(h);

  const wrap = document.createElement("div");
  wrap.className = "cat-children";
  container.appendChild(wrap);
  wireCatalogGroupToggle("cat:" + node.id, h, wrap,
    node.name + (ownParts.length ? " (" + ownParts.length + ")" : ""));

  ownParts.forEach(p => {
    wrap.appendChild(makePartButton(p, '<span class="badge b-produkt">produkt</span>', null));
  });
  (node.children || []).forEach(c => renderCategoryNode(c, byCategory, wrap, depth + 1));
}

function buildCatalogList(){
  const listEl = document.getElementById("catalogList");
  listEl.innerHTML = "";

  // bot2, 2026-07-28 (Robert: "nekterym produktum budeme pridavat fbx
  // model k uploadu (obdobne jako pro profily), polozka(produkt) ktery
  // bude mit fbx model, se nasledne pusti do 3D sceny do katalogu, ten
  // tam musime zaroven s tim zacit rozvetvovat do kategorii at je v tom
  // prehled") - katalog se ted deli na dve vetve: puvodni "Profily"
  // (beze zmeny, razeno podle layer alu/black/zinc) a nova "Produkty"
  // (razeno do stromu content_categories, viz CATEGORY_TREE vyse).
  // visible_in_scene=0 tady patri - je to picker "vloz novy dil do sceny",
  // ne resolver ulozenych dat (ten cte CATALOG primo, viz komentar u jeho
  // naplneni vyse). Bez tehle podminky by CATALOG bez fetch-time filtru
  // (viz oprava 2026-09-11) nabizel razitkove dily k rucnimu vlozeni.
  const viditelne = CATALOG.filter(p => p.visible_in_scene);
  const profilParts = viditelne.filter(p => p.source !== "product");
  const productParts = viditelne.filter(p => p.source === "product");

  if (profilParts.length) {
    const profHeader = document.createElement("h2");
    profHeader.textContent = "Profily";
    listEl.appendChild(profHeader);
    const groups = {};
    profilParts.forEach(p => { (groups[p.layer] = groups[p.layer] || []).push(p); });
    Object.keys(groups).sort().forEach(layer => {
      const h = document.createElement("div");
      h.className = "cat-group-title";
      listEl.appendChild(h);
      const layerWrap = document.createElement("div");
      layerWrap.className = "cat-children";
      listEl.appendChild(layerWrap);
      wireCatalogGroupToggle("layer:" + layer, h, layerWrap, layer + " (" + groups[layer].length + ")");
      groups[layer].forEach(p => {
        const dimTxt = (p.cross_section_mm && p.cross_section_mm[0] != null)
          ? `průřez ${p.cross_section_mm[0]}×${p.cross_section_mm[1]} mm · délka ${p.length_mm} mm`
          : `${p.dims_mm[0]}×${p.dims_mm[1]}×${p.dims_mm[2]} mm`;
        layerWrap.appendChild(makePartButton(p, `<span class="badge ${badgeClass(p.layer)}">${p.layer}</span>`, dimTxt));
      });
    });
  }

  // virtualni sestavy dilu (vzpera 45 st. s nastavitelnou delkou, viz BRACE_DEFS)
  {
    const sh = document.createElement("h2");
    sh.textContent = "Sestavy dílů – nastavitelná délka";
    listEl.insertBefore(sh, listEl.firstChild);
    let ref = sh.nextSibling;
    Object.keys(BRACE_DEFS).forEach(sys => listEl.insertBefore(makeBraceListButton(sys), ref));
  }

  if (productParts.length) {
    const prodHeader = document.createElement("h2");
    prodHeader.textContent = "Produkty";
    listEl.appendChild(prodHeader);
    const byCategory = {};
    productParts.forEach(p => { (byCategory[p.category_id] = byCategory[p.category_id] || []).push(p); });
    if (CATEGORY_TREE.length) {
      const wrap = document.createElement("div");
      listEl.appendChild(wrap);
      CATEGORY_TREE.forEach(node => renderCategoryNode(node, byCategory, wrap, 0));
      // Produkty bez kategorie (category_id null) - strom je nezachyti
      // (byCategory[null] nikdy nesedi na zadne skutecne node.id).
      (byCategory[null] || []).forEach(p => {
        listEl.appendChild(makePartButton(p, '<span class="badge b-produkt">produkt</span>', null));
      });
    } else {
      // strom kategorii jeste nedorazil (druhy fetch) - docasny plochy seznam
      productParts.forEach(p => {
        listEl.appendChild(makePartButton(p, '<span class="badge b-produkt">produkt</span>', null));
      });
    }
  }
  // katalog se prekresluje i pozdeji (druhy fetch se stromem kategorii,
  // smazani polozky) - obnov filtr, at hledani po prekresleni nezmizi
  reapplyCatalogSearch();
  ensureCatalogRemoveButtons();                             // hlidac: zadny radek bez mazaci ikony (admin)
}

// ---------------------------------------------------------------------------
// Hledani v levem panelu (Robert 2026-09-05: "Pridej funkci hledat katalogove
// cislo ve scene v levem panelu", upresneno "hledat chci nyni predevsim
// karoserie" a "budu hledat podle nazvu").
//
// PROC: karoserii je 912 (304 modelu x 3 steny L/R_D/B) a v katalogu dilu
// sedi VSECHNY v jedine skupine "auto" pod Profily. Karoserie VCELKU
// (L+R_D+B najednou) jsou navic uplne jinde - jako 304 polozek "... -
// karoserie (L+R_D+B)" v panelu Vlastni tvary. Bez hledani se v tom neda
// nic najit jinak nez scrollovanim.
//
// Proto jedno pole prohledava VSECHNY TRI stromy leveho panelu:
//   #catalogList          - katalog dilu (.part-btn)
//   #customShapesTree     - Vlastni tvary vc. celych karoserii (.custom-shape-btn-wrap)
//   #productAssembliesTree- Hotove sestavy (.custom-shape-btn-wrap)
//
// ZASADA: hledani NESMI zmenit ulozeny stav rozbaleni skupin
// (`is-collapsed`/`konfCatalogGroupsOpen` u katalogu, `expanded`/
// `expandedShapeCategoryIds` u tvaru). Pouziva vlastni, plne reverzibilni
// tridy `search-hit`/`search-miss` + prepinac `is-searching`; po vymazani
// pole se odeberou a strom vypada presne jako predtim.
// ---------------------------------------------------------------------------

// Slozeni diakritiky - Robert bude psat "citroen", ne "Citroën" (a "skoda",
// "peugeot"...). Bez tohohle by se nejpouzivanejsi znacky nenasly.
function catalogSearchFold(s) {
  return String(s == null ? "" : s)
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

// Text polozky se pocita az pri prvnim hledani a cachuje na elementu.
// Po prekresleni stromu jsou elementy nove => cache se prirozene zahodi.
function catalogSearchTextOf(el) {
  if (el._searchText === undefined) el._searchText = catalogSearchFold(el.textContent);
  return el._searchText;
}

const CATALOG_SEARCH_TREES = [
  { rootId: "catalogList", itemSel: ".part-btn", groupSel: ".cat-children",
    titleSel: ".cat-group-title", nodeSel: null },
  { rootId: "customShapesTree", itemSel: ".custom-shape-btn-wrap", groupSel: ".cs-cat-children",
    titleSel: null, nodeSel: ".cs-cat-node" },
  { rootId: "productAssembliesTree", itemSel: ".custom-shape-btn-wrap", groupSel: ".cs-cat-children",
    titleSel: null, nodeSel: ".cs-cat-node" },
];

function applyCatalogSearch(rawQuery) {
  const tokens = catalogSearchFold(rawQuery).split(/\s+/).filter(Boolean);
  const wrapEl = document.getElementById("catalogSearchWrap");
  const countEl = document.getElementById("catalogSearchCount");
  if (wrapEl) wrapEl.classList.toggle("has-query", tokens.length > 0);

  let hits = 0, total = 0;

  CATALOG_SEARCH_TREES.forEach(cfg => {
    const root = document.getElementById(cfg.rootId);
    if (!root) return;

    // uklid predchoziho behu - vzdy, i kdyz se ted hledat nebude
    root.querySelectorAll(".search-hit, .search-miss")
      .forEach(el => el.classList.remove("search-hit", "search-miss"));

    if (!tokens.length) { root.classList.remove("is-searching"); return; }
    root.classList.add("is-searching");

    const items = root.querySelectorAll(cfg.itemSel);
    total += items.length;
    items.forEach(item => {
      const hay = catalogSearchTextOf(item);
      const ok = tokens.every(t => hay.includes(t));
      item.classList.add(ok ? "search-hit" : "search-miss");
      if (!ok) return;
      hits++;
      // oznac celou cestu k tomuhle nalezu, at ho zadny predek neschova
      for (let par = item.parentElement; par && par !== root; par = par.parentElement) {
        if (!par.classList) continue;
        if (par.matches(cfg.groupSel) || (cfg.nodeSel && par.matches(cfg.nodeSel))) {
          par.classList.add("search-hit");
          par.classList.remove("search-miss");
          if (cfg.titleSel) {
            const title = par.previousElementSibling;
            if (title && title.classList && title.matches(cfg.titleSel)) {
              title.classList.add("search-hit");
              title.classList.remove("search-miss");
            }
          }
        }
      }
    });

    // co nema jediny nalez, schovej (vcetne nadpisu skupiny)
    root.querySelectorAll(cfg.groupSel).forEach(g => {
      if (g.classList.contains("search-hit")) return;
      g.classList.add("search-miss");
      if (cfg.titleSel) {
        const title = g.previousElementSibling;
        if (title && title.classList && title.matches(cfg.titleSel)) title.classList.add("search-miss");
      }
    });
    if (cfg.nodeSel) {
      root.querySelectorAll(cfg.nodeSel).forEach(n => {
        if (!n.classList.contains("search-hit")) n.classList.add("search-miss");
      });
    }
    // sekcni nadpisy katalogu ("Profily"/"Produkty") - schovej ten, pod kterym
    // uz nic neni. Jsou to primi sourozenci, ne rodice, takze se musi projit
    // dopredu az k dalsimu <h2>.
    if (cfg.rootId === "catalogList") {
      root.querySelectorAll(":scope > h2").forEach(h2 => {
        let anyHit = false;
        for (let sib = h2.nextElementSibling; sib && sib.tagName !== "H2"; sib = sib.nextElementSibling) {
          if (sib.classList && sib.classList.contains("search-hit")) { anyHit = true; break; }
        }
        if (!anyHit) h2.classList.add("search-miss");
      });
    }
  });

  if (countEl) {
    if (!tokens.length) {
      countEl.textContent = "";
      countEl.classList.remove("is-empty-result");
    } else {
      countEl.textContent = hits ? `${hits} z ${total} položek` : "Nic nenalezeno";
      countEl.classList.toggle("is-empty-result", hits === 0);
    }
  }
}

// Aktualni dotaz drzi primo input - prekresleni stromu si tak filtr obnovi samo.
function reapplyCatalogSearch() {
  const inp = document.getElementById("catalogSearchInput");
  if (inp && inp.value.trim()) applyCatalogSearch(inp.value);
}

function initCatalogSearch() {
  const inp = document.getElementById("catalogSearchInput");
  const clearBtn = document.getElementById("catalogSearchClear");
  if (!inp) return;
  let timer = null;
  const run = () => applyCatalogSearch(inp.value);
  // lehky debounce - pri 900+ karoseriich se tim setri prace pri rychlem psani
  inp.addEventListener("input", () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(run, 90);
  });
  inp.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.preventDefault(); inp.value = ""; applyCatalogSearch(""); }
    // Enter nesmi odeslat/pretocit fokus - pole je samostatny filtr
    if (e.key === "Enter") { e.preventDefault(); if (timer) clearTimeout(timer); run(); }
  });
  if (clearBtn) clearBtn.addEventListener("click", () => {
    inp.value = "";
    applyCatalogSearch("");
    inp.focus();
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initCatalogSearch);
} else {
  initCatalogSearch();
}

// Robert 2026-08-08 ("stromečková struktura leveho katalogu nevyhovuje
// uplne pro prehlednost... plovouci panel, v duchu Menu nastroje, ale
// nebudou tam texty ale obrazky jako tlačitka... vyndat na plochu jako
// oblibene a vratit zpet"): NEZAVISLA obrazkova verze katalogu (levy
// strom zustava beze zmeny). Skupiny jsou zamerne jednodussi nez levy
// strom (profily podle layer, produkty VSECHNY v 1 skupine "Produkty",
// ne cely strom kategorii) - cilem je "co nejmensi plocha", ne 1:1
// zrcadleni stromu. Drag-mechanika (vytazeni na plochu jako oblibene,
// navrat zpet do panelu) je vlastni nezavisla implementace INSPIROVANA
// Menu nastroji (makeToolButtonRelocatable), ne jeho znovupouziti - Menu
// nastroje jsou pevne navazane na existujici HTML tlacitka jednoho
// panelu (#toolsMenuList/#toolsMenuPanel), zatimco tady se tlacitka
// generuji dynamicky ze stovek CATALOG polozek - zavest zavislost by
// riskovalo rozbiti dobre otestovaneho Menu nastroju kvuli zobecnovani.
const CATALOG_IMG_LAYOUT_KEY = "konfCatalogImgPanelLayout";

function loadCatalogImgLayout() {
  try {
    const raw = localStorage.getItem(CATALOG_IMG_LAYOUT_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (e) { return {}; }
}
function saveCatalogImgLayout(layout) {
  try { localStorage.setItem(CATALOG_IMG_LAYOUT_KEY, JSON.stringify(layout)); } catch (e) { /* ignoruj */ }
}

function catalogImgGroupKey(p) { return p.source === "product" ? "produkty" : (p.layer || "ostatni"); }
function catalogImgGroupLabel(key) {
  return ({ alu: "Hliníkové profily", black: "Černé profily", zinc: "Pozinkované profily", produkty: "Produkty" })[key] || key;
}

function isPointOverCatalogImgPanel(x, y) {
  const panel = document.getElementById("catalogImgWindow");
  if (!panel || panel.style.display === "none") return false;
  const r = panel.getBoundingClientRect();
  return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
}

function makeCatalogImgBtnRelocatable(btn, partId) {
  btn.addEventListener("mousedown", (ev) => {
    if (ev.button !== 0) return;
    if (typeof floatingIconsLocked !== "undefined" && floatingIconsLocked) return;   // zamek pozic
    const startX = ev.clientX, startY = ev.clientY;
    let dragging = false, offsetX = 0, offsetY = 0;
    const viewport = document.getElementById("viewport");
    function onMove(mv) {
      const dx = mv.clientX - startX, dy = mv.clientY - startY;
      if (!dragging) {
        if (Math.hypot(dx, dy) < 5) return;
        dragging = true;
        const r = btn.getBoundingClientRect();
        const vpRect = viewport.getBoundingClientRect();
        offsetX = startX - r.left; offsetY = startY - r.top;
        if (btn.parentElement !== viewport) viewport.appendChild(btn);
        btn.classList.add("catalog-img-btn-floating", "catalog-img-btn-dragging");
        btn.style.left = (r.left - vpRect.left) + "px";
        btn.style.top = (r.top - vpRect.top) + "px";
      }
      const vpRect = viewport.getBoundingClientRect();
      btn.style.left = (mv.clientX - vpRect.left - offsetX) + "px";
      btn.style.top = (mv.clientY - vpRect.top - offsetY) + "px";
    }
    function onUp(mv) {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      if (!dragging) return;
      btn.classList.remove("catalog-img-btn-dragging");
      btn._justDragged = true;
      const layout = loadCatalogImgLayout();
      layout.floating = layout.floating || {};
      if (isPointOverCatalogImgPanel(mv.clientX, mv.clientY)) {
        delete layout.floating[partId];
        saveCatalogImgLayout(layout);
        renderCatalogImagePanel();
      } else {
        const vw = viewport.clientWidth, vh = viewport.clientHeight;
        const bw = btn.offsetWidth || 70, bh = btn.offsetHeight || 86;
        const left = Math.max(0, Math.min(vw - bw, parseFloat(btn.style.left) || 0));
        const top = Math.max(0, Math.min(vh - bh, parseFloat(btn.style.top) || 0));
        btn.style.left = left + "px"; btn.style.top = top + "px";
        layout.floating[partId] = { x: left, y: top };
        saveCatalogImgLayout(layout);
      }
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}

// Robert 2026-08-17 ("v katalogu obrazku mi podbarvi ty polozky kde
// potrebujes stanovit dolehaci plochy"): dily, kde bbox-plochy nestaci
// (viz rozek/product_3158 - mezera v T-spoji zpusobena chybejicim
// geo_faces) a Robert je bude oznacovat sam pres ✨ Rozpoznat plochy
// podle geometrie (startGeoFaceTool, kandidati primo z detectGeometricFaces,
// klik = potvrzeni, ulozeno v shop_products.geo_faces_json). Rozsah:
// attach_mode "corner_side"/"parallel_side" (dvoucestne bocni napojeni
// profil-profil pres prislusenstvi - stejna trida chyby jako u roku,
// SKU audit 2026-08-17 potvrdil VSECHNY takove dily bez geo_faces) BEZ
// ulozenych geo_faces. NE "corner3"/"wall"/"endcap" - u tech je bbox
// vetsinou dostacujici (jen nekolik jednotlivych dilu potrebovalo
// geo_faces, ne cela rodina - viz komentar u corner3 v refreshAttachTeachPanel),
// takze plosne podsviceni by tam bylo jen sum.
// OPRAVA (bot8, 2026-08-18, Robert "i kdyz neco odsouhlasim, nakonec to
// zapomenes - nic co se naucis se neuklada spravnym zpusobem na spravnem
// miste"): "naucene" pro corner_side/parallel_side dil NENI jen
// geo_faces (✨ Rozpoznat plochy) - stejne tak plati attach_pose (🎯
// Ulozit pozici / Auto-nauč, presna poza VC. mm odsazeni, ma navic
// PREDNOST pred geo_faces v runCornerSideAut). Puvodni verze kontrolovala
// jen geo_faces, takze dily potvrzene pres attach_pose (i tady hromadne
// dopoctene, viz AGENTS_LOG 2026-08-18) zustavaly falesne podbarvene
// jako "nehotove", presne tenhle dojem "proste to zapomenes" zpusobilo.
function partNeedsGeoFacesReview(p) {
  if (!p || isProfilePart(p) || p.is_board_material) return false;
  if (p.attach_mode !== "corner_side" && p.attach_mode !== "parallel_side") return false;
  const hasGeoFaces = Array.isArray(p.geo_faces) && p.geo_faces.length;
  const hasAttachPose = p.attach_pose && Array.isArray(p.attach_pose.pos) && Array.isArray(p.attach_pose.q);
  return !hasGeoFaces && !hasAttachPose;
}

function makeCatalogImgBtn(p) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "catalog-img-btn";
  btn.dataset.partId = String(p.id);
  btn.title = p.sku ? `${p.name}\nSKU: ${p.sku}` : p.name;
  if (partNeedsGeoFacesReview(p)) {
    btn.classList.add("catalog-img-btn-needs-faces");
    btn.title += "\n⚠ Potřeba stanovit dolehací plochy (✨ Rozpoznat plochy podle geometrie v panelu 🎓 Naučit napojení).";
  }
  const img = document.createElement("img");
  img.src = p.thumbnail_file;
  img.alt = p.name;
  img.loading = "lazy";
  const label = document.createElement("span");
  label.textContent = p.name;
  btn.appendChild(img);
  btn.appendChild(label);
  btn.addEventListener("click", () => {
    if (btn._justDragged) { btn._justDragged = false; return; }
    placeAtOrigin(p);
  });
  makeCatalogImgBtnRelocatable(btn, p.id);
  // Robert 2026-08-08 ("jakmile myš najede na tlacitko obrazku v
  // katalogovem okne, rozbal menší ikonu s nazvem Place All a spáruje se
  // to s funkcemi v Menu nástrojů, které automaticky osadí objekty právě
  // vybranými prvky"): jen u příslušenství (ne profilů/desek - ty se
  // nepřipojují na "plochu profilu", viz isProfilePart/is_board_material).
  // Skryté, objeví se přes CSS :hover (.catalog-img-btn:hover
  // .catalog-img-btn-placeall) - žádný JS mouseenter/leave netřeba.
  if (!isProfilePart(p) && !p.is_board_material) {
    const placeAllBtn = document.createElement("span");
    placeAllBtn.className = "catalog-img-btn-placeall";
    placeAllBtn.textContent = "Place All";
    // Robert 2026-08-12 ("musim te naucit osazovat profily... klikaci
    // prostredi pro odklikavani spravnych postupu"): explicitni
    // attach_mode (naucene v panelu 🎓 Naučit napojení) ma prednost;
    // dokud dil neni naucen, pada se zpet na puvodni hadani podle nazvu
    // (isEndCapPart), aby nic z uz funkcniho neprestalo fungovat.
    //
    // OPRAVA (Robert 2026-08-12, screenshot: naucil endcap, Place All
    // presto spustil UhelnikAut/roh): puvodne se effMode pocital JEDNOU,
    // uz pri VYKRESLENI tlacitka, a uzavrel se v teto funkci - kdyz
    // Robert naucil dil AZ POTOM (bez znovunacteni cele stranky/katalogu),
    // tlacitko porad drzelo starou (nenaucenou) hodnotu z chvile, kdy
    // vzniklo. effMode() je ted funkce - cte p.attach_mode ZIVE, pri
    // kazdem najeti mysi i pri samotnem kliku.
    const effMode = () => p.attach_mode || (isEndCapPart(p) ? "endcap" : "corner");
    const refreshPlaceAllBtn = () => {
      const m = effMode();
      placeAllBtn.title = m === "endcap"
        ? "Osadí tímto dílem všechna VOLNÁ ČELA označených profilů (konce, které na nic nenavazují) odpovídajícího průřezu."
        : m === "wall"
        ? "Osadí tímto dílem BOČNÍ STĚNU (ne roh, ne čelo) každého označeného profilu odpovídajícího průřezu - stejné místo, kam by se díl sám přimagnetoval při ručním tažení."
        : m === "corner3"
        ? "Osadí tímto dílem každý roh, kde se potkávají TŘI navzájem kolmé profily stejného průřezu - pozice i natočení se počítá přímo z geometrie."
        : m === "none"
        ? "Tento díl je nastaven na ČISTĚ RUČNÍ napojení (🎓 Naučit napojení) - Place All se pro něj nepoužívá."
        : m === "parallel_side"
        ? "Osadí tímto dílem švy MEZI dvěma DOTÝKAJÍCÍMI se rovnoběžnými profily stejného průřezu (ne roh) - pozici z boku (🎯 Uložit pozici) použije, pokud je naučená, jinak spočítá sám."
        : "Automaticky osadí tímto dílem všechny kolmé spoje stejného průřezu MEZI OZNAČENÝMI profily (roh = 1 kus, T-spoj = 2 kusy) - stejná detekce jako tlačítka Úhelník/Rožek/Kostka v Menu nástrojů (⟂ Automat), jen pro libovolný díl a jen v rámci výběru, nikdy celá scéna.";
      placeAllBtn.classList.toggle("catalog-img-btn-placeall-disabled", m === "none");
    };
    refreshPlaceAllBtn();
    placeAllBtn.addEventListener("mouseenter", refreshPlaceAllBtn);
    placeAllBtn.addEventListener("mousedown", (ev) => { ev.stopPropagation(); }); // nesmi spustit tazeni/vyjmuti tlacitka
    placeAllBtn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      // Robert 2026-08-08 ("Place All se týká jen vkládání... nazrcadlené
      // na... mini tlačítka... v menu nastrojů to skočí do všech míst na
      // celé scéně, a přes PlaceAll jen na vybrané profily") - stejná
      // funkce jako Menu nástrojů (viz runUhelnikAut), jen s
      // requireSelection:true (žádný tichý fallback na celou scénu).
      const m = effMode();
      if (m === "none") { showJoinToast(`„${p.name}“ je nastaven na ruční napojení - přetáhni ho myší k profilu (magnet).`); return; }
      // bot8 2026-08-20 (Robert: "kloub muze byt na cele ale i na plose
      // profilu" + "kloub nechce aplikovat na stenu"): dily s attach_mode
      // 'endcap' MAJI casto i naucenou wall pozu (kloub 3415: end_face+
      // wall_face soucasne) - Place All ale predtim spoustel VYHRADNE
      // runZaslepkaAut (jen cela), wall_face se z teto cesty NIKDY
      // nepouzil. Kdyz je wall poza naucena, spustit OBE funkce - kazda
      // sama o sobe je no-op (jen toast), kdyz pro ni nejsou cile.
      if (m === "endcap") {
        runZaslepkaAut(p, { requireSelection: true });
        if (p.attach_pose && Number.isInteger(p.attach_pose.wall_face)) runWallAut(p, { requireSelection: true });
      }
      else if (m === "wall") runWallAut(p, { requireSelection: true });
      else if (m === "corner_side") runCornerSideAut(p, { requireSelection: true });
      else if (m === "parallel_side") runParallelSideAut(p, { requireSelection: true });
      else if (m === "corner3") runCorner3Aut(p, { requireSelection: true });
      else runUhelnikAut(p, { requireSelection: true });
    });
    btn.appendChild(placeAllBtn);
  }
  // Mazaci ikona i u dilu z cfg_dily (Robert 2026-10-03: "chybi mazaci ikona" u testovacich polozek v obrazkovem katalogu) - viz attachCatalogRemoveButton.
  attachCatalogRemoveButton(btn, p, "catalog-img-btn-remove");
  return btn;
}

// ---------------------------------------------------------------------
// DYNAMICKY REZIM OBRAZKOVEHO KATALOGU (Robert 2026-08-12)
//
// "chceme 2 rezimy: ten co mame normalni... a zatrzitkem druhy rezim
// dynamicke zobrazovani: kdyz se vlozi profil, automaticky se zive
// odfiltruji/skryji nevhodne nekompatibilni prvky. Pokud je ve scene
// vice ruznych profilu, pribyva tim i prvku v okne katalogu."
// Upresneno: "kompatibilitu urcuje velikost drazky resp slotu a prurez
// profilu" + 4mistne pole v SKU je ROZMER PROFILU (ne dvojice rad) +
// neurcene dily (madla, vzpery) zobrazovat vzdy, ale filtrovat podle
// rozmeru - "madlo nema presahovat svou robustnosti rez profilu".
//
// Zdroj dat = struktura SKU, kterou uz e-shop pouziva:
//     2.2.001 . 08 . 3030 . 01
//               ^^   ^^^^
//            drazka  rozmer profilu (30x30)
// Drazka profilu podle prurezu je z PROFILY_KATALOG.md sekce 2b
// (potvrzeno Robertem u kazdeho profilu zvlast).
// ---------------------------------------------------------------------
const PROFILE_SLOT_BY_CROSS = {   // "sirka x vyska" (mensi x vetsi) -> drazka mm
  "10x40": 6, "20x20": 6, "20x40": 6, "20x80": 6,
  "30x30": 8, "30x60": 8, "35x35": 8,
  "40x40": 10, "40x80": 10, "45x45": 10, "45x90": 10,
};
const PROFILE_SIZE_NUMBERS = [10, 20, 25, 30, 35, 40, 45, 50, 60, 80, 90];

function profileSlotOf(part) {
  const cs = part && part.cross_section_mm;
  if (!cs || cs[0] == null) return null;
  const a = Math.round(Math.min(cs[0], cs[1])), b = Math.round(Math.max(cs[0], cs[1]));
  return PROFILE_SLOT_BY_CROSS[a + "x" + b] || null;
}

// Drazka a rozmery, na ktere je dil (prislusenstvi) urceny. Cte se ze SKU
// i z nazvu - nazvy typu "Drzak kabelu S10" nebo "Uhelnikova spojka 30x30"
// nesou tutez informaci u dilu, kde ji SKU nema.
function partCompatMeta(p) {
  if (p._compat) return p._compat;
  const sku = String(p.sku || "");
  const name = String(p.name || "");
  const seg = sku.split(".");
  let slot = null;
  const sizes = new Set();
  seg.forEach((x, i) => {
    if (i >= 3 && slot === null && (x === "06" || x === "08" || x === "10") && i < seg.length - 1) {
      slot = parseInt(x, 10);
    }
    if (x.length === 4 && /^\d+$/.test(x)) {
      const a = parseInt(x.slice(0, 2), 10), b = parseInt(x.slice(2), 10);
      if (PROFILE_SIZE_NUMBERS.includes(a) && PROFILE_SIZE_NUMBERS.includes(b)) { sizes.add(a); sizes.add(b); }
    }
  });
  const mSlot = name.match(/dr[áa]žk\w*\s*(\d{1,2})|\bS(\d{1,2})\b/i);
  if (slot === null && mSlot) slot = parseInt(mSlot[1] || mSlot[2], 10);
  const reSize = /(\d{2})\s*[xX×]\s*(\d{2,3})/g;
  let m;
  while ((m = reSize.exec(name)) !== null) {
    [m[1], m[2]].forEach(v => { const n = parseInt(v, 10); if (PROFILE_SIZE_NUMBERS.includes(n)) sizes.add(n); });
  }
  p._compat = { slot, sizes: Array.from(sizes) };
  return p._compat;
}

// Co je prave ve scene - drazky, cisla prurezu a nejvetsi prurez (ten
// slouzi jako strop "robustnosti" pro dily bez udaju).
function sceneProfileContext() {
  const slots = new Set(), dims = new Set();
  let maxCross = 0;
  (placed || []).forEach(e => {
    if (!isProfilePart(e.part)) return;
    const slot = profileSlotOf(e.part);
    if (slot) slots.add(slot);
    const cs = e.part.cross_section_mm || [];
    [cs[0], cs[1]].forEach(v => { if (v != null) { dims.add(Math.round(v)); maxCross = Math.max(maxCross, v); } });
  });
  return { slots, dims, maxCross, any: slots.size > 0 || dims.size > 0 };
}

function partFitsScene(p, ctx) {
  if (!ctx.any) return true;                       // prazdna scena = vse
  if (isProfilePart(p)) {
    // Profily: nechat ty, ktere jdou s necim ve scene spojit (stejna
    // drazkova rodina) - jinak by dynamicky rezim znemoznil rozsirit
    // sestavu o dalsi typ profilu.
    const slot = profileSlotOf(p);
    return !slot || ctx.slots.has(slot);
  }
  const meta = partCompatMeta(p);
  if (meta.slot && !ctx.slots.has(meta.slot)) return false;
  if (meta.sizes.length && !meta.sizes.some(n => ctx.dims.has(n))) return false;
  if (!meta.slot && !meta.sizes.length) {
    // Robert: "vzdy, ale s filtraci podle rozmeru - madlo nema presahovat
    // svou robustnosti rez profilu". Dva NEJMENSI rozmery dilu (jeho
    // "usazovaci" prurez, delka je jedno) se porovnaji s nejvetsim
    // prurezem profilu ve scene, s malou rezervou.
    const d = (p.dims_mm || []).filter(v => v != null).map(Number).sort((a, b) => a - b);
    if (d.length >= 2 && ctx.maxCross > 0 && d[1] > ctx.maxCross * 1.35) return false;
  }
  return true;
}

const CATALOG_IMG_DYNAMIC_KEY = "konfCatalogImgDynamic";
function catalogImgDynamicOn() {
  const el = document.getElementById("catalogImgDynamic");
  return !!(el && el.checked);
}
(function initCatalogImgDynamic() {
  const el = document.getElementById("catalogImgDynamic");
  if (!el) return;
  try { el.checked = localStorage.getItem(CATALOG_IMG_DYNAMIC_KEY) === "1"; } catch (e) { /* ignoruj */ }
  el.addEventListener("change", () => {
    try { localStorage.setItem(CATALOG_IMG_DYNAMIC_KEY, el.checked ? "1" : "0"); } catch (e) { /* ignoruj */ }
    renderCatalogImagePanel();
  });
})();

// Robert 2026-08-20 ("jak mam filtrovat napr polozky kompatibilni k
// systemu 30?"): rucni filtr podle rady profilu - vybrany prurez se pro
// filtraci chova PRESNE jako by takovy profil byl ve scene (stejna
// partFitsScene logika: drazka + rozmery + robustnost). Nezavisle na
// scene i na checkboxu dynamiky; volba se pamatuje v localStorage.
const CATALOG_IMG_SYSTEM_KEY = "konfCatalogImgSystem";
let catalogImgSystemWired = false;
function ensureCatalogImgSystemOptions() {
  const sel = document.getElementById("catalogImgSystemFilter");
  if (!sel || !Array.isArray(CATALOG) || !CATALOG.length) return;
  if (sel.options.length <= 1) {
    const seen = new Set();
    CATALOG.filter(p => isProfilePart(p) && p.cross_section_mm && p.cross_section_mm[0] != null).forEach(p => {
      const dims = p.cross_section_mm.slice(0, 2).filter(v => v != null).map(v => Math.round(v)).sort((a, b) => a - b);
      const key = dims.join("x");
      if (seen.has(key)) return;
      seen.add(key);
      const slot = (typeof profileSlotOf === "function") ? profileSlotOf(p) : null;
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = key + (slot ? ` (drážka ${slot} mm)` : "");
      sel.appendChild(opt);
    });
    try {
      const v = localStorage.getItem(CATALOG_IMG_SYSTEM_KEY);
      if (v && [...sel.options].some(o => o.value === v)) sel.value = v;
    } catch (e) { /* ignoruj */ }
  }
  if (!catalogImgSystemWired) {
    catalogImgSystemWired = true;
    sel.addEventListener("change", () => {
      try { localStorage.setItem(CATALOG_IMG_SYSTEM_KEY, sel.value); } catch (e) { /* ignoruj */ }
      renderCatalogImagePanel();
    });
  }
}
function catalogImgSystemCtx() {
  const sel = document.getElementById("catalogImgSystemFilter");
  if (!sel || !sel.value) return null;
  const dims = sel.value.split("x").map(Number).filter(v => !isNaN(v));
  if (!dims.length) return null;
  const rep = CATALOG.find(p => isProfilePart(p) && p.cross_section_mm &&
    p.cross_section_mm.slice(0, 2).filter(v => v != null).map(v => Math.round(v)).sort((a, b) => a - b).join("x") === sel.value);
  const slots = new Set();
  if (rep && typeof profileSlotOf === "function") {
    const s = profileSlotOf(rep);
    if (s) slots.add(s);
  }
  return { slots, dims: new Set(dims), maxCross: Math.max(...dims), any: true };
}

function renderCatalogImagePanel() {
  const body = document.getElementById("catalogImgPanelBody");
  if (!body) return;
  body.innerHTML = "";
  const layout = loadCatalogImgLayout();
  const floating = layout.floating || {};
  let withThumbs = CATALOG.filter(p => p.thumbnail_file);
  // Rucni filtr "System" ma prednost (nezavisi na scene); jinak dynamicky
  // rezim podle profilu ve scene.
  ensureCatalogImgSystemOptions();
  const manualCtx = catalogImgSystemCtx();
  const dynOn = catalogImgDynamicOn();
  const infoEl = document.getElementById("catalogImgDynamicInfo");
  if (manualCtx) {
    const before = withThumbs.length;
    withThumbs = withThumbs.filter(p => partFitsScene(p, manualCtx));
    if (infoEl) {
      const selEl = document.getElementById("catalogImgSystemFilter");
      infoEl.textContent = `· systém ${selEl ? selEl.value : "?"}: ${withThumbs.length}/${before} dílů (bez ohledu na scénu)`;
    }
  } else if (dynOn) {
    const ctx = sceneProfileContext();
    const before = withThumbs.length;
    withThumbs = withThumbs.filter(p => partFitsScene(p, ctx));
    if (infoEl) {
      infoEl.textContent = ctx.any
        ? `· ${withThumbs.length}/${before} dílů (drážka ${Array.from(ctx.slots).sort().join("/") || "?"} mm)`
        : "· scéna je prázdná, zobrazeno vše";
    }
  } else if (infoEl) {
    infoEl.textContent = "";
  }
  const groups = {};
  withThumbs.filter(p => !floating[p.id]).forEach(p => {
    const key = catalogImgGroupKey(p);
    (groups[key] = groups[key] || []).push(p);
  });
  Object.keys(groups).sort().forEach(key => {
    const section = document.createElement("div");
    section.className = "catalog-img-group";
    const h = document.createElement("h5");
    section.appendChild(h);
    const grid = document.createElement("div");
    grid.className = "catalog-img-grid";
    groups[key].forEach(p => grid.appendChild(makeCatalogImgBtn(p)));
    section.appendChild(grid);
    wireCatalogGroupToggle("img:" + key, h, grid,
      catalogImgGroupLabel(key) + " (" + groups[key].length + ")");
    body.appendChild(section);
  });
  if (!withThumbs.length) {
    body.innerHTML = '<div class="hint">Zatím žádný díl nemá vygenerovaný náhled (viz tlačítko "Generovat chybějící náhledy katalogu" nahoře v katalogu, jen pro admina).</div>';
  }
  // virtualni sestavy dilu (vzpera 45 st. s nastavitelnou delkou) - nezavisi na dilech s nahledem ani na filtru systemu
  {
    const section = document.createElement("div");
    section.className = "catalog-img-group";
    const h = document.createElement("h5");
    section.appendChild(h);
    const grid = document.createElement("div");
    grid.className = "catalog-img-grid";
    Object.keys(BRACE_DEFS).forEach(sys => grid.appendChild(makeBraceTile(sys)));
    section.appendChild(grid);
    wireCatalogGroupToggle("img:sestavy-dilu", h, grid, "Sestavy dílů – nastavitelná délka (" + Object.keys(BRACE_DEFS).length + ")");
    body.insertBefore(section, body.firstChild);
  }

  // Jiz drive vytazene (oblibene) - vykreslit primo do #viewport na jejich
  // ulozenou pozici, mimo panel (stejny princip jako Menu nastroje).
  document.querySelectorAll(".catalog-img-btn.catalog-img-btn-floating").forEach(el => el.remove());
  Object.entries(floating).forEach(([partId, pos]) => {
    const p = CATALOG.find(x => x.id === partId);
    if (!p || !p.thumbnail_file) return;
    const btn = makeCatalogImgBtn(p);
    btn.classList.add("catalog-img-btn-floating");
    document.getElementById("viewport").appendChild(btn);
    btn.style.left = (pos.x || 0) + "px";
    btn.style.top = (pos.y || 0) + "px";
  });
  ensureCatalogRemoveButtons();                             // hlidac: zadna dlazdice bez mazaci ikony (admin)
}

// --- Průvodce (wizard): profil -> přednastavený tvar ---
// Krok 1: vyber jednoho zástupce pro každý unikátní průřez (jedno alu id na
// průřez stačí - délka je stejně libovolná, viz VLASTNOSTI_PROFILU.md).
// Krok 2: klik na tvar rovnou vyčistí scénu a poskládá recept (shapeSteps)
// přes stejný runAIPlan, který používá AI modul - stejná fyzika spojů.
//
// OPRAVA (Robert, 2026-09-29, přes screenshot Průvodce: "co to jako je?
// nic takového jsem tam neschvalil" + "poslední 3 rozměry jsou spam"):
// chyběl filtr na `p.visible_in_scene`, takže sem protékaly i technické
// pomocné díly s `layer='alu'`, co nejsou skutečný profil - `vypln_placka`
// (10×16, "Výplň drážky 10mm, Vandr - zapuštěný čep pod razítko"),
// `vypln_placka_30` (8,2×11, totéž pro 30×30) a `vypln_drazky_30`
// (10×30) - všechny `visible_in_scene=0` v `cfg_dily`, žádný z nich
// zákazník nemá jak vybrat jako profil ke stavbě. Stejnou dírou proklouzlo
// i `logo_logiman_cz` (1,39×28, ochranné razítko LOGIMAN.CZ) - stejná
// příčina, opraveno zároveň. Skuteční skrytí sourozenci profilů (radius/
// light/uzavřený varianty, taky `visible_in_scene=0`) dřív neprotékali jen
// náhodou (sdílejí průřez s viditelným profilem, který jde v abecedním
// pořadí dřív) - přidaný filtr je zajistí i do budoucna, ne jen dnešní 4.
let wizardSelectedPart = null;

function uniqueProfilesForWizard() {
  const seen = new Set();
  const list = [];
  CATALOG.filter(p => p.layer === "alu" && p.visible_in_scene && p.cross_section_mm && p.cross_section_mm[0] != null).forEach(p => {
    const key = p.cross_section_mm.slice().sort((a, b) => a - b).join("x");
    if (seen.has(key)) return;
    seen.add(key);
    list.push(p);
  });
  return list;
}

function profileSchemaSvg(p) {
  const a = p.cross_section_mm[0], b = p.cross_section_mm[1];
  const maxDim = Math.max(a, b);
  const scale = 34 / maxDim;
  const w = Math.max(6, a * scale), h = Math.max(6, b * scale);
  const pad = 6;
  const svgW = 46, svgH = 46;
  const x = (svgW - w) / 2, y = (svgH - h) / 2;
  return `<svg width="${svgW}" height="${svgH}" viewBox="0 0 ${svgW} ${svgH}">
    <rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#3a5a7a" stroke="#8fb8e0" stroke-width="1.5"/>
  </svg>`;
}

function renderWizardStep1() {
  const el = document.getElementById("wizardStep1");
  if (!el) return;
  el.innerHTML = "";
  uniqueProfilesForWizard().forEach(p => {
    const btn = document.createElement("button");
    btn.className = "wizard-profile-btn" + (wizardSelectedPart && wizardSelectedPart.id === p.id ? " selected" : "");
    btn.innerHTML = profileSchemaSvg(p) + `<span>${p.cross_section_mm[0]}×${p.cross_section_mm[1]}</span>`;
    btn.title = p.name;
    btn.onclick = () => {
      wizardSelectedPart = p;
      // Robert ("jednou vše problikne na každém tlačitku profilu"): puvodne
      // se tu volalo cele renderWizardStep1() znovu jen kvuli prepnuti
      // .selected tridy - to smaze (innerHTML="") a znovu postavi VSECHNY
      // tlacitka/SVG ikony mrizky, coz je viditelny destroy+rebuild flash
      // cele mrizky pri KAZDEM kliknuti (bez ohledu na cache nahledu tvaru
      // nize). Misto toho jen prepnout tridu na existujicich tlacitkach.
      el.querySelectorAll(".wizard-profile-btn.selected").forEach(b => b.classList.remove("selected"));
      btn.classList.add("selected");
      document.getElementById("wizardStep2Wrap").style.display = "block";
      document.getElementById("wizardSelectedLabel").textContent = "Vybraný profil: " + p.name;
      renderWizardStep2();
    };
    el.appendChild(btn);
  });
}

// Robert 2026-08-09 ("zde preferujeme 3D automaticky nahled namísto
// textu... u obrácených verzí udelej jen příznak, velikost obrazku
// stejne jako mame v katalogu obrazků"): 6 ZAKLADNICH tvaru maji svuj
// vlastni 3D nahled (poskladany ze skutecne aktualne vybraneho profilu
// - viz generateWizardShapeThumbnails), 3 "obracene" varianty (stejny
// vzhled zvenku, jen jina strana spoje/smer) sdili nahled sveho zakladu
// a maji navic jen maly odznak (baseFor).
const WIZARD_SHAPE_DEFS = [
  { id: "segment", label: "Úsečka (1 profil)" },
  { id: "square", label: "Čtverec / rám" },
  { id: "square_reversed", label: "Čtverec / rám (prohozený směr)", baseFor: "square" },
  // Robert 2026-08-16: druha varianta rohu ramu - vsechny 4 profily v plne
  // delce, roh stejny jako u Tvaru L (vnejsi rozmer je pak L+w, ne L). Ma
  // vlastni 3D nahled (je to jiny tvar zvenku, ne jen prohozena strana
  // spoje), proto je i ve WIZARD_BASE_SHAPE_IDS nize.
  // POZOR - poznamka Z PRAXE (Robert 2026-08-16): "vetrnik v praci
  // v podstate nedelame, neni prakticky v zadnem smyslu... mozna jako
  // podstava nejakeho stojanu... jen ti rikam praxi, muze se teoreticky
  // hodit". Tvar tedy ZUSTAVA (Robert vyslovne: "muzes ho nechat"), ale je
  // to OKRAJOVE reseni - NENABIZET ho jako bezny/vychozi zpusob stavby
  // ramu. Bezny ram je "Ctverec / ram" (zkracene pricky, vnejsi presne
  // L x L) - to je varianta, kterou Robert potvrdil 2026-07-23 jako
  // "v praxi nejcastejsi reseni".
  { id: "square_pinwheel", label: "Čtverec / rám (plné profily)" },
  { id: "L", label: "Tvar L" },
  { id: "L_reversed", label: "Tvar L (obrácený spoj)", baseFor: "L" },
  { id: "T", label: "Tvar T" },
  { id: "spatial_L", label: "Prostorový L" },
  { id: "spatial_L_reversed", label: "Prostorový L (obrácený spoj)", baseFor: "spatial_L" },
  { id: "kvadr", label: "Kvádr (krabice)" },
];
const WIZARD_BASE_SHAPE_IDS = ["segment", "square", "square_pinwheel", "L", "T", "spatial_L", "kvadr"];
const WIZARD_SHAPE_THUMB_PLACEHOLDER = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4"><rect width="4" height="4" fill="%2320242b"/></svg>';
const wizardShapeThumbCache = new Map(); // "profileId|shapeId" -> dataURL
// Samostatny, NIKDY do DOM pripojeny renderer pro zachyceni nahledu
// (generateWizardShapeThumbnails i generateCatalogThumbnails) - viz
// suppressMainRender u animate(). Renderuje TENTYZ scene/camera jako
// hlavni viewport (docasne upravene beh generovani), ale do vlastniho
// nezavisleho canvasu, takze hlavni viditelny <canvas> se pri zachytavani
// vubec nemusi prekreslovat/menit velikost. Vytvoren jednou a znovupouzity
// (ne novy WebGLRenderer pri kazdem volani) - kazdy WebGLRenderer drzi
// vlastni WebGL kontext a prohlizece jich povoluji jen omezeny pocet
// soucasne.
const thumbOffscreenRenderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
let wizardShapeThumbGenerating = false;

function renderWizardStep2() {
  const el = document.getElementById("wizardStep2");
  if (!el || !wizardSelectedPart) return;
  const profileId = wizardSelectedPart.id;
  el.innerHTML = "";
  WIZARD_SHAPE_DEFS.forEach(def => {
    const baseId = def.baseFor || def.id;
    const dataUrl = wizardShapeThumbCache.get(profileId + "|" + baseId);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "catalog-img-btn wizard-shape-btn";
    btn.dataset.shape = def.id;
    btn.title = def.label;
    const img = document.createElement("img");
    img.src = dataUrl || WIZARD_SHAPE_THUMB_PLACEHOLDER;
    btn.appendChild(img);
    if (def.baseFor) {
      const badge = document.createElement("span");
      badge.className = "wizard-shape-reversed-badge";
      badge.title = "Obrácený spoj/směr";
      badge.textContent = "⇄";
      btn.appendChild(badge);
    }
    const label = document.createElement("span");
    label.textContent = def.label;
    btn.appendChild(label);
    el.appendChild(btn);
  });
  generateWizardShapeThumbnails(profileId);
}

// Robert ("jednou vse problikne..."): generateWizardShapeThumbnails nize
// pri KAZDEM z az 6 postupne vygenerovanych zakladnich tvaru volalo celou
// renderWizardStep2() znovu - to smaze (innerHTML="") a znovu postavi
// VSECH 9 tlacitek (vc. obrazku) mrizky Kroku 2, takze mrizka viditelne
// probliknula az 6x za sebou behem generovani jednoho profilu. Misto toho
// aktualizovat jen konkretni dokoncena tlacitka (zakladni tvar + jeho
// "obracena" varianta, ktera sdili stejny nahled - viz baseFor) primo,
// beze zmeny zbytku mrizky.
function updateWizardStep2ShapeThumb(profileId, baseShapeId, dataUrl) {
  const el = document.getElementById("wizardStep2");
  if (!el || !wizardSelectedPart || wizardSelectedPart.id !== profileId) return;
  WIZARD_SHAPE_DEFS.forEach(def => {
    if ((def.baseFor || def.id) !== baseShapeId) return;
    const btn = el.querySelector('.wizard-shape-btn[data-shape="' + def.id + '"]');
    const img = btn && btn.querySelector("img");
    if (img) img.src = dataUrl;
  });
}

// Stejny princip jako generateCatalogThumbnails (docasne schovat zivou
// scenu, vykreslit na male ctvercove platno, obnovit) - jen misto
// nacteni 1 GLB se pro kazdy zakladni tvar SKUTECNE POSTAVI (stejnou
// cestou jako skutecne vlozeni, buildNamedShape) a po zachyceni snimku
// zase kompletne uklidi (clearAll), nez se postavi dalsi tvar. Zadna
// zmena na serveru/DB - cistě klientský cache (Map), obnovuje se jen
// pro profily, ktere jeste nebyly v teto relaci vykresleny.
async function generateWizardShapeThumbnails(profileId) {
  if (wizardShapeThumbGenerating) return;
  const missing = WIZARD_BASE_SHAPE_IDS.filter(id => !wizardShapeThumbCache.has(profileId + "|" + id));
  if (!missing.length) return;
  wizardShapeThumbGenerating = true;
  // Robert ("flashuje ale cela scena, ne jen tlacitka") - 3 predchozi
  // pokusy (schovani <canvas> pres visibility, schovani jednotlivych
  // prekryvovych vrstev) porad nechavaly neco probleskavat, protoze
  // schovani nebranilo animate() smycce na pozadi dal prekreslovat/menit
  // hlavni viewport behem docasnych zmen scene/camera nize. Misto toho:
  // hlavni render smycka se na dobu generovani UPLNE VYPNE
  // (suppressMainRender), takze viewport zustane cely tu dobu zamrzly na
  // poslednim spravnem snimku. Zachyceni nahledu bezi na samostatnem,
  // nikdy nezobrazenem thumbOffscreenRenderer (viz jeho deklarace), ne na
  // hlavnim <canvas>u.
  suppressMainRender = true;

  const savedPlaced = placed.slice();
  const savedAxisIndicatorEntries = placed.filter(e => partAxisHelpers.has(e));
  placed.length = 0;
  savedPlaced.forEach(e => { e.object3d.visible = false; });
  if (typeof setHelperMarkersVisible === "function") setHelperMarkersVisible(false);
  const prevRenderMode = renderMode;
  renderMode = "rendered";
  const prevCamPos = camera.position.clone();
  const prevTarget = controls.target.clone();
  const prevAspect = camera.aspect;
  const prevGridVisible = grid.visible;
  const prevShadowGroundVisible = shadowGround.visible;
  grid.visible = false;
  shadowGround.visible = false;

  const THUMB_PX = 200; // stejna velikost jako Katalog (obrázky), viz .catalog-img-btn img
  thumbOffscreenRenderer.setSize(THUMB_PX, THUMB_PX, false);
  camera.aspect = 1;

  try {
    for (const shapeId of missing) {
      try {
        clearAll();
        await buildNamedShape(shapeId, profileId, { keepExisting: false });
        if (placed.length) {
          const box = bboxOfEntries(placed);
          const sphere = box.getBoundingSphere(new THREE.Sphere());
          const center = sphere.center;
          const radius = Math.max(sphere.radius, 10);
          camera.updateProjectionMatrix();
          const fovRad = (camera.fov * Math.PI) / 180;
          const dist = (radius * 1.3) / Math.sin(fovRad / 2);
          const dir = new THREE.Vector3(1, 0.85, 1).normalize();
          camera.position.copy(center).addScaledVector(dir, dist);
          camera.lookAt(center);
          thumbOffscreenRenderer.render(scene, camera);
          const dataUrl = thumbOffscreenRenderer.domElement.toDataURL("image/jpeg", 0.85);
          wizardShapeThumbCache.set(profileId + "|" + shapeId, dataUrl);
          // Aktualizovat jen tohle konkretni tlacitko (+ jeho "obracenou"
          // variantu), ne celou renderWizardStep2() mrizku znovu (viz
          // updateWizardStep2ShapeThumb - jinak by mrizka Kroku 2
          // probliknula az 6x behem generovani jednoho profilu).
          updateWizardStep2ShapeThumb(profileId, shapeId, dataUrl);
        }
      } catch (err) {
        console.error("Náhled tvaru selhal:", shapeId, err);
      }
    }
  } finally {
    clearAll();
    savedPlaced.forEach(e => { e.object3d.visible = true; });
    placed.push(...savedPlaced);
    savedAxisIndicatorEntries.forEach(e => {
      if (!partAxisHelpers.has(e) && typeof addPartAxisIndicator === "function") addPartAxisIndicator(e);
    });
    renderMode = prevRenderMode;
    if (typeof setHelperMarkersVisible === "function") setHelperMarkersVisible(true);
    grid.visible = prevGridVisible;
    shadowGround.visible = prevShadowGroundVisible;
    camera.aspect = prevAspect;
    camera.updateProjectionMatrix();
    camera.position.copy(prevCamPos);
    controls.target.copy(prevTarget);
    controls.update();
    rebuildOccupiedConnectors();
    refreshEndpointMarkers(); refreshDimLabels();
    refreshSummary();
    wizardShapeThumbGenerating = false;
    // Vse vyse plne obnoveno - az TED zase pustit hlavni render smycku a
    // hned vykreslit jeden spravny snimek, misto cekani na dalsi rAF tick.
    suppressMainRender = false;
    renderer.render(scene, camera);
    if (wizardSelectedPart && wizardSelectedPart.id === profileId) renderWizardStep2();
  }
}

// Recepty tvarů - kroky ve stejném formátu, jaký očekává runAIPlan (viz AI stavitel).
// rotation_deg je VŽDY absolutní natočení kolem svislé osy (ne relativní k rodiči),
// proto čtverec potřebuje kumulativní úhly 0/90/180/270, aby se rám skutečně uzavřel.
// conn_idx force-vybere konkrétní konektor rodiče (0/1 = konce, 2 = střed pro T-spoj);
// bez něj se automaticky použije první volný konec.
function shapeSteps(partId, shapeId) {
  switch (shapeId) {
    case "segment":
      return [
        { step: 1, part_id: partId, attach_to: null, rotation_deg: 0 },
      ];
    case "square":
      // POZOR: krok 2 musí být výslovně přišroubovaný na konektor 1 (druhý,
      // "vzdálený" konec) prvního dílu. Bez conn_idx by se automaticky vybral
      // konektor 0 (protože u čerstvě položeného kořenového dílu jsou volné
      // oba konce) - to je ten konec, odkud se díl 1 "nezačíná", takže by se
      // rám místo uzavření roztočil do spirály (přesně bug, co jsi našel).
      return [
        { step: 1, part_id: partId, attach_to: null, rotation_deg: 0 },
        { step: 2, part_id: partId, attach_to: 1, rotation_deg: 90, conn_idx: 1 },
        { step: 3, part_id: partId, attach_to: 2, rotation_deg: 180 },
        { step: 4, part_id: partId, attach_to: 3, rotation_deg: 270 },
      ];
    case "L":
      // Dil 1 (krok 1, attach_to:null) je RODIC - zustava cely/nezkraceny,
      // "pruchozi" (viz 2c). Dil 2 se na nej pripojuje - ten je "pripojovany",
      // dostava offset/zarovnani na konec rodice.
      return [
        { step: 1, part_id: partId, attach_to: null, rotation_deg: 0 },
        { step: 2, part_id: partId, attach_to: 1, rotation_deg: 90 },
      ];
    // "L_reversed" NENI tady - postavit stejnym receptem jako "L" by JEN
    // otocilo cely tvar (pruchozi/pripojovany role zustavaji na stejnych
    // KROCICH, tedy porad stejny spoj - presne tenhle bug Robert opravil:
    // "je to porad stejny spoj"). Skutecne obraceni (prohozeni CISLOVANI,
    // ktery profil je "1" a ktery "2" v Kusovniku/scene) potrebuje jine
    // poradi vkladani do placed[] nez poradi vypoctu geometrie - viz
    // dedikovana funkce buildLReversedShape() nize.
    case "T":
      return [
        { step: 1, part_id: partId, attach_to: null, rotation_deg: 0 },
        { step: 2, part_id: partId, attach_to: 1, rotation_deg: 90, conn_idx: 2 },
      ];
    case "spatial_L":
      return [
        { step: 1, part_id: partId, attach_to: null, rotation_deg: 0 },
        { step: 2, part_id: partId, attach_to: 1, rotation_deg: 90, conn_idx: 0 },
        { step: 3, part_id: partId, attach_to: 1, rotation_deg: 0, conn_idx: 0, orient: "vertical" },
      ];
    default:
      return [];
  }
}

// Kvadr (uzavrena krabice) NENI postaveny pres obecny shapeSteps()/runAIPlan()
// retezec jako ostatni tvary - zkousel jsem to 2x (spojovat sloupky pres
// stejnou "dolehani plochou" logiku jako vodorovne rohy) a pokazde to vyslo
// spatne (bud se horni ram rozjel vuci spodnimu, nebo se sloupky prekryvaly
// s ramem - overeno vypoctem, ne jen okem). Duvod: sloupek stojici v rohu,
// kam se sbihaji 2 vodorovne profily, neni geometricky stejna situace jako
// dva vodorovne profily vedle sebe - "dolehani plochou" tam nema jednoznacny
// smysl. Misto toho: spodni ram se postavi normalne (overeny "square" recept),
// sloupky se postavi primo do jeho rohu, a HORNI RAM JE PRESNA KOPIE
// SPODNIHO (stejne natoceni, jen posunuty nahoru) - tim je matematicky
// zarucene, ze horni ram sedi presne nad spodnim a nikde se nic neprekryva
// (overeno vypoctem vsech 12 dilu proti sobe navzajem, viz VLASTNOSTI_PROFILU.md).
// OPRAVENO 2026-07-23 (2. pokus byl porad spatne - Robert: "porad tam jen
// prohazujes cislovani profilu, 3D objekt se nehne"). Zmereno primo z
// Robertovych referencnich souboru "Profil 30x30 spoj A.fbx" / "...spoj
// B.fbx" (nacteno pres assimp_py, bounding boxy site v mm):
//   Spoj A: svisly dil (Object_8_2) je NEZMENENY/CELY - jde od Y=0 do
//     Y=1000, prochazi presne rohem. Vodorovny dil (Object_8) je
//     PRIPOJOVANY - jeho celo (~X=13.7) dolehá na stenu svisleho dilu
//     hned u jeho paty (Y=0-30).
//   Spoj B: presne OBRACENE - vodorovny dil je ted NEZMENENY/CELY (X=-15
//     az 985, prochazi rohem), svisly dil je PRIPOJOVANY - zvednuty o
//     30mm (Y=30-1030), jeho celo (spodni hrana) dolehá na vrch
//     vodorovneho dilu.
// DULEZITE zjisteni: ROTACE/ORIENTACE obou dilu (kdo je "vodorovny", kdo
// "svisly") se MEZI A a B NEMENI - meni se JEN to, KTERY dil dostane
// offset (pripojovany) a ktery zustane na miste (pruchozi). Predchozi 2
// pokusy byly obe spatne presne proto, ze menily bud jen natoceni (porad
// stejny spoj, jen pootoceny) nebo jen poradi vkladani do placed[]
// (porad stejna geometrie, jen jine cislo u stejneho 3D objektu - presne
// tohle Robert nahlasil jako "3D objekt se nehne").
// Spravne reseni: dil "1" ma STEJNOU rotaci (0°) jako u bezneho "L", dil
// "2" STEJNOU rotaci (90°) jako u "L", STEJNE prirozene poradi vkladani
// do placed[] (1 pak 2) - ale VYPOCET POZICE je obraceny: dil "2" se
// spocita/umisti JAKO PEVNY BOD (nezmeneny, na miste puvodniho rodice),
// a dil "1" se k NEMU pripoji (dostava offset) - i kdyz je cislovany
// "1" a vlozeny do sceny/Kusovniku první. attachEntryToParent() nevyzaduje,
// aby "parent" uz byl v poli `placed` - pracuje primo s 3D transformacemi,
// takze poradi vkladani do `placed` (cislovani) a poradi vypoctu pozice
// (kdo na koho navazuje geometricky) muzou byt nezavisle.
// Spolecna pomocna funkce pro kotveni "obracenych" variant Tvaru L na
// STEJNY vnejsi roh, jaky prirozene vznika u zakladni varianty "Tvar L"
// (a "Tvar L (zmena delek)") - stejna trida opravy jako u Ctverce/ramu
// (viz buildSquareShape, TVARY_PREDNASTAVENE.md 2g), ale aplikovana na dve
// SAMOSTATNE funkce (misto jednoho spolecneho volani pro obe varianty),
// protoze generickou cestu "L" (runAIPlan/shapeSteps, sdilenou i s T a
// spatial_L) nechceme kvuli riziku vedlejsich dopadu menit.
// "Prirozeny roh" spoje = bod, kde se stretava vnejsi stena pruchoziho
// dilu s bodem, kam by dosedla vnejsi stena pripojovaneho dilu - presne
// "krok 1" logiky z attachEntryToParent(), bez "kroku 2" (ten uz jen
// zasouva pripojovany dil zpet podel osy rodice, nemeni polohu rohu).
// OPRAVA (Robert 2026-07-23, "opět to má posun poloviny řezu"): prvni pokus
// (jednoduchy bodovy vzorec "konektor0 + pulsirka*smer") nestacil - nezachytil
// spravne skutecny vnejsi roh CELE sestavy (pogumovany "roh" je 3D bod na
// hrane bounding-boxu obou dilu dohromady, ne jen bod odvozeny z jednoho
// konektoru). U delkove varianty je to jeste zjevnejsi: pripojovany dil se
// tam napojuje BEZ zpetneho zasunuti ("krok 2"), takze fyzicky přečnívá
// kousek za roh rodice - o tenhle previs se puvodni vzorec vubec nestaral.
//
// Novy, spolehlivy pristup: misto odhadovat roh vzorcem, ho ZMERIME -
// sestavime "virtualni" (nevykreslenou) dvojici dilu STEJNOU logikou, jakou
// pouziva skutecna funkce (attachEntryToParent pro pozicni variantu,
// rucni napojeni+zkraceni pro delkovou variantu), a zmerime skutecny
// bounding-box vysledku. To same provedeme pro CILOVOU (zakladni,
// nereverzovanou) variantu tvaru. Rozdil mezi zmerenymi rohy = presny
// posun, ktery potrebuje pruchozi dil "2" v obracene variante.
function virtualEntry(connectorsLocal) {
  return { connectorsLocal, object3d: new THREE.Object3D() };
}

// 8 rohu dilu v jeho VLASTNIM lokalnim souradnem systemu (delkova osa +
// obe prurezove osy, viz computeConnectorsLocal/crossAxesLocal).
function localCorners8(connectorsLocal) {
  const center = connectorsLocal[0].point.clone().add(connectorsLocal[1].point).multiplyScalar(0.5);
  const lengthVec = connectorsLocal[0].point.clone().sub(center);
  const cross = connectorsLocal.crossAxesLocal;
  const out = [];
  [1, -1].forEach(sL => [1, -1].forEach(sA => [1, -1].forEach(sB => {
    out.push(center.clone()
      .addScaledVector(lengthVec, sL)
      .addScaledVector(cross[0].dir, sA * cross[0].halfWidth)
      .addScaledVector(cross[1].dir, sB * cross[1].halfWidth));
  })));
  return out;
}

// Nejmensi roh (min. souradnice ve vsech 3 osach) bounding-boxu zadanych dilu
// (kazdy popsany connectorsLocal/quat/pos/scale) - "vnejsi roh" sestavy L.
function assemblyOuterCornerMin(parts) {
  const min = new THREE.Vector3(Infinity, Infinity, Infinity);
  parts.forEach(p => {
    localCorners8(p.connectorsLocal).forEach(c => {
      const wc = c.clone().multiply(p.scale || new THREE.Vector3(1, 1, 1)).applyQuaternion(p.quat).add(p.pos);
      min.min(wc);
    });
  });
  return min;
}

// Vnejsi roh pro POZICNI spoj (Tvar L / Tvar L, obraceny spoj) - pruchozi dil
// na (0,0,0) s danym natocenim, pripojovany dil pripojeny přes SKUTECNOU
// attachEntryToParent() (stejna funkce, jakou pouziva "Tvar L").
function outerCornerOfPositionJoin(connectorsLocal, throughQuat, childQuat) {
  const through = virtualEntry(connectorsLocal);
  through.object3d.quaternion.copy(throughQuat);
  through.object3d.position.set(0, 0, 0);
  through.object3d.updateMatrixWorld(true);
  const child = virtualEntry(connectorsLocal);
  attachEntryToParent(child, through, childQuat, null, 0);
  return assemblyOuterCornerMin([
    { connectorsLocal, quat: throughQuat, pos: through.object3d.position },
    { connectorsLocal, quat: childQuat, pos: child.object3d.position },
  ]);
}

// Vnejsi roh pro DELKOVY spoj (Tvar L, zmena delek / obraceny) - pruchozi dil
// prodlouzeny o w, pripojovany dil napojeny NAPRIMO (bez odsazeni zpet) a
// zkraceny o w - stejna logika jako buildLLengthShape().
function outerCornerOfLengthJoin(connectorsLocal, throughQuat, childQuat, w) {
  const through = virtualEntry(connectorsLocal);
  through.object3d.quaternion.copy(throughQuat);
  through.object3d.position.set(0, 0, 0);
  through.object3d.updateMatrixWorld(true);
  const L1 = connectorsLocal[0].point.distanceTo(connectorsLocal[1].point);
  if (w && L1) applyLengthScale(through, (L1 + w) / L1, 0);

  const child = virtualEntry(connectorsLocal);
  child.object3d.quaternion.copy(childQuat);
  child.object3d.position.set(0, 0, 0);
  child.object3d.updateMatrixWorld(true);
  const childDirWorld = connectorsLocal[1].point.clone().sub(connectorsLocal[0].point)
    .applyQuaternion(childQuat).normalize();
  const parentConnWorld = worldConnectorsOf(through)[0];
  const parentHalf = crossAxisHalfWidthTowardDirection(connectorsLocal, through.object3d.quaternion, childDirWorld);
  const target = parentConnWorld.point.clone().addScaledVector(childDirWorld, parentHalf);
  const rotatedLocal = connectorsLocal[0].point.clone().applyQuaternion(childQuat);
  child.object3d.position.copy(target.clone().sub(rotatedLocal));
  child.object3d.updateMatrixWorld(true);
  const L2 = connectorsLocal[0].point.distanceTo(connectorsLocal[1].point);
  if (w && L2) applyLengthScale(child, (L2 - w) / L2, 0);

  return assemblyOuterCornerMin([
    { connectorsLocal, quat: throughQuat, pos: through.object3d.position, scale: through.object3d.scale },
    { connectorsLocal, quat: childQuat, pos: child.object3d.position, scale: child.object3d.scale },
  ]);
}

async function buildLReversedShape(partId, opts) {
  opts = opts || {};
  if (!opts.keepExisting) clearAll();
  const part = CATALOG.find(p => p.id === partId);

  // Dil "2" (90°) - PEVNY bod, stejna rotace jako u "L", ale ted hraje roli
  // pruchoziho/nezmeneneho (misto pripojovaneho).
  const obj2 = await loadGlbAsync(part.file);
  applyPartMaterial(obj2, part.layer);
  const entry2 = { part, object3d: obj2, connectorsLocal: computeConnectorsLocal(obj2) };
  const quatThrough2 = baseQuaternion(90);
  const quatChild1 = baseQuaternion(0);
  obj2.quaternion.copy(quatThrough2);
  // OPRAVA (kotva - vnejsi roh, stejna trida jako u Ctverce/ramu): dil "2"
  // tu hraje roli pruchoziho dilu se ZAMENENOU rotaci (90° misto 0° jako u
  // "Tvaru L") - kdyby zustal proste na (0,0,0), jeho vnejsi roh by vysel
  // na jinem miste nez u zakladniho "Tvaru L" (overeno simulaci), takze by
  // se obracena varianta jevila v jine casti sceny. Posunuti o rozdil mezi
  // cilovym rohem ("L"-formule) a prirozenym rohem teto (obracene)
  // konfigurace zajisti, ze obe varianty maji spolecny roh na stejnem miste.
  const targetCorner2 = outerCornerOfPositionJoin(entry2.connectorsLocal, quatChild1, quatThrough2);
  const naturalCorner2 = outerCornerOfPositionJoin(entry2.connectorsLocal, quatThrough2, quatChild1);
  obj2.position.copy(targetCorner2.clone().sub(naturalCorner2));
  obj2.updateMatrixWorld(true);

  // Dil "1" (0°) - pripoji se K DILU "2" (offset/zarovnani na jeho stenu),
  // i kdyz je cislovany a vlozeny do sceny drivo - presny opak "L", kde
  // dil "1" byl ten pevny/nezmeneny.
  const obj1 = await loadGlbAsync(part.file);
  applyPartMaterial(obj1, part.layer);
  const entry1 = { part, object3d: obj1, connectorsLocal: computeConnectorsLocal(obj1) };
  attachEntryToParent(entry1, entry2, quatChild1, null, 0);

  // OPRAVA (Robert 2026-07-23): "obraceni spoje" znamena, ze dite a rodic
  // VYMENI ROLE - NE ze se cela sestava nejak prostorove posune/pretoci.
  // Drivejsi verze tady mela navic globalni -90° korekci celeho tvaru,
  // protoze pevny dil ma jinou prirozenou rotaci (90°) nez u "Tvaru L"
  // (0°) a vysledek se jevil "otoceny" - ale to byla spatna interpretace:
  // zadna dodatecna prostorova korekce se delat NEMA, staci cista zamena
  // roli (kdo je pevny/pruchozi, kdo se pripojuje), zbytek uz resi
  // attachEntryToParent() uplne stejne jako u beznehho "L".
  entry2.wasThrough = true;
  entry1.wasAttached = true;
  obj1.userData.basePos = obj1.position.clone();
  obj2.userData.basePos = obj2.position.clone();
  scene.add(obj1);
  scene.add(obj2);

  // Prirozene cislovani - STEJNE jako u "L" (0° = "1.", 90° = "2."),
  // ZADNE prehazovani poradi vkladani.
  placed.push(entry1, entry2);

  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
}

// "Tvar L (zmena delek)" - LEARNING od Roberta (2026-07-23): existuji 2 ruzne
// zpusoby, jak geometricky vyresit spoj dvou profilu v rohu (viz
// PRAVIDLA_SPOJU.md 2f):
//   1) beze zmeny delky, se zmenou POZICE na podelne ose (= "Tvar L" a
//      "Tvar L (obraceny spoj)" vyse - attachEntryToParent odsazuje
//      pripojovany dil o sirku rodice, delka dilu se nemeni)
//   2) beze zmeny pozice, se zmenou DELEK obou dilu - jeden se ZKRATI o
//      rozmer prurezu (w), druhy se o STEJNY rozmer PRODLOUZI - tim se
//      dosahne stejneho vysledneho tvaru rohu, aniz by se cokoli posouvalo
//      mimo svou puvodni osu/pocatecni bod.
// Tady je implementovana varianta 2): dil "1" (pruchozi, 0°) zustava na
// SVEM prirozenem miste (roh = pocatek souradnic, presne jako u "Tvaru L")
// a jen se PRODLOUZI o w na svem volnem konci (rohovy konec se nehne). Dil
// "2" (pripojovany, 90°) se napoji NAPRIMO na rohovy konektor dilu "1" BEZ
// dodatecneho pozicniho odsazeni (na rozdil od attachEntryToParent) a
// nasledne se ZKRATI o w se zafixovanym VZDALENYM (volnym) koncem - jeho
// blizky/rohovy konec se tak sam odsune o w a spravne dolehne na stenu
// dilu "1", presne jako u "Tvaru L", ale zmenou delky misto zmeny pozice.
async function buildLLengthShape(partId, opts) {
  opts = opts || {};
  if (!opts.keepExisting) clearAll();
  const part = CATALOG.find(p => p.id === partId);
  const w = (part.cross_section_mm && part.cross_section_mm[0]) || 0;

  // Dil "1" (0°) - pruchozi, na miste jako u "Tvaru L", prodlouzeny o w na
  // volnem konci (roh = konektor 0, musi zustat pevny).
  const obj1 = await loadGlbAsync(part.file);
  applyPartMaterial(obj1, part.layer);
  const entry1 = { part, object3d: obj1, connectorsLocal: computeConnectorsLocal(obj1) };
  obj1.quaternion.copy(baseQuaternion(0));
  obj1.position.set(0, 0, 0);
  obj1.updateMatrixWorld(true);
  const cornerConnIdx1 = 0;
  const L1 = entry1.connectorsLocal[0].point.distanceTo(entry1.connectorsLocal[1].point);
  if (w && L1) applyLengthScale(entry1, (L1 + w) / L1, cornerConnIdx1);

  // Dil "2" (90°) - napojeny NAPRIMO (bez odsazeni) na rohovy konektor
  // dilu "1", pak zkraceny o w se zafixovanym volnym koncem.
  const obj2 = await loadGlbAsync(part.file);
  applyPartMaterial(obj2, part.layer);
  const entry2 = { part, object3d: obj2, connectorsLocal: computeConnectorsLocal(obj2) };
  const quat2 = baseQuaternion(90);
  obj2.quaternion.copy(quat2);
  obj2.position.set(0, 0, 0);
  obj2.updateMatrixWorld(true);
  const childConnIdx2 = 0;
  const farConnIdx2 = 1;
  // POTVRZENO Robertem (varianta "C" z porovnavacich obrazku, 2026-07-23):
  // dil "2" musi dosednout na VNEJSI stenu dilu "1" (odsazeno od jeho
  // stredove osy o polovinu jeho sirky), ne na jeho stredovou osu - to byl
  // puvodni bug ("prunik do dilu 1" na Robertove screenshotu). Stejny
  // "krok 1" I "krok 2" jako v attachEntryToParent() - drivejsi verze
  // krok 2 vynechavala s (chybnym) tvrzenim, ze ho nahradi nasledne
  // zkraceni delky dilu 2 - viz OPRAVA komentar u childHalf2 nize.
  const otherChildConnIdx2 = 1 - childConnIdx2;
  const childDirWorld2 = entry2.connectorsLocal[otherChildConnIdx2].point.clone()
    .sub(entry2.connectorsLocal[childConnIdx2].point)
    .applyQuaternion(quat2)
    .normalize();
  const parentConnWorld = worldConnectorsOf(entry1)[cornerConnIdx1];
  const parentHalf2 = crossAxisHalfWidthTowardDirection(entry1.connectorsLocal, obj1.quaternion, childDirWorld2);
  const target2 = parentConnWorld.point.clone().addScaledVector(childDirWorld2, parentHalf2);
  // OPRAVA (bot8 2026-08-19, nalezeno hloubkovou matematickou kontrolou na
  // realne .glb geometrii): drivejsi verze VYNECHAVALA zasunuti dilu "2"
  // podel osy dilu "1" (komentar vyse tvrdil, ze ho "resi az nasledne
  // zkraceni delky" - to je ale geometricky spatne: zkraceni pusobi podel
  // VLASTNI osy dilu 2, kolme na osu dilu 1, takze zub v ose dilu 1 vubec
  // neovlivni). Dusledek, zmereno presne: dil 2 precnival o polovinu sveho
  // prurezu (15mm u 30x30) ZA konec dilu 1 ("zub") a jeho celo bylo kryte
  // jen z poloviny - presne ta chyba, kterou Robert reklamoval u Ctverce
  // ("zeleny profil musi jit zarovno koncem bileho") a ktera tam uz opravu
  // MA (placeAttached: posun o vlastni pulsirku dovnitr) - tyhle dve
  // funkce (L_length + L_length_reversed) ji nikdy nedostaly. Poruseni
  // dokumentovane varianty C ("zadny presah") i nadrazeneho pravidla
  // "zadne castecne kryte celo" (VLASTNOSTI_PROFILU.md). Stejny "krok 2"
  // jako attachEntryToParent: zasunout dil 2 o jeho vlastni pulsirku
  // DOVNITR podel osy dilu 1 (proti vnejsi normale rohoveho konektoru).
  // Overeno na 3 realnych profilech vc. pivot-offset 30x30: presah 0.0000,
  // kryti cela plne, gap 0.0000, delky L+w/L-w zachovane.
  const childHalf2 = crossAxisHalfWidthTowardDirection(entry2.connectorsLocal, quat2, parentConnWorld.normal);
  target2.addScaledVector(parentConnWorld.normal, -childHalf2);
  const rotatedLocal2 = entry2.connectorsLocal[childConnIdx2].point.clone().applyQuaternion(quat2);
  obj2.position.copy(target2.clone().sub(rotatedLocal2));
  obj2.updateMatrixWorld(true);
  entry1.usedConn = entry1.usedConn || new Set();
  entry1.usedConn.add(cornerConnIdx1);
  entry2.usedConn = new Set([childConnIdx2]);
  // Dil 2 dosedl celou svou plochou na stenu dilu 1 - ta plocha uz neni
  // zvenku videt, takze se na ni nema kreslit textura cela.
  entry2.hiddenEndConn = new Set([childConnIdx2]);

  // OPRAVA (Robertovo hlaseni "odskocilo to" - mezera mezi dily): puvodne
  // se tu zkraceni delalo se zafixovanym VZDALENYM koncem (farConnIdx2),
  // coz ale znamena, ze se BLIZKY/rohovy konec (ktery uz drive presne
  // dosedl na dil "1") pri zkracovani odsune SMEREM OD rohu - presne to
  // vytvorilo tu mezeru. Dil "2" uz na rohovem konektoru spravne "dosedal"
  // (viz vyse, napojeni bez odsazeni) - zkraceni proto MUSI drzet TENTO
  // (blizky, cornConnIdx2) konec pevny a ubirat delku z volneho konce,
  // aby zustalo spojene presne podle pravidla "kratsi celem k delsimu".
  const L2 = entry2.connectorsLocal[0].point.distanceTo(entry2.connectorsLocal[1].point);
  if (w && L2) applyLengthScale(entry2, (L2 - w) / L2, childConnIdx2);

  entry1.wasThrough = true;
  entry2.wasAttached = true;
  entry2.jointCount = (entry2.jointCount || 0) + 1;
  linkJointPeers(entry1, entry2);
  // Robert 2026-08-16 (Stage 2 oprava #3, "zacneme od nuly"): tahle
  // "stavěcí" funkce (na rozdil od attachEntryToParent-based sourozencu
  // vyse) nikdy nenastavovala lastJoint - R-cykleni (R/prstenec) na
  // takhle vytvorenem spoji bylo mrtve. iHoldCount kopiruje uz existujici
  // pravidlo o par radku vyse (jointCount drzi entry2/pripojovany dil).
  entry1.lastJoint = { otherEntry: entry2, myConnIdx: cornerConnIdx1, otherConnIdx: childConnIdx2, iHoldCount: false };
  entry2.lastJoint = { otherEntry: entry1, myConnIdx: childConnIdx2, otherConnIdx: cornerConnIdx1, iHoldCount: true };

  obj1.userData.basePos = obj1.position.clone();
  obj2.userData.basePos = obj2.position.clone();
  scene.add(obj1);
  scene.add(obj2);
  placed.push(entry1, entry2);

  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
}

// "Tvar L (zmena delek, obraceny spoj)" - zrcadlena verze buildLLengthShape():
// role jsou prohozene, dil "2" (90°) je ted PRUCHOZI (prodlouzeny o w, na
// svem miste jako pevny bod), dil "1" (0°) je ted PRIPOJOVANY (dosedne na
// VNEJSI stenu dilu "2", pak se zkrati o w). Cislovani zustava PRIROZENE
// (0° = "1.", 90° = "2.") - stejny princip jako u pozicni varianty
// "Tvar L (obraceny spoj)" / buildLReversedShape(). POTVRZENO Robertem
// jako varianta "C'" (zrcadlo "C") z porovnavacich obrazku, 2026-07-23.
async function buildLLengthReversedShape(partId, opts) {
  opts = opts || {};
  if (!opts.keepExisting) clearAll();
  const part = CATALOG.find(p => p.id === partId);
  const w = (part.cross_section_mm && part.cross_section_mm[0]) || 0;

  // Dil "2" (90°) - ted pruchozi, na miste (roh = pocatek souradnic),
  // prodlouzeny o w na volnem konci.
  const obj2 = await loadGlbAsync(part.file);
  applyPartMaterial(obj2, part.layer);
  const entry2 = { part, object3d: obj2, connectorsLocal: computeConnectorsLocal(obj2) };
  const quat2 = baseQuaternion(90);
  const quat1ForCorner = baseQuaternion(0);
  obj2.quaternion.copy(quat2);
  // OPRAVA (kotva - vnejsi roh, stejna logika jako u buildLReversedShape a
  // Ctverce/ramu): pred zafixovanim rohoveho konektoru (nasledujici
  // applyLengthScale) posunout dil "2" tak, aby jeho vlastni "prirozeny
  // roh" (kdyby zustal na (0,0,0)) padl na STEJNE misto jako u zakladni
  // varianty "Tvar L (zmena delek)" - jinak by obracena varianta vznikla
  // jinde ve scene nez normalni.
  const targetCorner2 = outerCornerOfLengthJoin(entry2.connectorsLocal, quat1ForCorner, quat2, w);
  const naturalCorner2 = outerCornerOfLengthJoin(entry2.connectorsLocal, quat2, quat1ForCorner, w);
  obj2.position.copy(targetCorner2.clone().sub(naturalCorner2));
  obj2.updateMatrixWorld(true);
  const cornerConnIdx2 = 0;
  const L2 = entry2.connectorsLocal[0].point.distanceTo(entry2.connectorsLocal[1].point);
  if (w && L2) applyLengthScale(entry2, (L2 + w) / L2, cornerConnIdx2);

  // Dil "1" (0°) - ted pripojovany: dosedne na VNEJSI stenu dilu "2"
  // (stejny "krok 1" I "krok 2" jako v attachEntryToParent - viz OPRAVA
  // zub-fix nize), pak se zkrati o w se zafixovanym blizkym/rohovym koncem.
  const obj1 = await loadGlbAsync(part.file);
  applyPartMaterial(obj1, part.layer);
  const entry1 = { part, object3d: obj1, connectorsLocal: computeConnectorsLocal(obj1) };
  const quat1 = baseQuaternion(0);
  obj1.quaternion.copy(quat1);
  obj1.position.set(0, 0, 0);
  obj1.updateMatrixWorld(true);
  const childConnIdx1 = 0;
  const otherChildConnIdx1 = 1 - childConnIdx1;
  const childDirWorld1 = entry1.connectorsLocal[otherChildConnIdx1].point.clone()
    .sub(entry1.connectorsLocal[childConnIdx1].point)
    .applyQuaternion(quat1)
    .normalize();
  const parentConnWorld = worldConnectorsOf(entry2)[cornerConnIdx2];
  const parentHalf1 = crossAxisHalfWidthTowardDirection(entry2.connectorsLocal, obj2.quaternion, childDirWorld1);
  const target1 = parentConnWorld.point.clone().addScaledVector(childDirWorld1, parentHalf1);
  // OPRAVA (bot8 2026-08-19): stejny chybejici zub-fix jako u
  // buildLLengthShape vyse (viz obsahly komentar tam) - zrcadlene role,
  // dil "1" se zasouva dovnitr podel osy dilu "2".
  const childHalf1 = crossAxisHalfWidthTowardDirection(entry1.connectorsLocal, quat1, parentConnWorld.normal);
  target1.addScaledVector(parentConnWorld.normal, -childHalf1);
  const rotatedLocal1 = entry1.connectorsLocal[childConnIdx1].point.clone().applyQuaternion(quat1);
  obj1.position.copy(target1.clone().sub(rotatedLocal1));
  obj1.updateMatrixWorld(true);
  entry2.usedConn = entry2.usedConn || new Set();
  entry2.usedConn.add(cornerConnIdx2);
  entry1.usedConn = new Set([childConnIdx1]);
  entry1.hiddenEndConn = new Set([childConnIdx1]);

  const L1 = entry1.connectorsLocal[0].point.distanceTo(entry1.connectorsLocal[1].point);
  if (w && L1) applyLengthScale(entry1, (L1 - w) / L1, childConnIdx1);

  entry2.wasThrough = true;
  entry1.wasAttached = true;
  entry1.jointCount = (entry1.jointCount || 0) + 1;
  linkJointPeers(entry1, entry2);
  // Robert 2026-08-16 (Stage 2 oprava #3) - viz stejny komentar v
  // buildLLengthShape(); zrcadlene role (jointCount tu drzi entry1).
  entry2.lastJoint = { otherEntry: entry1, myConnIdx: cornerConnIdx2, otherConnIdx: childConnIdx1, iHoldCount: false };
  entry1.lastJoint = { otherEntry: entry2, myConnIdx: childConnIdx1, otherConnIdx: cornerConnIdx2, iHoldCount: true };

  obj1.userData.basePos = obj1.position.clone();
  obj2.userData.basePos = obj2.position.clone();
  scene.add(obj1);
  scene.add(obj2);
  // Prirozene cislovani - stejne jako u normalni varianty (0° = "1.", 90° = "2.")
  placed.push(entry1, entry2);

  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
}

// Spolecne pomocne funkce pro kotveni "Prostoroveho L" na SKUTECNY vnejsi
// roh cele sestavy (ne na centerline konektor) - Robert 2026-07-23: "vykazuje
// posun o polovinu rezu jako v predeslych pripadech". Prvni verze kotvila
// jen samotny konektor 0 dilu "1" (bez korekce na pulsirku prurezu) - stejna
// nedostatecna chyba, jakou uz jsme opravovali u Ctverce/ramu a Tvaru L (viz
// TVARY_PREDNASTAVENE.md 2h). Tady navic (na rozdil od plocheho L) NEPOUZIVAME
// bodovy vzorec ani pro "cilovy" roh - rovnou MERIME skutecny bounding-box
// cele 3dilne sestavy (2 vodorovne + 1 svisly sloupek), protoze rucni odvozeni
// vzorce pro roh, kde se navic uplatnuje i VYSKA sloupku, uz je prilis
// nachylne na chybu (presne poucení z oprav Tvaru L).
function sceneLocalCorners8(connectorsLocal) {
  const center = connectorsLocal[0].point.clone().add(connectorsLocal[1].point).multiplyScalar(0.5);
  const lengthVec = connectorsLocal[0].point.clone().sub(center);
  const cross = connectorsLocal.crossAxesLocal;
  const out = [];
  [1, -1].forEach(sL => [1, -1].forEach(sA => [1, -1].forEach(sB => {
    out.push(center.clone()
      .addScaledVector(lengthVec, sL)
      .addScaledVector(cross[0].dir, sA * cross[0].halfWidth)
      .addScaledVector(cross[1].dir, sB * cross[1].halfWidth));
  })));
  return out;
}
function sceneAssemblyBBoxMin(parts) {
  const min = new THREE.Vector3(Infinity, Infinity, Infinity);
  parts.forEach(p => {
    sceneLocalCorners8(p.connectorsLocal).forEach(c => {
      const wc = c.clone().applyQuaternion(p.quat).add(p.pos);
      min.min(wc);
    });
  });
  return min;
}
// Sestavi "virtualni" (nevykreslenou) trojici dilu STEJNOU logikou jako
// skutecna funkce (attachEntryToParent), aby se dal zmerit skutecny
// bounding-box PRED nacitanim GLB souboru (staci sdilet connectorsLocal ze
// stejneho profilu). throughQuat = natoceni pruchoziho dilu "1" (nebo "2" u
// obracene varianty), attachQuat = natoceni pripojovaneho vodorovneho dilu.
//
// OPRAVA (3. kolo, Robert: "vnejsich rohu, nikoli os profilu" - opravnene
// druhe upozorneni): puvodni verze tehle funkce merila bounding-box se
// SLOUPKEM PRED retreat opravou (viz buildSpatialLShape nize) - tedy se
// sloupkem jeste centrovanym presne na konektoru, ktery v tomhle smeru
// prectuhoval DAL nez skutecne vodorovne nohy L. Kotva se tak spocitala
// podle "vnejsiho rohu" definovaneho SLOUPKEM (jeho docasnym presahem), ne
// podle skutecneho vnejsiho rohu vodorovnych profilu - jakmile se pak
// sloupek retreat opravou zatahl zpet (viz nize), cela sestava se ocitla
// posunuta o presne polovinu prurezu (15mm pro 30mm profil) OPROTI puvodne
// zamerenemu rohu. Overeno Node.js simulaci (sim23/sim24) - bez teto
// opravy vychazel finalni bounding-box na (0,0,15) mm misto (0,0,0).
// Oprava: virtualni mereni ted aplikuje STEJNY retreat na sloupek, jaky
// pouziva realna konstrukce - zmereny roh tak uz odpovida SKUTECNE
// geometrii po vsech opravach, ne mezikroku pred nimi.
function spatialLOuterCornerMin(connectorsLocal, throughQuat, attachQuat) {
  const through = { connectorsLocal, object3d: new THREE.Object3D() };
  through.object3d.quaternion.copy(throughQuat);
  through.object3d.position.set(0, 0, 0);
  through.object3d.updateMatrixWorld(true);
  const attached = { connectorsLocal, object3d: new THREE.Object3D() };
  attachEntryToParent(attached, through, attachQuat, 0, 0);
  const column = { connectorsLocal, object3d: new THREE.Object3D() };
  attachEntryToParent(column, through, baseQuaternion(0, "vertical"), 0, 1);
  const conn0NormalWorld = worldConnectorsOf(through)[0].normal.clone();
  const colHalf = crossAxisHalfWidthTowardDirection(column.connectorsLocal, column.object3d.quaternion, conn0NormalWorld);
  column.object3d.position.addScaledVector(conn0NormalWorld, -colHalf);
  column.object3d.updateMatrixWorld(true);
  return sceneAssemblyBBoxMin([
    { connectorsLocal, quat: through.object3d.quaternion, pos: through.object3d.position },
    { connectorsLocal, quat: attached.object3d.quaternion, pos: attached.object3d.position },
    { connectorsLocal, quat: column.object3d.quaternion, pos: column.object3d.position },
  ]);
}

// "Prostorovy L" (roh se svislym sloupkem) - Robert 2026-07-23: "musi byt
// zarovnany rohem na stred" + (2. kolo, "stale ses nepoucil") "zarovnat
// VNEJSIMI rohy na stredu, vykazuje posun o polovinu rezu". Puvodne se
// tenhle tvar stavel pres genericky shapeSteps("spatial_L")/runAIPlan()
// retezec (viz case "spatial_L" vyse) - ten zustava netknuty (uz se
// nepouziva pro tlacitko v panelu), protoze sdili kod s "L" a "T" a
// nechceme tam riskovat vedlejsi dopady.
//
// OPRAVA (2. kolo): misto kotveni na samotny konektor 0 (centerline bod,
// stejna nedostatecna chyba jako u Ctverce/L pred opravou "vnejsi roh") se
// cely tvar postavi, zmeri se jeho SKUTECNY bounding-box (pres
// spatialLOuterCornerMin - virtualni sestava, presne kopiruje realnou
// konstrukci nize) a cely tvar (vsechny 3 dily) se posune tak, aby tenhle
// zmereny vnejsi roh (min. souradnice ve vsech 3 osach) padl presne na
// (0,0,0).
//
// Druha cast opravy: sloupek (dil "3") pripojeny na konektor 0 pres
// orient:"vertical" prirozene DOSEDA spravne SVISLE (attachEntryToParent
// uz ho zvedne o pulsirku rodice, takze spodni celo sedi presne na horni
// stene vodoroveho dilu - to bylo v poradku uz drive), ale VODOROVNE
// (podel delkove osy pruchoziho dilu) byl centrovany PRESNE NA konektoru,
// takze polovina jeho vlastniho prurezu prectuhovala DO PRAZDNA za spicku
// pruchoziho dilu ("bez presahu" - Robertovo hlaseni). Oprava: sloupek se
// posune zpet (retreat) o svou vlastni pulsirku prurezu ve smeru OPACNEM
// nez je vnejsi normala konektoru 0 pruchoziho dilu (tedy DOVNITR, smerem
// k telu pruchoziho dilu) - stejny princip jako "krok 2" v
// attachEntryToParent (tam se pro svisle spoje zamerne vynechava, protoze
// normalne resi jen prekryv s "protejsim koncem" ve vodorovne rovine - tady
// ho ale potrebujeme aplikovat rucne, aby sloupek nedosahal do prazdna).
async function buildSpatialLShape(partId, opts) {
  opts = opts || {};
  if (!opts.keepExisting) clearAll();
  const part = CATALOG.find(p => p.id === partId);
  const quat1 = baseQuaternion(0);
  const quat2 = baseQuaternion(90);

  const obj1 = await loadGlbAsync(part.file);
  applyPartMaterial(obj1, part.layer);
  const entry1 = { part, object3d: obj1, connectorsLocal: computeConnectorsLocal(obj1) };
  obj1.quaternion.copy(quat1);
  obj1.position.set(0, 0, 0);
  obj1.updateMatrixWorld(true);

  // Zmer skutecny vnejsi roh cele (jeste neposunute) sestavy pres realne
  // connectorsLocal tohoto konkretniho dilu/profilu, pak posun dilu "1"
  // (a tim padem i dila "2"/"3", ktere se pripoji AZ POTE k jeho aktualni
  // svetove pozici) tak, aby tenhle roh padl presne na (0,0,0).
  const shift = spatialLOuterCornerMin(entry1.connectorsLocal, quat1, quat2).negate();
  obj1.position.copy(shift);
  obj1.updateMatrixWorld(true);

  const obj2 = await loadGlbAsync(part.file);
  applyPartMaterial(obj2, part.layer);
  const entry2 = { part, object3d: obj2, connectorsLocal: computeConnectorsLocal(obj2) };
  attachEntryToParent(entry2, entry1, quat2, 0, 0);

  const obj3 = await loadGlbAsync(part.file);
  applyPartMaterial(obj3, part.layer);
  const entry3 = { part, object3d: obj3, connectorsLocal: computeConnectorsLocal(obj3) };
  attachEntryToParent(entry3, entry1, baseQuaternion(0, "vertical"), 0, 1);
  // Retreat sloupku podel delkove osy dilu "1", aby nepresahoval do prazdna
  // za jeho spicku (viz komentar vyse) - "bez presahu", cele na miste.
  const conn0NormalWorld = worldConnectorsOf(entry1)[0].normal.clone();
  const colHalf = crossAxisHalfWidthTowardDirection(entry3.connectorsLocal, obj3.quaternion, conn0NormalWorld);
  obj3.position.addScaledVector(conn0NormalWorld, -colHalf);
  obj3.updateMatrixWorld(true);

  entry1.wasThrough = true;
  entry2.wasAttached = true;
  entry3.wasAttached = true;
  entry3.vertical = true;
  [obj1, obj2, obj3].forEach(o => { o.userData.basePos = o.position.clone(); scene.add(o); });
  placed.push(entry1, entry2, entry3);

  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
}

// "Prostorovy L (obraceny spoj)" - stejna zamena roli jako u
// buildLReversedShape(): dil "2" (90°) je ted pruchozi/pevny, dil "1" (0°)
// se k nemu pripoji. Svisly sloupek (dil "3") se pripoji k tomu, kdo je
// PRAVE TED pruchozi (tedy k dilu "2"), aby porad vyrustal ze stejneho
// rohu. Stejna 2-kolova oprava kotvy (skutecny vnejsi roh, ne jen
// centerline konektor) a stejny retreat sloupku jako u nereverzovane
// varianty vyse.
async function buildSpatialLReversedShape(partId, opts) {
  opts = opts || {};
  if (!opts.keepExisting) clearAll();
  const part = CATALOG.find(p => p.id === partId);
  const quat1 = baseQuaternion(0);
  const quat2 = baseQuaternion(90);

  const obj2 = await loadGlbAsync(part.file);
  applyPartMaterial(obj2, part.layer);
  const entry2 = { part, object3d: obj2, connectorsLocal: computeConnectorsLocal(obj2) };
  obj2.quaternion.copy(quat2);
  obj2.position.set(0, 0, 0);
  obj2.updateMatrixWorld(true);
  // Stejny princip jako u nereverzovane varianty, jen "pruchozi"/"pripojovany"
  // role (throughQuat/attachQuat) jsou prohozene.
  const shift = spatialLOuterCornerMin(entry2.connectorsLocal, quat2, quat1).negate();
  obj2.position.copy(shift);
  obj2.updateMatrixWorld(true);

  const obj1 = await loadGlbAsync(part.file);
  applyPartMaterial(obj1, part.layer);
  const entry1 = { part, object3d: obj1, connectorsLocal: computeConnectorsLocal(obj1) };
  attachEntryToParent(entry1, entry2, quat1, 0, 0);

  const obj3 = await loadGlbAsync(part.file);
  applyPartMaterial(obj3, part.layer);
  const entry3 = { part, object3d: obj3, connectorsLocal: computeConnectorsLocal(obj3) };
  attachEntryToParent(entry3, entry2, baseQuaternion(0, "vertical"), 0, 1);
  const conn0NormalWorld = worldConnectorsOf(entry2)[0].normal.clone();
  const colHalf = crossAxisHalfWidthTowardDirection(entry3.connectorsLocal, obj3.quaternion, conn0NormalWorld);
  obj3.position.addScaledVector(conn0NormalWorld, -colHalf);
  obj3.updateMatrixWorld(true);

  entry2.wasThrough = true;
  entry1.wasAttached = true;
  entry3.wasAttached = true;
  entry3.vertical = true;
  // Prirozene cislovani - stejne jako u nereverzovane varianty (0° = "1.",
  // 90° = "2.", sloupek = "3."), i kdyz se dil "2" vypocita/umisti prvni.
  [obj1, obj2, obj3].forEach(o => { o.userData.basePos = o.position.clone(); scene.add(o); });
  placed.push(entry1, entry2, entry3);

  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
}

// "Ctverec / ram" - PRIMA konstrukce (Robert 2026-07-23: "dve protilehle
// strany nechat cele/pruchozi a druhe dve zkratit, aby presne zapadly mezi
// ne... tohle v praxi nejcastejsi reseni, super udelej to"). NAHRAZUJE
// puvodni retezovy pristup (4x attachEntryToParent s kumulativni rotaci
// 0/90/180/270 + closeLoopIfCoincident na uzaviraci roh) - ten matematicky
// NEuzaviral smycku presne: overeno samostatnou Node.js simulaci (three.js
// v0.128.0, presna kopie vsech relevantnich funkci vcetne
// attachEntryToParent/crossAxisHalfWidthTowardDirection), ze kazdy roh
// pridava realny diagonalni posun dims[0]*sqrt(2)/2 (21.2mm pro 30mm
// profil, 31.8mm pro 45mm) - po 4 rozich se to NEVYRUSI, zbyde skutecna
// fyzicka mezera (ne jen chyba v pocitadle spoju).
//
// Tenhle pristup ma jinou strukturu (skutecny "obraz ramu", ne retezena
// rotace): strany A, B jsou stejne natocene (0°), rovnobezne, rozteceny
// presne o L (puvodni/nezmenena delka profilu) podel smeru kolmeho na
// jejich osu - OBE zustavaji CELE/nezkracene ("pruchozi"). Strany C, D
// (90°) spojuji A a B: kazda zacne na vnejsi stene A (odsazeno o
// crossAxisHalfWidthTowardDirection, presne stejna technika jako u "Tvaru L
// (zmena delek)"), pak se ZKRATI o soucet poloviny sirky A a poloviny sirky
// B (= sirka profilu w, protoze A a B maji stejny prurez) se zafixovanym
// BLIZKYM (A-ovym) koncem - tim jejich VZDALENY konec presne dosedne na
// vnejsi stenu B. Overeno v simulaci: gap = 0.000000mm pro 30x30, 45x45 i
// nesymetricky 30x60 prurez.
//
// DULEZITE: samostatna funkce, NEZASAHUJE do shapeSteps("square") ani do
// attachEntryToParent() - ty pouziva i buildKvadrShape() pro sve spodni/
// horni ramy, jehoz VLASTNI (stejna) chyba je vyslovne odlozena Robertem
// ("ke kvadru se jeste vratime, je to slozity, postupujme postupne").
// reversed=true: PROHOZENI roli - profily, ktere by normalne byly cele/
// pruchozi (delsi), se stanou zkracenymi/pripojovanymi a naopak (Robert
// 2026-07-23: "prida druhy ram, ktery jen prohodi profily delsi za
// kratsi, takze se zmeni jakoby smer ctverce"). Vnejsi rozmer ctverce (L)
// zustava stejny - meni se JEN to, ktera dvojice protilehlych stran je
// cela/pruchozi a ktera zkracena.
// Vytahnute "jadro" primé konstrukce ramu (bez clearAll() a bez zaverecneho
// refresh/rebuild volani) - pouziva ho jak samostatne tlacitko "Ctverec/ram"
// (pres tenky wrapper buildSquareShape nize), tak buildKvadrShape() pro
// spodni i horni ram krabice (Robert 2026-07-23: "podle poslednich
// standardu spoju" - uz zadny stary retezovy pristup se
// shapeSteps("square")/closeLoopIfCoincident, viz VLASTNOSTI_PROFILU.md).
async function buildSquareFrameEntries(partId, reversed) {
  const part = CATALOG.find(p => p.id === partId);
  const quatThrough = baseQuaternion(reversed ? 90 : 0);
  const quatAttach = baseQuaternion(reversed ? 0 : 90);

  const objA = await loadGlbAsync(part.file);
  applyPartMaterial(objA, part.layer);
  const entryA = { part, object3d: objA, connectorsLocal: computeConnectorsLocal(objA) };
  objA.quaternion.copy(quatThrough);
  objA.position.set(0, 0, 0);
  objA.updateMatrixWorld(true);
  const L = entryA.connectorsLocal[0].point.distanceTo(entryA.connectorsLocal[1].point);

  const attachDir = entryA.connectorsLocal[1].point.clone()
    .sub(entryA.connectorsLocal[0].point)
    .applyQuaternion(quatAttach)
    .normalize();

  // POZOR (Robert 2026-07-23: "aby to davalo ctverec, musis to zkratit vic
  // z 970mm na 940mm"): "L" (delka profilu A/B, napr. 1000mm) je VNEJSI
  // rozmer pozadovaneho ctverce, ne osova roztec mezi A a B. Kdyby B stalo
  // presne o L dal (stara verze), vnejsi pudorys by byl L x (L + w) -
  // obdelnik, ne ctverec (w = sirka prurezu, pridava se navic na obou
  // vnejsich stranach A/B). Aby vnejsi pudorys vysel presne L x L, musi byt
  // osova roztec A-B zmensena o w (= halfA + halfB) - halfA se proto pocita
  // PRED umistenim B (drive se pocitalo az po, kdy uz bylo pozde tuhle
  // korekci pouzit). Pocita se uz tady (misto az po objA.position), protoze
  // ho potrebuje i kotva o pár radku niz.
  const halfA = crossAxisHalfWidthTowardDirection(entryA.connectorsLocal, objA.quaternion, attachDir);
  const halfB = halfA;
  const centerDist = L - halfA - halfB;

  // OPRAVA (Robert 2026-07-23, screenshoty "proc se kazdy objevil jinde" a
  // pak "porad je tam posun o pulku prurezu v obou osach"): nestacilo kotvit
  // konektor 0 (stredovou osu na konci A) na pocatek - to je porad bod NA
  // OSE dilu, ne skutecny VNEJSI ROH ctverce (ten je od stredove osy jeste
  // odsazeny o halfA smerem OD B, protoze A ma nenulovou sirku). Bez tohohle
  // dodatecneho odsazeni vychazel vnejsi roh u normalni a prohozene varianty
  // porad na 2 ruzna mista (lisici se o presne halfA v kazde ose, protoze
  // attachDir a vlastni osa A si mezi variantami vymeni role). Kotvime proto
  // VNEJSI ROH (konektor 0 + halfA proti smeru attachDir) na (0,0,0).
  const rotatedConn0A = entryA.connectorsLocal[0].point.clone().applyQuaternion(quatThrough);
  objA.position.copy(rotatedConn0A.clone().negate()).addScaledVector(attachDir, halfA);
  objA.updateMatrixWorld(true);

  const objB = await loadGlbAsync(part.file);
  applyPartMaterial(objB, part.layer);
  const entryB = { part, object3d: objB, connectorsLocal: computeConnectorsLocal(objB) };
  objB.quaternion.copy(quatThrough);
  objB.position.copy(objA.position).addScaledVector(attachDir, centerDist);
  objB.updateMatrixWorld(true);

  async function placeAttached(endIdx) {
    const obj = await loadGlbAsync(part.file);
    applyPartMaterial(obj, part.layer);
    const entry = { part, object3d: obj, connectorsLocal: computeConnectorsLocal(obj, partConnectorOpts(part)) };
    obj.quaternion.copy(quatAttach);
    obj.position.set(0, 0, 0);
    obj.updateMatrixWorld(true);
    const childConnIdx = 0;
    const wcA = worldConnectorsOf(entryA)[endIdx];
    // OPRAVA (Robert 2026-07-23, screenshot rohu: "zeleny profil musi jit
    // zarovno koncem bileho profilu"): bez tehle korekce se C/D umistuji
    // se stredem PRESNE na spicce A (wcA.point), takze pulka jejich
    // vlastniho prurezu prečnívá VEN za spicku A (misto aby s ni licovala)
    // a druha pulka se prekryva s telem A - vizualne to vypadalo jako
    // "zub"/přesah v rohu. A/B uz svou celou delkou L definuji presny
    // vnejsi rozmer ctverce (viz komentar u centerDist vyse) - C/D se
    // proto MUSI vejit CELE dovnitr tohoto rozsahu (podel osy A), ne
    // pretekat ven. Reseni: posunout C/D o jejich VLASTNI polovicni sirku
    // v teto ("outward") ose SMEREM DOVNITR (opacne nez outwardDir), aby
    // jejich VNEJSI plocha (ne stred) presne licovala se spickou A.
    const otherEndIdx = 1 - endIdx;
    const outwardDir = entryA.connectorsLocal[endIdx].point.clone()
      .sub(entryA.connectorsLocal[otherEndIdx].point)
      .applyQuaternion(objA.quaternion)
      .normalize();
    const halfAlongA = crossAxisHalfWidthTowardDirection(entry.connectorsLocal, quatAttach, outwardDir);
    const target = wcA.point.clone()
      .addScaledVector(attachDir, halfA)
      .addScaledVector(outwardDir, -halfAlongA);
    const rotatedLocal = entry.connectorsLocal[childConnIdx].point.clone().applyQuaternion(quatAttach);
    obj.position.copy(target.clone().sub(rotatedLocal));
    obj.updateMatrixWorld(true);
    const L0 = entry.connectorsLocal[0].point.distanceTo(entry.connectorsLocal[1].point);
    const targetLen = centerDist - halfA - halfB;
    if (targetLen && L0) applyLengthScale(entry, targetLen / L0, childConnIdx);
    entry.usedConn = new Set([0, 1]);
    entry.hiddenEndConn = new Set([0, 1]);
    entry.wasAttached = true;
    obj.userData.basePos = obj.position.clone();
    scene.add(obj);
    return entry;
  }

  const entryC = await placeAttached(0);
  const entryD = await placeAttached(1);

  entryA.usedConn = new Set([0, 1]);
  entryB.usedConn = new Set([0, 1]);
  entryA.wasThrough = true;
  entryB.wasThrough = true;

  registerJoint(entryA, 0, entryC, 0);
  registerJoint(entryC, 1, entryB, 0);
  registerJoint(entryA, 1, entryD, 0);
  registerJoint(entryD, 1, entryB, 1);

  objA.userData.basePos = objA.position.clone();
  objB.userData.basePos = objB.position.clone();
  scene.add(objA);
  scene.add(objB);
  placed.push(entryA, entryC, entryB, entryD);

  // Robert 2026-07-24: "vsechny zavrene tvary je vhodne mit moznost
  // natahnout" - oznacit vsechny 4 dily spolecnymi metadaty ramu, aby
  // sipky pro natazeni (viz refitRectFrameEntries/refreshFrameResizeHandles
  // nize) nasly celou skupinu z libovolneho jejiho dilu.
  const frameMeta = { kind: "rectFrame", entryA, entryB, entryC, entryD };
  [entryA, entryB, entryC, entryD].forEach(e => { e.frameGroup = frameMeta; });

  return { entryA, entryB, entryC, entryD, frameMeta };
}

async function buildSquareShape(partId, reversed, opts) {
  opts = opts || {};
  if (!opts.keepExisting) clearAll();
  await buildSquareFrameEntries(partId, reversed);
  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
}

// "Ctverec / ram (plne profily)" - DRUHA varianta ramu, Robert 2026-08-16.
//
// Kontext: pri stavbe prehledu typu spoju (custom_shapes id 160) Robert
// oznacil rohy ramu za spatne s odkazem "podivej se na sousedni L tvary, a
// mas to". Rozdil je v TYPU ROHU:
//   - buildSquareFrameEntries() (stavajici "Ctverec / ram"): 2 pruchozi
//     dily v plne delce + 2 pricky ZKRACENE (applyLengthScale) vmacknute
//     mezi ne. Vnejsi pudorys vyjde presne L x L. Robertem potvrzeno
//     2026-07-23 ("tohle v praxi nejcastejsi reseni") - zustava beze zmeny.
//   - tahle funkce: "vetrnik" - VSECHNY 4 dily v PLNE delce, kazdy dosedne
//     celem na BOK nasledujiciho, presne stejny roh jako "Tvar L" a
//     "Prostorovy L" (stejny mechanismus - attachEntryToParent v retezu).
//     Vnejsi pudorys je pak (L + w) x (L + w), ne L x L.
// Robert 2026-08-16 zvolil mit OBE varianty vedle sebe jako 2 tvary, at si
// uzivatel vybere podle toho, jestli potrebuje presny vnejsi rozmer, nebo
// plne (nezkracene) profily.
//
// Poznamka k drivejsimu komentari u buildSquareShape/buildKvadrShape, ze
// "retezovy pristup NEuzavira smycku presne (diagonalni posun
// dims[0]*sqrt(2)/2)": to plati pro starou cestu PRES closeLoopIfCoincident.
// Tady se retez uzavira uplne presne (overeno Node.js harnessem na skutecne
// GLB geometrii: dotyk 0.000mm na vsech 4 rozich, zadny prunik ani mezera) -
// zaverecny spoj se registruje primo pres registerJoint(), zadne dohledavani
// koincidence se nedela.
async function buildSquarePinwheelFrameEntries(partId) {
  const part = CATALOG.find(p => p.id === partId);
  const mkEntry = async () => {
    const obj = await loadGlbAsync(part.file);
    applyPartMaterial(obj, part.layer);
    // connectorsLocal se MUSI pocitat, dokud je objekt v identite (viz
    // stejna poznamka u loadCustomShapePartEntry/placeAtOrigin) - rotaci i
    // pozici nastavi az attachEntryToParent nize.
    return { part, object3d: obj, connectorsLocal: computeConnectorsLocal(obj, partConnectorOpts(part)) };
  };

  const entry1 = await mkEntry();
  entry1.object3d.quaternion.copy(baseQuaternion(0));
  entry1.object3d.position.set(0, 0, 0);
  entry1.object3d.updateMatrixWorld(true);

  // Stejny retez jako shapeSteps("square") / runAIPlan - 4 dily s rotacemi
  // 0/90/180/270, kazdy pripojeny celem na bok predchoziho.
  const entry2 = await mkEntry();
  attachEntryToParent(entry2, entry1, baseQuaternion(90), 1, 0);
  const entry3 = await mkEntry();
  attachEntryToParent(entry3, entry2, baseQuaternion(180), null, 0);
  const entry4 = await mkEntry();
  attachEntryToParent(entry4, entry3, baseQuaternion(270), null, 0);

  // Uzavreni smycky: volny konec dilu 4 dosedl na bok dilu 1 - zaznamenat
  // jako skutecny spoj (jinak by ram nebyl datove uzavreny: chybel by
  // licPeers/jointCount/lastJoint pro tenhle ctvrty roh a "Spocitej spoje"
  // by hlasil o jeden min).
  {
    const idx4 = findFreeEndIdx(entry4);
    const idx1 = findFreeEndIdx(entry1);
    if (idx4 >= 0 && idx1 >= 0) registerJoint(entry4, idx4, entry1, idx1);
  }

  const all = [entry1, entry2, entry3, entry4];
  all.forEach(e => e.object3d.updateMatrixWorld(true));

  // Kotva na vnejsi roh (stejna konvence jako Tvar L / Ctverec / Prostorovy
  // L - viz TVARY_PREDNASTAVENE.md 2h): posunout celou sestavu tak, aby jeji
  // skutecna vnejsi hrana v obou vodorovnych osach lezela na 0. Merime
  // SKUTECNY bounding box cele sestavy (ne bodovy vzorec) - stejny pristup
  // jako sceneAssemblyBBoxMin u Prostoroveho L, presne z toho duvodu, ze
  // rucne odvozeny vzorec je na tuhle korekci nachylny na chybu.
  {
    const box = new THREE.Box3();
    all.forEach(e => box.union(new THREE.Box3().setFromObject(e.object3d)));
    const shift = new THREE.Vector3(-box.min.x, 0, -box.min.z);
    all.forEach(e => { e.object3d.position.add(shift); e.object3d.updateMatrixWorld(true); });
  }

  all.forEach(e => { e.object3d.userData.basePos = e.object3d.position.clone(); scene.add(e.object3d); });
  placed.push(entry1, entry2, entry3, entry4);

  // Role pro roztahovani (modre sipky): entryA/entryB je dvojice
  // ROVNOBEZNYCH dilu podel jedne osy, entryC/entryD podel druhe - u
  // vetrniku to jsou (1,3) a (2,4). Vlastni "kind" proto, ze refit tehle
  // struktury je jiny nez u zkracene varianty (viz
  // refitPinwheelFrameEntries nize).
  const frameMeta = { kind: "pinwheelFrame", entryA: entry1, entryB: entry3, entryC: entry2, entryD: entry4 };
  all.forEach(e => { e.frameGroup = frameMeta; });

  return { entryA: entry1, entryB: entry3, entryC: entry2, entryD: entry4, frameMeta };
}

async function buildSquarePinwheelShape(partId, opts) {
  opts = opts || {};
  if (!opts.keepExisting) clearAll();
  await buildSquarePinwheelFrameEntries(partId);
  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
}

// "Kvadr (krabice)" - PREPSANO 2026-07-23 (Robert: "priprav upravy krychle
// ... podle poslednich standardu spoju, vycentruj na stred"). Puvodni verze
// stavela spodni/horni ram pres shapeSteps("square")/runAIPlan()
// (retezovy pristup + closeLoopIfCoincident) - presne stejna trida chyby
// jako u puvodniho (jiz opraveneho) samostatneho "Ctverec/ram" tlacitka:
// retez 4 dilu s kumulativni rotaci NEuzavira smycku presne (mereno drive
// v simulaci - realny diagonalni posun dims[0]*sqrt(2)/2, viz komentar u
// buildSquareFrameEntries vyse). Tahle oprava byla vyslovne odlozena
// Robertem drive ("ke kvadru se jeste vratime, je to slozity, postupujme
// postupne") - ted na ni dosla rada.
//
// Zmeny oproti puvodni verzi:
// 1) Spodni i horni ram se stavi pres buildSquareFrameEntries() - presne
//    stejna 0mm-gap konstrukce jako u samostatneho "Ctverec/ram".
// 2) Sloupky se pripojuji na konektory 0/1 PRUCHOZICH dilu A/B (ne na stary
//    indexovy system zalozeny na retezovem poradi) - to jsou ctyri
//    SKUTECNE rohy ramu; C/D (pripojovane, zkracene strany) maji konektory
//    0/1 oznacene jako "hiddenEndConn" (jejich cela dosedaji na A/B, nejsou
//    to volne rohy).
// 3) Kotva: "vnejsi roh" v X/Z uz resi buildSquareFrameEntries() sama (roh
//    presne na (0,0) - stejny standard jako Tvar L/Prostorovy L, viz
//    TVARY_PREDNASTAVENE.md 2h). NAVIC (nove pro kvadr, protoze jde o
//    skutecnou 3D krabici, ne plochy ram): cely spodni ram se jeste posune
//    nahoru o polovinu vlastni vysky profilu, aby jeho SKUTECNA spodni
//    hrana (ne stredova osa) sedela presne na Y=0 - konzistentni s tim, jak
//    "vnejsi roh" znamena skutecnou vnejsi hranu materialu vsude jinde v
//    teto appce (Ctverec, Tvar L, Prostorovy L), ne osu/stred profilu.
async function buildKvadrShape(partId, opts) {
  opts = opts || {};
  if (!opts.keepExisting) clearAll();
  const part = CATALOG.find(p => p.id === partId);
  const vertQuat = baseQuaternion(0, "vertical");

  const bottom = await buildSquareFrameEntries(partId, false);
  const { entryA, entryB, entryC, entryD } = bottom;
  // Poradi shodne s puvodnim "placed" poradim (A, C, B, D), pouziva se dal
  // pri kopirovani na horni ram.
  const bottomEntries = [entryA, entryC, entryB, entryD];

  // Kotva ve svisle ose (viz komentar u buildKvadrShape vyse) - cely spodni
  // ram posunout nahoru, aby SKUTECNA spodni hrana (ne stredova osa
  // profilu) sedela presne na Y=0.
  // OPRAVA (bot8 2026-08-19, nalezeno primym overenim matematiky na
  // SKUTECNE geometrii .glb - viz VLASTNOSTI_PROFILU.md): puvodni vzorec
  // "position.y += halfHeight" predpokladal, ze lokalni pocatek (pivot)
  // dilu je totozny s jeho geometrickym stredem - u syntetickeho testu to
  // vzdy plati, ale u SKUTECNEHO .glb nemusi (napr. profil_30x30_
  // uzavreny.glb ma pivot posunuty o ~0.75mm od geometrickeho stredu na
  // prurezove ose). Dusledek: mezi sloupky a hornim ramem vznikala mezera
  // presne o velikost tohoto posunu (overeno primo: 0.7522mm mezera misto
  // 0.0000mm), zatimco vsechny predchozi kontroly (vizualni v prohlizeci i
  // Node.js testy se syntetickym BoxGeometry) tuhle konkretni chybu
  // nemohly odhalit. Misto odvozovani ze "size/2 + position" se ted
  // SKUTECNA spodni hrana kazdeho dilu ZMERI (Box3) a posune presne na
  // Y=0 - funguje spravne bez ohledu na to, kde presne v .glb sedi pivot.
  bottomEntries.forEach(e => {
    const currentBottomY = new THREE.Box3().setFromObject(e.object3d).min.y;
    e.object3d.position.y -= currentBottomY;
    e.object3d.updateMatrixWorld(true);
  });

  // 4 sloupky presne do rohu spodniho ramu - pripojene na konektory 0/1
  // PRUCHOZICH dilu A/B (skutecne rohy ramu; C/D maji sve konektory 0/1
  // oznacene jako hiddenEndConn - jejich cela dosedaji na A/B, nejsou to
  // volne rohy k pripojeni). cornerSpec si drzime navic pro pouziti i na
  // horni ram nize (posts-to-top-frame).
  const cornerSpecs = [
    { entry: entryA, connIdx: 0 },
    { entry: entryA, connIdx: 1 },
    { entry: entryB, connIdx: 0 },
    { entry: entryB, connIdx: 1 },
  ];
  const posts = [];
  for (const spec of cornerSpecs) {
    const obj = await loadGlbAsync(part.file);
    applyPartMaterial(obj, part.layer);
    const connectorsLocal = computeConnectorsLocal(obj, partConnectorOpts(part));
    const postEntry = { part, object3d: obj, connectorsLocal };
    attachEntryToParent(postEntry, spec.entry, vertQuat, spec.connIdx, 1);
    // Retreat sloupku podel delkove osy rohoveho dilu (stejny princip jako
    // u Prostoroveho L - viz TVARY_PREDNASTAVENE.md 2h) - bez tohohle by byl
    // sloupek centrovany PRESNE na konektoru a polovina jeho prurezu by
    // prectuhovala do prazdna za vnejsi hranu ramu (overeno simulaci:
    // bez retreat vychazel roh na (0,0,-15) misto (0,0,0)).
    const cornerNormalWorld = worldConnectorsOf(spec.entry)[spec.connIdx].normal.clone();
    const postHalf = crossAxisHalfWidthTowardDirection(postEntry.connectorsLocal, obj.quaternion, cornerNormalWorld);
    obj.position.addScaledVector(cornerNormalWorld, -postHalf);
    obj.updateMatrixWorld(true);
    obj.userData.basePos = obj.position.clone();
    scene.add(obj);
    placed.push(postEntry);
    posts.push(postEntry);
  }

  // Vyska, na kterou se ma posunout kopie horniho ramu: presne vrchol
  // sloupku (aby spodni hrana horniho ramu lipla presne na vrchol
  // sloupku, misto aby stred ramu byl na urovni vrcholu sloupku a pulka
  // jeho tela tak zapadla do sloupku).
  const postTopWorld = worldConnectorsOf(posts[0])[0].point;

  const topEntries = [];
  for (const be of bottomEntries) {
    const obj = await loadGlbAsync(be.part.file);
    applyPartMaterial(obj, be.part.layer);
    const connectorsLocal = computeConnectorsLocal(obj, partConnectorOpts(be.part));
    obj.quaternion.copy(be.object3d.quaternion);
    obj.position.copy(be.object3d.position);
    // DULEZITE (jinak nova chyba): C/D jsou u primé konstrukce zkracene
    // (applyLengthScale) - bez zkopirovani scale by horni kopie C/D
    // zustaly na plnou delku a prekryvaly by se s hornimi A/B.
    obj.scale.copy(be.object3d.scale);
    obj.updateMatrixWorld(true);
    // OPRAVA (bot8 2026-08-19, viz kotva spodniho ramu vyse) - stejnym
    // zpusobem zmerit SKUTECNOU spodni hranu teto konkretni kopie (ne
    // odvozovat z position.y +/- halfHeight, ktere by u profilu s
    // mimostrednym pivotem v .glb zpusobilo mezeru presne o velikost
    // tohoto posunu) a posunout ji presne na vrchol sloupku.
    const currentBottomY = new THREE.Box3().setFromObject(obj).min.y;
    obj.position.y += (postTopWorld.y - currentBottomY);
    obj.updateMatrixWorld(true);
    obj.userData.basePos = obj.position.clone();
    scene.add(obj);
    const topEntry = { part: be.part, object3d: obj, connectorsLocal };
    topEntry.hiddenEndConn = be.hiddenEndConn ? new Set(be.hiddenEndConn) : undefined;
    placed.push(topEntry);
    topEntries.push(topEntry);
  }

  // Horni ram je presna kopie spodniho (vcetne scale), takze ma STEJNOU
  // strukturu spoju - stejne 4 rohy jako buildSquareFrameEntries() sama
  // registruje pro spodni ram (topEntries poradi odpovida bottomEntries
  // poradi: [A, C, B, D]).
  const [topA, topC, topB, topD] = topEntries;
  registerJoint(topA, 0, topC, 0);
  registerJoint(topC, 1, topB, 0);
  registerJoint(topA, 1, topD, 0);
  registerJoint(topD, 1, topB, 1);

  // Sloupky na horni ram: stejne rohy (topA/topB konektory 0/1) jako dole.
  const topCornerSpecs = [
    { entry: topA, connIdx: 0 },
    { entry: topA, connIdx: 1 },
    { entry: topB, connIdx: 0 },
    { entry: topB, connIdx: 1 },
  ];
  posts.forEach((post, i) => {
    const spec = topCornerSpecs[i];
    registerJoint(spec.entry, spec.connIdx, post, 0);
  });

  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
}

// Spolecne jadro pro Pruvodce (tlacitka) i AI stavitele (shape_calls, viz
// sendAiMessage) - vezme konkretni partId (misto cteni globalniho
// wizardSelectedPart), aby ho slo volat z obou mist. KAZDA vetev zacina
// clearAll() (bud primo, nebo skrze volanou funkci) - shape_calls proto
// SMI obsahovat jen JEDNU polozku na odpoved (viz system prompt v
// /api/ai/generate), jinak by kazdy dalsi tvar smazal ten predchozi.
// SSE sestava ODSTRANENA (Robert 2026-08-04: "SSE sestavu smaz") -
// tlacitko btnInsertSSE, buildSSEShape i SSE_MANIFEST smazany; viz git
// historie pred timto commitem, kdyby bylo potreba obnovit.

async function buildNamedShape(shapeId, partId, opts) {
  opts = opts || {};
  if (shapeId === "kvadr") {
    await buildKvadrShape(partId, opts);
    return;
  }
  if (shapeId === "L_reversed") {
    await buildLReversedShape(partId, opts);
    return;
  }
  if (shapeId === "L_length") {
    await buildLLengthShape(partId, opts);
    return;
  }
  if (shapeId === "L_length_reversed") {
    await buildLLengthReversedShape(partId, opts);
    return;
  }
  if (shapeId === "square") {
    // OPRAVENO 2026-07-23: puvodni retezovy pristup (runAIPlan +
    // closeLoopIfCoincident) neuzaviral smycku presne - viz komentar u
    // buildSquareShape() vyse (mereno Node.js simulaci, realna mezera
    // dims[0]*sqrt(2)/2 v uzaviracim rohu). Nahrazeno primou konstrukci
    // "2 strany pruchozi/cele + 2 strany zkracene, aby presne zapadly mezi
    // ne" (Robertovo potvrzeni: "tohle v praxi nejcastejsi reseni").
    await buildSquareShape(partId, false, opts);
    return;
  }
  if (shapeId === "square_reversed") {
    await buildSquareShape(partId, true, opts);
    return;
  }
  // Robert 2026-08-16 - druha varianta ramu (vetrnik, plne profily, roh jako
  // u Tvaru L); stavajici "square" zustava beze zmeny, viz komentar u
  // buildSquarePinwheelFrameEntries.
  if (shapeId === "square_pinwheel") {
    await buildSquarePinwheelShape(partId, opts);
    return;
  }
  if (shapeId === "spatial_L") {
    // OPRAVENO 2026-07-23 (Robert: "musi byt zarovnany rohem na stred") -
    // puvodni genericka cesta (runAIPlan + shapeSteps) nechavala roh, kde
    // se sbihaji vsechny 3 dily, na "prirozenem" (neanchorovanem) miste.
    await buildSpatialLShape(partId, opts);
    return;
  }
  if (shapeId === "spatial_L_reversed") {
    await buildSpatialLReversedShape(partId, opts);
    return;
  }
  if (!opts.keepExisting) clearAll();
  await runAIPlan(shapeSteps(partId, shapeId));
}

// Spocita spolecny bounding box (Box3) vsech dilu v poli entries - pouziva
// se pro automaticke rozmisteni nove pridavaneho tvaru vedle stavajicich
// (viz buildWizardShape nize).
function bboxOfEntries(entries) {
  const box = new THREE.Box3();
  entries.forEach(e => {
    e.object3d.updateMatrixWorld(true);
    box.union(new THREE.Box3().setFromObject(e.object3d));
  });
  return box;
}

// Robert 2026-07-24: "at se objekty pridavaji panelem na tvary a
// nenahrazovaly" - tlacitka v panelu Tvary uz nemaz scenu (viz
// opts.keepExisting vyse), ale vsechny tvary se stavi lokalne kolem
// (0,0,0), takze druhy a dalsi tvar by bez upravy skoncil PRESNE na tom
// prvnim (prekryv). Tahle funkce po dostavbe posune jen NOVE pridane dily
// (indexy >= startIdx v poli `placed`) tak, aby jejich spolecny bounding
// box zacinal hned vedle (podel +X, s mezerou) bounding boxu vseho
// PREDCHOZIHO obsahu sceny. Kdyz byla scena predtim prazdna, nic se
// neposouva (novy tvar zustava presne na (0,0,0), jak byl doteď zvykly).
const SHAPE_AUTO_PLACEMENT_GAP_MM = 300;
function applyAutoPlacementOffset(startIdx, extraObjects) {
  const existing = placed.slice(0, startIdx);
  const added = placed.slice(startIdx);
  if (!existing.length || !added.length) return; // prazdna scena predtim - zadny posun potreba
  const existingBox = bboxOfEntries(existing);
  const addedBox = bboxOfEntries(added);
  const offsetX = (existingBox.max.x - addedBox.min.x) + SHAPE_AUTO_PLACEMENT_GAP_MM;
  added.forEach(e => {
    e.object3d.position.x += offsetX;
    e.object3d.updateMatrixWorld(true);
  });
  // bot8, 2026-08-17: text_labels (viz sceneTextLabels) nejsou soucasti
  // `placed` - musi se posunout stejnym offsetem rucne, jinak zustanou
  // viset na puvodni (ulozene) pozici, mimo prave vlozenou sestavu.
  (extraObjects || []).forEach(o => {
    o.position.x += offsetX;
    o.updateMatrixWorld(true);
  });
}

async function buildWizardShape(shapeId) {
  if (!wizardSelectedPart) return;
  // Zachytit, kolik dilu uz bylo ve scene PRED timhle tvarem - viz
  // applyAutoPlacementOffset vyse.
  const startIdx = placed.length;
  await buildNamedShape(shapeId, wizardSelectedPart.id, { keepExisting: true });
  // Robert 2026-08-04 ("pres rastr chci vkladat i zakladni tvary,
  // vsechny"): stejne interaktivni umisteni na rastr jako u vlastnich
  // tvaru - fallback na puvodni auto-offset jen kdyz rezim nejde spustit.
  const addedWizardEntries = placed.slice(startIdx);
  if (typeof startShapePlacementMode !== "function" || !startShapePlacementMode(addedWizardEntries)) {
    applyAutoPlacementOffset(startIdx);
  }
  // Po posunu je potreba znovu prepocitat obsazene konektory/znacky/kotvici
  // popisky - pozice dilu se od puvodniho (build funkci jiz jednou
  // provedeneho) refreshe zmenila.
  rebuildOccupiedConnectors();
  refreshEndpointMarkers(); refreshDimLabels();
  refreshSummary();
}

document.getElementById("wizardStep2").addEventListener("click", (ev) => {
  const btn = ev.target.closest("button[data-shape]");
  if (!btn) return;
  buildWizardShape(btn.dataset.shape);
});

// --- three.js scene setup ---
const viewport = document.getElementById("viewport");
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x14161b);

// Polovicni vyska zorneho pole (v mm) pro ortografické 2D pohledy - sdilena
// konstanta mezi initializaci kamery a resize handlerem (updateViewportSize),
// aby ortho projekce sedela i po zmene velikosti okna.
const ORTHO_VIEW_HALF_HEIGHT = 800;
const VIEW_DEFAULT_TARGET = new THREE.Vector3(0, 50, 0);

  // Robert 2026-07-25 ("objekty v dalce mizi, chci aby byly stale videt"):
  // OrbitControls nema zadny maxDistance limit, takze pri oddalovani (zoom
  // out) muze byt kamera libovolne daleko od cile - puvodni far=10000 pak
  // orezavalo (clipping) vsechno, co bylo od kamery dal nez 10000 jednotek,
  // coz se pri vetsim oddaleni snadno stalo i pro dily blizko stredu sceny.
  // Zvyseno na 100000, at je rezerva i pri velkem oddaleni.
let camera = new THREE.PerspectiveCamera(45, viewport.clientWidth/viewport.clientHeight, 1, 100000);
// Vychozi vzdalenost kamery - puvodne (300,250,400), pak na zadost Roberta
// 6x dal (1800,1500,2400, "dej ji 6x dal"). Robert 2026-08-09 ("3D objekt
// na počátku přiblizit pořádně") - 6x bylo moc daleko, snizeno na 3x
// puvodni vzdalenosti (900,750,1200). Robert 2026-08-22 ("výchozí pohled...
// dej 2x dál od centra os") - ted zase 2x DALEKO OD TE (mezitim zmensene)
// vzdalenosti, ne od puvodni - vysledkem je numericky stejny bod jako
// drivejsi "6x", ale duvod je jiny (mezitim pribyla cela funkce karoserii
// - cele auto delky nekolika metru se do puvodniho 3x zoomu nevejde
// pohodlne). Stejny smer pohledu.
camera.position.set(1800, 1500, 2400);

// preserveDrawingBuffer:true - bez tohohle vraci canvas.toDataURL() prazdny/cerny
// obrazek (drawing buffer se jinak po kazdem snimku vymaze) - potreba pro
// #btnGenerateOffer (export pohledu do PDF nabidky, Robert 2026-08-04).
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(viewport.clientWidth, viewport.clientHeight);
renderer.setPixelRatio(window.devicePixelRatio);
viewport.appendChild(renderer.domElement);
document.getElementById("loadingMsg").remove();

let controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.target.copy(VIEW_DEFAULT_TARGET);
controls.update();

// --- Přepínač 2D/3D pohledů (#viewModeSelect v toolbaru) ---
// Three.js nema zpusob, jak "prepnout" existujici kameru mezi perspektivni a
// ortografickou projekci - musime vytvorit novou instanci kamery a na ni
// prevazat (recreate) OrbitControls. Vsechny ostatni mista v kodu (raycasting,
// projekce kotovacich/cislovacich popisku, render smycka) čtou promennou
// `camera` za behu, takze reassign zde se automaticky projevi vsude.
// Robert 2026-09-15 ("v půdorysu pokud je dlouhý tvar je potřeba je
// natočit tak aby nevytvářel prázdné místa..., online nabídka verze pdf"):
// `aspectOverride` je volitelny druhy parametr - kdyz chybi (VSICHNI
// puvodni volajici, vc. zivyho prepinace 2D pohledu v toolbaru), chovani
// je presne jako drive (fixni pomer aktualniho viewportu). Pouziva ho jen
// captureOrthoWithDims() nize, kdyz pro export nabidky docasne zmensi
// renderer na pomer stran odpovidajici skutecnemu tvaru modelu.
function setViewMode(mode, aspectOverride, paddingOverride) {
  const naturalW = viewport.clientWidth, naturalH = viewport.clientHeight;
  // Sebe-opravny navrat na prirozenou velikost viewportu při přechodu do
  // "3d" (živý interaktivní/path-tracing pohled) - kdyby predchozi
  // captureOrthoWithDims() docasne zmenila rozliseni rendereru kvuli
  // fitovani na tvar modelu (2D export) a nechala ho tak, dalsi 3D snimky
  // by jinak vysly deformovane/oriznute podle posledniho 2D zaberu.
  // Vzdy (ne jen podminene) - renderer.domElement.width je SKUTECNY
  // pixelovy rozmer bufferu (naturalW * devicePixelRatio na HiDPI), takze
  // porovnavat ho primo s naturalW by na takovem displeji vzdy vyslo
  // "ruzne" i kdyz nic zmenit netreba. setSize() na uz spravnou velikost
  // je levna operace, neni duvod se podmince slozite vyhybat.
  if (mode === "3d") {
    renderer.setSize(naturalW, naturalH, false);
  }
  const aspect = aspectOverride || (naturalW / naturalH);

  if (controls) controls.dispose();

  let viewTarget = VIEW_DEFAULT_TARGET.clone();

  if (mode === "3d") {
    camera = new THREE.PerspectiveCamera(45, aspect, 1, 100000);
    camera.position.set(1800, 1500, 2400); // stejna vychozi vzdalenost jako pri prvnim vytvoreni kamery vyse
    camera.up.set(0, 1, 0);
  } else {
    // Robert 2026-08-05 ("cely produkt musi byt vzdy videt, okna 2D pohledu
    // jsou moc male"): puvodne pevnych 800mm pulvysky kolem fixniho bodu
    // (0,50,0) bez ohledu na skutecnou velikost/polohu sestavy - vetsi nebo
    // mimostredove sestavy se orezavaly, mensi zas zbytecne male uprostred
    // velkeho prazdneho ramu. Ram se pocita ze skutecneho bounding boxu
    // vsech dilu (bboxOfEntries) + rezerva navic pro kotovaci cary/popisky a
    // celkovy rozmer z drawDimensionOverlay (sahaji dal nez samotny model,
    // do bounding boxu dilu se nepocitaji). PUVODNICH 40% (Robert: "porad
    // male, musi byt na cele okno") bylo vic, nez kolik kotovani realne
    // potrebuje - pri OFFSET=26px + max 1 dalsi prstenec (LANE_STEP=22px po
    // oprave kaskadovani vyse) + popisek navic staci cca 20% rezervy.
    // paddingOverride (bot5, 2026-10-01): export vykresu do nabidky (captureOrthoWithDims) chce vic mista na vetsi koty
    // (OFFER_VIEW_PADDING); bez nej beze zmeny 1,2.
    const PADDING = paddingOverride || 1.2;
    const box = placed.length ? bboxOfEntries(placed) : null;
    const size = box ? box.getSize(new THREE.Vector3()) : null;
    const center = box ? box.getCenter(new THREE.Vector3()) : new THREE.Vector3(0, 50, 0);
    let halfW, halfH, cx, cy;
    if (!size) {
      halfW = ORTHO_VIEW_HALF_HEIGHT * aspect; halfH = ORTHO_VIEW_HALF_HEIGHT; cx = 0; cy = 50;
    } else if (mode === "top") {
      halfW = Math.max(size.x, 1) / 2 * PADDING; halfH = Math.max(size.z, 1) / 2 * PADDING; cx = center.x; cy = center.z;
    } else if (mode === "side") {
      halfW = Math.max(size.z, 1) / 2 * PADDING; halfH = Math.max(size.y, 1) / 2 * PADDING; cx = center.z; cy = center.y;
    } else {
      halfW = Math.max(size.x, 1) / 2 * PADDING; halfH = Math.max(size.y, 1) / 2 * PADDING; cx = center.x; cy = center.y;
    }
    const h = Math.max(halfH, halfW / aspect);
    camera = new THREE.OrthographicCamera(-h * aspect, h * aspect, h, -h, 1, 100000);
    if (mode === "top") {
      camera.position.set(cx, 2000, cy + 0.01);
      camera.up.set(0, 0, -1);
      viewTarget = new THREE.Vector3(cx, 0, cy);
    } else if (mode === "front") {
      camera.position.set(cx, cy, 2000);
      camera.up.set(0, 1, 0);
      viewTarget = new THREE.Vector3(cx, cy, 0);
    } else if (mode === "side") {
      camera.position.set(2000, cy, cx + 0.01);
      camera.up.set(0, 1, 0);
      viewTarget = new THREE.Vector3(0, cy, cx);
    }
  }

  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.target.copy(viewTarget);
  controls.enableRotate = (mode === "3d");
  camera.lookAt(controls.target);
  controls.update();
}

const viewModeSelectEl = document.getElementById("viewModeSelect");
if (viewModeSelectEl) {
  // Robert hlasil, ze prepinac "Pohled na scenu" nekdy nezareaguje hned,
  // az na kolikaty pokus (2026-07-23). Puvodne se poslouchal jen "change" a
  // vykresleni nove kamery se nechalo na dalsi tik animacni smycky
  // (requestAnimationFrame) - v nekterych prohlizecich/webview se "change" u
  // <select> spolehlive spusti az po ztrate fokusu (napr. az kliknutim
  // JINAM), takze prvni vyber vypadal, ze "nic neudelal". Reseni:
  // 1) posloucha se i "input" (u <select> ho vetsina prohlizecu vysila hned
  //    pri vyberu, driv nez "change"), s ochranou proti dvojitemu spusteni
  //    pro stejnou hodnotu,
  // 2) po prepnuti se hned zavola synchronni render (nespoleha se jen na
  //    dalsi animacni frame),
  // 3) select se hned zase odfokusuje, aby si "neschoval" nasledujici
  //    klik/tazeni na canvasu (fokus na <select> muze v nekterych
  //    prohlizecich zachytavat klavesove/mysi udalosti mist canvasu).
  let lastAppliedViewMode = null;
  function applyViewMode(mode) {
    if (mode === lastAppliedViewMode) return;
    lastAppliedViewMode = mode;
    setViewMode(mode);
    renderer.render(scene, camera);
  }
  // Robert 2026-08-12 ("tlačítko U nefunguje ve 2D pohledech"): blur() byl
  // puvodne jen v "change" - v prohlizecich/webview, kde "change" u <select>
  // nezafunguje hned (presne duvod, proc byl pridan i "input" listener nize),
  // zustaval fokus trvale na <select>u. Klavesove zkratky (J/U/...) pak
  // ev.target.tagName === "SELECT" hned zahazuji, takze po prepnuti na 2D
  // pohled U (a J) prestaly reagovat, dokud uzivatel nekliknul jinam rucne.
  // Blur ted bezi VZDY po kazde aplikaci rezimu, bez ohledu na to, ktery
  // event se skutecne spustil.
  viewModeSelectEl.addEventListener("input", (ev) => { applyViewMode(ev.target.value); viewModeSelectEl.blur(); });
  viewModeSelectEl.addEventListener("change", (ev) => { applyViewMode(ev.target.value); viewModeSelectEl.blur(); });
  // Robert 2026-08-16 ("na startu naskoci 2D shora ale ve scene je 3D,
  // asi pri reloadech kdyz necham 2D"): prohlizec si u <select> casto sam
  // pamatuje posledni vybranou hodnotu pres bezny reload (F5) - nativni
  // chovani formularovych prvku, zcela nezavisle na JS/localStorage (ten
  // tu pro rezim pohledu vubec neni). `camera` o par radku vyse (4789) se
  // ale VZDY vytvori jako 3D perspektiva bez ohledu na to, co dropdown
  // ukazuje - po takovem reloadu tak dropdown mohl ukazovat treba "Shora",
  // zatimco scena zustavala porad ve 3D. Opravny sync NELZE zavolat rovnou
  // tady (setViewMode pro rezimy "top"/"front"/"side" cte `placed`, ktere
  // se jako "const placed = []" deklaruje az mnohem niz v souboru -
  // synchronni pristup k nemu odsud by shodil TDZ ReferenceErrorem cely
  // zbytek scriptu, presne stejny bug jako u dimLabelEntries vyse). Sync
  // je proto az za "const placed = []" (viz komentar tam).
}

// Vyssi okolni/hemisferni svetlo + druhe (vyplnove) svetlo z opacne strany -
// bez toho vypadaji kovove materialy (metalness > 0) prakticky cerne, protoze
// PBR kovy odrazi hlavne okolni prostredi, ktere tu jinak neni (zadna env mapa).
const hemiLight = new THREE.HemisphereLight(0xffffff, 0x4a4f58, 1.6);
scene.add(hemiLight);
const dirLight = new THREE.DirectionalLight(0xffffff, 1.3);
dirLight.position.set(400, 600, 300);
scene.add(dirLight);
const fillLight = new THREE.DirectionalLight(0xffffff, 0.6);
fillLight.position.set(-350, 250, -300);
scene.add(fillLight);
const ambLight = new THREE.AmbientLight(0xffffff, 0.35);
scene.add(ambLight);

// Puvodni ("zakladni") intenzity vyse - posuvnik "Svetlo" (Robert 2026-08-06:
// "posuvník na intenzitu hlavního/ambientního světla") vsechny 4 skaluje
// spolecne stejnym nasobitelem, at zustane pomer mezi hlavnim/vyplnovym/
// ambientnim svetlem tak, jak byl vyladeny.
const BASE_LIGHT_INTENSITY = { hemi: 1.6, key: 1.3, fill: 0.6, ambient: 0.35 };
let lightIntensityMul = 1;
try {
  const li = parseFloat(localStorage.getItem("konfLightIntensity"));
  if (isFinite(li)) lightIntensityMul = Math.max(0.2, Math.min(2.5, li));
} catch (e) { /* ignoruj */ }

function applyLightIntensity(mul) {
  lightIntensityMul = Math.max(0.2, Math.min(2.5, mul));
  hemiLight.intensity = BASE_LIGHT_INTENSITY.hemi * lightIntensityMul;
  dirLight.intensity = BASE_LIGHT_INTENSITY.key * lightIntensityMul;
  fillLight.intensity = BASE_LIGHT_INTENSITY.fill * lightIntensityMul;
  ambLight.intensity = BASE_LIGHT_INTENSITY.ambient * lightIntensityMul;
  try { localStorage.setItem("konfLightIntensity", String(lightIntensityMul)); } catch (e) { /* ignoruj */ }
}
applyLightIntensity(lightIntensityMul);

// "Simultanni kontrast" (Robert 2026-08-06, po vysvetleni optiky oka -
// stejne sedy dil na cernem pozadi opticky vypada svetlejsi nez na bilem,
// i kdyz se jeho barva vubec nezmenila) - misto slozite post-processing
// pipeline (riziko, viz predchozi incident "cela scena se rozbila")
// nejjednodussi bezpecna cesta: CSS filter contrast() primo na canvas
// (renderer.domElement) - realny kontrast cele vykreslene scmeny (tmave
// jeste tmavsi, svetle jeste svetlejsi), presne to, co jasovy kontrast
// vnimany okem zesiluje. Nema vliv na UI panely (filter pusobi jen na
// canvas element, ne na sourozence v DOM).
let sceneContrast = 100; // % (100 = beze zmeny)
try {
  const sc = parseFloat(localStorage.getItem("konfSceneContrast"));
  if (isFinite(sc)) sceneContrast = Math.max(70, Math.min(160, sc));
} catch (e) { /* ignoruj */ }

function applySceneContrast(pct) {
  sceneContrast = Math.max(70, Math.min(160, pct));
  renderer.domElement.style.filter = sceneContrast === 100 ? "" : ("contrast(" + sceneContrast + "%)");
  try { localStorage.setItem("konfSceneContrast", String(sceneContrast)); } catch (e) { /* ignoruj */ }
}
applySceneContrast(sceneContrast);

// Robert 2026-08-08 ("musí být dobře vidět střed všech os ve scéně"):
// stredove cary mrizky (X a Z osa procházející pocatkem) drive skoro
// splyvaly s ostatnimi carami (0x333944 vs 0x24282f - skoro identicke),
// ted vyrazne svetlejsi/kontrastnejsi, at je patrne, kudy prochazi
// pocatek souradnic i bez potreby priblizit se.
// Robert 2026-08-08 ("tu mříž pořádně zjemni" -> upresneno "nemyslel
// jsem zjemnit sít na menší oka, ale ty linky zeslabit... velikost oka
// je stanovena stejným číslem které nastavuje vstupní grid tvaru"):
// PUVODNI pokus (pevnych 100 deleni) byl spatne pochopeny pozadavek -
// spravne reseni je (a) ciselna velikost oka = #shapeInsertGridMm
// ("Rastr vkládání" u Vlastnich tvaru, shapeInsertGridStepMm() nize -
// hoisted function deklarace, volatelna uz odsud), NE pevne cislo, a
// (b) same cary vizualne slabsi/svetlejsi pres opacity (WebGL beztak
// ve vetsine prohlizecu ignoruje material.linewidth - jediny funkcni
// zpusob "tenci" cary je pruhlednost, stejny trik uz pouziva docasna
// mrizka pri vkladani tvaru nize).
const GRID_TOTAL_SIZE_MM = 1000;
function mainGridDivisions() {
  const step = (typeof shapeInsertGridStepMm === "function") ? shapeInsertGridStepMm() : 50;
  return Math.max(1, Math.round(GRID_TOTAL_SIZE_MM / step));
}
// Robert 2026-08-11 ("totez chci primo ve scene namisto cerne mrize" -
// po odsouhlaseni HUD mrizky v renderu): stejny vzhled jako podlaha
// renderu - HUD zelene cary, kazda pata v oranzovem akcentu, zadny
// sedy podklad (rovina je pruchozi uz z podstaty GridHelperu).
const HUD_GRID_COLOR = 0x2fe07a;        // stejna zelena jako HUD nadpisy
const HUD_GRID_ACCENT = 0xff9e33;       // oranzovy akcent jako pozadi webu
const HUD_GRID_ACCENT_EVERY = 5;        // kazda pata cara

// GridHelper umi jen 2 barvy (stred + zbytek), takze akcentni cary
// delame druhym, ridsim GridHelperem polozenym pres ten hlavni.
function makeHudGrid(divisions) {
  const g = new THREE.Group();
  const base = new THREE.GridHelper(GRID_TOTAL_SIZE_MM, divisions, HUD_GRID_COLOR, HUD_GRID_COLOR);
  base.material.transparent = true;
  base.material.opacity = 0.22;
  g.add(base);
  const accDiv = Math.max(1, Math.round(divisions / HUD_GRID_ACCENT_EVERY));
  const acc = new THREE.GridHelper(GRID_TOTAL_SIZE_MM, accDiv, HUD_GRID_ACCENT, HUD_GRID_ACCENT);
  acc.material.transparent = true;
  acc.material.opacity = 0.30;
  acc.position.y = 0.02;   // zlomek mm nad zakladni mrizkou, at neprobliskava
  g.add(acc);
  g.traverse(o => { if (o.material) o.material.depthWrite = false; });
  return g;
}

let grid = makeHudGrid(mainGridDivisions());
scene.add(grid);

// Prekresli hlavni mrizku se soucasnym krokem "Rastr vkládání" - volano
// pri zmene #shapeInsertGridMm (viz listener u shapeInsertGridStepMm
// nize) i jednou hned po nacteni (kdyby uz predtim byla v localStorage
// jina hodnota nez vychozich 50).
function rebuildMainGrid() {
  const wasVisible = grid.visible;
  scene.remove(grid);
  grid.traverse(o => {
    if (o.geometry) o.geometry.dispose();
    if (o.material) o.material.dispose();
  });
  grid = makeHudGrid(mainGridDivisions());
  grid.visible = wasVisible;
  scene.add(grid);
}

// Vrhane stiny (Robert 2026-08-06: "pridejme lehce moznost stinu") -
// "lehka" varianta: jen hlavni (key) svetlo vrha stin, mensi shadow-mapa
// (1024, ne 2048+), pevny (ne dynamicky dopocitavany) frustum - postacuje
// pro typickou velikost sestavy u stredu sceny, bez narocneho prepocitavani
// pri kazdem pridani/presunuti dilu. Puvodne VYCHOZI VYPNUTO, ted (Robert
// 2026-08-07: "chci krásnou technickou 3D scénu, moderní") VYCHOZI
// ZAPNUTO - dily bez stinu pusobily "plovouci"/needly, se stinem maji
// jasnou vazbu na podlahu. Toggle "Stiny" v panelu Prostredi sceny
// zustava, kdyby to nekdo chtel vypnout (napr. slabsi GPU).
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
dirLight.shadow.mapSize.set(1024, 1024);
dirLight.shadow.camera.left = -3000;
dirLight.shadow.camera.right = 3000;
dirLight.shadow.camera.top = 3000;
dirLight.shadow.camera.bottom = -3000;
dirLight.shadow.camera.near = 100;
dirLight.shadow.camera.far = 8000;
dirLight.shadow.bias = -0.0015; // potlaci "shadow acne" na tenkych profilech

// Neviditelna "podlaha" (jen zachytava stin, sama se nekresli) - podlaha
// sceny je realne Y=0 (overeno - grid pro kotaci se kresli na Y=0.5,
// "tesne nad podlahou").
const shadowGroundMat = new THREE.ShadowMaterial({ opacity: 0.32 });
const shadowGround = new THREE.Mesh(new THREE.PlaneGeometry(20000, 20000), shadowGroundMat);
shadowGround.rotation.x = -Math.PI / 2;
shadowGround.position.y = 0;
shadowGround.receiveShadow = true;
shadowGround.visible = false; // zapina applyShadowsEnabled()
scene.add(shadowGround);

let shadowsEnabled = true;
try {
  const savedShadows = localStorage.getItem("konfShadows");
  if (savedShadows !== null) shadowsEnabled = savedShadows === "1";
} catch (e) { /* ignoruj */ }

function applyShadowsEnabled(on) {
  shadowsEnabled = !!on;
  dirLight.castShadow = shadowsEnabled;
  shadowGround.visible = shadowsEnabled;
  try { localStorage.setItem("konfShadows", shadowsEnabled ? "1" : "0"); } catch (e) { /* ignoruj */ }
}
applyShadowsEnabled(shadowsEnabled);

(function setupShadowsToggle() {
  try {
    const cb = document.getElementById("shadowsToggle");
    if (!cb) return;
    cb.checked = shadowsEnabled;
    cb.addEventListener("change", () => applyShadowsEnabled(cb.checked));
  } catch (e) { /* prepinac neni kriticky */ }
})();

// Robert 2026-08-20/21 ("jak se da scena nastavit, at bere co nejmene
// vykonu pocitace" -> "ad 1 uz mame [stiny], udelej prepinac ad 2
// [rozliseni]"): SAMOSTATNY prepinac jen na vykreslovaci rozliseni,
// nezavisly na Stinech (ty uz svuj vlastni prepinac meli davno pred
// timhle). Pomer pixelu (devicePixelRatio) na Retina/4K displejich byva
// 2-3, tedy 4-9x vic pixelu k prekresleni kazdy snimek nez na bezne
// obrazovce - jednim zaskrtnutim se stahne na 1x. antialias/HDRI se
// zde MENIT NEMOHOU (jsou nastavene uz pri vytvoreni WebGLRenderer,
// zivá zmena by vyzadovala ho cely znovu vytvorit - prilis invazivni
// na jednoduchy prepinac).
let lowResEnabled = false;
try {
  lowResEnabled = localStorage.getItem("konfLowRes") === "1";
} catch (e) { /* ignoruj */ }

function applyLowRes(on) {
  lowResEnabled = !!on;
  renderer.setPixelRatio(lowResEnabled ? 1 : window.devicePixelRatio);
  try { localStorage.setItem("konfLowRes", lowResEnabled ? "1" : "0"); } catch (e) { /* ignoruj */ }
}
applyLowRes(lowResEnabled);

(function setupLowResToggle() {
  try {
    const cb = document.getElementById("lowResToggle");
    if (!cb) return;
    cb.checked = lowResEnabled;
    cb.addEventListener("change", () => applyLowRes(cb.checked));
  } catch (e) { /* prepinac neni kriticky */ }
})();

// Robert 2026-08-02 ("muzem udelat scenu s nejakym barevnym prostredim,
// resp prechod do dalky sede stupne? pokud ano dejme rovnou na scenu
// prouzek na zmenu barvy"): "blizka" barva (vybrana prouzkem) dole,
// nahore prechazi do neutralni sedi ENV_FOG_GRAY - STEJNE sedi, jakou
// pouziva scene.fog nize, takze se vzdaleny/vysoko polozeny okraj
// pozadi a mlhou-zesedivela geometrie vizualne slijou do sebe beze sve
// (bez viditelneho svu). Vlastni "obloha" je proste plnobrazovkovy
// vertikalni gradient (CanvasTexture jako scene.background) - u
// orbitalni kamery (nehleda se "ven" volne jako od-ruky) je tohle
// bezny/postacujici zpusob "studioveho" pozadi, bez potreby skutecne
// sferické env-mapy.
const ENV_FOG_GRAY = 0x9199a3;
// Fog zacina az za typickym pracovnim prostorem (radove tisice mm) - at
// se nerozbije Robertovo drivejsi zadani "objekty v dalce nesmi mizet"
// (to bylo o TVRDEM oriznuti kamerou, far=100000 beze zmeny; fog tady je
// jen jemne barevne stmivani, nikdy nic neudela neviditelnym).
scene.fog = new THREE.Fog(ENV_FOG_GRAY, 10000, 80000);

let envHue = 210; // vychozi odstin (naladeno na modrosedou, blizko existujicimu --accent)
// Jas "blizke" barvy gradientu (Robert 2026-08-06: "pridejme do sceny k
// barve prostredi take posuvnik jasu") - drive napevno 20 (viz puvodni
// hsl(...,38%,20%) nize), ted nastavitelne posuvnikem vedle barevneho
// prouzku.
let envLightness = 20;
// Sytost (saturace) "blizke" barvy gradientu (Robert 2026-08-06: "čím
// pořeším menší podíl barvy?" - drive napevno 38%, viz puvodni
// hsl(hue,38%,lightness%) nize). Nizsi sytost = vetsi "podil sede" vuci
// zvolenemu odstinu.
let envSaturation = 38;
try {
  const savedHue = parseFloat(localStorage.getItem("konfEnvHue"));
  if (!isNaN(savedHue)) envHue = ((savedHue % 360) + 360) % 360;
  const savedLight = parseFloat(localStorage.getItem("konfEnvLightness"));
  if (isFinite(savedLight)) envLightness = Math.max(5, Math.min(70, savedLight));
  const savedSat = parseFloat(localStorage.getItem("konfEnvSaturation"));
  if (isFinite(savedSat)) envSaturation = Math.max(0, Math.min(100, savedSat));
} catch (e) { /* ignoruj */ }

const envBgCanvas = document.createElement("canvas");
envBgCanvas.width = 2; envBgCanvas.height = 256;
const envBgCtx = envBgCanvas.getContext("2d");
const envBgTexture = new THREE.CanvasTexture(envBgCanvas);

// HDRI environmentalni mapa (Robert 2026-08-06) - kdyz je aktivni, barevny
// gradient pozadi se nesmi prepisovat (deklarovano PRED applyEnvironmentHue,
// ktere se vola hned pri startu - TDZ).
let activeHdriFile = "";

function applyEnvironmentHue(hue) {
  envHue = ((hue % 360) + 360) % 360;
  // "Blizka" barva prostredi - tlumeny (nizka saturace/svetlost), at
  // nerusi barvy dilu ve scene; nahore vzdy stejna neutralni sed jako fog.
  const nearColor = "hsl(" + envHue.toFixed(0) + "," + envSaturation.toFixed(0) + "%," + envLightness.toFixed(0) + "%)";
  const farColor = "#" + ENV_FOG_GRAY.toString(16).padStart(6, "0");
  const grad = envBgCtx.createLinearGradient(0, 0, 0, envBgCanvas.height);
  grad.addColorStop(0, farColor);   // nahoru = "do dalky" = sedive
  grad.addColorStop(1, nearColor);  // dolu = "blizko" = zvolena barva
  envBgCtx.fillStyle = grad;
  envBgCtx.fillRect(0, 0, envBgCanvas.width, envBgCanvas.height);
  envBgTexture.needsUpdate = true;
  scene.background = envBgTexture; // pozadi je VZDY gradient (HDRI jde jen do environment)
  const thumb = document.getElementById("envThumb");
  const strip = document.getElementById("envColorStrip");
  if (thumb && strip) thumb.style.left = (envHue / 360 * strip.clientWidth) + "px";
  try { localStorage.setItem("konfEnvHue", String(envHue)); } catch (e) { /* ignoruj */ }
}
applyEnvironmentHue(envHue);

(function setupEnvColorStrip() {
  const strip = document.getElementById("envColorStrip");
  if (!strip) return;
  function hueFromEvent(ev) {
    const r = strip.getBoundingClientRect();
    const x = Math.max(0, Math.min(r.width, ev.clientX - r.left));
    return (x / r.width) * 360;
  }
  strip.addEventListener("mousedown", (ev) => {
    ev.preventDefault();
    // barva pozadi a HDRI odlesky funguji nezavisle - vyber barvy HDRI nevypina
    applyEnvironmentHue(hueFromEvent(ev));
    function onMove(mv) { applyEnvironmentHue(hueFromEvent(mv)); }
    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
  window.addEventListener("resize", () => applyEnvironmentHue(envHue));
})();

function applyEnvironmentBrightness(lightness) {
  envLightness = Math.max(5, Math.min(70, lightness));
  try { localStorage.setItem("konfEnvLightness", String(envLightness)); } catch (e) { /* ignoruj */ }
  applyEnvironmentHue(envHue); // prekresli gradient se stejnym odstinem, novou svetlosti
}

function applyEnvironmentSaturation(sat) {
  envSaturation = Math.max(0, Math.min(100, sat));
  try { localStorage.setItem("konfEnvSaturation", String(envSaturation)); } catch (e) { /* ignoruj */ }
  applyEnvironmentHue(envHue); // prekresli gradient se stejnym odstinem, novou sytosti
}

(function setupEnvBrightnessSlider() {
  try {
    const slider = document.getElementById("envBrightnessSlider");
    const valEl = document.getElementById("envBrightVal");
    if (!slider) return;
    const sync = () => {
      slider.value = envLightness;
      if (valEl) valEl.textContent = Math.round(envLightness) + "%";
    };
    slider.addEventListener("input", () => {
      applyEnvironmentBrightness(parseFloat(slider.value));
      sync();
    });
    sync();
  } catch (e) { /* posuvnik neni kriticky */ }
})();

(function setupEnvSaturationSlider() {
  try {
    const slider = document.getElementById("envSaturationSlider");
    const valEl = document.getElementById("envSaturationVal");
    if (!slider) return;
    const sync = () => {
      slider.value = envSaturation;
      if (valEl) valEl.textContent = Math.round(envSaturation) + "%";
    };
    slider.addEventListener("input", () => {
      applyEnvironmentSaturation(parseFloat(slider.value));
      sync();
    });
    sync();
  } catch (e) { /* posuvnik neni kriticky */ }
})();

(function setupLightIntensitySlider() {
  try {
    const slider = document.getElementById("lightIntensitySlider");
    const valEl = document.getElementById("lightIntensityVal");
    if (!slider) return;
    const sync = () => {
      slider.value = lightIntensityMul;
      if (valEl) valEl.textContent = Math.round(lightIntensityMul * 100) + "%";
    };
    slider.addEventListener("input", () => {
      applyLightIntensity(parseFloat(slider.value));
      sync();
    });
    sync();
  } catch (e) { /* posuvnik neni kriticky */ }
})();

(function setupSceneContrastSlider() {
  try {
    const slider = document.getElementById("sceneContrastSlider");
    const valEl = document.getElementById("sceneContrastVal");
    if (!slider) return;
    const sync = () => {
      slider.value = sceneContrast;
      if (valEl) valEl.textContent = Math.round(sceneContrast) + "%";
    };
    slider.addEventListener("input", () => {
      applySceneContrast(parseFloat(slider.value));
      sync();
    });
    sync();
  } catch (e) { /* posuvnik neni kriticky */ }
})();

