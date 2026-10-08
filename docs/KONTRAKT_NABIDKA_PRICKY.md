# Kontrakt: příčky do Multiboxů a ocelových šuplíků v online nabídce – sety pro celou polici / výsuv / sloupec šuplíků (bot8, 2026-10-07)

Robert 2026-10-07: *„multiboxy mají možnost dělících příček, navrhni zjednodušené tvary, a v online nabídce pro multiboxy nějaký systém pro přiobjednání příček jako příslušenství,
v nějakých pár variantách i vizuálně přímo v multiboxech, ať jsou vidět ceny aby si uživatel vybral“*; *„na konci multiboxů je malý výkroj, že za něj může viset šikmo zahaknuto za podélník nad ním“*;
*„toto neexistuje“* (k podélným příčkám a mřížkám → NEEXISTUJÍ, jen příčné); *„délky multiboxů a max možný počet slotů/příček: 300 (= náš cca 296 mm) > 4 ks; 400 (= náš cca 396 mm) > 6 ks;
500 (zatím nepoužíváme ale možná budeme) > 8 ks“*; *„jde o to nabídnout vždy nějaké varianty SETŮ, vždy pro celou polici / šuplík s multiboxy“*.

Dále Robert: *„chci možnost v jedné polici kombinovat různé počty příček“* → *„nemyslím každý zvlášť, ale chci hotové varianty mix, v jedné polici např. 4 možnosti různých kombinací“*, *„je zdlouhavé klikat každý box zvlášť“*
(proto žádný výběr po jednotlivých boxech v UI; mixy jsou hotové varianty) a *„potom i příčky v šuplíku, v šuplíku jsou sloty po 100 mm, směr jen zepředu dozadu“* (šuplíky = v5, oddíl 10).

Platí jen pro **Vandr nabídky** (model s `scenes[0].extras.v3d`) obsahující Multiboxy. Bez Multiboxu v modelu se nic nezobrazí a nic se nemění.

## 1) Tvar Multiboxu, příčka, sloty a sety

Multibox (zjednodušený Vandr model, změřeno): vnější délka × šířka × výška = **395,5 | 288 | (500) × 186 | 91 × 81 mm** (kusy široké 92 mm = typ 91). Stěny a dno 2 mm.
Na jednom konci (místní X = 0 … 28,4) je lem a **spodek konce je vykrojený do výšky ~33 mm** (za výkroj se box dá zavěsit šikmo za podélník nad ním). Příčky se vkládají jen do „studny“ boxu
za lemem: X 28,4 … L−2, na dno (Y 2) do výšky 77 mm (okraj boxu je 79–81 mm). Místní systém boxu: X = délka od konce s výkrojem, Y = výška od spodku boxu, Z = šířka.

**Jen PŘÍČNÉ příčky** (kolmé na délku boxu). Příčka = tenká deska 2 mm × 75 mm (jednoduchý kvádr). Dva díly (= dvě katalogové karty, SKU stabilní):

| klíč | SKU | název | rozměr (tloušťka × výška × délka) | orient. cena |
|---|---|---|---|---|
| `p186` | `MBX-PRICKA-PRICNA-186` | Příčka do Multiboxu šířky 186 mm | 2 × 75 × 181 | 39 Kč |
| `p91` | `MBX-PRICKA-PRICNA-91` | Příčka do Multiboxu šířky 91 mm | 2 × 75 × 86 | 29 Kč |

**Sloty** (= největší možný počet příček v boxu): délka 288 → **4**, 395,5 → **6**, 500 → **8**. Sloty jsou rovnoměrně po studni (rozteč ~52 mm); n příček se rozloží do slotů co nejrovnoměrněji.

