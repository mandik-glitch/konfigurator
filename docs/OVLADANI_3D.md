# Ovládání přímo ve 3D (drag and drop, nabídka pravým tlačítkem, propojení s panelem)

Robert 2026-10-03: *„udělej zatím přídavné ovládací prvky přímo do 3D pohledu/modelu, systémem drag and drop, a nabídkou přes pravé tlačítko myši s vizuálním
propojením do panelu“* a *„středovou nohu když táhnu, neukazuje se o kolik mm – je potřeba vylepšit všechny prvky i přímo 3D prohlížení“*.

**Princip (žádný kód pro konkrétní produkt v prohlížeči):** generátor popíše, co se dá ve 3D chytit a co nabídnout (`vodici.ovladani`), a jeden obecný modul
`webapp/js/v3d-ovladani.js` to vykreslí a zpracuje. Nový generátor (vozík, stojan…) tedy dostane stejné ovládání jen tím, že vrátí stejný popis.

## Kde popis je
`GET /api/stul/konfigurace` (zaměstnanci) → `vodici.ovladani` (souřadnice GLB: mm, X hloubka dozadu, Y nahoru, Z šířka doprava, vycentrováno, podlaha y = 0).
Staré `vodici.stredni_noha` zůstává (veřejná Volba komponent ho používá); pro stránku platí: chybí-li `ovladani`, modul si tah střední nohy dopočítá ze `stredni_noha`.
Generuje `api/stul_konfigurator.py: ovladani_3d(r)`, do GLB souřadnic převádí `api/stul_glb.py: vodici()`. Test: `scripts/2026-10-02_stul_testy/test_stul_ovladani.py`.

## `casti` – co lze najet / kliknout pravým tlačítkem
`{id, label, param:[parametry pro propojení s panelem], aabb:[[x,y,z],[x,y,z]], priorita, menu:[polozka]}`
- Výběr kliknuté části: paprsek z kamery (`viewer.cameraInfo()`: pos, target, up, fov, aspect) proti AABB; vyhrává nejbližší vstup paprsku, při rozdílu < 3 mm vyšší `priorita`.
- `polozka`: `{text, nastav:{parametr:hodnota…}|null, zakazano:bool, duvod, bod_na_desce?, fokus?}`.
  - `nastav` se sloučí do parametrů stránky (`null` = výchozí, např. `stredni_noha: null` = doprostřed) a provede se obnova (jako změna posuvníku).
  - `zakazano:true` = šedá položka, `duvod` se ukáže pod ní; nelze vybrat.
  - `bod_na_desce:{x:param, z:param, stred_o:[param_d, param_w]}` (jen „Přidat výřez sem“): bod kliknutí se přepočte na desku
    (`ovladani.deska.pocatek` = [x předního okraje, y horní plochy, z levého okraje]) a uloží do `x`/`z` jako vzdálenost od předního/levého okraje, odečte se půl rozměru (`stred_o`), zaokrouhlí na 10 mm.
  - `fokus:param` = položka bez změny, jen posune panel k ovladači a zablikne.

## `tahy` – uchopovací body (drag and drop)
Společně: `{id, label, typ, ikona, bod:[x,y,z], casti:[id], mereni:[{label, param, mul?, add?}], krok}`.
- `typ:"osa"`: `osa:[x,y,z]` (jednotkový směr), `param`, `faktor`, `hodnota`, `min`, `max`, volitelně `zakazano:[[od,do]…]` (v jednotkách parametru) a `odstup_od_prekazky` (mm).
  **Nová hodnota = hodnota_na_začátku + faktor × posun uchopeného bodu podél osy (mm)**; zaokrouhlit na `krok`, omezit na `min..max`.
  `faktor` 2 u šířky a hloubky: model se ve 3D vždy vystředí, hrana se tedy pohne jen o polovinu změny rozměru (ověřeno testem). Zakázaná pasma: hodnota se do pásma nesmí dostat –
  táhne-li se do něj, zastaví se u okraje (u střední nohy tak, že mezera k překážce je `odstup_od_prekazky`; ověřeno v existujícím testu stránky).
