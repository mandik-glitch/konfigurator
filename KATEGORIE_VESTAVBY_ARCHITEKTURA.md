# Architektura kategorií "Vestavby do dodávek, aut" — dva stromy

Návrh pro `autovestavby.logiman.cz`, kategorie `184` a její potomci.
Vzniklo 2026-09-17 workflow (3 nezávislé návrhy — SEO úhel / zákaznická
cesta / škálovatelnost — + syntéza), agenti si fakta ověřovali přímo
živě v DB (121 SQL dotazů celkem), ne jen z brífu. Píše/udržuje bot7,
doména kategorie/texty/SEO. Kontext: `PLAN_TVORBY_MINIWEBU.md` (bot3),
`TEXT_FILTR.md` pravidlo 16 (skládat z ověřených zdrojů, nevymýšlet).

**Zadání:** Robert chce DVA SOUBĚŽNÉ STROMY (ne jeden se třemi filtry):
1. podle značky/modelu auta,
2. podle typologie (typu úložiště) — SEO nejdůležitější osa.
Navigace = víc samostatných rozcestníků/hub stránek (Robertovo
rozhodnutí), propojených přes "Související stránky", ne jedna stránka
s filtry.

## ⚠️ Technické opravy oproti původnímu zadání (ověřeno živě, důležité)

- **Routing je PLOCHÝ `/kategorie/<slug>`, NE vnořený podle `parent_id`.**
  `content_categories.slug` je globálně unikátní sloupec. Proto musí být
  KAŽDÝ slug sám o sobě popisný (`vestavby-pro-citroen-jumpy`, ne holé
  `jumpy` — kolidovalo by/bylo by nesrozumitelné mimo kontext stromu).
- **`car_bodies` (912 řádků) NENÍ zákaznická rozměrová varianta** — je to
  čistě interní 3D geometrie scény (`name` = "leva"/"prava"/"koncova",
  912 = 304 modelů × 3 panely). Skutečný zdroj modelové/rozměrové úrovně
  je **`karoserie_model_reference.model_range`** (existuje, vyplněno, 61
  distinktních hodnot pokrývá celý katalog — Sprinter 21 karoserií,
  Transit 21, Custom 16, Crafter 12, TGE 12, Expert 11, Scudo 11, Vivaro
  11, Jumpy 8, Jumper 7, Doblò 6, Ducato 5...).
- **Kategorie 184 dnes má v `bottom_body_html` 6 odkazů, z nich 5 mrtvých**
  (vedou na neexistující slugy: `stavebnice-do-aut`,
  `vestavba-dodavky-ford-custom`, `vestavby-pro-toyota-proace`,
  `vestavby-dodavek-pro-elektrikare`, `vestavby-dodavek-pro-instalatera`).
  Opravit v rámci téhle přestavby.
- **Všech 10 dnešních dětí kategorie 184 je `is_visible=1`** (živě
  ověřeno) — nic z toho se nesmí tiše skrýt kvůli úklidu struktury, jen
  přeřadit (`parent_id`). Skrytí publikované/indexované stránky je SEO
  riziko vyžadující výslovné Robertovo schválení.

## Strom podle vozidla

**Hranice ruční vs. šablonovaná tvorba (4 vrstvy):**

1. Kořen `184` "Vestavby do dodávek, aut" (`vestavby-do-dodavek-aut`) —
   beze změny, společný rodič obou stromů.
2. Nový manuální rozcestník "Vestavby podle vozidla"
   (`vestavby-podle-vozidla`) — kořen brand-tree.
3. **Značkový hub** — 20 řádků, 1:1 na `car_makes`. VŽDY `is_visible=1`,
   šablonovaný index modelových řad dané značky. Vlastní ruční úvod jen
   u značek s reálnými sestavami (dnes: Citroën 120, Fiat 16, Mercedes 8,
   VW 3 — ze 147/404 sestav s vyplněným `car_model_id`; zbylých 16
   značek nemá ani jednu). Slug: `vestavby-pro-<znacka>` (konzistentní
   se živým vzorem `vestavby-pro-ducato-jumper-boxer`).
4. **Nameplate úroveň** (klíč = `karoserie_model_reference.model_range`,
   NE `car_bodies`). Pod ní **nevzniká další `content_categories`
   řádek** pro jednotlivý K-kód/model — šablonovaná route stejným
   mechanismem jako dnešní `car_storefronts`/`car_storefront_models`.
   Generovat jen tam, kde `karoserie_model_reference.car_models_id`
   NENÍ NULL (15 z 319 řádků tuhle vazbu nemá — jinak vznikne mrtvá
   stránka bez možnosti koupě).