**Sety = hotové MIXY** (stejné pro všechny skupiny; platí NA VŠECHNY multiboxy skupiny naráz; v jedné polici jsou v různých boxech různé počty příček): `bez` Bez příček · `mix1` střídavě husté a řídké dělení · `mix2` střídavě husté
a středně husté · `mix3` husté dělení, každý třetí box řidčeji · `mix4` postupně od řídkého dělení k hustému · `pln` Plný set (všechny sloty ve všech boxech). Mix je VZOR podle pořadí boxu ve skupině (`i` z `N`) a úrovně hustoty
(úroveň 1 = 1 příčka, 2 = polovina slotů 2 / 3 / 4, 3 = všechny sloty 4 / 6 / 8 podle délky boxu 288 / 395 / 500): mix1 `3,1,3,1…`, mix2 `3,2,3,2…`, mix3 `3,3,1,3,3,1…`, mix4 `1 + round(2·i/(N−1))`, pln `3…`.
Příklad police 8 × 395 mm: mix1 `6,1,6,1,6,1,6,1`, mix2 `6,3,6,3,…`, mix3 `6,6,1,6,6,1,6,6`, mix4 `1,1,3,3,3,3,6,6`, pln `6×8`. Set, který by ve skupině dal STEJNÉ počty jako jiný (u 2 boxů je mix3 = pln, u 1 boxu jsou všechny = pln),
se nenabízí dvakrát (přednost bez, pln, mixy v pořadí). Cena setu = součet příček přes boxy skupiny. **Geometrii příček (`desky`) počítá server** a posílá ji v JSON v místním systému boxu; prohlížeč ji jen přepočte do světa.

**Skupina** = jedna police nebo jeden šuplík (výsuv) s multiboxy = jedna instance komponenty ve Vandr modelu (typicky řada 7–8 boxů vedle sebe); samostatně stojící multiboxy tvoří jednu skupinu na zdroj.
Druh skupiny: `police` | `vysuv` | `box` (samostatné). Číslo skupiny `s` (1…), v nabídce „Police s multiboxy 1 · levá strana“, „Výsuv s multiboxy 2 · levá strana“.

## 2) Spec v3d: `mbx` (zákaznický GLB, `scenes[0].extras.v3d.mbx`)

```
"mbx": [ {"id": "b01", "min": [x,y,z], "max": [x,y,z], "e": 1, "p": "p22", "n": 1, "s": 1, "sk": 1, "g": "left"} , ... ]
```
`min`/`max` = světový AABB boxu v ZAVŘENÉM stavu (glTF mm, Y nahoru). Delší vodorovný rozměr = délka boxu (osa `a`: 0 = X, 2 = Z).
`e = +1`: konec s výkrojem je na MIN straně délky (místní X roste se světovou souřadnicí osy `a`); `e = -1`: na MAX straně (místní X klesá).
`p` = id pivotu (box jede s výsuvem; `null` = statický), `n` = pořadí, `s` = číslo skupiny (police / šuplík), `sk` = druh skupiny jako číslo (1 police, 2 výsuv, 3 samostatné; jména komponent do GLB nesmí),
`g` = strana (`left|right|bulkhead`, jen u společné nabídky). Žádná jména komponent.
Převod místního bodu (x,y,z) do světa: `a = osa_delky; b = 2 - a;`
`svět[a] = e > 0 ? min[a] + x : max[a] - x;  svět[b] = min[b] + z;  svět[1] = min[1] + y`.
Objekty pod pivotem `p` se řídí jeho pohybem: viewer drží pivot jako uzel modelu (jméno `p22`); plugin ho najde a přidá objekty jako potomky.
Viewer (`validateSpec`) neznámé klíče ignoruje, takže `mbx` čte jen plugin z `gltf.scenes[0].userData.v3d.mbx`.

## 3) Veřejný JSON nabídky: `offer.pricky` (`GET /api/public/offers/<token>`)