- `typ:"rovina"`: tah ve vodorovné rovině y = `bod[1]`; `param_x`+`faktor_x`+`hodnota_x`+`min_x`+`max_x` (posun podél +X, tj. dozadu), `param_z`+`faktor_z`+… (podél +Z, doprava).
  `ikona:"presun"` = přesun výřezu, `ikona:"roh"` = změna velikosti (zadní pravý roh).
- `mereni`: řádky, které se při tažení ukazují VE 3D: hodnota = `add` (výchozí 0) + `mul` (výchozí 1) × hodnota parametru, v mm. Příklady: střední noha „od levé nohy 985 mm“ / „od pravé nohy 985 mm“;
  výřez „od předního okraje“, „od levého okraje“.

## Co musí ovládání ve 3D umět (zadání pro `webapp/js/v3d-ovladani.js`)
1. **Najetí myší na část**: obrys části (průmět AABB) ve 3D + popisek a **zvýraznění ovladačů v panelu** (řádky s `param`); **najetí na ovladač v panelu** zvýrazní části a táhla s tímto `param` ve 3D (obousměrné propojení).
2. **Pravé tlačítko** (na dotyku dlouhý stisk ≥ 450 ms bez pohybu) na části = nabídka s názvem části a položkami; šipky/Enter/Esc; zavře se kliknutím mimo.
3. **Drag and drop táhel** (myš, dotyk, pero; Pointer Events s capture): úchyt ~30 px (na dotyku ≥ 44 px), ikona podle `ikona`, najetí = zvýraznění propojených částí a panelu.
4. **Při tažení vždy ukázat v mm**: štítek u úchytu s názvem, NOVOU hodnotou, **rozdílem proti začátku tažení (+40 mm / −10 mm)**, řádky `mereni`; u tahu se `zakazano` navíc „do překážky N mm“ (≤ 100 mm) a červeně „překážka“, když se zastavil;
   „min“/„max“ na mezi. Panel (posuvník + číslo) se mění živě během tažení. **Esc** vrátí původní hodnotu.
5. Střední noha: dnešní úchyt (id `midHandle`) a jeho chování (zastavení 10 mm před překážkou, popisek) nahradit tímto obecným mechanismem – bez ztráty funkcí a bez rozbití existujících testů stránky.
6. Dotyk/mobil: úchyty se nesmí překrývat s tlačítky Prohlížeče; dlouhý stisk nesmí spustit otáčení modelu; vše uvnitř plátna (pod pruhem tlačítek).
7. Výkon: překreslení z `viewer.onCamera`, bez čtení layoutu v cyklu; popis ovládání se po každé obnově vymění (model se přitom může vycentrovat jinak).

## Implementace (hotovo 2026-10-03, bot8)
**Modul `webapp/js/v3d-ovladani.js`** (`V3DOvladani.create({stage, overlay, getParams, applyPatch, dragState, onLink, focusParam, handleIds, texts})`; hlavička souboru = API).
Nic o stole v něm není. Stránka stolu dřív (`stul-konfigurator-page.js`, od 2026-10-04 smazaná, nahradil ji společný modul voleb `product-configurator.js`) mu dávala jen: `applyPatch` (sloučí změnu do parametrů jako pohyb jezdce a překreslí panel), `rowsFor/paramAt`
(řádky panelu k parametru, obousměrné zvýraznění `v3do-lnk`), `focusParam` (posun panelu + zablikání; na mobilu pod přilepenou 3D plochu) a `dragState`.
- **Najetí / nabídka:** paprsek proti AABB (`priorita`), obrys (průmět kvádru) + popisek + zvýraznění řádků panelu; pravé tlačítko se vyhodnotí po puštění (pohyb > 5 px = posun modelu, nabídka se neotevře);
  dotyk: dlouhý stisk 450 ms **jen na části modelu**, do 8 px pohybu se model neotáčí (touchmove se zadrží – OrbitControls r128 používá touch\*, ne pointer\*).
  Nabídka je `position:fixed` v `body` (nezařezává ji plátno), šipky/Home/End/Tab/Esc, klik mimo zavře.
