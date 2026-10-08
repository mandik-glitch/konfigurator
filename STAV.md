# STAV.md — digest projektu konfigurátor

**Aktualizuj při každém handoveru / konci úkolu — nikdy nenech zastarat.**
Nový bot čte TENHLE soubor MÍSTO celého `AGENTS_LOG.md` (ten zůstává jako
chronologická historie, ne úvodní čtení). Zdroj pravdy pro detail: `scripts/handover.py dump`.

## 1) Co je živě

- **Stack**: Flask (`api/app.py`) + gunicorn 4 workery (bez `--preload`) na unix socketu
  `/opt/konfigurator/api/konfigurator.sock`, nginx reverse proxy
  (`/etc/nginx/sites-available/logiman-autovestavby` = veřejná doména
  `autovestavby.logiman.cz` [vlastní cert, bot10 2026-09-06], `konfigurator`
  = IP vhost `75.119.132.164:8090`, oba mimo git). **`vandrawee.cz` už
  NENÍ naše doména** (bot9/bot10, 2026-09-06) - DNS zrušena a doména navíc
  přešla pod samostatný nový projekt `/opt/vandrawee` (Unity/Laravel test
  instance), vhost `vandrawee` teď servíruje JEHO obsah, ne náš. `PUBLIC_BASE_URL`/
  `APP_BASE_URL`/`CAPTURE_BASE_URL` (`api/app.py`/`api/.env`) přepsány na
  `autovestavby.logiman.cz` - viz `AGENTS_LOG.md` pro kompletní seznam míst.
  DB = MySQL **lokálně na tomtéž VPS** (`api/.env` `DB_HOST=127.0.0.1`,
  db `konfigurator_v3`) — ověřeno přímo 2026-09-30, starší záznam
  `80.211.73.226` byl zastaralý (Forpsi cutover proběhl už 2026-09-09,
  viz `TASKS.md` archiv). Vždy čti `DB_HOST` čerstvě z `api/.env`,
  nespoléhej na starší zápisy.
- **Nasazení kódu `api/*.py` (od 2026-10-01, bot16)**: neresetuje se ad hoc. Commitnuté změny
  jdou ven samy 2× denně (0:00 a 12:30 Europe/Prague, `konfigurator-nasazeni.timer`) bez výpadku -
  gunicorn HUP: žádný požadavek nespadne, ~4 s pauza obsluhy. Necommitnutá změna v `api/*.py`
  plánované nasazení zablokuje. `scripts/restart_konfigurator.sh --stav` ukáže, kdy půjde tvůj commit
  ven; `--reload` je výjimka pro nalehavou opravu (zná ho Robert nebo bot s jeho povolením), tvrdý
  restart zůstává jen pro `api/.env` a změnu unitu. Dashboard → panel „Nasazení serveru". Časovač
  je zapnutý od 2026-10-01 10:45 (Robert), první běh OK (obsluha stála 4,6 s, 0 z 52 požadavků selhalo,
  vypnout: `systemctl disable --now konfigurator-nasazeni.timer`). Po nasazení ověř
  endpoint, který se měnil (pravidlo 33), ne jen `/api/health`. Detail: hlavička `scripts/nasazeni.py`.
- **nginx po změně vhostu**: záloha configu do scratchpadu → `nginx -t` →
  `systemctl reload nginx`. Nebylo v této session ani jednou blokováno
  sandboxem (ani reload nginx, ani `systemctl daemon-reload`/`enable`
  pro nové jednotky v `deploy/`).
- **`ram-watchdog.service` na TOMTO VPS (Contabo, vmi3540839) NEEXISTUJE**
  (`SERVER_RAM_WATCHDOG.md` popisuje jiný, starší server) - `/run/ram-watchdog-alert`
  nikdy nevznikne, žádná automatická ochrana proti paralelnímu RAM náběhu víc botů.
- **Zámek/BOT_ID/commit disciplína**: detail v `WORKFLOW.md` (git/zámek sekce) -
  nekopírovat sem, ať se to nerozejde na dvou místech.
- **`scripts/handover.py`** (nový nástroj, tabulka `bot_handover`) - `add`/`list`/`show`/`dump`/`close`.
  Používat pro předání session navíc k `AGENTS_LOG.md`.
- **QA běhy jsou VYPNUTÉ od 2026-10-04** (Robert; časovače `konfigurator-qa` a
  `konfigurator-qa-audit` disabled). Kód `scripts/qa/run_all.sh`, `api/qa_checks.py` a tlačítko
  v adminu (Dashboard → "QA běhy") zůstávají pro ruční spuštění. Zapnout zpět:
  `systemctl enable --now konfigurator-qa.timer konfigurator-qa-audit.timer`.
- **nginx `access.log` má vlastní `log_format konf_ext`** (mimo git) -
  `scripts/qa/logs.py` filtruje 404/5xx jen na konfigurátor a počítá p95.
- **POZOR na `webapp/katalog/`**: nginx servíruje aliasem přímo z
  pracovního stromu — jakákoli změna GLB je živá pro zákazníky okamžitě,
  bez ohledu na commit. Riziko je naopak v necommitnutém stavu.