`null` (nebo klíč chybí) = nabídka příčky nenabízí. Jinak (přesný tvar viz test `test_pricky.py`, vzorky generuje `api/nabidka_pricky.payload`):
```
{ "enabled": true, "nahled_admin": false,
  "sety": [ {"id":"bez","popis":"Bez příček","pozn":""}, {"id":"mix1","popis":"Mix 1","pozn":"střídavě husté a řídké dělení"}, … {"id":"pln","popis":"Plný set","pozn":"všechny sloty ve všech boxech"} ],
  "skupiny": [ {"id":"s1","k":"police","n":1,"g":"left"|null,"popis":"Police s multiboxy 1 · levá strana","boxu":8,"boxy":["b01",…],
                "sety": {"bez":{…}, "mix1":{"priccek":28,"cena":1012,"dily":{"p186":…,"p91":…},"po_boxech":[6,1,6,1,6,1,6,1]}, …, "pln":{…}} }, … ],   // jen sety nabízené skupině (bez duplicit)
  "boxy": [ {"id":"b01","k":"395x186","n":1,"g":"left"|null,"s":"s1","sk":"police"}, … ],       // id odpovídá spec.mbx; k = typ boxu; s = id skupiny
  "typy": { "395x186": { "popis":"Multibox 395 × 186 mm","max":6,"dil":"p186",
                         "pocty": [ {"n":0,"desky":[]}, {"n":1,"desky":[{"s":[x,y,z],"r":[dx,dy,dz],"d":"p186"}]}, … {"n":6,"desky":[…]} ] }, … },   // geometrie příček pro LIBOVOLNÝ počet 0..max
  "dily": [ {"klic":"p186","nazev":"…","cena":39,"product_id":123}, … ],
  "geom": {"vyska_boxu": 81, "studna_od": 28.4} }
```
Ceny jsou v Kč **bez DPH**: `skupiny[].sety[].cena` za CELOU skupinu, `dily[].cena` za 1 kus. `po_boxech` = počet příček v každém boxu skupiny v pořadí `skupiny[].boxy` (= „Multibox 1…N“ v nabídce).
`nahled_admin: true` = admin (odkaz „Zobrazit online“) vidí aspoň jednu skupinu, kterou zákazník ještě nevidí (karta některého jejího dílu není aktivní; taková skupina má `skupiny[].skryto: true`). Od v5 se skupiny nabízejí NEZÁVISLE (oddíl 10): `payload(spec, ceny, nahled_admin)`, `dily` jen použité, `typy[k]` nese `druh/os/L/W/H/lem`. `typy[k].pocty[n].desky`: `s` střed, `r` rozměr (X,Y,Z místního systému), `d` klíč dílu.

## 4) Výběr zákazníka a přenos na server

Zákazník vybírá hotový set pro polici / šuplík; na server (i do `localStorage`) jde výběr **PO BOXECH** = `{id boxu: počet příček}` (set je jen zkratka, server mixy nezná, zná jen počty a platí je přesně).
Kanonický zápis (query i tělo): `"b01:6,b02:1,b05:4"` = jen boxy s n > 0, seřazeno podle čísla boxu. Server (`nabidka_pricky.parse_vyber` / `over_vyber`): box existuje, 0 ≤ n ≤ počet slotů typu (288 → 4, 395 → 6, 500 → 8), jinak 400.
- QR platba: `GET /api/public/offers/<token>/payment-qr?qty=…&deposit_pct=…&pr=b01:6,b02:1` – částka se počítá STEJNĚ jako objednávka (`_offer_gross_total` + příčky); neplatný `pr` = 400.
- Přijetí: `POST /api/public/offers/<token>/accept` s polem `pricky` (týž řetězec) – server výběr znovu ověří proti boxům z GLB a ceny vezme z karet; neplatný = 400 `{"error": "Výběr příček není platný, obnovte stránku."}`.
- Bez DDL: výběr se na serveru NEukládá do `scene_offer_order_prefs`; stránka ho drží v paměti + `localStorage` (`pricky:<token>` = `{"v":2,"boxy":{"b01":6,…}}`, verze 1 ignorovat).
- Součet: příčky (za 1 kus sestavy, bez DPH) × `qty` se přičtou k ceně zboží (`items_net`) PŘED montáží a dopravou → montáž % se z nich počítá (jako u ručních položek). Objednávka dostane
  řádky `shop_order_items` (jeden na typ dílu: název karty, qty = kusy × qty sestavy, jednotková cena) + poznámku s rozpisem po skupinách a **počty po boxech v pořadí Multibox 1…N** („Police s multiboxy 1 · levá strana - Mix 2
  (8 z 8 boxů, 36 příček, 1 284 Kč; příček po boxech v pořadí Multibox 1…8: 6, 3, 6, 3, 6, 3, 6, 3)“), aby výroba věděla, který box má kolik příček.

## 5) Plugin prohlížeče: `webapp/js/v3d/pricky-multibox.js` (`window.V3DPricky`, v5.0.0)

