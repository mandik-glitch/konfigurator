# Horní police mezi zadní stojky – 2. kolo: ŠIKMÁ POLICE NA BOXY (bot8, fork 3, 2026-10-08)
Nad v1 (commit 110b03d3: rovná, rámová, s lemem, rám s deskou v drážce, rám s přepážkami) přibývá šestý typ `sikma` (veřejně `slope`) + parametr `hpolice_sklon` (5–30°, krok 5, výchozí 15; veřejně slot `upshelftilt`).
Popis (konstrukce, uchycení konzolami #3323 / #3324, výška, kolize, hash / token / API / 3D / cena): **`DOKUMENTACE_SIKMA.md`** (vkládá se do `docs/KONTRAKT_KONFIGURATOR_UI.md`). V živém stromu se NIC neměnilo.
## Soubory (pathspec pro commit)
`api/stul_hpolice.py` (celý nový soubor v2; zdroj `scripts/2026-10-07_police_stojky/stul_hpolice.py`), záplaty `api/stul_konfigurator.py`, `api/stul_sse.py`, `api/stul_ovladani_verejne.py`, `api/stul_shop.py`, `docs/KONTRAKT_KONFIGURATOR_UI.md`,
a ve složce `scripts/2026-10-07_police_stojky/`: `stul_hpolice.py`, `apply_patches_v2.py`, `patch_docs_v2.py`, `DOKUMENTACE_SIKMA.md`, `test_hpolice.py`, `test_hpolice_shop.py`, `test_hpolice_sikma.py` (nový), `mutace_hpolice.py`, `prepare_cand_v2.sh`, `README.md`, `commit_api_v2.txt`, `apply_v2.sh`.
Žádná nová karta ani GLB (konzoly #3323 / #3324 jsou v katalogu); `api/stul_glb.py` beze změny.
## Nasazení (pod zámkem, nad v1)
1. `bash apply_v2.sh /opt/konfigurator` (vše spočítá a ověří do dočasné složky, pak zapíše; kotvy se musí vyskytovat právě jednou, jinak se nezapíše NIC);
2. `api/venv/bin/python3 scripts/2026-10-07_police_stojky/test_hpolice_sikma.py`, `test_hpolice.py` (hermetické), `test_hpolice_shop.py` (`systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator ...`, DB jen čte) a existující sada `scripts/2026-10-02_stul_testy/run_all.sh`;
3. commit (`commit_api_v2.txt`), 4. reload API plánovanou službou (api/*.py nasazuje samo 0:00 / 12:30).
## Kandidát a testy bez zásahu do živého stromu
`bash prepare_cand_live.sh <složka>` postaví kandidátní strom z ŽIVÉHO stromu PO v2 (zdroje i záplaty už jsou v živých souborech; symlinky včetně `.env`), testy se pouští z `<složka>/repo`; mutace: `STUL_KANDIDAT=<složka> api/venv/bin/python3 <složka>/repo/scripts/2026-10-07_police_stojky/mutace_hpolice.py [id ...] [-j 3]` (151 mutací; `--kotvy` ověří jen kotvy; mutace chycená pádem testu = `PAD`, běh bez výpisu a bez výjimky = `CHYBA BEHU`, ne chycená; `EKVIVALENTNI` = zdůvodněné výjimky k05, x36). `prepare_cand_v2.sh` platil jen PŘED commitem v2 (aplikuje záplaty, na živý strom po v2 už nejde).
## Otevřené body pro Roberta
Viz závěrečná zpráva forku.