## 2) Skladové karty sestav — standing pravidla

- Struktura je **karta na VOZIDLO, ne na sestavu** (WORKFLOW.md pravidlo 26)
  — verze/provedení téhož vozu se přidávají na tutéž kartu, ne novou.
- **Názvy provedení jdou ven přes `pdAssemblyLabel`** (`webapp/product.html`).
  Ořez `[hranatých závorek]` a `K-XXX` je TRVALÁ pojistka, neodstraňovat —
  hlídají to i kontroly `k_kod_v_zakaznickem_textu` a
  `interni_poznamka_v_zakaznickem_textu`.
- **Veřejné stránky vracejí poctivou 404** místo prázdné stránky s 200 u
  skrytého produktu/kategorie (`api/storefront_pages.py`). Hlídá QA kontrola
  `ssr_slug_route_without_visibility_filter`.
- Aktuální SKU/`kod_sestavy` formát, číselníky (`regal_typologie`,
  `regal_umisteni`, `karoserie_verze`, `horni_blok_varianty`) a otevřené
  otázky kolem sestav: `PLAN_TVORBY_SESTAV.md` (živý, jen bot3 zapisuje).

## 3) RBAC / opravnění (admin panel) — přestavěno 2026-09-29/30

- **3 vrstvy MUSÍ sedět spolu**, jinak vzniká tichá díra (nalezeno 3x
  nezávisle za jeden večer): (1) backend `@require_permission(section,
  action)` v `api/*.py` — skutečné vynucení dat; (2) `TAB_SECTION`
  (`webapp/admin.html`) — která záložka se vůbec zobrazí dané roli;
  (3) `DASHBOARD_PANEL_SECTION` (`webapp/admin.html`) — jemnější gating
  uvnitř záložky Dashboard (8 namixovaných panelů). Přidáváš-li novou
  záložku/panel, **zkontroluj všechny 3**, ne jen tu, kterou zrovna píšeš.
- **`kategorie_obsah`/`ceny_prislusenstvi`/`produkty_sklad`** (staré
  3 široké sekce) rozseknuty na **15 granulárních** (1 sekce ≈ 1 záložka)
  — viz `PERMISSION_SECTIONS` v `api/app.py`, kompletní mapování
  `grep -n "granularni" AGENTS_LOG.md`.
- **`renderAreaSwitch()`** (zkopírovaná v 5 souborech —
  index/category/product/blok/realizace.html) řídí odkaz "Administrace"
  v hlavičce podle `permissions` (z `/api/auth/me`), NE podle
  `role === "admin"` — zkopíruješ-li vzor pro 6. stránku, nepoužij starou
  natvrdo-admin variantu.
- **Robert si `role_permissions` živě upravuje sám přímo v UI** (Role a
  opravnění) — necti žádný starší zápis/paměť jako aktuální stav rolí,
  vždy `SELECT * FROM role_permissions WHERE role=...` čerstvě.
- **Sandbox na zápis do `role_permissions`**: nekonzistentní (na rozdíl
  od `app_settings`, které blokuje spolehlivě) — úzký jednořádkový
  UPDATE prošel, širší DELETE+multi-INSERT zablokován. Zkus přímo dřív,
  než to rovnou hodíš na Roberta.
- Detail/historie nálezů: `AGENTS_LOG.md` (`grep -n "bot16" `, sekce od
  2026-09-29 večer), `scripts/handover.py show 408`.

## 4) Render/výroba pipeline — automaty a jejich mezera

- **`production_work_claims.py::blokovano()`** (bot4 2026-09-30) místo pevného „po 3 selháních navždy vzdát"
  (`fail_count_of(...) >= MAX_FAIL`, přes které automat při DOČASNÉ příčině - pauza renderu, výpadek, neplatný panel -
  položku tiše vyřadil napořád): po `max_fail` selháních počká 30 min, pak 1 h, 2 h … max 24 h a zkusí znovu.
  Použité v `2026-09-14_render_auto_dispatch.py`, `2026-09-23_vandr_render_auto_dispatch.py` i `2026-09-11_watchdog_prace.py` (bot5 2026-10-02).
  Test: `scripts/2026-09-30_render_panel_testy/test_opakovani_automatu.py`.
- **Nabídky/testy ze scény** (bot4 2026-10-01, `PRODUKTOVE_RENDERY.md`): `ucel: "nabidka"` → Omen (online/Blender ≥ 5.2/volný,
  jinak Logiman2; pro automat **vyhrazený**, `RENDER_NABIDKY_STROJ`) a **vzhled jako karty** = job `turntable` z `recipe` dílů
  (`api/nabidka_kartova_cesta.py`, šablona+HDRI+panel; selže-li cokoli, stará cesta GLB; `job_type=None` při done - lepivý klíč).
