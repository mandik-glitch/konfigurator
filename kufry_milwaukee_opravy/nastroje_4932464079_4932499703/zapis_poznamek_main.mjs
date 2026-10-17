// Sestaví zdroje/<SKU>_poznamky.md pro 4932464079, 4932464080, 4932499703, 4932499704. node zapis_poznamek_main.mjs
import fs from 'node:fs';
import path from 'node:path';
import { tabulkaStaraNova, historie, f4, kola, rd, SR, ROOT } from './zapis_poznamek.mjs';
import { V79, V80, V499703, SPOLECNE } from '../p4932464079_data.mjs';
const OUT = s => path.join(ROOT, 'kufry_milwaukee_opravy/zdroje', s + '_poznamky.md');

const KAMERA_POCTIVE = `**Kamera (poctivě):** kamery z kontroly (\`kufriky_cloud/srovnani_opravy/<SKU>/kamery_<SKU>.json\`, klíč \`z_kontroly\`) jsou odhad z ručně změřených rohů fotografie; výška horních bodů byla volný parametr. Sloupec „kamera z kontroly“ je proto jediný srovnatelný se starým IoU (u otevřeného víka se, stejně jako v kontrole, dofituje jen úhel víka). Sloupec „dofitovaná kamera“ (6 parametrů kamery + úhel víka optimalizováno proti obrysu NAŠEHO modelu, \`kamery_dofit_<SKU>.json\`) **není důkaz správnosti tvaru** – kamera se přizpůsobila modelu. IoU maska fotografie vyplňuje díry uvnitř obrysu (stejný postup jako \`foto_maska.py\`), proto sama průchozí okna IoU nezvyšují ani nesnižují; silueta kvádrového boxu vychází vysoko i u hrubého tvaru, rozhodující jsou proto detaily (tabulka „Co z reportu je opraveno“) a IoU červených prvků.`;

function spolecneBoxy(s, V, extra) {
  const J = kontrola(s);
  return '';
}
function kontrola(s) { return rd(path.join(ROOT, 'kufriky_cloud/kontrola_john_v6', s, 'kontrola.json')); }

export { KAMERA_POCTIVE, OUT, V79, V80, V499703, SPOLECNE };