- **Táhla:** `osa` (nejbližší bod osy k paprsku) a `rovina` (průsečík s rovinou y = `bod[1]`); hodnota = začátek + `faktor` × posun, mřížka `krok` od začátku tažení, meze, zakázaná pasma
  (zastaví se u okraje na bezpečné straně; přeskok na druhou stranu pásma jako dosud), štítek nad úchytem (na dotyku výš): název, nová hodnota, rozdíl proti začátku, řádky `mereni`, „do překážky N mm“ (≤ 100),
  červeně „překážka – zastaveno, mezera N mm“, „minimum/maximum/na mezi“. Esc / `pointercancel` vrátí původní hodnoty. Šipky na zaměřeném úchytu posouvají o `krok` (Shift = 10×).
- **Živý model při tažení (bez `zive`):** stránka během tažení posílá nejvýš jeden dotaz naráz (vždy s nejnovějšími parametry), odpověď nepřepisuje parametry/ovladače; po puštění běžná obnova (server hodnoty případně ořízne).
  Popis ovládání z odpovědí přijatých během tažení se pozdrží až do konce tažení. Takhle se táhnou výřezy (typ `rovina`) a vše, co nemá `zive`.
- **ŽIVÉ tažení vrcholů (tahy se `zive`):** viz sekce níže – model se hýbe plynule přímo v prohlížeči, na server se jde až po puštění.
- **Zpětná kompatibilita:** chybí-li `vodici.ovladani`, stránka dopočítá jediný tah střední nohy ze starého `vodici.stredni_noha` (id úchytu `midHandle`, jinak `v3do_<id>`). Chybí-li modul, stránka funguje jen s jezdci.
- **Test:** `scripts/2026-10-02_stul_testy/test_stul_prohlizec.js` (Chromium; nezávislá kontrola projekce, hover-výběru a bodu na desce přes THREE; mobil přes CDP dotyk).
  Pozn.: v headless Chromiu (swiftshader) běží po první interakci vykreslování ~3 snímky/s – čekání v testech proto jen `polling: 100`, ne přes rAF.

## Živé tažení: hýbání vrcholů přímo v načteném modelu (2026-10-03)
Důvod: při tažení se každý krok počítal na serveru a stahoval se celý GLB (5,6 MB) → 2–3 snímky/s. GLB je slepený po materiálech (uzly `n0..n6`, vrcholy napečené ve světových souřadnicích),
proto popis ovládání nese, kde jsou vrcholy každého dílu, a operace, kterými se díly při tažení hýbou.