Viewer má `opts.plugins: [function (ctx) {...; return dispose}]` (`viewer3d.js` ~ř. 946–980; volá se po každém postavení modelu, předchozí plugin se nejdřív ukončí) – **viewer3d.js se kvůli příčkám nemění**.
```
var pr = V3DPricky.create({ payload: offer.pricky, onChange: function (vyber, souhrn) {} });
V3D.mount(container, { ..., plugins: [pr.plugin] });
pr.api.skupiny()                // [{id, k, n, g, popis, boxu, ready, pocet_ready, set, priccek, cena}]  ready = aspoň jeden box skupiny je v načteném modelu; set = rozpoznaný set (bez / id setu / vlastni)
pr.api.get()                    // {id boxu: počet příček} (jen n > 0, seřazeno podle čísla boxu, kopie)
pr.api.setGroup(gid, setId)     // nastaví počty ve VŠECH boxech skupiny z payload.skupiny[].sety[setId].po_boxech; true = platná dvojice; neznámá skupina / set (i set, který skupina nenabízí) = false a nic se nezmění
pr.api.setAll(setId)            // totéž pro všechny skupiny, které set nabízejí; vrací počet skupin, kterým se set nastavil
pr.api.setBox(boxId, n)         // počet příček v jednom boxu (0..max typu); pro budoucí použití, v UI zákazník boxy po jednom neklikne
pr.api.setMany({boxId: n})      // nahradí CELÝ výběr (obnova z localStorage; funguje i před mountem); neplatné dvojice přeskočí
pr.api.clear()                  // zruší všechny příčky
pr.api.groupInfo(gid)           // {set, priccek, cena, boxu_s_pricky} nebo null
pr.api.highlightGroup(gid|null) // oranžový obrys VŠECH boxů skupiny (hover karty), jako potomek pivotu následuje pohyb; pr.api.highlightBox(boxId|null) totéž pro jeden box
pr.api.souhrn()                 // {boxu, kusy, cena_net, radky:[{klic,nazev,qty,unit_price,total}], skupiny:[{id,set,cena,priccek,boxu_s_pricky}]} – jen pro zobrazení; server počítá znovu z karet
pr.api.motionIds(gid|undefined) // v4.1: ID pohybů vieweru (spec.motions[].id), které otevřou (zvednou) boxy skupiny (bez gid všech skupin); unikátní, v pořadí boxů; box → pohyb, jehož steps[].p je pivot boxu (mbx[].p), přednost má k:'box';
                                //       box bez pivotu / bez pohybu / mimo model se přeskočí; nikdy nevyhodí výjimku (neplatné gid, po dispose, bez modelu = [])
pr.api.setOf(gid) / pr.api.boxes() / pr.api.ready()                 // pomocné
```
Box je „ready“, když je v `payload.boxy`, má platné `mbx` (min/max/e, pivot existuje nebo je `null`) a jeho rozměr odpovídá typu z payloadu (délka ±12, šířka ±5, výška ±3 mm); jinak se tiše přeskočí a jeho cena zůstane v souhrnu.
Příčky jednoho boxu = jeden spojený mesh + jedny hrany (světlá modrá `#dbe6ff`, tmavé hrany) jako potomek pivotu boxu (jede s výsuvem i se zvednutím boxu), statický box = potomek modelu; výběr přežije `setModel`;
drátěný režim (`root.v3d-mode-wire`, kontrola přes `ctx.onFrame`) kreslí jen hrany; `dispose` uklidí geometrie i materiály; bez WebGL / `mbx` / platného payloadu je plugin no-op a nikdy nevyhodí výjimku do smyčky vieweru.
Omezení: obrys skupiny prosvítá přes geometrii; příčky nejsou klikací (klik jde na box pod nimi); bez `ctx.onFrame` (starší viewer) se drátěný vzhled nepřepíná.

## 6) Stránka `nabidka-online.html` (sekce „Příčky do multiboxů“, od v5 podle druhů skupin i „Příčky do šuplíků“ / „Příčky do multiboxů a šuplíků“)