**Graduace nameplate hubu na ruční Tier1 stránku** (vlastní intro/body/
FAQ jako dnešní 184/233) — datově řízený práh, NAVRŽENO syntézou, ne
Robertovo číslo, potvrdit/upravit:
- ≥ ~15 reálných sestav soustředěných na jednu modelovou řadu, NEBO
- živě ověřená TOP10 pozice v Google na frázi vázanou k modelu.

Dnešní kandidáti: **Citroën Jumpy** (120 sestav na 8 K-kódech),
**Fiat Doblò** (16 sestav, 15 na K-075), **Ford Transit Custom** (0
sestav, ale živě ověřeno #6 v Google pro "vestavba Ford Transit Custom
na míru" — otevřená otázka, viz níž). Mercedes Vito/eVito (8) a VW
Transporter (3) zůstávají zatím šablona, nejblíž k povýšení.

Elektrické varianty se STEJNÝMI mm jako spalovací dvojče (Jumpy L1
[K-120] vs. ë-Jumpy L1 [K-121e], oboje 4609×2204×1905mm) sdílí JEDNU
šablonovanou stránku jako badge/atribut, ne duplicitní URL. Karoserie s
fakticky jinými rozměry (Crew Cab: 1940mm výška vs. 1895mm standard)
dostávají vlastní stránku.

**Příklad — Citroën:**
```
184 vestavby-do-dodavek-aut
 → vestavby-podle-vozidla
   → vestavby-pro-citroen (brand hub + ruční úvod)
     → vestavby-pro-citroen-jumpy (MANUÁL, 120 sestav)
       → šablony: l1 (K-120/K-121e badge, 4609×2204×1905mm)
                  l2 (K-122/K-123e, 4956×2204×1895mm)
                  l3 (K-124/K-125e, 5309×2204×1895mm)
                  crew-cab-l2 (K-118, 4959×2204×1940mm — vlastní stránka)
                  crew-cab-l3 (K-119, 5309×2204×1940mm)
     (zbylých ~21 modelů Citroën bez sestavy: jen položka v dynamickém
      výpisu brand hubu + šablona, žádný content_categories řádek)
```

**Sdílená platforma** (stejná karoserie napříč značkami, žádná nemá dost
sestav samostatně) — NENÍ rozdělena na tenké klony. Zůstává 1 stránka
přímo pod `vestavby-podle-vozidla` (příklad: kategorie 233 "Vestavby pro
Ducato, Jumper, Boxer" — zachovat beze změny, cross-linkovat ze všech
dotčených brand hubů). Do budoucna: `car_models.platform_group` (dnes
neexistuje) pro obecné řešení i u Trafic/Primastar/Talento apod. — mimo
scope tohohle zadání, jen avizováno.

## Strom podle typologie

5 kanonických hub kategorií 1:1 s `regal_typologie` + 1 navržený uzel
navíc. Živě ověřeno: ze 404 sestav má typologii vyplněnou 404 (100 %) a
VŠECH 404 je EB — 0 u ostatních čtyř.

| kód | název | slug | is_visible | proč |
|---|---|---|---|---|
| EB | Regál na euroboxy | `regal-na-euroboxy` | **true** | jediná s reálnou konstrukcí (recepty + 404/404 sestav) |
| OS | Ocelové šuplíky | `ocelove-supliky` | **true, s výhradou** | 0 sestav vlastní konstrukce, ALE pod uzlem visí živá kategorie 210 (partnerský produkt TECNO) — nemažeme, jen přeřazujeme; text musí čestně říct "dnes přes partnera TECNO, vlastní konstrukci připravujeme" |
| EV | Euroboxy na výsuvech | `euroboxy-na-vysuvech` | **true, s výhradou** | 0 sestav v DB, ALE kategorie 248+249 popisují reálný fungující mechanismus (výsuvné rámy s pružinovou aretací, princip Systému 30) — v rozporu s `regal_typologie.popis` "obsah neurčen". **Nahlásit Robertovi, ne rozhodnout za něj** (viz otevřené otázky) |
| UN | Univerzální regál | `univerzalni-regal` | **false (draft)** | 0 sestav, po správném přeřazení 246→nový uzel nezbývá žádný reálný text |
| UK | Ukládání kufrů | `ukladani-kufru` | **true** | jen obsah 220 ("jumbo šuplíky z bočních dveří na kufry" — reálně prodávaný produkt na míru, ne fabrikace) |
| PL* | Podlahy a ložné plochy | `podlahy-a-lozne-plochy` | **true** | NAVRŽENÝ, mimo 5 kódů `regal_typologie` — vzniká sloučením 254+246, reálně odlišný koncept od zbytku. Formální zápis nového kódu do `regal_typologie` je otevřená organizační otázka |

**Umístění** (levý/pravý/na přepážku/spojený/výsuvný modul/druhá
podlaha): zůstává **filtr/atribut uvnitř hub stránky**, NE 3. strom —
všechny 3 nezávislé návrhy k tomu došly samostatně (silný signál).
Doplnění: (a) uložit jako normalizovanou tabulku (oživit neaplikovaný
`vestavby_typy`/`vestavby_verze`), ne text/enum natvrdo, (b) filtr se
needexuje jako vlastní URL — canonical vždy na typologii, (c) únikový
ventil: konkrétní kombinace s dost sestavami se smí ručně povýšit na
vlastní dítě typologického hubu.

## Mapování 10 dnešních dětí kategorie 184

Všechny `is_visible=1` dnes — **žádné se tiše neskrývá**, jen mění
`parent_id`:

| id | název | akce |
|---|---|---|
| 247 | Regály do auta | **zachovat slug beze změny** (Google #1/#2/#3/#5 na "regály do auta hliníková stavebnice") — stává se vstupní stránkou typologického stromu, rodičem EB/OS/EV/UN/UK/PL |
| 233 | Vestavby pro Ducato, Jumper, Boxer | zachovat beze změny, sdílená platforma přímo pod `vestavby-podle-vozidla` |
| 210 | Šuplíkové vestavby do aut - ocel/TECNO | přeřadit pod OS |
| 248 | Výsuvný systém euroboxů v autě | přeřadit pod EV (hlavní obsah) |
| 249 | Úložný prostor v podlaze dodávky | přeřadit pod EV jako "umístění: druhá podlaha" (text zmiňuje "euroboxy na výsuvech" — NE pod OS/PL/UN) |
| 254 | Výsuvné podlahy do dodávek | přeřadit pod nový PL |
| 246 | Vyjímatelná přídavná ložná plocha dodávky | přeřadit pod nový PL (spolu s 254) |
| 220 | Výsuvy z dodávky na míru | přeřadit pod UK (text: "jumbo šuplíky ... na kufry") |
| 260 | Kotvení vestaveb do auta | **zůstává přímo pod 184, mimo OBA stromy** — průřezová technická stránka, cross-linkovat odevšad |
| 244 | Přívěsný vozík s úložným systémem | **přesunout MIMO větev 184** (není vestavba DO auta) — kam přesně je otevřená otázka |

## Cross-linking

Mechanismus zůstává dnešní (`content_pages.bottom_body_html`, ruční
blok "Související stránky"), NE nový dynamický SQL join. Odkazy musí
mířit na PLOCHOU cestu `/kategorie/<slug>`.

Příklad na hubu "Regál na euroboxy":
```html
<p class="seo-related"><strong>Související stránky:</strong>
<a href="/kategorie/vestavby-pro-citroen-jumpy">Citroën Jumpy</a>,
<a href="/kategorie/vestavby-pro-fiat-doblo">Fiat Doblò</a>,
<a href="/kategorie/kotveni-vestaveb-do-auta">Kotvení vestaveb do auta</a>,
<a href="/kategorie/vestavby-do-dodavek-aut">Vestavby do dodávek, aut — přehled</a></p>
```
(Jumpy a Doblò nejsou nahodilé — jediné 2 řady, kde EB reálně vzniká:
120, resp. 15 z 16 sestav. Opačným směrem na Jumpy stejná logika —
100 % jeho sestav je typologicky EB.)

## Otevřené otázky pro Roberta

1. **EV rozpor**: `regal_typologie` říká "obsah neurčen", ale živé
   kategorie 248+249 popisují reálný mechanismus. Nedopracovaná
   typologie, nebo se řádek jen nestihl aktualizovat? Pokud jde o
   reálnou konstrukci, EV by měla jít live jako 2. plně rozpracovaná
   typologie vedle EB.
2. Nový uzel "Podlahy a ložné plochy" — zapsat jako nový kód do
   `regal_typologie` (např. `PL`), nebo nechat mimo tuhle tabulku?
3. Kam přesně má jít **244 Přívěsný vozík**, mimo větev 184? (chybí
   přehled celého stromu webu)
4. **Ford Transit Custom**: investovat ruční redakční čas do modelu bez
   jediné prodané sestavy, jen na základě SEO signálu (#6 pozice)?
5. Potvrdit/upravit navržený práh graduace (≥15 sestav NEBO TOP10
   Google pozice) — je to návrh syntézy, ne Robertovo číslo.
6. **210 (TECNO)** — v pořádku prezentovat partnerský produkt jako obsah
   OS uzlu, dokud nevznikne vlastní konstrukce?
7. `car_models.platform_group` (nový sloupec pro obecné řešení sdílených
   platforem) — mimo scope, jen avizováno pro budoucí schéma.

Detail celé debaty (3 nezávislé návrhy + zdůvodnění, proč syntéza
rozhodla, jak rozhodla) v transcriptu workflow, ne tady — tenhle
soubor drží jen finální doporučení (pravidlo 37).