**Kontrakt (server, `api/stul_konfigurator._zive_operace`, `api/stul_glb.vodici`):**
- `vodici.ovladani.zive_rozsahy[index dílu]` = `[uzel, od, počet]` (rozsah VRCHOLŮ v atributu POSITION uzlu `n<uzel>`) nebo `null` (deska s otvory – nehýbe se).
- `vodici.ovladani.zive_rozsahy_extra[index dílu jako text]` = seznam DALŠÍCH rozsahů `[[uzel, od, počet], …]` dílu, který je v modelu rozdělený do víc uzlů (od 2026-10-05 horní šuplík boxu: vlastní uzel pod pivotem `p1`, pohyb na klik); `zive_rozsahy` má dál přesně jeden prvek na díl (u boxu rozsah jeho těla). Prohlížeč (`v3d-ovladani.js` 1.1.5) aplikuje operace dílu i na jeho další rozsahy (klíč `i+k`), takže šuplík jede s boxem; starší klient klíč ignoruje (šuplík by za tažením zůstal do puštění). **Od 2026-10-08 i plastový kužel stavitelné patky** (vlastní kus v černém plastu, extra rozsah v uzlu materiálu „cerna“; dílem patky zůstává šroub s maticí – viz `stul_glb.KUZEL_PATKY`).
- `vodici.ovladani.razitka` = `[{dil, uzel, vypln: [uzel, od, počet]}]` (od 2026-10-08, jen když je výchozí model S razítky – WORKFLOW pravidlo 61; Robert: „razítka na generátoru při tažení zůstávají na místě“): na kterém dílu (`dil` = index dílu) razítko sedí, který uzel `n<uzel>` je jeho logo a kde jsou vrcholy výplně drážky v uzlu hliník. Prohlížeč (`v3d-ovladani.js` 1.2.0) při živém tažení hýbe razítka jako tuhá tělesa: `posun` stejně jako díl, `natahni` / `roztahni` podle polohy STŘEDU razítka vůči STŘEDU dílu podél osy (stejné pravidlo jako pro vrcholy dílu; logo se nedeformuje); zrušení tažení (Esc) je vrátí, razítka na dílech, které se nehýbou, stojí; po puštění přijde přesný model s razítky (na novém hashi jsou umístěná znovu). Starší klient pole ignoruje (razítka by za tažením zůstala do puštění). Test: `scripts/2026-10-08_razitka_tazeni/` (emulace pravidla nad skutečným GLB + prohlížeč).
- tah `zive` = seznam operací `{op: "posun"|"natahni"|"roztahni", ix: [indexy dílů], k, strana?}`; `d = k × s × osa`, kde `s = (nová hodnota − hodnota na začátku tažení) / faktor` (mm podél osy tahu).
  `posun`: všechny vrcholy dílu o `d`; `natahni`: jen vrcholy na straně `strana` (u = v·osa, střed = (min+max)/2 dílu; +1 = u > střed, −1 = u < střed) o `d`;
  `roztahni`: u > střed o +`d`, u < střed o −`d`. Operace se aplikují popořadě. Referenční implementace + test: `scripts/2026-10-02_stul_testy/test_stul_zive.py` (`aplikuj`).
  **Vrcholy PŘESNĚ uprostřed dílu** (|u − střed| ≤ 0,05 mm; mesh laminodesky 4933 má vrchol i uprostřed plochy) se při `natahni` pohnou o `d`/2 (leží uprostřed natažené desky) a při `roztahni` zůstanou (bylo: o jejich straně rozhodl zaokrouhlovací šum a deska se při natažení jednoho konce zdeformovala až o d/2; od 2026-10-05, `v3d-ovladani.js` `liveApply`). Profily středové vrcholy nemají, jich se pravidlo netýká. Díky tomu sedí i NÁHLED šířky/hloubky desek (max. odchylka 0,4 mm místo desítek).