Jen když `offer.pricky && offer.pricky.enabled`. Sekce u 3D okna (stejný snímek, vedle modelu; na mobilu pod ním, sbalitelná):
- krátké vysvětlení („Přiobjednejte dělicí příčky do multiboxů – vyberte set pro celou polici nebo šuplík, ve 3D se ukáže hned. Ceny bez DPH.“);
- **karta za každou skupinu** (police / šuplík): titulek `popis` + „8 boxů“ a **čipy setů** (jen sety nabízené skupině, v pořadí `payload.sety`): miniatura = řada malých boxů podle `po_boxech` (každý s n čarami příček), název (Bez příček / Mix 1–4 / Plný set),
  poznámka, **cena za celou skupinu** (`+1 012 Kč`, „Bez příček“ = 0 Kč), počet příček, `aria-pressed`; klik = `setGroup` → ve 3D se ukáže hned, v každém boxu jiný počet; hover nad kartou = `highlightGroup`;
- **v4.1 (Robert po zkoušce živé nabídky, přes bot10: „Všechny police a šuplíky · 3 skupiny, multibox příčky tam nechci“; „jen postupně po policích ať je vidět do kterých šuplíků / polic to je myšleno a zároveň se musí všechny multiboxy vysunout aby to bylo rovnou vidět ve 3D“):**
  řádek „Všechny police a šuplíky“ (`setAll`) je pryč, set se vybírá jen po jednotlivých policích / šuplících; **zvýraznění skupiny ve 3D** (`highlightGroup`, oranžový obrys) při najetí myší, dotyku (po puštění ještě ~3 s – na telefonu není hover)
  a při zaostření klávesnicí, po kliknutí na set zůstane skupina zvýrazněná 3 s; **po výběru setu jiného než „Bez příček“ se ve 3D vysunou VŠECHNY boxy té skupiny**: `viewer.play(id, 1)` pro ID z `api.motionIds(gid)` (viewer sám otevře rodiče – výsuv pod boxem –
  a zavře, co blokuje), po jednom s odstupem 150 ms; jen na klik zákazníka (ne při obnově z `localStorage`), zavírání se nedělá; bez prohlížeče / `motionIds` / chyby se nic nestane;
- patička „Příčky celkem: N ks · X Kč bez DPH“, poznámka, že se objednají spolu s nabídkou; u `nahled_admin` pruh „Náhled pro zaměstnance – karty příček ještě nejsou aktivní“;
- cena: do součtu (`effectiveNetTotal`) se příčky × qty přičtou před montáž; do cenové tabulky přibudou řádky (podle dílů); QR (`&pr=`) a přijetí (`pricky`) viz oddíl 4; výběr v `localStorage`; po přijetí je výběr jen ke čtení; tisk: bez panelu, řádky v tabulce zůstanou.
Žádný výběr po jednotlivých boxech (Robert: „je zdlouhavé klikat každý box zvlášť“).

## 7) Soubory

| soubor | co |
|---|---|
| `api/nabidka_pricky.py` | čistá logika (typ boxu, sloty, sety, geometrie, ceny, výběr, payload) – jedno místo pravdy |
| `api/scene_offers.py` | `_pricky_*`: blok `pricky` ve veřejném JSON, QR `?pr=`, přijetí `pricky`, `_offer_gross_total` (`prefs.pricky_net`), poznámka objednávky a e-mailu |
| `api/orders.py` | `create_order_from_scene_offer(…, extra_items=…)` – řádky příček do `shop_order_items` |
| `api/v3d_glb.py`, `api/v3d_merge.py` | validace a slučování `mbx` (volitelné `s`, `sk` 1..4, `g`, `n`; `final_check` zná klíče `mbx`, `e`, `s`, `sk` a id `b<N>`) |
| `scripts/v3d/vandr_offer_build.py` | Blender build: detekce multiboxů (`Multibox_Arc`) a podnosů ocelových šuplíků (`Suplikocel…` / `2suplikyocel…`, část `Default`), skupin (instance komponenty), konce s výkrojem / čela (`e`) a pivotu → `V3D["mbx"]` |
| `webapp/js/v3d/pricky-multibox.js`, `webapp/nabidka-online.html` | plugin a stránka |
| `webapp/katalog/product_<id>.glb` + 2 karty `MBX-PRICKA-PRICNA-186|91` | `scripts/2026-10-07_multibox_pricky/zaloz_karty.py` (neaktivní, bez kategorie, orientační ceny 39 / 29 Kč) |