// ============================================================================================================
// 4932499703 / 4932499704
// ============================================================================================================
function md703(sku) {
  const s = sku, drug = s === '4932499703' ? '4932499704' : '4932499703', nm = s === '4932499703' ? 'Box pro elektrikáře' : 'Box pro instalatéry';
  const fotky = ['c01', 'c02', 'c03'];
  return `# ${s} – Milwaukee PACKOUT ${nm} (165 × 410 × 560) – poznámky k opravenému modelu

Nová verze postavená vlastním generátorem (jádro \`kufriky_cloud/jadro\`), **ne** úpravou Johnových souborů. Johnův GLB se jen četl jako reference toho, co se opravuje (jediný panel, 5 kapes 60×60, plný hladký box).
${s === '4932499704' ? `\n**Model je STEJNÝ jako u ${drug}** (box pro elektrikáře) – jen s jiným SKU v \`asset.extras.sku\`. Důvod: viz oddíl „Elektrikář × instalatér“ níže (výrobce používá pro obě SKU totožnou fotografii, doplňkové fotografie sad ukazují stejný box se stejnými panely, GLB obou SKU u Johna byly binárně shodné).\n` : ''}
Generátor: \`kufry_milwaukee_opravy/kufr_${s}.mjs\` ${s === '4932499704' ? '(importuje a volá `kufr_4932499703.mjs`)' : ''} + společný základ \`p4932464079_{zaklad,data,korpus,vicko,celo,sestav}.mjs\` (stejný základ jako u 4932464079/80) + \`p4932499703_vnitrek.mjs\` (panely).
Sestavení: \`node kufry_milwaukee_opravy/vytvor_4932464079_4932499703.mjs ${s}\` → \`modely/${s}.glb\` (obálka ${V499703.X * 2} × ${V499703.Y * 2} × ${V499703.H} mm, kontroluje skript ±1 mm). Náhled: \`nahled/${s}.html\`.
Souřadnice: X = hloubka 410 (čelo s rukojetí a západkami do +X, pant vzadu −X), Y = délka 560, Z = výška 165; počátek = střed obálky.

## 1. Fotografie
| foto | co ukazuje | použití |
|---|---|---|
| c01 (Hero_1, výrobce) | otevřený box přesně shora, víko vzadu, dva panely, 4 kapsy | **jediná fotografie přímo k SKU**: panely, kapsy, panel ve víku, pás úchytů, štítek; obrys |
| c02 (sada 4932499466, Hero_3) | **nepřímý důkaz** – box ze sady „PACKOUT Electrician Set 62 pcs“ zepředu zprava, otevřený | vnější tvar (bez tyčí a krytek), červené žebrované držadlo, kruhový otvor, západky s třmeny, poloha západek |
| c03 (sada 4932499466, Hero_2) | totéž shora | rozteč panelů a víka, drážka s úchyty ve víku |
| c04, c05 (sada 4932499466; its.co.uk) | šikmo shora; zavřený box shora | rozložení 10 kapes na víku (2 skupiny po 5 + drážka), štítek v kapse |

Fotografie nejsou v repu. URL: \`zdroje/${s}_fotky_url.tsv\`. Doplňkové fotografie jsem stáhl jen do scratchpadu (\`…/scratchpad/kufry3/${s}/c02–c05.jpg\`).
**Pozor:** c02–c05 patří k SADĚ (box + nářadí), ne k samostatnému SKU ${s}. Box v sadě je podle názvu stránky milwaukeetool.eu „packout electrician box“ (/en-eu/packout-electrician-set-62pcs/packout-electrician-box); panely na c01 a na fotografiích sady jsou shodné, ale 100% jistota, že jde o totéž provedení, **není**.

## 2. Elektrikář × instalatér
- Hero_1 obou SKU je **bajt po bajtu totožná** (md5 812c851f…, kontrola i my); PNG verze Hero_1 je také shodná. Hero_2–5 (a další) pro 4932499703/04 vracejí 404.
- Prodejce haumesser.com používá pro 4932499704 stejný snímek (800 px).
- Sady výrobce: elektrikář 4932499466 a instalatér 4932499467 – fotografie (Hero_1–5) ukazují **tentýž box**, stejné dva panely (vlevo hladký, vpravo se čtyřmi kapsami), stejný panel ve víku s pásem úchytů; liší se jen vložené nářadí. Prázdné SKU 4932499703/04 se tedy podle dostupných podkladů **neliší**. Model je proto totožný, jen s jiným SKU v meta (\`asset.extras.sku\`, \`nazev\`).
- Neověřeno: zda existuje drobný rozdíl (barva úchytů, potisk, počet kapes) – fotografie ho neukazují.

## 3. Co z reportu je opraveno (všech 5 bodů kontroly + nové zjištění)
| č. | report | stav | jak |
|---|---|---|---|
| 1 | dva vložné panely (levý hladký, pravý červeně lemovaný) ≈ 490×300 celkem | **opraveno** | levý panel Y −244…70, pravý Y −108…236, oba X ≈ −145…144 (z c01 přes mřížku bodů; ±10 mm); černá plsť + červená obruba 4 mm. Zakrytá část levého panelu pod pravým = odhad |
| 2 | 4 vysoké látkové kapsy ≈ 75×130 mm (ne 5× 60×60) | **opraveno** | 4 kapsy 74 × 128 mm (Y × X), výška 17 mm (vyboulení), při zadní hraně pravého panelu; středy Y −52, 28, 107, 187 (c01) |
| 3 | pás červených pružných úchytů ve víku + červený štítek vlevo nahoře | **opraveno** | panel ve víku 300 × 492 mm s červeným lemem; černá lišta 44 × 384 mm u pantové hrany + 64 červených „prstů“ (jen výška a rozteč odhad); červený štítek 22 × 54 mm v rohu u čela vlevo |
| 4 | poloha západek ≈ ±160 mm (model ±179) | **opraveno** | střed západek ±155 mm (c01 třmeny; c02 poloha vůči rukojeti), velikost jazyka 56 × 62 mm |
| 5 | víko: silný rám s žebrovaným okrajem, pantové články | **opraveno zjednodušeně** | víko jako dutá skořepina 62 mm (strop −17,5 mm), 10 kapes + drážka (c05), 5 pantových ok střídavě s oky vany, ocelový čep |
| nové | vnější tvar nešlo z c01 posoudit | **částečně z c02–c05** | tub se zaoblenými rohy bez hliníkových tyčí a rohových krytek (na žádné fotografii sady nejsou), červené žebrované držadlo s kruhovým otvorem, dvě západky s drátěným třmenem – vše **nepřímý důkaz** (fotografie sady) |

## 4. Změřeno / odhad / neověřeno
**Změřeno z c01 (shora, kamera dofitována k obrysu; ±10 mm):** poloha a rozměr panelů a kapes, poloha poutka, štítku ve víku a pásu úchytů; rozteč západek.
**Z fotografií sady (nepřímo, ±15 mm):** tvar rukojeti (červený U s žebrovaným úchopem a oválným otvorem nad ním), západky (červený jazyk se 4 zuby + drátěný třmen, v otevřeném stavu visí dolů), uspořádání kapes víka (10 + drážka), absence tyčí.
**Odhad (výslovně neověřeno):**
- **celý vnější tvar** (stěny, rohové poloměry ≈ 36 mm, šikmé ramena víka, výška víka 62 mm / těla 103 mm, švík z' = 103) – fotografie SKU je kolmo shora a nedává vnější pohled; použito jen z fotografií sady;
- zadní strana, spodek, boky: žádná fotografie;
- rozměry a tvar kapes na víku (hloubka 14 mm), zakrytá část levého panelu, tloušťky stěn a panelů (8 mm), šrouby;
- výška uložení panelů v těle (panel z' 58–74), tloušťka plsti;
- pružné úchyty: počet (64) a tvar jsou stylizace;
- barva/potisk drobností (bez loga na čele – na fotografiích sady žádné není);
- zda jsou panely samostatně vyjímatelné: v modelu jsou samostatné uzly \`panel_levy\`, \`panel_pravy\` (bez pohybové osy).

## 5. Pohyblivé uzly (extras.osa, souřadnice uzlu)
\`vicko\` (pant vzadu, osa −Y, 0…110°), \`drzadlo_cervene\` (výklop, osa −Y, 0…55°), \`trmen_L/P\` (drátěné třmeny, osa +Y, 0…165°; zavřený = nahoře u víka, otevřený visí dolů). Panely a kapsy jsou samostatné uzly/díly.

## 6. IoU (silueta) a poctivé upozornění
${tabulkaStaraNova(s, fotky)}
Poznámky: c01 – kamera kontroly je téměř ortografická (fov ≈ 10°, 4 body na 6 parametrů) a **slabě určená**; naše IoU při této kameře je proto nižší, ale při kameře s reálnější perspektivou (fov ≈ 30°) vychází 0,94–0,95. U c02, c03 jde o **jiné fotografie (sada), kamera z kontroly neexistuje** – jsou jen dofitované; slouží výhradně ke kontrole vnějšího tvaru, nejsou důkazem pro samotné SKU.
${KAMERA_POCTIVE.replace(/<SKU>/g, s)}

### Historie kol
${historie(s, fotky)}

## 7. Co zůstalo / proč
- Vnější tvar je podložen jen fotografiemi sady (nepřímo) – označeno neověřeno. Je-li k dispozici fotografie samotného SKU z boku/zepředu, je třeba ověřit: poloměry rohů, výšku víka, zda mají boky chytací okna (v sadě ne).
- Panely jsou hladké kvádry s kapsami (bez rozměrové jemnosti látky).
- Pružné úchyty ve víku jsou stylizované.
`;
}
export { md703 };

