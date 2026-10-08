# Příčky do Multiboxů a ocelových šuplíků v online nabídce – testy (bot8, 2026-10-07)

Kontrakt: `docs/KONTRAKT_NABIDKA_PRICKY.md`. Nic z toho nezapisuje do ostrých dat (DB testy jen nad dočasnými tabulkami, model a obrázky v dočasné složce, e-mail a audit vypnuté, prohlížečové testy s atrapou API).
Celek: `run_all.sh [--rychle] [--mutace] [--kandidat <složka api>]` (kandidát před nasazením: složka s `nabidka_pricky.py`, `scene_offers.py`, `orders.py`, `v3d_glb.py`, `v3d_merge.py`).
Fixtury: zákaznická GLB osmi Vandr karet (`build_karty.py 4453 4474 4594 4910 4917 4918 4921 4968`, Blender na CPU, ~2 min; `V3D_TEST_OUT` = složka mimo repo, nikdy ne společné `/tmp/v3d_testy` z cizích buildů). Karta 4968 = otočená instalace šuplíků (čelo na MAX straně, e = −1);
ctx fixtura `scripts/2026-10-02_v3d_testy/fixtures/ctx/ctx_4968.json`.

| soubor | co hlídá | očekávání |
|---|---|---|
| `test_pricky.py` | čistá logika `api/nabidka_pricky.py`: typ boxu z AABB (multiboxy 288 / 395 / 500 × 186 / 91, podnosy šuplíků S<šířka>x<hloubka>x<výška>), sloty 4 / 6 / 8 a 4 / 6 / 9, sety bez / mix 1–4 / plný, geometrie příček (ve slotech, uvnitř studny / dutiny podnosu, bez kolize), skupiny, gating po skupinách, slova, ceny, výběr, payload | 2388 kontrol |
| `test_spec_mbx.py` | validace `mbx` ve spec v3d (`api/v3d_glb.py`, `sk` 1..4): platné i neplatné vstupy, `sanitize`, `final_check`, žádná jména komponent v GLB | 51 |
| `test_merge_mbx.py` | slučování více karet (`api/v3d_merge.py`): id, pivoty, strany `g`, čísla skupin `s`, souřadnice | 18 |
| `test_build_mbx.py` | Blender build (`scripts/v3d/vandr_offer_build.py`): police / výsuvy / podnosy šuplíků, konec s výkrojem `e`, čelo podnosu (`e` nezávisle ověřené proti čelnímu panelu v katalogu), pivoty, karta bez multiboxu beze změny | 144 |
| `test_pricky_backend.py` | skutečné endpointy nad dočasnými tabulkami: veřejný JSON `pricky` (gating po skupinách podle aktivních karet, admin náhled, chyby modelu), QR `?pr=`, přijetí → objednávka (řádky, cena, poznámka, qty, montáž %), podnosy šuplíků, `orders` `extra_items` | 95 |
| `test_plugin.js` (+ `make_glbs.py`) | prohlížeč: plugin `webapp/js/v3d/pricky-multibox.js` (mixy ve 3D, pohyb s výsuvem, wire, dispose, výkon, `api.motionIds`, podnosy šuplíků ve světě pro všechny typy / orientace / osy) | 127 (121 na GLB bez podnosů) |
| `test_page.js` (+ `harness_pricky.js`, `stub-pricky.js`) | prohlížeč: `webapp/nabidka-online.html` – sekce příček po jednotlivých policích / šuplících, zvýraznění skupiny, vysunutí boxů (atrapa vieweru), šuplíky (miniatury, štítek „zákazník zatím nevidí“), ceny, QR, přijetí, localStorage, mobil, tisk | 120 |
| `test_page_real.js` | prohlížeč se SKUTEČNÝM `viewer3d.js` a pluginem: klik na set vysune všechny boxy skupiny (`viewer.play`), zvýraznění 3 s, obnova z localStorage nic nevysune (~3–6 min, swiftshader) | 15 (11 na GLB bez podnosů) |
| `mutace_pricky.py` | záměrné chyby (modul, spec, merge, backend, orders, Blender build podnosů); každá musí shodit příslušný test (~20 min) | 95 mutací, všechny chycené |
| `mutace_plugin.py` | záměrné chyby pluginu (~30–50 min) | 93 mutací, všechny chycené |
| `mutace_page.py` | záměrné chyby stránky příček (zkrácené testy po sekcích) | 72 mutací, všechny chycené |
| `zaloz_karty.py` | založení 7 karet příček (2 multiboxy `MBX-PRICKA-PRICNA-186\|91`, 5 šuplíků `SUP-PRICKA-PRICNA-<hloubka>x<výška>`; neaktivní, bez kategorie, orientační ceny) + GLB | náhled bez `--apply` |

DB testy: `systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PRICKY_CAND=<složka api> --setenv=PRICKY_FIX=<OUT>/out2 --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_multibox_pricky/test_pricky_backend.py`
(`<OUT>/out2` = zákaznická GLB z `build_karty.py`, `V3D_TEST_OUT` vč. `out`). Mutace stavby: `KANDIDAT_V3D` / `KANDIDAT_TESTY` (kandidátní `scripts/v3d` a testy 3D nabídky; vychozí repo).