## 8) Nasazení, pasti, otevřené body

- **Pořadí:** `api/*.py` se nasadí plánovaně (0:00 / 12:30) nebo `scripts/restart_konfigurator.sh --reload` na Robertovo slovo; statika (plugin, stránka) je živá hned a bez `offer.pricky` nic nedělá. **`scripts/v3d/vandr_offer_build.py` s `mbx` smí do repa AŽ PO nasazení API
  s novým `v3d_glb.py`** – starý běžící proces zná jen spec bez `mbx` a odmítl by ho (nabídka by vznikla jako statický model bez pohybů, `v3d:false`).
- **Gating (pravidlo 54):** veřejnost vidí SKUPINU, jen když mají VŠECHNY její díly kartu s cenou a aktivní kartu (v5: po skupinách, viz oddíl 10; multiboxové skupiny potřebují `p186` / `p91` podle typů boxů, šuplíkové díl(y) `ps…`); admin (odkaz „Zobrazit online“) vidí i skupiny s dosud neaktivními kartami (štítek „zákazník zatím nevidí“, pruh „Náhled pro zaměstnance“). Karty zakládá `zaloz_karty.py` neaktivní (7 karet); aktivuje Robert.
- Jen nabídky z **Vandr** modelů (i společných z více karet) postavených NOVÝM buildem mají `mbx`; starší nabídky a nabídky z nativní scény se nemění (`pricky: null`). Nabídky z nativní scény (karty Multibox 3958 / 3959) příčky zatím nenabízejí.
- Výběr se na serveru **neukládá** (bez DDL): stránka ho drží v paměti a v `localStorage` (`pricky:<token>`), na server jde v QR a při přijetí; admin ho vidí v objednávce (řádky + poznámka s rozpisem po policích / šuplících).
- Montáž v % se počítá i z příček (jako z ručních položek). Příčky se násobí počtem kusů sestavy.
- Typ boxu 500 mm (8 příček) zatím neexistuje ve Vandr modelech; délka 500,0 mm je předpoklad (`TRIDY_DELKY` v `api/nabidka_pricky.py`), upravit až bude skutečný model.
- Otevřené: texty sekce a názvy karet ke kontrole (bot7), překlady do dalších jazyků nejsou (nabídky jsou česky); nabídky z nativní scény s multiboxy; individuální výběr po boxech Robert nechce.

## 9) Testy

`scripts/2026-10-07_multibox_pricky/run_all.sh [--rychle] [--mutace] [--kandidat <api>]` (README v téže složce): čistá logika, validace spec, slučování, Blender build (4921 = police + 2 šuplíky, 4917 = 4 skupiny vč. otočených boxů), backend nad dočasnými tabulkami (veřejný JSON, QR, přijetí, objednávka),
plugin a stránka v Chromiu, mutační kontroly (47 + 25 + stránka).
## 10) v5 – příčky do ocelových šuplíků (Robert 2026-10-07: „potom i příčky v šuplíku, v šuplíku jsou sloty po 100 mm, směr jen zepředu dozadu“; „jen typy šuplíku s modrým čelem ocelové“)

Přibývá druhý druh „boxu“: **podnos ocelového šuplíku** (komponenty `Suplikocel…` / `2suplikyocel…` ve Vandr modelech; čelo je modré / `tyrkys` a nemění se). Platí vše z oddílů 1–9 (hotové MIXY pro celou skupinu, výběr po boxech `{id: n}`, QR `?pr=`, přijetí, bez DDL).

