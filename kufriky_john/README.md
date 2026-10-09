> Aktuální pokračování: [fotografie a modely v6](README_doladeni_v6.md), [náhled v6](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v6/). Pět organizérů přepracovaných; přesnost detailů dosud neověřená. V5 zachovaná.

> Předchozí pokračování: [doladění organizérů v5](README_doladeni_v5.md), náhled https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v5/. V4 zůstává zachovaná.

> Předchozí pokračování: [doladění v3](README_doladeni_v3.md), náhled https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v3/. Starší etapy níže jsou historické.

> Historický stav v2: 20 reálných tvarů / 21 GLB místo obálek. [Postup a limity](README_tvar_v2.md), [náhled v2](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v2/). Přesnost nekótovaných detailů není ověřená. Níže zůstává popis předchozích etap.

# Kufříky PACKOUT — etapa 2

Autor: John, 5. 10. 2026. Celé aktuální zadání včetně všech tří doplnění a pravidla AGENTS.md včetně 4d byly přečteny.

**Přesné modely výrobků nejsou hotové: 0 z 20.** Připravené jsou rozměrové obálky 20 schválených typů (21 SKU/GLB, protože XL má staré a nové číslo). Shoda s celkovými údaji neprokazuje skutečný tvar. Žádné rozměry detailů nebyly odhadnuty.

Náhled: [3D podklady](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v1/). Dřívější [schválená tabulka](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-tabulka-v1/) zůstává zachovaná.

Podrobný průzkum, zdroje, výpočty každého typu, konvence skutečných katalogových GLB a otevřené věci jsou v [ETAPA2.md](ETAPA2.md). Historický popis první etapy: [README_etapa1.md](README_etapa1.md).

- `kufriky.json` + `kufriky.csv`: aktuální katalog. `model_file` je null, stav skutečného modelu chybí. Samostatné pole `envelope` a sloupce CSV odkazují na pomocnou obálku.
- `modely/<SKU>.glb`: jednotky mm, X = Š, Y = L, Z = V. V metadatech je výslovně `is_product_geometry = false`; soubor nemodeluje skutečný kufřík.
- `mereni/<SKU>.json` a `mereni/prehled.csv`: chybějící vstupy pro skutečný model, hodnoty null.
- `zdroje/cad_etapa2/`: nové ověření rozměrů na devíti výrobních rodinách a kandidáti s doloženými/nejistými podmínkami. Cizí model nebyl stažen, nebyl založen žádný účet.
- `nahled-modely/`: pouze veřejné statické soubory, lokální knihovny a fotografie. `nahled/` zůstává historická etapa 1.
- `overeni-modely/`: nezávislá měření skutečných vrcholů, ověření všech 20 typů v prohlížeči a doklady nahrání.

Čisté ověření bez DB a sítě:

```bash
python3 vystupy/kufriky/over_katalog.py
python3 vystupy/kufriky/over_modely.py
node vystupy/kufriky/over_modely_sdilenym_parserem.js
node vystupy/kufriky/over_nahled_modely.js
```

Reprodukce obálek: `python3 vystupy/kufriky/vytvor_obalky.py`. Čtení veřejných stránek je oddělené v `pruzkum_cad.py` a není součástí testů.

K dokončení požadovaného skutečného tvaru chybí licencovaný úplný CAD / kalibrovaný sken správného evropského SKU, nebo přesně kótované měření těla, víka, držadel, zámků, kol a spojů. Fotografie výrobce slouží jako reference vzhledu, ne jako měřidlo hloubek. Přesnost fyzického kusu ani funkční vůle nejsou doložené.

Veřejný náhled má noindex a žádná volání cizích služeb. Three.js je místní kopie nasazené knihovny s MIT licencí. Fotografie jsou původní interní miniatury výrobce s uvedenými zdroji. Nebyl změněn cizí kód ani provedena integrace do živého katalogu.


## Aktuální pokračování 7. 10. 2026

Oprava podstav prvních tří organizérů a kontrola všech typů: [README_doladeni_v4.md](README_doladeni_v4.md). Aktuální náhled: https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v4/.