- **Co se smí natahovat (Robert 2026-10-03: „roztahuje se děrovaný panel, aniž by se to roztahování týkalo“):** `natahni`/`roztahni` jen PROFILY a LAMINODESKY (`PROTAHOVANE` v generátoru). Příslušenství s fixní velikostí (panely, LED, elektrožlab, boxy, držák, kolečka, spojky) se NIKDY neprotahuje, jen se posouvá (`posun`) s tou stranou, ke které patří; při změně hloubky jde horní rám s LED se zadními stojkami. Test `test_stul_zive.py` to hlídá (rozměry dílů se při náhledu nemění).
- Při živém tažení stránka vypne kóty (Rozměry), protože by ukazovaly původní čísla; vrátí je, až přijde přesný model (`product-configurator.js`: `kotyBehemTazeni` / `kotyZpet`, platí pro všechna místa, kde jsou kóty = Generátor stolu 01–04, mini-shopy i vložený generátor; ověřuje `test_stul_koty_stranka.js` část D). Kóty samotné: `api/stul_koty.py`, popis v `MAPA_3D_A_GENERATORU.md`.
- **Svítidla LED (bot8 2026-10-08):** každé svítidlo je vlastní část `led_<k>` (veřejně `ledlamp<k>`, `priorita` 3) s nabídkou „Odebrat toto svítidlo“ / „Vrátit svítidlo na výchozí místo“ a TAH `led_z<k>` (veřejně `ledpos<k>`; osa Z podél příčného profilu, `faktor` 1, `min`/`max` = sousední svítidla / okraj, `mereni` „od levého / pravého okraje stolu“ a „od levého / pravého svítidla“ jako `add + mul × hodnota`); jeho `zive` je jediná PŘESNÁ operace `posun` svítidla (ostatní díly stojí; globální vycentrování modelu klient nedělá, jako u ramene LED). Část `led` (celé osvětlení) má navíc nabídku „Přidat svítidlo LED“. Viz `docs/KONTRAKT_KONFIGURATOR_UI.md`, sekce „Svítidla LED ručně“.
- Přesně: `stredni_noha`, `led_rameno`, `suplik_posun`, `led_z<k>`. NÁHLED (po puštění přijde přesný model, může být malý skok): `sirka`, `hloubka`, `vyska`. Výřezy (`rovina`) `zive` nemají.
- **Panely, stojky, elektrožlab, vestavěný rám (bot8 2026-10-05):** tahy `panely_posun` (veřejně `panelpos`: panely s profily a elektrožlabem po zadních stojkách), `panely_z` (veřejně `panelside`: panely do stran mezi nohama, jen má-li panel mezeru; krok 1 mm, `mereni` = mezery od VŠECH noh jako lineární funkce hodnoty `add + mul × hodnota`; `zive` = `posun` panelů a elektrožlabu s k = 1 ze sondy s malými kroky 10/5/2/1 mm), `stojky_vyska` (`posth`: výška zadních stojek, rameno LED jede se stojkou), `elzlab_y` / `elzlab_z` (`socketup` / `socketside`) mají `zive` ze SONDY (`_zive_sondou`: znovu poskládá stůl o ±100/±30 mm a každý díl zařadí podle toho, co se s ním opravdu stalo; když se sada dílů nebo opora elektrožlabu při kroku změní, sonda krok přeskočí, a když nepůjde žádný, `zive` chybí a model se obnoví až po puštění). Tah `stredni_noha` ve stole se střední NOHOU nese i `op_posun(panel + elektrožlab, k = 0,5)` (panel se v úseku mezi stojkami středí, hýbe se napůl); spojky profilů panelu u krajních noh stojí. Ve vestavěném rámu patří tah `mid` k části `ram` (veřejně `frame`: příčky + svislé profily ramu + jejich spojky se posouvají s úchytem; části desek se natahují, viz níže).
- **Desky dělené u střední opory (bot8 2026-10-05, formáty tabulí):** pracovní deska i police jsou u střední nohy / rámu dvě desky (`deska_id` `…_0` levá, `…_1` pravá). Tah `stredni_noha` (noha i rám) proto nese `natahni` levých desek pravým koncem (`strana` +1) a pravých levým (`strana` −1) – seam se hýbe s opěrou, delší část se prodlužuje, druhá zkracuje; u rámu se hýbou i obě hrany mezery spodní police. Jen desky z JEDNOHO kusu (kusy kolem výřezu v pracovní desce nemají vlastní vrcholy v GLB – ty se obnoví ze serveru po puštění). 3D části: `deska` = obálka obou částí pracovní desky, `police_<n>` = obálka obou částí police patra n (tah `police_h<n>` také jedna část na patro). Nabídky: „Přidat panel“ / „Odebrat panel (i elektrožlab)“ / „Odebrat všechny panely“ / „Panely vrátit do spodní polohy“; u elektrožlabu „vrátit na výchozí místo“; u střední nohy „Střední nohy nahradit vestavěným rámem“, u rámu „Střední nohy místo vestavěného rámu“.

**Prohlížeč (`v3d-ovladani.js` 1.1.0):** `V3D.mount(stage, {plugins: [ov.plugin]})` – viewer3d volá plugin po každém `setModel` (ctx.model = načtená scéna), po dalším `setModel` se kopie zahodí.
Na začátku tažení tahu se `zive` + `zive_rozsahy` se zálohují POSITION dotčených dílů (Float32Array kopie rozsahů), při každém pohybu se rozsahy vrátí z kopie a aplikují se operace s aktuálním `s`
(O(počet vrcholů dotčených dílů)), `attribute.needsUpdate`, `requestRender`; `frustumCulled = false` po dobu tažení, obalka se přepočítá jednou po puštění. Esc vrátí vrcholy z kopie.
Stránka (`state.liveDrag`) během takového tažení NEVOLÁ server (žádné `refresh()`, pozdní odpověď dřívějšího dotazu se zahodí – nesmí vyměnit model pod rukama); jezdec a číslo v panelu se mění živě;
po puštění běžná obnova (`refresh()`) přinese přesný model. Chybí-li `zive` nebo `zive_rozsahy` (starší server), nebo se uzel v modelu nenajde, chová se tažení jako dosud (obnova ze serveru).
Zkoušky: `ov.liveBox(index dílu)` čte obálku a střed vrcholů dílu přímo z atributu v načteném modelu; `ov.debug().drag.live`.

