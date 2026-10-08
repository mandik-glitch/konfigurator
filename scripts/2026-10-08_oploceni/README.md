# Ochranný kryt a oplocení z profilů 40×40 – FÁZE 1 (jádro)

bot8, 2026-10-08. Robert: *„udělej mezitím generátor ochranného oplocení a krytování strojů z profilů 40×40“* (fotka klece z profilů s čirými panely a dveřmi kolem pískovacího stroje).
Tohle je **jen jádro**: geometrie, kusovník, 3D model, cena, testy, obrázky. **Žádná shop vrstva** (veřejné API, registr, stránka, karty, košík) – ta je fáze 2 (níže). Vše je zatím jen v této složce, nic není nasazené,
nic se nezapisuje do DB, nic se nedotýká živých souborů.

## Co generátor umí

Jeden generátor s **obdélníkovým půdorysem** (šířka X, hloubka Z, výška Y). Každá ze 4 stran (`celo`, `prava`, `zadni`, `leva`) je:
`stena` (rám z profilů + výplň), `dvere` (křídlové dveře v jednom poli strany) nebo `otevreno` (bez stěny – z téhož generátoru jde udělat i prosté **oplocení**: jedna strana = řada polí, L, U).
Střecha `zadna` / `ram` / `vyplne`. Výplň: polykarbonát čirý / kouřový 4 mm, plexisklo 5 mm, svařovaná síť, plná (hliníkový kompozit 3 mm) – pro celek, pro každou stranu a pro střechu zvlášť.
Profil: SuperLight S10 40×40 (karta #3468, SKU 1.1.10.040040.03, GLB díl `Object_11`, drážka 10 mm).

| parametr | hodnoty | výchozí |
|---|---|---|
| `sirka`, `hloubka`, `vyska` | 600–6000, 600–6000, 1000–3000 mm | 1500, 1500, 2200 |
| `celo`, `prava`, `zadni`, `leva` | `stena` / `dvere` / `otevreno` | dveře vpředu, ostatní stěna |
| `strecha` | `zadna` / `ram` / `vyplne` | `vyplne` |
| `vyplne` (+ `vyplne_celo/prava/zadni/leva/strecha`) | `pc_cira`, `pc_koura`, `plexi`, `sit`, `plna` | `pc_cira`, strany bez vlastní volby |
| `dvere_sirka`, `dvere_vyska` | 600–1200, 1500–2400 mm (výška `None` = min(2000, max. možná)) | 800, `None` |
| `dvere_poloha`, `dvere_zavesy` | `vlevo`/`stred`/`vpravo` (u strany zvenku), `vlevo`/`vpravo` | `vpravo`, `vpravo` |
| `zamek` | `zapadka` (#3298) / `zamek` (#3423) / `zadny` | `zapadka` |
| `patky` | ano/ne (stavitelná patka M10, #3283) | ne |

Souřadnice: x = šířka (zleva doprava při pohledu na čelo zvenku), y nahoru, z = hloubka, ČELO v rovině z = D. `u` = poloha podél stěny zleva při pohledu zvenku (zadává se v ní poloha dveří a strana závěsů).

## Konstrukční rozhodnutí (vše NÁVRH k potvrzení Robertem)

* **Rohové sloupky** jdou celou výškou (s patkou nebo záslepkou), **mezilehlé sloupky končí pod souvislou horní příčkou** (T-spoj, 2 spojky). Díky tomu střechou procházejí jen rohové sloupky a střešní
  výplň / příčky nikdy nenarazí na sloupek (původní verze s průběžnými sloupky to dělala – nalezeno testem, přestavěno).
* **Rohová spojka** (karta #3176) v každém vnitřním úhlu spoje (L-roh 1 ks, T-spoj 2 ks). Poloha je **odvozená ze šablony stolu systému 40** (stejný díl, stejný tvar): `R = [b, a, b×a]`,
  `pos = Q + 57·a − 18,5·(b×a)` (Q = střed čela dosedajícího profilu na ploše nosného, b = směr dosedajícího profilu pryč od spoje, a = směr podél nosného profilu k vnitřnímu úhlu). Test ověřuje shodu
  se třemi spojkami šablony (poloha i kvaternion) + žádné zanoření na mřížce konfigurací.
* **Výplň** je vsazená do **drážky** profilu (střední rovina profilu = střední rovina výplně, jako na fotce), zasunutí 9 mm, tenké tabule v těsnění na sklo (#3218, délka = obvod otvoru; síť / plná v měkkém těsnění
  #3199). Spojky leží v rovině výplně (blok 37×37×37), proto má tabule v každém rohu **výřez 47×47 mm** (tvar kříž = 3 kvádry); u rohového sloupku (střecha) malý výřez 9,5×9,5.
* **Pole**: nejvyšší světlá šířka pole 1200 mm, nejvyšší světlá výška mezi příčkami 1100 mm (jinak mezilehlý sloupek / mezipříčka); nejmenší pole 150 mm.
* **Dveře**: rám křídla ze 4 profilů 40×40 (+ mezipříčka, když je světlá výška křídla nad 1100 mm), výplň jako v poli (pole nad dveřmi se u nízkých dveří ve vysoké stěně dělí mezipříčkou jako každé jiné), **3 závěsy** Pant 40×40 (levý #3645 / pravý #3644) na vnější straně, otevírání ven, vůle 3 mm k sloupku
  na obou stranách, spodek 5 mm nad podlahou / patkou, nad dveřmi vždy **nadpraží** (příčka + pole s výplní, světlost ≥ 150 mm), aby spojky neležely v otvoru dveří (dveře proto potřebují výšku ≥ 1750 mm + patky).
  Zámek / západka na protější stojce křídla, **plošně** na vnější ploše stojky, ve výšce min(1000, výška křídla / 2).
* **Spodní příčka** jen u polí (u dveří žádný práh). Pole dole u podlahy má příčku, výplň tedy začíná nad ní.
* Jedna stěna bez střechy (oplocení): rozměr kolmý na stěnu nemá vliv a normalizace ho vrací na výchozí (jedna kanonická podoba = jeden hash).
* Upozornění ve výsledku: ISO 14120 / 13857 (generátor řeší **konstrukci**, ne posouzení bezpečnosti stroje), ukotvení vysokých / dlouhých konstrukcí, těžké široké křídlo, síťová výplň.

## Soubory

| soubor | účel |
|---|---|
| `oploceni_konfigurator.py` | jádro: `normalizuj(**p)`, `sestav_oploceni(**p)` → díly (umístěné katalogové díly), výplně (pole + kusy kvádrů), spoje, `entries` pro `configurator_price.price_entries`, kusovník, `extra_prace` (těsnění), rozměry, upozornění, hash |
| `oploceni_glb.py` | GLB skladač: `sestav_glb(r, otevrit_dvere=0)` → bajty, `model_pro_parametry(p)` → `(hash, glb)` s LRU cache; spec `extras.v3d` jako u stolů; průsvitné výplně = samostatné uzly s BLEND, síť = textura s UV |
| `oploceni_cena.py` | cena: `cena(r, ctx)` přes `price_entries`, výplně jako virtuální desky `navrh:<typ>` s orientační cenou za m², spojovací materiál podle SKU, `doplnky_ctx(cur, ctx)` (karty dílů mimo scénu) |
| `test_oploceni.py` | hermetický test (bez DB, falešné prostředí), 603 kontrol (~13 s) |
| `mutace_oploceni.py` | 143 mutací, každá musí shodit test (kopie adresáře + symlinky, 4 paralelně); poslední celý běh: 143/143 zachyceno |
| `render_oploceni.py`, `render_glb.js` | obrázky konfigurací (GLB → three.js v Chromiu → PNG), jen pro náhled |
| `overeni_ve_vieweru.js` | načte GLB do SKUTEČNÉHO vieweru projektu (`webapp/js/v3d/viewer3d.js` 1.16.0, three r128, CSS `webapp/css/v3d.css`) v headless Chromiu, vypíše `v.state()` (legacy / mode / warnings) a uloží snímek |
| `zaloz_karty_vyplni.py` | **dry-run** návrhu 5 neaktivních karet výplní (`--apply` záměrně neimplementováno) |

## Spuštění (z kořene repa)

```
api/venv/bin/python3 scripts/2026-10-08_oploceni/test_oploceni.py                  # ~13 s, 603 kontrol
api/venv/bin/python3 scripts/2026-10-08_oploceni/mutace_oploceni.py [nazev ...]    # všechny mutace ~25 min při zátěži; --kotvy jen ověří kotvy
SP=<adresář> api/venv/bin/python3 scripts/2026-10-08_oploceni/render_oploceni.py <vystupni_adresar>
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
    api/venv/bin/python3 scripts/2026-10-08_oploceni/zaloz_karty_vyplni.py         # dry-run karet (jen čte)
```

## Fáze 2 (návrh, nic z toho není hotové)

1. `oploceni_shop.py` jako `dopravnik_shop.py`: `schema(lang)` (parametry, rozsahy, výchozí), `resolve(selection)` → `{valid, selection, hash, price, bom, warnings}`, `pro_objednavku(selection)`,
   `glb_bytes(selection)`, `tokens`; veřejné endpointy + rate limit jako u stolů.
2. `konfigurator_registr.py` zobecnit na slovník recept → modul (dnes pevně stůl + `dopravnik_valeckovy`).
3. Karta produktu „Ochranný kryt a oplocení – konfigurovatelný“ (neaktivní do schválení), staff stránka generátoru (okno Vzhled online nabídek), tlačítko do online nabídky / košíku.
4. Karty výplní (viz `zaloz_karty_vyplni.py`), potom v `VYPLNE` doplnit id karty a `entries` přepnout z `navrh:<typ>` na `product_<id>`.
5. GLB uzly pojmenovat `bomgrp_<n>` (zvýraznění kusovníku ve vieweru), případně pohyb dveří (`motions`) místo jen náhledového otevření.

## Otevřené body

Viz závěrečná zpráva fáze 1 (umístění zámku / západky a závěsů k potvrzení, kategorie a ceny karet výplní, meze polí, ISO 14120, síť jako výplň do drážky).