- **Skupina = instance komponenty šuplíků** (sloupec 1–8 podnosů nad sebou, někdy dva sloupce 443 + 695 vedle sebe; `sk = 4`, popis „Šuplíky N“). Pořadí podnosů: shora dolů, pak podle polohy. Sety jsou stejné MIXY (úroveň 1 = 1 příčka, 2 = každý druhý slot, 3 = všechny sloty; počet slotů 4 / 6 / 9).
- **Typy** (rozměry AABB zavřeného stavu změřeny na všech Vandr modelech): klíč `S<šířka>x<hloubka>x<výška>`, např. `S950x384x101`. Šířky 443 / 695 / 950, hloubky (zepředu dozadu) 332 / 384, výšky 101 / 137 / 210; díl (karta) podle hloubky × výšky: `ps332v137`, `ps332v210`, `ps384v101`, `ps384v137`, `ps384v210` (SKU `SUP-PRICKA-PRICNA-<hloubka>x<výška>`, orientační ceny 59 / 79 / 59 / 69 / 89 Kč bez DPH, neaktivní, bez kategorie). Jiná kombinace (např. 332 × 101) se nenabízí.
- **Sloty a příčky:** sloty po 100 mm napříč šířkou, souměrně kolem středu (`max = floor((šířka − 2 · bok) / 100)` → 4 / 6 / 9); příčka je 2 mm silná, vysoká výška podnosu − 8 mm (93 / 129 / 202), dlouhá přes celou vnitřní hloubku zaokrouhlenou dolů (313 / 362 mm), stojí na podlaze uprostřed dutiny a jde **zepředu dozadu**. Dutina podnosu (z podlahy): od čela 0,4 | 0,5 mm, od zadního lemu 17,8 | 20,6 mm, od boku 12,5 | 11,4 | 11,7 mm, podlaha 1,0 | 1,4 | 2,1 mm.
- **Spec `mbx`** (beze změny struktury): `sk = 4`; **`e` se u podnosů vztahuje ke KRATŠÍ vodorovné ose `b` (hloubka)**: `e = +1` … čelo (konec s malou mezerou dna) je na MIN straně osy b, `e = −1` … na MAX straně (otočená instalace). Build `scripts/v3d/vandr_offer_build.py` ho určuje z mezer dna od konců hloubky a ověřil jsem ho nezávisle proti poloze čelního panelu v katalogu (9 podnosů e = +1 na kartách 4921 / 4917 / 4918, 6 podnosů e = −1 na kartě 4968). Validátor: `sk` 1..4.
- **Veřejný JSON:** `typy[k]` nese u všech typů nová pole `druh` (`box` | `suplik`), `os` (`a` | `b` = osa, kterou převrací `e`), `L`, `W`, `H`, `lem` (délka lemu / vykroje, který miniatura kreslí tmavě; u šuplíku 0); `skupiny[].skryto` (jen admin: karta dílu ještě není aktivní); `dily` jen díly použité v zahrnutých skupinách.
  Desky podnosu `desky[j] = {"s":[x,y,z], "r":[2, h, délka], "d":dil}` v místním systému: `x` podél delší osy `a` od `min[a]` (souměrně, **bez převrácení**), `y` nahoru od `min[1]`, `z` podél kratší osy `b` **od čela**. Převod do světa (plugin) pro `os = "b"`: `svět[a] = min[a] + x`, `svět[b] = e > 0 ? min[b] + z : max[b] − z`, `svět[1] = min[1] + y`.
- **Gating po skupinách (nově):** skupina se nabízí veřejnosti, když mají VŠECHNY její díly kartu s cenou a aktivní kartu (`nabidka_pricky.dostupne_boxy`); skupiny jsou nezávislé (multiboxy se nabízejí i bez karet šuplíků a naopak). Admin vidí i skupiny s dosud neaktivními kartami (`skryto: true`, banner „Náhled pro zaměstnance“). `payload(spec, ceny, nahled_admin=False)`, `scene_offers._pricky_kontext` používá stejnou funkci (QR i přijetí tak odmítnou výběr ze skrytých skupin).
- **Slova:** u šuplíků „šuplík / šuplíků / šuplících“, „Šuplík 1…N“ (rozpis, poznámka objednávky); nadpis poznámky „Příčky do multiboxů“ / „Příčky do šuplíků“ / „Příčky do multiboxů a šuplíků“.
- **Testy v5:** `test_pricky.py` (typy, sloty, geometrie dutiny pro všech 10 typů, mixy, gating, slova, payload), `test_build_mbx.py` (osm karet vč. 4968 s otočenými podnosy), `test_pricky_backend.py` (sekce X: veřejný JSON, QR, poznámka, objednávka s podnosy), mutace `mutace_pricky.py` (95 mutací vč. 5 stavebních), plugin a stránka v Chromiu.
