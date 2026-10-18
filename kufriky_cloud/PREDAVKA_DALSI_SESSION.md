# Předávka pro další session (cloudový bot „Karel“), stav 2026-10-12

Větev: `cloud/kufriky-vlastni-cloud` (do `main` NIKDY nepushovat bez výslovného pokynu Roberta). Poslední commit k datu zápisu: viz `git log`.
Robert píše česky, stručně, čte z mobilu; chce viditelný malý výsledek brzy, ne hotový koncept až na konci. Souborů typu .html se v chatu neukazují jako stránka, proto se posílají jako soubor ke stažení (SendUserFile) a na web je nahrává bot9 (autovestavby.logiman.cz/nahled-bot9/).

## Pravidla od Roberta (platí trvale)
- Fotografie výrobců jen ke čtení/měření, do repa se NEUKLÁDAJÍ (jen URL v `fotky_url*.tsv`). Stahují se do scratchpadu.
- Modely kufrů: ZAVŘENÁ verze a VNĚJŠÍ pohled; vnitřek může být hladký (doděláme později). Obálka GLB musí odpovídat katalogovým rozměrům (±1 mm, kontroluje `vytvor.mjs`).
- Vždy poctivě napsat, co je změřené, odhad a neověřené. IoU obrysu NENÍ ověření rozměrů (při obrysu z téže fotky je to jen shoda s fotkou).
- Výběr kufrů není podle prodejnosti (prodejní čísla nejsou veřejná; Makita/DeWalt jen nepřímo podle zbozi.cz). Nic nevymýšlet.
- Cena, jména výrobců z fotek, vymyšlené viditelné názvy: ne. Žádné „mutační testy". Nic nenasazovat, nesahat na DB/produkci; zápis do DB jen na výslovný pokyn.
- Stop-hook vyžaduje commit+push nepushnutých souborů (jinak hlásí chybu); při běžících agentech se commituje jako WIP.
- Ukončení: když Robert napíše „stop / čekej na pokyn", nic dalšího nespouštět.

