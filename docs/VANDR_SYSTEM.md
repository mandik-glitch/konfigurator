# Vandr systém u nás – registr komponent

Robert 2026-10-05: *„Začneme postupně přetahovat vandr system k nám. Připrav si nějakou strukturu pro různé komponenty. Jako první si tam ulož právě dokončený natahovací výsuv,
vytvoř mu kartu a SKU, ale cena bude podle délky“* a *„nemíchat Vandr s první větví“* (tj. s nativní větví: `komponenty*`, `product_assemblies`, `cfg_dily`, `custom_shapes`).

Komponenty ze starého systému vanDrawee (Unity + Laravel, naše testovací kopie `/opt/vandrawee`) se u nás přebírají **po jedné**: kus geometrie z jeho exportu + kusovník a ceny
z jeho databáze → vlastní záznam v naší DB + model v naší chráněné složce. Vandr zůstává zdrojem ceníku (materiály, díly), ne běhovým prostředím.

## Hranice (co sem patří a co ne)
| | Vandr systém u nás | 1. větev (nativní) | sestavy z FBX (automaty Vandru) |
|---|---|---|---|
| tabulky | `vd_komponenty`, `vd_komponenty_dily` | `komponenty*`, `product_assemblies`, `cfg_dily`, `custom_shapes` | `stored_models` (Vandr DB), `shop_products` |
| SKU | `VDK-<KÓD>` | číselné (Dogus), `STUL.SYSTEM30/35/40.KONF` | `VD-<uuid>` |
| model | `webapp/katalog/vandr/komponenty/<kód>.glb` | `webapp/katalog/*.glb` | `webapp/katalog/vandr/…` |

SKU `VDK-…` se **nechytá** na `sku LIKE 'VD-%'` (cena-sync, razítka, render, aktivace, přehledy Vandru čtou z `VD-` uuid) – nic z toho se komponent netýká. Test
`scripts/vandr_system/test_vandr_system.py` hlídá (AST), že SQL modulu i skriptů sahá jen na `vd_*`; karta se zakládá zvlášť (`zaloz_kartu.py`).
Model leží pod `/katalog/vandr/`, kterou nginx vrací 401 (jen zaměstnanci přes `/api/vandr-glb-file/`) – Vandr 3D nesmí ven (veřejně jen otočka).

## Datový model
`vd_komponenty`: `kod` (malá písmena + pomlčky, jedinečný), `sku`, `shop_product_id` (karta), `vandr_unity_id` / `vandr_component_id` (odkud pochází), `nazev_cs/en`, `kategorie` (volný text,
např. `vysuvy`), `typ` (`pevny` | `parametricky`), `hloubka_mm`, `parametrizace_json`, `glb_soubor`, `mena`, `cena0` + `vaha0_g` (výchozí rozměr), `cenik_snimek` (datum ceníku), `stav`
(`koncept` | `schvaleno`), `poznamka`. `vd_komponenty_dily`: kusovník (`dil`, `ks`, `cena_ks`, `vaha_ks_g`, `delka_pravidlo_json`); smazání komponenty smaže díly (CASCADE).
Kód: `api/vandr_system.py` (bez Flasku): `nacti_komponentu`, `kusovnik(komp, hodnoty)`, `cena`, `over_hodnoty`, `zaregistruj`, `pripoj_kartu`, `kod_na_sku`, `glb_cesta`, `zaloz_schema`.

## Cena podle rozměru
Stejné pravidlo jako ve Vandru (cena = součet cen dílů × počet; cena na webu = cena v DB 1:1, bez koeficientu a bez DPH – Robert přes bot3 2026-09-25). Dílům, které se při změně rozměru
protahují, se cena a váha dopočítají z materiálu (`delka_pravidlo`: cena / váha za 1 mm, název dílu se šablonou délky); operace (např. vrtání Zx4) se nemění; ostatní díly beze změny.
Parametr se zadává jako **světlá šířka mezi nohami** (jako ve Vandru `min_width`), `vnejsi_pricist_mm` převádí na vnější šířku modelu. Ceník je **snímek k datu `cenik_snimek`**:
po změně cen/materiálů ve Vandru spustit znovu `pridej_komponentu.py … --zapsat` (přepíše kusovník a model stejné komponenty, SKU a karta zůstanou, `stav` se vrací na `koncept`).

**Výsuv pro 3 systainery (`kufrik-3x43-vysuv-d459`)** – plato bez noh: podélné profily 20×40 (2 ks) a dno 6 mm se protahují; světlá šířka **359–1589 mm** (délka profilu 300–1530 mm, zadal
Robert), výchozí 967 mm = **4 677,59 Kč**, 7 363,94 g. Sklon **1,32814 Kč/mm** (3 870,08 Kč při 359 mm, 5 503,69 Kč při 1589 mm). Hloubka 459 mm pevná.

## Přidání další komponenty (postup)
1. Ve Vandru najít komponent (`components.unity_id`) a sestavu, ve které je – export `…/exported_models/<uuid>/` (nebo už převedené GLB v mm).
2. `scripts/vandr_system/pridej_komponentu.py --unity-id … --kod … --kategorie … --zdroj-uuid|--zdroj-glb … --koren <předpona uzlu komponentu> --delka-dil … --delka-od … --delka-do …`
   (bez `--zapsat` jen náhled): převede FBX→GLB postupem automatu konverze, ořízne podstrom komponentu (bez noh a okolí), protáhne podle roviny (`scripts/2026-10-05_vandr_plato/vandr_param.py`),
   přiloží kusovník z DB Vandru (kontroluje, že součet dílů = cena a váha komponentu), zapíše GLB a řádky registru.
3. `scripts/vandr_system/zaloz_kartu.py --kod … --nazev "…"` – neaktivní karta (bez ceny, bez kategorie, bez modelu); aktivace a kategorie = Robert / bot7 (pravidlo 54).
4. Kontrola: `/api/kontrola-scena?rezim=param&komponenta=<kód>` (jen zaměstnanci) – posuvník šířky, cena a kusovník podle šířky; test `scripts/vandr_system/test_kontrola_komponenta.js`.
Dnes podporováno: jediný parametr, typ `natazeni_podle_roviny` (jedna rovina natažení, díly přes rovinu se protahují, ostatní se posouvají); další typy parametrizace se přidají s další komponentou.

## Určení komponent a stav
**Komponenty se neprodávají samostatně, slouží generátorům** (Robert 2026-10-05: *„komponenty jsou hlavně do generátoru, neprodávají se samostatně, tak to zatím neřešme“*). Proto nevzniká
prodejní tok pro cenu podle šířky (veřejné API, volba šířky na kartě, košík); generátor si cenu a kusovník vezme z `api/vandr_system.py` (`cena`, `kusovnik`) a model z registru. Karta komponenty
je jen **evidenční** (SKU pro kusovníky a odkazy) a zůstává neaktivní, bez kategorie a textu – aktivace jen Robert (pravidlo 54).
Hotovo (2026-10-05): tabulky, modul, import, první komponenta (#1), karta #4966 `VDK-KUFRIK-3X43-VYSUV-D459` (neaktivní), testy (`test_vandr_system.py` 154, `test_kontrola_komponenta.js` 44).
Otevřené: další komponenty (pořadí určí Robert); mechanická vhodnost nad 1357 mm (Vandr má u delších výsuvů 4×43 a jiné vedení) není ověřená – rozsah je zadání Roberta (profil 300–1530 mm).