## Vzpěry ramen LED (2026-10-03)
Část `vzpery` (jen když jsou zapnuté): `param ["vzpery","vzpera_delka"]`, nabídka „Odebrat vzpěry ramen LED“, „Vzpěry delší (+50 mm)“, „Vzpěry kratší (−50 mm)“ (zakázané s důvodem na skutečných mezích délky 100 mm / `vzpera_meze.max` – horní mez dává rameno LED a okolí, ne pevných 700 mm; „+50“ se zastaví na mezi); v nabídce části `led` „Přidat vzpěry ramen LED“, když vypnuté. Živé tažení: díly vzpěr (profil + 2 spojky) se NIKDY nenatahují – při změně hloubky jdou jako pevná skupina se zadními stojkami (stejně jako horní rám), při šířce a výšce s tou stranou/výškou, ke které patří; střední vzpěra (u střední stojky) je ve skupině střední nohy. Test `test_stul_zive.py` to hlídá.

## Zapojeni do VEREJNE Volby komponent (mini-shop) – kontrakt pro bot16 (bot8 2026-10-03)
Stejny obecny modul `webapp/js/v3d-ovladani.js` (v1.1.0), zadny kod pro stul v nem neni. Stranka (adapter) dodava jen parametry a obnovu modelu; popis ovladani dodava server.
**Data:** `POST /api/shop/configurator/resolve` → `vodici.ovladani` (public tvar z `api/stul_ovladani_verejne.py`): `casti[]`, `tahy[]`, `deska`, `zive_rozsahy`, texty uz v jazyce pozadavku (cs/en/sk), `nastav`/`bod_na_desce`/`param`
jsou **verejne nazvy slotu** (`w`, `d`, `h`, `cut1x`, `boxpos`, `arm`, `braces`, `bracelen`…; stredni noha je `mid` v %, tah `stredni_noha` se NEPREDAVA – zustava `vodici.stredni_noha`).
**Pouziti (adapter = tvoje mapovani slot → hodnota):**
```js
var ov = V3DOvladani.create({
  stage: stageEl, overlay: overlayEl,              // overlay = absolutne pozicovany prvek nad platnem, pointer-events:none
  getParams: function () { return selection; },    // {slot: hodnota} (verejny vyber)
  applyPatch: function (patch, o) { /* slouci patch do vyberu, prekresli slidery, naplanuje resolve; o.live = behem tazeni, o.cancel = Esc vratil puvodni */ },
  dragState: function (on, tah, o) { /* on=true zacatek tazeni; o.live=true -> NEvolat resolve do pusteni (vrcholy se hybou v prohlizeci); po pusteni (on=false) resolve s koncovymi hodnotami */ },
  onLink: function (params) { /* zvyraznit radky slotu v panelu */ }, focusParam: function (slot) { /* posunout panel k slideru a zablikat */ }
});
V3D.mount(stageEl, { /* … */ plugins: [ov.plugin] });   // plugin potrebny pro ZIVE tazeni (dostane scenu nacteneho modelu)
ov.setViewer(viewer);                                // po mountu: viewer.cameraInfo()/onCamera()
// po KAZDE odpovedi resolve (a po setModel): ov.setDescription(resp.vodici && resp.vodici.ovladani || null);
// mys na slideru v panelu: ov.hoverParam(slot) / ov.hoverParam(null)
```
**Pravidla adapteru:** (1) `applyPatch` hodnoty pred ulozenim ORIZNE na `options[slot].min/max` z odpovedi (mimo rozsah se nikdy neposila); (2) `dragState(true,…,{live:true})` → po dobu tazeni zadny resolve/GLB (jinak se model prepise a vrcholy poskoci); `live:false` (vyrezy – deska je jeden povrch) → obnova ze serveru nejvys 1 dotaz naraz;
(3) slot s nesplnenym `depends_on` nema ovladani ve 3D ani v panelu; (4) tazeni musi mit mm-stitek (modul ho kresli sam); (5) mobil: uchyty 44 px, dlouhy stisk = nabidka (modul resi sam); (6) po tazeni `resolve` vrati presny model, `setDescription` obnovi uchyty.
**Testovaci data:** `resolve {selection:{w:2000, mid:50, cut1:true}}` (stredni noha + vyrez), `{w:1840, drawers:true, boxpos:-120}` (meze suplíku: `options.boxpos`), `{braces:true, bracelen:300}` (vzperam se vodici nemeni). Referencni adapter: `webapp/js/stul-konfigurator-page.js` (`initOvladani`, `applyPatch`, `dragState`, `onLink`, `focusParam`, `rowsFor/paramAt`).