- **`scripts/2026-09-17_card_auto_link.py`** (timer 15 min) — STANDING
  mechanismus "schválená sestava (`technicky_ok=1`) → karta
  (`shop_product_id`)" UŽ EXISTUJE, nestavět znovu. Má safety-gate: první
  auto-založená karta NOVÉ typologie čeká na Robertovo vizuální schválení
  (`bot_ukoly`, tag `AUTO_TEMPLATE_APPROVAL:typologie_kod=X`), dokud není
  hotovo, další karty stejné typologie se nezakládají — než hlásit "karty
  nevznikají", zkontroluj `bot_ukoly WHERE hotovo=0` na tenhle tag.
- `konfigurator-qa.service` je vypnutá spolu s QA (2026-10-04), `send_alert.py` se neopravuje.
  `konfigurator-kolize-uhelniky.service` opraven
  2026-10-02 (`63538531`; padal od 17. 9. na pantu `product_3219`, 3 meshe — parser/pojistka
  sweepu; běží, 530 sestav změřeno). `systemctl --failed` na začátku session je levná kontrola.

## 5) Platby a objednávky — gotchas (2026-09-29/30)

- **`shop_orders.payment_received_total_czk` musí být GROSS (vč. DPH)**,
  stejná jednotka jako `total_czk` — VŠECHNA porovnání (`admin_documents_
  list`, badge v `objednavky-doklady.js`) to tak už čekala, ale 2 zápisová
  místa (`bank_statements.py`, `documents.py::admin_documents_mark_
  payment_received`) tam dlouho přičítala NET. Opraveno (`702b2182`) a
  hlídá to nová QA kontrola `order_payment_received_mismatch`
  (`api/qa_checks.py`) — porovnává se součtem skutečně vystavených VDD.
- **Nové tabulky: `COLLATE utf8mb4_0900_ai_ci`, NE `_unicode_ci`** — pár
  starších migrací (např. `sestava_typ.sql`) používá `_unicode_ci`, ale
  zbytek DB (`shop_customers`, `shop_orders`…) běží na `_0900_ai_ci` —
  mix collations shodí JOIN hned při prvním ostrém použití ("Illegal
  mix of collations"), zjištěno živě na nové `shop_customer_addresses`.
- **`scripts/2026-09-22_vandr_fbx_watcher.py`**: INSERT nové VD-% karty
  nezapomeň na `price_visible_default=0` (DEFAULT tabulky je `1`) — 11
  karet z 27.-30.9. to nemělo (chybí hover efekt na e-shopu), opraveno
  `3887cedb`, ověřeno na celé VD-% populaci (343/343 teď jednotně).
- **Dealeři (bot5, živě od 2026-10-02 12:30):** `DEALER_API.md`, `api/dealer*.py`, objednávka
  dealera = `order_path='dealer'`; nová tabulka s `product_id` → `product_duplicate.py`.
- **Mini-shop SK (bot5, 2026-10-03):** `baliace-stoly.top` JE ŽIVÝ (kategorie, produkt, konfigurátor, ceny v EUR bez DPH = Kč × kurz Fio + marže 0 %, poptávka jen firmám, právní dokumenty). NASAZENO v kódu (API po HUP): konfigurace v košíku/objednávce, ceny EUR (`api/miniweb_cena.py`), sada „objednavky“ = `POST /api/miniweb/quote|orders|vat-check` (objednávka hosta, fakturační i dodací adresa, Toptrans odhad, VIES, DPH 0 % u platného IČ DPH, k úhradě v Kč = EUR × kurz), `POST /api/admin/orders/<id>/shipping` (schválení dopravy → záloha), původ v admin přehledu; objednávky ZA PŘEPÍNAČEM `orders_enabled` (zapnout `miniweb_shop.py --orders on --apply`). Čeká: sady `doklady` (DPH 0 % + doložka, k potvrzení účetní) a `adminmw` (admin API Mini-shopy + RBAC pro bot16), `nasad_cekajici_bot5.sh doklady|adminmw`; hmotnosti dílů stolu (4933 4930 4931 4929 4932 4928 4916 3025) a SK tarif Toptrans (SK PSČ = pásmo 700 km); nové právní texty bot7 (cf2532e3) importovat AŽ současně se zapnutím objednávek. Detail: `scripts/2026-10-03_miniweb_objednavky_testy/nasazeni/README.md`.

## 6) Kde hledat víc

- `scripts/handover.py dump` (nebo `list --project konfigurator`) - aktuální
  stav/paměť jednotlivých botů, strukturovaně, nejnovější první.
- `TASKS.md` - otevřené úkoly (task board), sekce "Hotovo" pro kontext.
- `AGENTS_LOG.md` - chronologická historie ("co se stalo"), starší v
  `AGENTS_LOG_ARCHIVE_do_*.md` (`grep -n "výraz" AGENTS_LOG*.md` prohledá obojí).
- `scripts/qa/README.md` - QA framework kontrakt a jak přidat suitu.
- `WORKFLOW.md` - git/zámek disciplína, "AKTIVNÍ POKYNY OD ROBERTA".
- `MAPA_3D_A_GENERATORU.md` - generátory stolů 01–05 (systémy 30/35/40/41/45 „Robustní“), zlomové míry po systémech, Vzhled online nabídek (bot10 2026-10-07).