## Hotové (vše v repu, větev výše)
- 5 organizérů Milwaukee PACKOUT: `kufriky_cloud/` (generátor `jadro/`, `render/`, `nastroje/`, `organizer_<SKU>.mjs`, `modely/*.glb`, `nahled/`, `srovnani/`, `zdroje/*_poznamky.md`, `POSTUP.md`, `README.md`).
- Stůl balení z PDF (40×40 profily, do kontrolní scény): `stul_balici/` (zapsáno v DB jako custom_shapes #592 botem9; polohy lamina 4933 opraveny jen v DB).
- Válečková dráha PL-601F_WS: `dily_cloud/valeckova_draha_PL-601F_WS/` (nahled.html předán botu9 k hostování, nepotvrzeno).
- Kufry Hilti (10): ProKit 2437394, 2437354, 2437355, 2437399, 2441669 a pro vrtačky 2284143, 2273022, 2294834, 2329229, 2329206: `kufry_hilti/` (kufr_<číslo>.mjs, p<číslo>_*.mjs, `vytvor.mjs <číslo>`, `modely/`, `nahled/`, `zdroje/<číslo>_poznamky.md`, podklady `kufriky_hilti.csv`, `vrtacky_hilti.csv`, `README*.md`).
- Kufry Makita MAKPAC Typ 1–4 (8215495/8215500/8215518/8215526): `kufry_makita/` (jeden parametrický generátor `makpac*.mjs`).
- Kufry DeWalt: TSTAK DWST83346/83345 (`tstak_*.mjs`, `vytvor_tstak.mjs`), ToughSystem DS300/DS400 DWST83294/83342 (`ts2_*.mjs`, `vytvor_ts2.mjs`) v `kufry_dewalt/`.
- Nevynecháno záměrně: Makita organizér s krabičkami 191X80-2 a DeWalt DS450 (kolečka, výsuvné madlo, málo fotek).
- Srovnání foto vs. model (jen vlastní rendery + json, bez cizích fotek): `kufriky_cloud/srovnani/<kód>/`.
- Materiály přidané do `kufriky_cloud/jadro/glb.js`: `tyrkys`, `zluta`, `seda_svetla`.
- Řady euroboxů pro bota10: `dily_cloud/eurobox_rady/` (`eurobox_rady.py` – `postav`, `kopie_rady`, `min_vyska_patra`, `max_pocet_boxu`; `test_eurobox_rady.py`, `nahled.html`, `ODVOZENI.md`, `dily/katalog/product_<karta>.glb`, `dily/5276.glb` ze STEPu).

## Otevřené
- Řady euroboxů: Robert řekl botu10 „skladby boxů OK, válečkové dráhy mám špatně“ a NEŘEKL co. Bot10 zapojí zatím jen boxy; dráhy čekají na opravu. Nejdřív zjistit od Roberta konkrétně co (jedna krátká otázka s obrázkem, ne hádat). Otevřené body z geometrie jsou v `ODVOZENI.md`: kapsa koncovky 5282 pod předkem boxu (průnik), nožka jen 3,8 mm na válečku 5276, ucho 5275 o 1 mm nad válečky, spojení modulů, střední podpora dlouhých drah, výchozí dráha (zatím 5276), strop řady 20 m (hotovo).
- Hostování náhledů: bot9 nahrává přes `autovestavby.logiman.cz/nahled-bot9/`; poslední pokus zablokovala bezpečnostní kontrola v jeho „auto“ režimu (je potřeba Shift+Tab nebo nová session bota9). Nepotvrzeno, že je hostovaný kufr Hilti 2437394 ani opravená válečková dráha.
- Nahrání modelů do scény/Vlastních tvarů/DB: nic neděláno, jen na výslovný pokyn.
- Hilti SF 6/SF 4/TE 6-22: tvar víka/pantu odvozen z kufru 2-tools (jedna generická čelní fotka) – nízká přesnost.
- DeWalt DS400: fotka c01 neodpovídá výšce 408 mm (model drží datasheet).
- Zbývá případně: vnitřky kufrů, kontrola dalších kufrů nad rámec vlny 1–2.

## Technické poznámky
- Cloudový kontejner: `pip install cadquery-ocp` funguje (čtení STEP, skripty `/tmp/stepocc.py`, `dily/step_na_glb.py`); katalogové GLB jsou veřejně na `https://autovestavby.logiman.cz/katalog/product_<karta>.glb` (curl funguje; zápis na server ne). Náš `readGLB` (`jadro/glb.js`) čte jen vlastní GLB, katalogové ne.
- Scratchpad s fotkami (`.../scratchpad/hilti/foto`, `kufry2/<číslo>`) se po skončení session ztratí; fotky lze znovu stáhnout podle URL v `kufry_hilti/fotky_url*.tsv`, `kufry_makita/fotky_url.tsv`, `kufry_dewalt/fotky_url.tsv`.
- Renderování: Playwright + three.js swiftshader (`kufriky_cloud/render/render.mjs`), kamera z ručně změřených bodů (`kalibruj.py`, `fit_lm.mjs`); volný odhad kamery na těsně oříznutých fotkách degeneruje (IoU zdánlivé).
- Pravidlo z `CLAUDE.md` projektu: před prací zjistit `$BOT_ID`/specializaci (u cloudové session se nezjistí; řešit podle pokynů Roberta), číst `WORKFLOW.md`, `TASKS.md`, `STAV.md`; do `AGENTS_LOG.md` se zapisuje jen na pokyn.
- Spolupráce: bot9 (hosting, DB zápisy), bot10 (Generátor konstrukcí Dynamic, přebírá `dily_cloud/eurobox_rady/`; zpětný kanál ke mně jen přes zprávy/GitHub).

## 3D prohlídka všech modelů (2026-10-18)
Nástroj `kufriky_cloud/nastroje/zabal_prohlidku.mjs` + šablona `kufriky_cloud/prohlizec/prohlidka.html` vyrobí jeden samostatný HTML se všemi modely skupiny (výběr, šipky, víka/zásuvky/madla, řez). Výstupy (HTML jsou velké, nejsou v repu): `node nastroje/zabal_prohlidku.mjs <out.html> --titulek "…" <složky s modely oddělené čárkou> --jmena <csv…>`; složky: `kufriky_cloud/modely`, `kufry_milwaukee_opravy/modely`, `kufry_hilti/modely`, `kufry_makita/modely`, `kufry_dewalt/modely`.
