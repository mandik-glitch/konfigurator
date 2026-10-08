#!/usr/bin/env python3
"""Zaplata dokumentace (bot8, 2026-10-08, WORKFLOW pravidlo 61): razitka loga jsou VYCHOZI na vsech 3D modelech generatoru. Meni 3 soubory v koreni repa (argument = koren, vychozi /opt/konfigurator):
MAPA_3D_A_GENERATORU.md, docs/KONTRAKT_KONFIGURATOR_UI.md, docs/STUL_ZASLEPKY_A_RAZITKA.md. Kazda kotva musi byt v souboru prave jednou.
Pouziti: patch_docs.py [koren]"""
import io
import os
import sys

koren = sys.argv[1] if len(sys.argv) > 1 else "/opt/konfigurator"


def uprav(soubor, zmeny):
    p = os.path.join(koren, soubor)
    s = io.open(p, encoding="utf-8").read()
    for a, b in zmeny:
        if s.count(a) == 0 and s.count(b) >= 1:                      # uz aplikovano (commit 3b7d5076)
            continue
        assert s.count(a) == 1, (soubor, s.count(a), a[:70])
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8").write(s)
    print("OK", soubor)


uprav("MAPA_3D_A_GENERATORU.md", [(
    "a **model v online nabídce má razítka loga** (`glb_bytes(..., razitka=True)`, `api/stul_razitka.py`; veřejný generátor a košík bez nich) – `docs/STUL_ZASLEPKY_A_RAZITKA.md`.",
    "a **razítka loga jsou na všech 3D modelech generátoru** – živý model, košík, nabídka, karta (WORKFLOW pravidlo 61, Robert 2026-10-08; `stul_glb.model_pro_parametry` má razítka výchozí, `api/stul_razitka.py`) – `docs/STUL_ZASLEPKY_A_RAZITKA.md`.")])

uprav("docs/STUL_ZASLEPKY_A_RAZITKA.md", [
    ("## 2) Razítka loga v modelu online nabídky (Robert přes bot5 / bot9, 2026-10-06; pravidlo 2026-09-06: razítkování = stupeň 2 = model v nabídce)",
     "## 2) Razítka loga na VŠECH 3D modelech generátoru (Robert přes bot5 / bot9, 2026-10-06 pro nabídku; od 2026-10-08 VÝCHOZÍ všude – WORKFLOW pravidlo 61: „razítka budou na všech 3D modelech ve všech generátorech“)"),
    ("`stul_shop.glb_bytes(selection, system=30, razitka=False)` → `stul_glb.model_pro_parametry(parametry, razitka=True)` → `api/stul_razitka.py`. **Veřejný generátor a košík beze změny** (výchozí `razitka=False`;\nmodel s razítky má vlastní cache). Zapnout ho má jen `nabidka_z_konfigurace._zakaznicky_glb` (bot5).",
     "`stul_glb.model_pro_parametry(parametry, razitka=None)` → `api/stul_razitka.py`; `None` = výchozí nastavení generátoru `RAZITKA_VYCHOZI = True` (živý model `/api/shop/configurator/glb/<token>` a tím i košík a odkaz na konfiguraci,\nnabídka, karta `STUL-S…`, staff `/api/stul/model.glb`; stejně `stul_shop.glb_bytes(…, razitka=None)` a `konfigurator_registr.glb_bytes`), `razitka=False` = holý model (testy geometrie, srovnání). Model s razítky a bez nich mají každý svou cache\na komprimovaná cache (`zakoduj_pro_klienta`) se klíčuje i délkou dat; vedlejší cache (posun, rozsahy dílů, extra rozsahy) jsou společné – razítka žádný díl neposouvají, takže uchyty ve 3D, payload luxů a živé tažení\nfungují nad modelem s razítky stejně. Hash konfigurace, `RULES_VERSION`, cena, kusovník a odpovědi API se nemění (razítka jsou jen v GLB). Váha: +~0,52 MB surově (jeden sdílený mesh loga, nezávisle na počtu razítek),\npo brotli +~115 KB, skládání +30–60 ms. Test a regrese bit po bitu: `scripts/2026-10-08_razitka_generatory/` (873 konfigurací, systémy 30 / 35 / 40 / 41 / 45)."),
])

uprav("docs/KONTRAKT_KONFIGURATOR_UI.md", [(
    "- **Komprese modelu GLB** (bot8 2026-10-04, Robert: „model stolu se tam načítá dlouho“):",
    "- **Razítka loga na modelu** (WORKFLOW pravidlo 61, Robert 2026-10-08: „razítka budou na všech 3D modelech ve všech generátorech“): GLB z `GET /api/shop/configurator/glb/<token>` (a staff `/api/stul/model.glb`) nese ochranné logo LOGIMAN.CZ na profilech stolu "
    "(u všech systémů 30 / 35 / 40 / 41 / 45; 2–19 razítek podle stolu): jeden sdílený mesh loga + instance uzlů na KONCI seznamu uzlů, pod logem vyplněná drážka v materiálu hliník. `scenes[0].extras.v3d` (box, kóty, čelo, pohyby) a indexy dřívějších uzlů zůstávají "
    "beze změny, loga vyčnívají z boxu nejvýš o 3 mm (relief); hash, `rules_version`, cena i ostatní odpovědi API se nemění; velikost +~0,52 MB surově (+~115 KB po brotli). Klient nic nedělá. Holý model (`razitka=False`) jen interně.\n"
    "- **Komprese modelu GLB** (bot8 2026-10-04, Robert: „model stolu se tam načítá dlouho“):")])
