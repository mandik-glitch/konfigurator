# Stůl balení LIDL (prototyp II) - 3D model z dílů katalogu

Model stolu z výkresu "Stůl balení - Stůl LIDL - balení - prototyp II" (4 listy), poskládaný z katalogových dílů (profil 40x40 SuperLight S10 `Object_11`, laminodesky `product_4933`, rohové spojky `product_3176`, patky `product_3283`, úhelníky `product_3207`, LED `product_4929`) a doplněný zástupnými díly pro válečkové dráhy, kování, rameno monitoru a vypínač (ty v katalogu nejsou). Karoserie v modelu není (WORKFLOW pravidlo 25).

Podrobnosti, rozpory výkresu, zástupné/neověřené díly, použitá pravidla spojů, kusovník a tabulka kót: **`POZNAMKY.md`**.

## Co kde je

| soubor | obsah |
|---|---|
| `nahled/stul_balici.html` | samostatný 3D náhled (bez sítě, GLB vložené): otáčení myší, díly barevně podle druhu, každý díl samostatný uzel s `part_id`, najetí myší ukáže part_id / SKU / rozměr, tabulka kót z výkresu x naměřeno |
| `nahled/kontrola_2d_celo.svg`, `_bok.svg`, `_pudorys.svg` | 2D pohledy s mm mřížkou a kótami změřenými z Box3 reálných GLB (WORKFLOW pravidlo 10, doplněk) |
| `vystup/custom_shape_data.json` | sloupec `custom_shapes.data` = `{parts, join_groups, frame_groups}`, jen díly s kartou v katalogu (142 dílů) |
| `vystup/custom_shape_data_se_zastupnymi.json` | totéž + 18 zástupných dílů (`part_id` = `__KVADR_1x1x1__`, doplní se id karty jednotkového kvádru) |
| `vystup/sestava_parts.json` | jednoduchý seznam všech 160 dílů (part_id, SKU, pozice, kvaternion, měřítko, rozměr, obálka) |
| `vystup/zastupne_dily.json` | zástupné díly zvlášť |
| `vystup/kusovnik.md`, `kusovnik.json` | kusovník (profily po délkách, desky, spojky, patky, úhelníky, zástupné) |
| `vystup/koty.json`, `vystup/validace.txt` | kóty výkres x naměřeno; plná validace včetně rozsahu měření |
| `zapis_do_db.py` | zápis do `custom_shapes` (NESPOUŠTĚNO, výchozí dry-run) |
| `stul_balici_spec.json`, `generuj_sestavu.mjs` | zdroj modelu: kóty z výkresu, členy rámu, desky, příslušenství; skript z toho model vyrobí a změří |

## Jak model otevřít v Kontrolní scéně (pro bota s přístupem k DB)

V cloudu DB není, takže tvar zatím v `custom_shapes` není. Kontrolní scéna (`webapp/kontrola.html`, produkčně `https://autovestavby.logiman.cz/api/kontrola-scena?items=...`) umí `cs:<id>` = řádek `custom_shapes`, `pa:<id>` = `product_assemblies`, `vd:<karta>`. Stůl je Vlastní tvar, tedy `cs:`; do `product_assemblies` se neukládá (WORKFLOW 23).

1. Zkontroluj, že na serveru existují katalogové karty a jejich GLB: `Object_11`, `product_3176`, `product_3283`, `product_3207`, **`product_4933` (laminodeska 18)**, **`product_4929` (LED 1200)**. GLB posledních dvou v repu chybí, geometrie je počítaná podle kontraktu (viz `POZNAMKY.md`, oddíl 2).
2. Dry-run (nic nezapíše, jen zkontroluje schéma a karty proti živé DB):
   `api/venv/bin/python3 stul_balici/zapis_do_db.py`
3. Zástupné díly (válečkové dráhy, kování, rameno monitoru, vypínač) nejdou do katalogu - kontrolní scéna zná jen díly z `/api/katalog`. Chceš-li je vidět jako orientační kvádry, najdi kartu s `kvadr_plny_1x1x1.glb` (dry-run vypíše kandidáty z `cfg_dily`) a spusť s `--zastupny-kvadr <part_id>`. Bez toho se zapíše jen to, co karty má (142 dílů).
4. Zápis jen na výslovný pokyn: `api/venv/bin/python3 stul_balici/zapis_do_db.py --apply [--category-id N] [--zastupny-kvadr product_NNNN]` (jeden `INSERT` do `custom_shapes`, jméno "Stůl balení LIDL - prototyp II (z výkresu)", `is_public=1`, po zápisu zpětné přečtení). Skript vypíše odkaz do Kontrolní scény: `...kontrola-scena?items=cs:<nové id>`.
5. Kontrola ve scéně (WORKFLOW 48 a 53: geometrie se Robertovi ukazuje jen ve scéně / v Kontrolní scéně, ne screenshotem do chatu): rozměry z `POZNAMKY.md` (oddíl 6), desky a LED zkontrolovat hlavně vizuálně, protože jejich GLB nebyl při výrobě k dispozici.

Role všech dílů jsou unikátní a začínají `stulbal-` (role jsou sdílený jmenný prostor, žádný jiný generátor tenhle prefix nepoužívá).

## Když se změní kóta na výkrese

Změň číslo v `stul_balici_spec.json` (sekce `param`, případně člen v `profily`/`desky`/`zastupne`) a spusť v kořeni repa (po `npm install`, three@0.128.0; trvá asi 1 minutu):

`node stul_balici/generuj_sestavu.mjs`

Přegenerují se všechny výstupy a validace; exit kód 0 = vše změřeno a čisté (vypíše se i rozsah měření), 1 = nalezen problém (vypíše se, který). Dev zkratka `SKIP_MESH=1` přeskočí přesný mesh test a výsledek označí jako neplatný. Pozor: jiný výkres znamená nový `stul_balici_spec.json` (stejný nástroj, jiná specifikace); ID desek/spojek se berou z části `katalog` ve specifikaci.