## Police BEZ DESKY (bot8 2026-10-07)
Je-li parametr `police_deska` vypnutý (slot `shelfboard`), část `shelf<N>` tvoří rám police (obě boční příčky) místo desky; `param` je `["shelf","shelfboard"]`, nabídka má navíc „Odebrat desku police“ / „Vrátit desku police“ (u více polic „…desky všech polic“; mění všechny spodní police). Části `supports<N>` (podpěry pod deskou) bez desky nevznikají. Tahy `sh<K>` a jejich `zive` operace se chovají jako s deskou (výška se měří k rovině horní plochy desky = horní hrana rámu + 18 mm).

## Části `podpery_<N>` (bot8 2026-10-03)
Při hloubce > 900 mm má popis ovládání u každé spodní police část `podpery_<N>` (veřejně `supports<N>`): „Podpěry spodní police“, `param` `["police","hloubka","sirka"]`, nabídka jen s informativními položkami (`fokus` na šířku / hloubku) – počet podpěr
určuje šířka stolu a střední noha, nejdou přidávat ručně. Živé tažení: podpěry se při změně hloubky natahují s deskami a příčkami (`roztahni`), při změně šířky zůstávají (náhled; přesné rozmístění přijde po puštění).

## Část `suplik` (veřejně `drawers`): počet šuplíků (bot8 2026-10-05)
`param` `["suplik","suplik_pocet","suplik_posun","suplik_vlevo"]` (veřejně `drawers, drawercount, boxpos, drawleft`); nabídka pravým tlačítkem: „Odebrat šuplíky“, „Box s 1 šuplíkem / s 2 šuplíky / s 3 šuplíky“ (jen počty různé od aktuálního; `nastav: {suplik_pocet: N}`),
„Šuplíky vrátit na výchozí místo“, „Přehodit šuplíky na levou/pravou stranu“. Texty menu se v EN/SK překládají tabulkou v `api/stul_ovladani_verejne.py` – nová položka bez překladu by v daném jazyce **vynechala celé 3D ovládání** (log „ovladani ve 3D vynechano“). Tah `suplik_posun` (živý, přesný) hýbe boxem libovolného počtu šuplíků (`posun` dílů `product_4930 / 4956 / 4957` a jejich příček).

## Stůl SSE (vnitřní klíč systému 41): ovládání ve 3D (bot8 2026-10-05)
`stul_sse.ovladani(r)` (volá ho `ovladani_3d` pro systém 41; stejná struktura `{jednotky, deska, casti, tahy}`): `casti` = `deska` (rozměry v panelu), `noha_0…2` („Levá / Střední / Pravá noha SSE“: výšku a hloubku nastavit v panelu, přidat spodní polici, střední nohu vrátit doprostřed), `police_1` (odebrat), `suplik` (odebrat, počet 1 / 2 / 3, vrátit na výchozí místo, přehodit stranu); `tahy` = `vyska` (horní konec jeklu levé nohy, osa y), `sirka` (pravá hrana desky, faktor 2), `hloubka` (přední hrana, faktor 2) a `suplik_posun` (osa ±z podle strany, meze z `suplik_meze`, ŽIVÉ: `zive: [{op: posun, ix: box + příčky + spojky, k: 1}]`). Rozměrové tahy se po puštění obnoví ze serveru (živý náhled jen u šuplíků). Veřejně `deck`, `leg1…3`, `shelf1`, `drawers`, `h`, `w`, `d`, `boxpos`; nové texty mají překlady v `stul_ovladani_verejne._PREKLADY` (bez překladu by se ovládání v en / sk vynechalo).