// ============================================================================================================
// 4932464079 / 4932464080 (společný generátor, výška jako parametr)
// ============================================================================================================
function md7980(sku) {
  const s = sku, V = s === '4932464079' ? V79 : V80, velky = s === '4932464079';
  const fotky = velky ? ['c01', 'c02', 'c03', 'c01_nahore'] : ['c01', 'c02'];
  const zs = V.H - V.lidH, zk = zs + V.capUp;
  return `# ${s} – Milwaukee PACKOUT ${velky ? 'Velký box na nářadí (282 × 411 × 561)' : 'Box na nářadí (165 × 411 × 561)'} – poznámky k opravenému modelu

Nová verze postavená vlastním generátorem (jádro \`kufriky_cloud/jadro\`), **ne** úpravou Johnových souborů. Johnův GLB (\`kufriky_john/nahled-modely-v6/modely/${s}.glb\`) se jen četl jako reference toho, co se opravuje (a pro přeměření IoU); jeho geometrie se nekopírovala.

**Společný parametrický generátor** pro 4932464079 (V = 282) a 4932464080 (V = 165): \`kufry_milwaukee_opravy/kufr_4932464079.mjs\` a \`kufr_4932464080.mjs\` volají tentýž \`p4932464079_sestav.mjs\` (moduly \`p4932464079_{zaklad,data,korpus,rohy,vicko,celo,drzadlo}.mjs\`); výška je parametr \`V.H\` v \`p4932464079_data.mjs\`, svislé polohy předního hardwaru a rohových krytek jsou parametry pro jednotlivé SKU (změřeno zvlášť na každé fotografii).
Sestavení: \`node kufry_milwaukee_opravy/vytvor_4932464079_4932499703.mjs ${s}\` → \`modely/${s}.glb\`${velky ? ' + varianta \`modely/4932464079_drzadlo_nahore.glb\` (horní držadlo zvednuté jako na fotografii c01, obálka záměrně překročena)' : ''}; obálka ${V.X * 2} × ${V.Y * 2} × ${V.H} mm, kontroluje skript (±1 mm). Náhled: \`nahled/${s}.html\`.
Souřadnice: X = hloubka 411 (čelo s rukojetí a západkami do +X, pant vzadu −X), Y = délka 561, Z = výška ${V.H}; počátek = střed obálky. Katalog (\`kufriky_john/kufriky.csv\`): L 561, Š 411, V ${V.H}.
**Obálka vs. držadlo:** katalogová výška ${V.H} mm platí pro zavřený box. ${velky ? 'Horní držadlo (na c01 zvednuté) je v hlavním GLB ve **sklopené** poloze uvnitř obálky (uzel `horni_drzadlo`, 0°); tvar sklopené polohy není na žádné fotografii – **odhad**. Varianta se zvednutým držadlem je jen pro porovnání s c01.' : 'Tento box horní držadlo nemá.'}

## 1. Fotografie
Fotografie nejsou v repu. URL v \`zdroje/${s}_fotky_url.tsv\`; kopie jen ve scratchpadu (\`…/scratchpad/kufry3/${s}/cNN.jpg\`, doplňkové \`…/scratchpad/mk79/dalsi/\`).
${velky ? `| c01 | zavřený box zepředu zprava, horní držadlo zvednuté | kalibrace, silueta, rohy, rukojeť, západky, víko zvenčí |
| c02 | otevřený, víko vzhůru (≈ 100°), shora zepředu | tělo, víko zevnitř, tyče, okna |
| c03 | totéž + vyjmutá vložka vpravo (z masky vyloučena) | totéž |
| d01–d02 (Feat_1/2, scratchpad) | detaily rukojeti a západky | jen tvar rukojeti (výklopná za horní čepy) a západky (jazyk + drátěný třmen) – **bez kamery** |` : `| c01 | zavřený box zepředu zprava | kalibrace, silueta, rohy, rukojeť, západky, víko |
| c02 | otevřený box, dvě vyjmuté boční přihrádky, třmeny visí | tělo, víko zevnitř; přihrádky mimo box z masky vyloučeny |
| c03 (Hero_3) | **jiný výrobek** (červený velký box), nepoužito | – |
| d01–d02 (Feat_1/2, scratchpad) | detaily rukojeti a západky | tvar rukojeti a západky |`}

## 2. Konstrukce (z fotografií) a rozměry
| prvek | hodnota | zdroj / jistota |
|---|---|---|
| obálka | 411 × 561 × ${V.H} (katalog) – model se nenatahuje | \`kufriky.csv\` |
| rohové tyče | 4 ks hliník, průřez ≈ 29 (Y) × 8 (X) mm, mezi černými krytkami, stojí mimo stěnu těla | c01–c03, ±3 mm; X-hloubka je odhad z šířky viditelných ploch |
| rohové krytky | horní ${V.capT} × 56 × 58 mm (z' ${(zk - V.capT).toFixed(0)}…${zk.toFixed(0)}), dolní ${V.capB} mm (z' ${V.capZ0}…${V.capZ0 + V.capB}); zasahují o ${V.capUp} mm do rohových výřezů víka | c01–c03, ±10 mm (svislé polohy z kamery ±15 mm) |
| chytací okna | průchozí: vana má v každém rohu výřez 56 × 58 mm (koncová stěna končí v |X| = ${V.xN}, čelní/zadní v |Y| = ${V.yN}); mezi tyčí a stěnou zbývá okno ≈ 27–29 mm | c01–c03: na fotografii je skrz okno vidět pozadí |
| spodní hrana těla | tělo (patky/nožky) sahá ≈ 11 mm pod dolní krytky; celá čelní hrana je souvislá | c01: silueta pod čarou spodních rohů krytek |
| švík víko/tělo | z' ${zs} (víko ${V.lidH} mm vysoké); odhad z kamery | ±15 mm |
| víko | hluboká skořepina: spodní lem s rohovými výřezy, vertikální čelo, zkosená ramena na koncích (≈ 40 mm), zaoblené rohy ≈ 30 mm, plató s **10 kapsami** (2 skupiny po 5: zadní řada 2, střední 1 dlouhá, přední 2; hloubka 14 mm), středové žebro, červený štítek 114 × 12 mm vpravo; uvnitř 2 podélná žebra, kruhový výstupek ⌀ 66, 5 šikmých výztuh u pantu, šrouby | c01 (vnějšek), c02/c03 (vnitřek); polohy kapes po hloubce X jsou odhad (±15 mm) |
| červená U-rukojeť | šířka 230 (Y ±115), z' ${V.handlePivot - V.handleH}…${V.handlePivot}, sloupky s 3 prsty a čepy nahoře, červená příčka, ${velky ? 'černý gumový' : 'černý gumový'} úchop se žebry, vystupuje do X = 205; **pohyblivý uzel** \`drzadlo_cervene\` (výklop kolem horních čepů, 0…55°) | c01, d01 |
| západky (2×) | červený jazyk 52 × ${V.latchH} mm se 4 zuby, střed Y = ±${V.yLatch}, z' ${V.latchTop - V.latchH}…${V.latchTop}; drátěný třmen Ø 4 mm jako **pohyblivý uzel** \`trmen_L/P\` (čep dole, 0…165°); černé pouzdro pod víkem | c01 (poloha), d02 (tvar); ≈ 2× větší a o ≈ 60–85 mm níž než Johnovy |
| kroužek s otvorem | ⌀ 37 mm, červený, v černém okruží ⌀ 54 mm, střed Y ≈ +14, z' ${V.ringZ} | c01 |
| logo | ${V.logoZ != null ? 'potisk „MILWAUKEE“ + blesk + „PACKOUT“ (bitmapové písmo, plochý červený reliéf 0,5 mm) nad rukojetí, střed Y ≈ +8' : 'nad rukojetí na fotografii není – v modelu není'} | c01 – zjednodušené písmo, ne věrný font |
| červený jazýček a žebrovaný kanál pod rukojetí | jazýček 38 × 18 mm u dolní hrany, 7 žeber | c01 |
| pant | 4 oka vany + 5 ok víka, ocelový čep, osa Y | c02/c03 (tvar a počet odhad) |

## 3. Co z reportu je opraveno
| č. | report | stav | jak |
|---|---|---|---|
| 1 | rohy: hliníkové tyče + rohové krytky (zásadní) | **opraveno** | 4 tyče 29 × 8 mm, horní a dolní krytky s šrouby, samostatné díly (\`tyc_hlinik\`, \`krytka_horni/dolni\`) |
| 2 | krátké strany: průchozí chytací okna | **opraveno** | rohové výřezy vany – skutečné průchozí okno (ověřeno renderem: skrz okno je vidět pozadí) |
| 3 | čelní rukojeť: červená U-rukojeť, o ≈ ${velky ? '130' : '100'} mm níž, jiný tvar (zásadní) | **opraveno** | tvar U s prsty a gumovým úchopem, správná výška, pohyblivý uzel |
| 4 | západky ≈ 65×57 / 70×73 mm, o ≈ ${velky ? '60' : '85'} mm níž | **opraveno** | 52 × ${V.latchH} mm + drátěný třmen (uzel); polohy podle c01 |
| 5 | víko: 10 kapes, zkosená ramena, štítek podélně | **opraveno** | viz tabulka výše |
| 6 | dělení víko/tělo ≈ 50 mm pod rovinou víka | **opraveno** | švík z' ${zs}, krytky do z' ${zk} (vychází z kamery, ±15 mm) |
| 7 | víko zevnitř: skořepina, žebra, kruhový výstupek | **opraveno zjednodušeně** | skořepina ${V.lidH} mm, žebra, výstupek ⌀ 66, výztuhy u pantu; jemné reliéfy nemodelovány |
| 8 | vnitřek těla: model má lavici/vložku, na fotkách není | **opraveno (odstraněno)** | prázdná vana s rohovými sloupky a lemem; ${velky ? 'vložku z c03 (dvě přihrádky) jsem NEmodeloval – zda je součástí dodávky, fotografie neříkají (**neověřeno**)' : 'přihrádky a boční vložky z c02 **nemodelovány – neověřeno** (viz níže)'} |
| 9 | ${velky ? 'horní držadlo: foto zvednuté, model sklopené' : '(u tohoto boxu není)'} | ${velky ? '**opraveno jako uzel + varianta**' : '–'} | ${velky ? 'uzel `horni_drzadlo` (čepy na oušcích víka, X ≈ −12, ramena 202 mm, rozteč 524 mm z c01); výchozí poloha sklopená; varianta `…_drzadlo_nahore.glb` zvednutá ≈ 92° pro srovnání s c01' : '–'} |
| 10 | logo, kruhový otvor, jazýček (kosmetické) | **opraveno** | viz tabulka výše |
| 11 | spodní hrana čela (kosmetické) | **opraveno** | souvislá hrana na nejnižší úrovni |

## 4. Pohyblivé uzly (extras.osa, souřadnice uzlu; v prohlížeči kladný úhel)
\`vicko\` (osa −Y, 0…110°; pant vzadu), \`drzadlo_cervene\` (osa −Y, 0…55°), \`trmen_L/P\` (osa +Y, 0…165°)${velky ? ', `horni_drzadlo` (dítě uzlu `vicko`, osa −Y, 0…95°)' : ''}.

## 5. Neověřeno / odhad (poctivě)
- Zadní strana, spodek (patky, zámkové prvky), koncové stěny zblízka – žádná fotografie; koncové stěny, žebra pod uchem víka, zadní stěna jsou odhad podle tvaru rohové sestavy.
- Tloušťky stěn (5 mm), poloměry, úkosy, hloubka kapes, tvar rohových krytek (zjednodušený hranol se zkosením).
- Svislé polohy (švík, krytky, hardware) jsou ±10–15 mm kvůli slabě určené kameře.
${velky ? '- Horní držadlo: poloha čepů a délka ramen z jediné fotografie (c01); **sklopená poloha je odhad**; není jisté, že držadlo patří k tomuto SKU (na fotografii výrobce je zvednuté, katalogová obálka ho nezahrnuje).\n- Vložka z c03 (dvě přihrádky) a obsah (nářadí) – neověřeno, nemodelováno.' : '- **Interiér z c02 (3 + 3 přihrádky vlevo/vpravo, volný střed, dvě vyjmuté boční přihrádky s víčky) NEmodelován:** pokus o rektifikaci polohy přihrádek na rovinu okraje vany dal při kameře dofitované k obrysu protichůdné rozměry (přihrádky mimo půdorys vany), tj. polohy nelze bezpečně odvodit; přihrádky jsou pravděpodobně vyjímatelné doplňky. Označeno **neověřeno**.\n- Boční přihrádky mimo box (c02) nejsou součástí modelu.'}
- Logo je zjednodušené písmo, ne věrný font.

## 6. IoU (silueta) – staré a nové
${tabulkaStaraNova(s, fotky)}
${velky ? 'Řádek `c01_nahore`: úplná silueta včetně zvednutého držadla (varianta GLB); staré hodnoty pro něj nejsou (Johnův IoU vylučoval oblast držadla).' : ''}
Johnův IoU z kontroly (první sloupec) vylučoval oblast zvednutého držadla / vyjmuté vložky; u otevřeného víka nejde Johnův GLB nastavit (víko je rozptýlené ve 'viko-*' dílech bez uzlu s osou), proto jsou „přeměřené“ hodnoty jen u fotografií se zavřeným víkem; u ostatních platí hodnota z kontroly (s dofitovaným úhlem víka).
${KAMERA_POCTIVE.replace(/<SKU>/g, s)}

### Historie kol
${historie(s, fotky)}

## 7. Co zůstalo / proč
- Tvar rohových krytek, koncových stěn a víka zevnitř je zjednodušený (bez jemných žeber, vybrání a zaoblení z fotografií).
- Logo, drobná žebra a plsť/gumové struktury: stylizace.
- Zadní strana a spodek: neověřeno (viz výše).
`;
}
export { md7980 };

// --- zápis souborů ---
if (process.argv[1].endsWith('zapis_poznamek_main.mjs')) {
  const which = process.argv.slice(2).length ? process.argv.slice(2) : ['4932464079', '4932464080', '4932499703', '4932499704'];
  for (const s of which) fs.writeFileSync(OUT(s), (s.startsWith('49324640') ? md7980(s) : md703(s)));
  console.log('zapsáno', which.join(', '));
}
