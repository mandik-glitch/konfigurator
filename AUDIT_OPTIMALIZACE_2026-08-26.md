# Audit optimalizace procesů — 2026-08-26

Zadání: Robert přes bot3 (koordinátor), hloubkové šetření CELÉHO backendu
konfigurátoru (~31 modulů importovaných v `api/app.py`, řádky 9331+).
Souběžně stejný audit běží na sesterských projektech Toscanaccio a
vybaveni-uzitkovych-vozidel, každý projekt má vlastního bota, žádné
překrývání. Provádí bot10.

**Charakter tohoto dokumentu: AUDIT, NE úpravy.** Žádný z nálezů níže
nebyl opraven v rámci téhle práce — jde čistě o report s návrhem řešení,
rozhodnutí o dalším postupu je na Robertovi/bot3.

Metodika: per modul — živý stav přes DB (počty řádků, poslední aktivita),
výkon (neindexované dotazy, N+1, velké payloady), chyby/křehkost (holé
except, TODO/FIXME), duplicity mezi moduly, ruční kroky k automatizaci,
soulad s `WORKFLOW.md` (zejména bod 11 "standardní přehledová obrazovka",
bod 16 "žádné automatické e-maily bez schválení").

Práce probíhá po skupinách ~10 modulů, průběžně committováno.

---

# Skupina 1/3: e-shop core (customers, documents, purchase_orders, emails, system_emails, gallery, gallery_items, products, orders, cart)

Rozsah: `customers.py`, `documents.py`, `purchase_orders.py`, `emails.py`,
`system_emails.py`, `gallery.py`, `gallery_items.py`, `products.py`,
`orders.py`, `cart.py`. Pravidla ověřena proti `WORKFLOW.md` (bod 11
„standardní přehledová obrazovka", bod 16 „žádné automatické e-maily",
bod 19 VDD). Živá DB ověřena přes `systemd-run ... EnvironmentFile=api/.env`.

## Živý stav DB (souhrn, 2026-08-26)

| Tabulka | Řádků | Poslední aktivita |
|---|---|---|
| `shop_customers` / `app_users` | 3 / 6 | 2026-08-21 |
| `shop_documents` | **0** | — |
| `shop_emails` | 1 | 2026-08-24 |
| `shop_purchase_orders` / `_items` | 1 / 1 | 2026-08-24 |
| `shop_suppliers` | 41 | 2026-07-31 |
| `system_emails` | **0** | — |
| `shop_gallery_images` | 226 | 2026-07-25 |
| `content_gallery_items` | 5 | 2026-08-08 |
| `shop_products` | 739 | 2026-08-23 |
| `shop_product_documents` / `_coupons` | 0 / 0 | — |
| `shop_stock_movements` | **0** | — |
| `shop_orders` / `_items` | 39 / 150 | 2026-08-22 |
| `shop_order_status_history` | **0** | — |
| `shop_cart_items` | **0** | — |

Zjištění: `documents.py` (1608 řádků) obsluhuje tabulku, která je aktuálně
**prázdná** — 39 objednávek existuje, ale ani jeden doklad. `purchase_orders.py`
má jen 1 živou objednávku. `shop_stock_movements`/`shop_order_status_history`
prázdné navzdory tomu, že `orders.py` do nich za určitých přechodů zapisuje —
nasvědčuje to, že objednávky zůstávají většinou ve stavu `nova` a
skladové/historické větve kódu jsou v produkci prakticky nevyzkoušené.
Vzhledem k testovací fázi (bod 18) to nemusí být bug, ale je to riziko pro
produkční cutover — tyhle cesty kódu nemají živé pokrytí.

---

## customers.py

1. **Hard delete zákazníků/účtů — porušuje WORKFLOW.md bod 11.2** (`api/customers.py:689,751,790,1037`).
   `admin_customers_delete_one/_delete_all/_bulk_delete` dělají `DELETE FROM app_users`
   (kaskádově smaže `shop_customers`); `shop_customers` navíc nemá vůbec
   žádný `is_active`/archivační sloupec — soft-delete infrastruktura zde
   chybí úplně. **Vysoká závažnost** — jde o standardní evidenci zákazníků,
   přesně cílovku bodu 11. Návrh: doplnit `is_active` na `shop_customers`,
   hard-delete tlačítko přesunout za výslovné schválení Robertem případ od
   případu (dle bodu 11.2, „trvalé smazání jen na výslovnou žádost").
2. `SELECT *` na `shop_customers`/`shop_customer_groups` (`api/customers.py:407,617,962`)
   — tabulky jsou malé, nízká závažnost, jen k evidenci.
3. Bez `except`/TODO nálezů — modul je v tomto ohledu čistý.
4. Audit log pokrývá 11/17 endpointů — dobrý poměr.

## documents.py

1. **Hard delete daňových dokladů/faktur — nejzávažnější nález celého auditu**
   (`api/documents.py:1129,1179,1227,1262`, funkce `_unlink_and_delete_documents`).
   `DELETE FROM shop_documents` trvale maže vystavené faktury/VDD/dodací
   listy včetně kaskádového mazání navázaných `shop_emails` a zpětného
   vrácení `payment_received_total_czk`. Vlastní komentář v kódu přitom
   doklad označuje jako „neměnný snapshot" — přesto je plně mazatelný.
   Přímo v rozporu s bodem 11.2 (nikdy hard delete, jen archivace) a
   rizikové vůči bodu 19/účetní stopě. Historicky šlo o výslovné Robertovo
   zadání (2026-07-26, 2026-08-01/02), ale předchází current WORKFLOW.md
   bodu 11 (2026-08-21) a nebylo od té doby přehodnoceno. **Vysoká
   závažnost.** Návrh: probrat s Robertem, zda u vystavených dokladů
   nahradit hard-delete stavem „stornováno"/archivací místo fyzického
   smazání.
2. **Zastaralý/matoucí docstring o automatickém odesílání**
   (`api/documents.py:342-343`, `_auto_email_after_issue`: „AUTOMATICKY
   posle e-mail... zákazníkovi"). Skutečná implementace
   (`emails.send_document_email_auto` → `send_and_log(..., auto=True)`)
   korektně loguje jako `pending` a čeká na schválení admina (viz
   `api/emails.py:178-187`) — kód je v souladu s bodem 16, ale komentář lže
   o chování. Nízká závažnost, ale riziko, že to příští bot přečte doslovně
   a udělá regresi. Návrh: přepsat docstring na „zařadí do fronty ke
   schválení".
3. **Velký payload v seznamovém endpointu** (`api/documents.py:829-832`,
   `admin_documents_overview`) — `SELECT d.*` z `shop_documents`, která má
   4 JSON sloupce (`recipient_snapshot`, `delivery_snapshot`,
   `items_snapshot`, `vat_breakdown`) + `note text`. Stránkovaný seznam
   (50 řádků/stránka) pro admin tabulku pravděpodobně nepotřebuje plné
   JSON snapshoty. Střední závažnost. Návrh: explicitní sloupcový výběr
   pro list, JSON dotahovat jen v detailu/PDF.
4. Bare `except Exception: pass` (`api/documents.py:112,347`) — u fontu
   (neškodné) a u `_auto_email_after_issue` (záměrně, ale bez logu — viz
   společný nález níže).
5. List/overview endpoint (`admin_documents_overview`) je vzorově kompletní
   dle bodu 11 (filtr na typ/text/datum, stránkování, counts) — pozitivní
   kontrast k modulům níže.

## purchase_orders.py

1. **Hard delete nákupních objednávek i dodavatelů** (`api/purchase_orders.py:233,838-841`)
   — `admin_suppliers_delete` kaskádově maže i všechny PO dodavatele
   (`_delete_one_purchase_order`), žádný `is_active` na
   `shop_suppliers`/`shop_purchase_orders`. Stejný vzorec jako u
   customers/documents, stejné doporučení (bod 11.2). Střední-vysoká
   závažnost (aktuálně jen 41 dodavatelů/1 PO, ale roste).
2. `SELECT *` na `shop_purchase_orders`/`_items`/`shop_suppliers` na více
   místech (řádky 126,143,368,373,411,522,591,651,939,967) — u
   `note`/`admin_note`/`supplier_address` textových polí nízká závažnost.
3. `except Exception` bez logu do aplikačního logu (679,771,884) — chyby
   jdou jen do HTTP odpovědi/`str(e)`, žádné `logger.exception`. Nízká-
   střední závažnost — ztížené dohledání příčiny při produkčním incidentu.
4. List endpoint (`api/purchase_orders.py:505-535`) je správně stránkovaný
   s filtrem na status/text — v souladu s bodem 11.

## emails.py

1. **Modul je vzorově v souladu s bodem 16** — `send_and_log()`
   (řádky 154-214) explicitně větví `auto=True` → `status='pending'`,
   nikdy neposílá SMTP bez ručního schválení. Dobře zdokumentováno v
   docstringu.
2. **Hard delete historie e-mailů** (`api/emails.py:683,691-707`) —
   `DELETE FROM shop_emails` bez `is_active`. Na rozdíl od dokladů jde jen
   o log odeslání, ne o účetní záznam, ale pořád je to protokol o
   komunikaci se zákazníkem/dodavatelem — nižší závažnost než u dokladů,
   ale stejná nekonzistence s bodem 11.2. Komentář v kódu cituje Robertovo
   „mazat musí být všude!!" z 2026-07-26, tedy před zavedením bodu 11
   (2026-08-21).
3. `except Exception as e` (204, 250) — zalogováno do
   `shop_emails.error_message`, korektní, žádná ztráta informace.

## system_emails.py

1. Malý, čistý modul (126 řádků) — plně v souladu s bodem 16 (fronta
   `pending`→admin schvaluje, viz `api/system_emails.py:1-18,97-113`).
   Žádné nálezy vysoké závažnosti.
2. **„Postavená, ale mrtvá" funkce** — `system_emails` má 0 řádků v DB.
   Registrační ověřovací e-maily buď zatím nikdo nevyužil, nebo cesta
   `issue_email_verification` (v `app.py`) tuhle frontu v praxi nenaplňuje.
   Nízká závažnost, ale stojí za ověření, že se fronta skutečně používá.
3. Chybí `is_active`/archivace u `system_emails`, ale jde o frontu-log, ne
   evidenci — nízká relevance vůči bodu 11.

## gallery.py

1. **Hard delete obrázků + mazání souboru z disku** (`api/gallery.py:261-278`)
   — bez `is_active` archivace u `shop_gallery_images` (sloupec `active`
   existuje, ale mazací endpoint jej nevyužívá, dělá rovnou `DELETE`).
   Nižší závažnost než u obchodních dokladů (jde o mediální assety), ale
   technicky opět proti bodu 11.2 — vhodnější by bylo `active=0` + úklid
   souboru až při skutečném schválení retence.
2. `except Exception as e` (357) — kontext nekontrolován blíže, doporučuji
   ověřit, že se loguje.

## gallery_items.py

1. **N+1 při reorder** (`api/gallery_items.py:718-720`) —
   `for i, item_id in enumerate(ids): cur.execute(UPDATE...)` — jeden
   UPDATE na položku místo hromadného `CASE WHEN`/`UPDATE...JOIN`. Nízká
   závažnost (typicky málo položek na vlastníka).
2. Hard delete (399,432,748) bez archivace — `content_gallery_items` nemá
   `is_active`. Nízká závažnost (obrázky/přílohy, ne obchodní záznam).
3. Audit log pokrývá jen 5/11 endpointů — nižší poměr než ostatní moduly,
   stojí za doplnění na create/delete cestách.
4. `SELECT *,` (řádek 1002) v dynamicky skládaném dotazu — ověřit, zda
   cílová tabulka nemá zbytečně velké sloupce pro danou odpověď.

## products.py

1. **Hard delete produktů souběžně s existující archivační infrastrukturou
   — jasný rozpor s bodem 11.2** (`api/products.py:1250-1330`).
   `shop_products` MÁ `active`/`is_archived` sloupce a vlastní toggle
   endpoint (řádky 943-945), přesto existuje samostatné DELETE tlačítko
   (`shop_products_delete`, `shop_products_bulk_delete`), které řádek
   skutečně smaže z DB (s fallbackem na FK `IntegrityError` u produktů
   použitých v nákupní objednávce). **Vysoká závažnost** — tohle je modul,
   kde archivační mechanismus už existuje a hard-delete cesta ho prostě
   obchází. Návrh: hard-delete endpoint zrušit/omezit na skutečně osiřelé
   záznamy bez historie, běžné mazání směrovat na `is_archived=1`.
2. `shop_products.active` **nemá index** přestože je časté ve
   `WHERE active=1 AND is_archived=0` (řádky 75,335,377,751) — při 739
   řádcích zatím nevadí, ale je to kandidát na index před růstem katalogu.
   Nízká-střední závažnost.
3. Generátory testovacích dat (`api/products.py:1857,1919`) dělají N+1
   (`for _ in range(count): UPDATE + INSERT`) — omezeno na max 200
   iterací, admin-only nástroj, nízká závažnost, jen pro úplnost.
4. List endpoint (`api/products.py:193-220`) je naopak vzorový — explicitní
   sloupce (ne `SELECT *`), stránkování, filtr na text/SKU/nízký sklad/
   scénu, poddotaz na náhledový obrázek — nejlépe navržený modul z
   auditované sady.

## orders.py

1. **Hard delete objednávek včetně kaskádového smazání faktur/dokladů**
   (`api/orders.py:2269-2330`, `_delete_orders_cascade`) — `DELETE FROM
   shop_documents WHERE order_id IN (...)` a `DELETE FROM shop_orders`,
   přestože existuje řádný „soft" stav `zrusena` v
   `ORDER_STATUSES`/`ALLOWED_TRANSITIONS` (řádky 113-154). Modul má tedy
   DVĚ cesty jak „zrušit" objednávku — stavový přechod (soft) i fyzický
   DELETE (hard) — a hard-delete navíc trhá účetní doklady napojené na
   objednávku. **Vysoká závažnost**, přímo proti bodu 11.2 i duchu bodu 19
   (účetní doklady).
2. **Stav auto-transitions swallow chyby bez logu** (`api/orders.py:2078-2096,2110-2126`,
   `auto_confirm_after_confirmation_email`, `try_release_waiting_orders`) —
   `except Exception: return None/released` bez jakéhokoli
   `logger`/audit záznamu. Pokud automatické odbavení objednávek při
   naskladnění selže, nikde to nezanechá stopu. Střední závažnost —
   doporučuji přidat alespoň log/`log_audit` při selhání.
3. **N+1 vzory při potvrzení/zrušení objednávky** (`api/orders.py:951-954,1777-1819,2032-2058`)
   — per-položkový `SELECT stock_qty ...` a `UPDATE ...` v cyklu místo
   jednoho hromadného dotazu. Pro typickou objednávku s pár položkami
   nízká závažnost, ale při objednávkách s desítkami řádků naroste na
   desítky roundtripů do vzdálené DB.
4. **Zastaralý docstring o automatickém e-mailu** (`api/orders.py:2145`
   „Zákazníkovi se při změně stavu pošle e-mail (pokud je SMTP
   nastaveno)") — skutečnost je `_send_status_change_email` →
   `send_and_log(auto=True)` → fronta `pending`, ne přímé odeslání (stejná
   nekonzistence jako v documents.py, bod 2 výše). Nízká závažnost, ale
   matoucí pro budoucí čtení kódu.
5. `SELECT * FROM shop_orders` v paginovaném adminím seznamu
   (`api/orders.py:1300`) — `shop_orders` má 4 `text` sloupce
   (`delivery_address`, `billing_address`, `note`, `admin_note`),
   zbytečně tažené pro každý řádek přehledové tabulky. Nízká-střední
   závažnost.
6. Pozitivně: batch dotaz na napárované faktury k celé stránce objednávek
   najednou (`api/orders.py:1305-1318`) — explicitně zdůvodněno v
   komentáři jako prevence N+1, správně implementováno.
7. `pass  # e-mail o zmene stavu zamerne neposilame` (`api/orders.py:2129`)
   — komentářem odůvodněný záměrný no-op, ne bug.

## cart.py

1. **`admin_carts_list` bez stránkování/LIMIT** (`api/cart.py:478-497`) —
   `SELECT ... FROM shop_cart_items JOIN app_users JOIN shop_products` bez
   `WHERE`/`LIMIT`, načte VŠECHNY položky VŠECH košíků najednou a agreguje
   v Pythonu. Ostatní moduly (customers/orders/documents/purchase_orders)
   používají `get_pagination_args`+`paginated_query` — cart.py je jediný z
   auditovaných modulů s admin-seznamem, který tenhle vzor nedodržuje.
   Aktuálně 0 řádků, ale bez LIMIT je to škálovací riziko a nekonzistence
   s bodem 11.3. Střední závažnost.
2. Bez `except`/TODO/`SELECT *` nálezů, žádný hard-delete problém (košíky
   jsou dočasná data, ne evidence dle bodu 11).
3. Audit log jen 1/7 endpointů (`bulk-clear`) — u
   `cart_add_item`/`cart_update_item`/`cart_delete_item` chybí, ale jde o
   zákaznická vlastní data, ne admin akci nad cizí evidencí — nízká
   relevance vůči bodu 11.7.

---

## Napříč moduly — shrnutí systémových nálezů (skupina 1)

1. **Hard-delete vzorec opakovaný v 7 z 10 modulů** (customers, documents,
   purchase_orders, products, orders, emails, gallery/gallery_items) —
   všechny vznikly na explicitní Robertovo přání „mazat musí být všude!!"
   (2026-07-26) a navazující rozhodnutí z 2026-08-01/02, tedy PŘED
   zavedením bodu 11.2 (2026-08-21, „nikdy hard delete, jen archivace").
   Nejzávažnější dopad má u `documents.py` (mazání vystavených
   faktur/VDD) a `orders.py` (mazání objednávek i jejich dokladů) — tam
   jde o účetní/obchodní záznamy, ne jen pomocná data. Doporučuji jedno
   systémové rozhodnutí od Roberta, zda tahle starší rozhodnutí bod 11
   přepisuje, nebo jestli u dokladů/objednávek/zákazníků/produktů/
   dodavatelů nahradit hard-delete tlačítko archivací a hard-delete
   omezit na výslovné jednorázové schválení.
2. **Zastaralé docstringy tvrdící „automaticky se pošle e-mail"**
   (`documents.py:342-343`, `orders.py:2145`) — sám kód je od 2026-08-22 v
   souladu s bodem 16 (fronta `pending`), ale komentáře nebyly při té
   úpravě přepsané. Riziko špatného pochopení pro budoucí boty/lidi.
3. **Sdílená logika `reverse_and_delete_stock_movements`** (definována v
   `products.py:1734`, importována `documents.py`/`purchase_orders.py`) je
   správně sdílená, ne duplikovaná — pozitivní zjištění, žádný zásah
   nutný.
4. **Chybějící index `shop_products.active`** a `shop_customers.email`/
   `shop_orders.customer_email` — žádný z nich není dnes akutní (stovky,
   ne statisíce řádků), ale jsou to nejsnáze predikovatelní kandidáti při
   růstu dat.
5. **N+1 vzory soustředěné v orders.py/purchase_orders.py** kolem
   skladových pohybů a zpracování položek objednávky/PO — nikde
   katastrofické při dnešních objemech, ale stojí za refaktor při
   produkčním náběhu (bod 18 — testovací fáze nesmí snižovat nároky).

---

# Skupina 3/3: render/misc/remeslo (dimension_match_fbx, hdri, rendering_settings, blender_render, render_worker, inquiries, qa_audit, bank_statements, tracking, system_pipeline, remeslo)

Read-only audit, živý stav ověřen přes DB (`systemd-run ... EnvironmentFile=.env`,
hodnoty `.env` nikam nevypsány, jen SELECT dotazy). Žádné úpravy kódu/DB
provedeny nebyly.

## Nejzávažnější nálezy skupiny 3 (shrnutí nahoru)

| Závažnost | Modul:řádek | Nález |
|---|---|---|
| **Vysoká** | `remeslo.py:10983-10994, 11027-11038` | `send_email()` voláno přímo/synchronně na accept/decline veřejné nabídky - **obchází pending-frontu**, porušuje WORKFLOW.md bod 16 |
| **Vysoká** | `bank_statements.py:380-402` | "Ghost" VDD doklad při částečném selhání - INSERT dokladu proběhne, ale navazující UPDATE selže tiše (`print()`), doklad zůstane bez audit logu a bez e-mailové fronty |
| **Vysoká** | `dimension_match_fbx.py:187-266` | Robertem požadovaný endpoint "Převod" pro FBX rozklad nemá žádné UI tlačítko - nedosažitelný běžnou cestou |
| **Vysoká** | `inquiries.py` (celý modul) | 0 reálných odeslání za 18 dní provozu, formulář `poptavka-stul.html` nikde na webu neodkázán |
| **Vysoká** | `inquiries.py:50-70` | Auto-match do CRM leadu bez ruční opravné cesty při chybném spárování - porušuje ducha bodu 17 |

## dimension_match_fbx.py (345 řádků)

1. **`187-266` (vysoká)** - endpoint `POST /api/shop/products/<id>/decompose-fbx` je přesně funkce, o kterou Robert žádal ("uloz pod tlacitkem Prevod"), ale žádné tlačítko v `admin.html` ji nevolá (skladová karta má jen "Převod na GLB" → `/convert-to-glb`). Dosažitelné jen přímým API voláním. Návrh: doplnit tlačítko, nebo pokud záměr zanikl, endpoint odstranit a rozhodnutí zapsat.
2. **`187-266` vs `269-345` (střední)** - orphan endpoint navíc ukládá `parts` bez `_validate_custom_shape_parts`/`_validate_custom_shape_relations`, na rozdíl od druhého endpointu (313-319). Návrh: sjednotit na jednu validovanou cestu.
3. **celý modul (střední)** - žádné volání `log_audit` při vzniku `custom_shapes` záznamu, porušuje bod 11.7 (audit log na create). Návrh: doplnit `log_audit(...)` po INSERTu.
4. **`44, 240` (nízká)** - duplicitní `from collections import Counter` (top-level i uvnitř funkce).
5. **DB stav**: `custom_shapes` 339 řádků, poslední `created_at` 2026-08-23, ale žádný záznam neodpovídá výchozímu pojmenování z tohoto modulu - potvrzuje, že modul reálně nikdy nebyl použit.

## hdri.py (75 řádků)

1. **`63-75` (nízká/střední)** - `hdri_delete` je okamžitý hard delete bez potvrzení/archivace, formálně proti bodu 11.2. Vzhledem k technické (ne obchodní) povaze assetu nižší dopad. Návrh: buď explicitně vyjmout technické assety z pravidla 11, nebo přidat potvrzovací krok.
2. Žádné ošetření I/O chyb (`os.listdir`/`f.save`/`os.remove`), spadne jako neošetřená 500 - nízká závažnost.
3. Jinak čistý, malý, bez TODO, bez duplicit. Wired do `scene.html`.

## rendering_settings.py (240 řádků)

1. **`41-60` (nízká)** - `_detect_pbr_role` je čistá heuristika podle názvu souboru bez validace obsahu a bez viditelného varování v UI, když role zůstane nerozpoznaná.
2. Bezpečnostně kritický veřejný endpoint `public_rendering_file` (213-240) má správně omezenou kontrolu `folder_id` - bez nálezu.
3. Žádné bare except, žádné TODO. Živě používaný modul (`shared_drive_files` 939 řádků, aktivita dnes).

## blender_render.py (656 řádků)

1. **`114-126` (nízká/střední)** - `_cleanup_stale_jobs` se spouští jen reaktivně (při dalším renderu), ne na cronu/timeru. Reálně na disku leží 4 orphan soubory z 11.8. (15 dní staré) proti `JOB_RETENTION_S=3600s`. Návrh: zařadit do existujícího periodického QA/cron auditu.
2. **`152` (nízká)** - `_fail_orphaned_jobs_on_startup()` volaná jako top-level side effect při importu modulu, spustí se 2× (2 gunicorn workery). Návrh: přesunout do explicitní start-up funkce.
3. **`463-539` (nízká)** - 2 samostatná DB spojení otevřená za sebou místo sdíleného cursoru.
4. **`642-653` (nízká)** - celé PNG (přes 1 MB) base64 kódováno přímo do JSON odpovědi místo binárního endpointu.
5. Dobrá praxe: žádný bare except, všechny `except Exception` mají log + zápis do status souboru.
6. **Živý stav**: poslední render 11.8.2026 - 15 dní bez nové aktivity, pipeline momentálně nevyužívaná.

## render_worker.py (378 řádků)

1. **GPU worker heartbeat: offline 15 dní** (poslední heartbeat 11.8.2026 18:28, `WORKER_ONLINE_S=90s`). Nelze z auditu odlišit "nikdy nezapnuto" od "vypnuto" - doporučeno ověřit u Roberta relevanci funkce.
2. **`97-105` (střední)** - endpoint `/api/admin/render-worker/status` existuje, ale není volaný z žádného `webapp/*.html` - admin nemá v UI žádnou viditelnost stavu GPU workeru, jediná cesta zjištění je ruční čtení souboru na disku. Přímý kandidát na automatizaci.
3. Stale-detection/timeout mechanismus (`WORKER_CLAIM_TIMEOUT_S=25s`, `WORKER_NO_PROGRESS_S=240s`, `WORKER_RESULT_TIMEOUT_S=3600s`) je dobře navržený, vícevrstvý, vzniklý z reálně opravených bugů - bez nálezu.
4. **`110` (nízká)** - token porovnáván `==` místo `hmac.compare_digest` (teoretické timing-attack riziko, malá útočná plocha).
5. Žádné bare except, žádné TODO.

**Duplicity v render pipeline (5 modulů):**
- `system_pipeline.py:58-59` si hardcoduje `RENDER_OUT_DIR`/heartbeat cestu znovu místo importu z `blender_render.py`/`render_worker.py` - riziko tichého rozjetí při budoucí změně cesty (**střední**).
- Dva nezávislé "vyber HDRI mapu" systémy (`hdri.py` pro scénu vs. `rendering_settings.py` pro path-traced render) - záměrně oddělené, ale UX riziko záměny adminem (**nízká/střední**).
- `_folder_id_setting`/`_detect_pbr_role`/konstanty správně sdíleny importem mezi `rendering_settings.py` a `blender_render.py` - pozitivní nález, ne duplicita.

**Fronta jobů - shrnutí**: souborová (ne DB, záměrně kvůli sdílení mezi gunicorn workery), aktuálně bez zaseknutých jobů, ale 15 dní "zamrzlá v čase". Timeout na "running" job existuje ve 3 vrstvách. Úklid orphan souborů existuje, ale jen reaktivně.

## inquiries.py (186 řádků)

1. **Celý modul (vysoká)** - 0 reálných odeslání za 18 dní provozu (`crm_leads.source='web'` = 0 z 17 řádků), formulář `poptavka-stul.html` není odkázán z žádné jiné stránky webu (nav/footer/produkt). Návrh: doplnit CTA/odkaz, nebo s Robertem ověřit, zda má zůstat "unlisted" odkaz sdílený mimo web.
2. **`50-70` (vysoká vůči bodu 17)** - `_find_or_create_web_lead` automaticky matchuje/mergeuje zprávu do CRM leadu podle e-mailu bez jakékoli admin kontroly v okamžiku zápisu, a neexistuje následná cesta k ručnímu přesunu zprávy k jinému leadu, pokud se match splete. Existující "ruční přiřazení" v `admin.html` (`supportTriageLeadPick`) funguje jen pro e-mailovou triage, ne pro tuto webovou cestu. Návrh: přidat admin endpoint "přesunout zprávu k jinému leadu".
3. **`50-70` vs `crm.py:333` (střední)** - zjednodušená zrcadlená kopie párovací logiky (jen podle e-mailu, bez threadování Message-ID), riziko divergence od originálu při budoucích úpravách.
4. **`94` (střední-vysoká)** - veřejný POST endpoint bez rate limitu (existující `_rate_limited()` helper z `app.py` se nepoužívá), navíc přijímá přílohu do 15 MB celou do paměti - snadný vektor spamu/vyčerpání zdrojů.
5. Bod 16 (e-maily): v pořádku, žádné auto-odesílání.

## qa_audit.py (141 řádků)

1. Tenký, dobře navržený obal nad `qa_checks.py` - žádná duplicitní logika kontrol.
2. **(nízká)** - žádná cache/throttling proti opakovanému rychlému refreshi GET (`qa_checks.py` má sice mtime-cache, ale to řeší jen výkon, ne spam requestů).
3. **(nízká)** - přehled `qa_reported_tasks` chybí hledání/filtr v UI (bod 11) - u malého interního diagnostického seznamu (11 řádků) diskutabilní závažnost.
4. Živě používaný: 11 záznamů, poslední aktivita 2026-08-20, panel funguje.

## bank_statements.py (698 řádků)

1. **`380-402` (vysoká)** - `_create_auto_payment_tax_document()`: `try/except` obepíná INSERT VDD dokladu i navazující `UPDATE shop_orders`. Pokud INSERT projde a UPDATE selže, `except` jen `print()`-uje a vrátí `None` → doklad se ale zapíše natrvalo při pozdějším commitu, aniž by prošel `log_audit()` nebo e-mailovou frontou (`auto_issued` ho nezaznamená jako vystavený). `bank_paid=1` se navíc nastaví nepodmíněně dřív, takže se to samo neopraví. Návrh: rozdělit na dva try bloky s kompenzací, logovat strukturovaně místo `print`.
2. **`265-268` (střední)** - post-commit smyčka `log_audit`/e-mail fronta bez ošetření výjimek - selhání u jednoho dokladu v dávce zablokuje audit/e-mail i pro zbylé, bez retry (protože `bank_paid=1` je už committnuté).
3. **`487` (střední)** - `shop_orders.bank_paid` nemá index, `match_bank_payments_to_orders()` dělá full scan. Zatím 39 řádků bez dopadu, ale relevantní před ostrým provozem.
4. **frontend `admin.html:17148-17160` (střední)** - `amount_warnings`/`auto_issued` z odpovědi syncu se nikde nezobrazují ani neukládají - mechanismus navržený přímo Robertem pro sledování opakovaných neshod fakticky nefunguje (data se po requestu zahodí).
5. **`636` (nízká)** - `LIMIT 300` bez stránkování v seznamu transakcí, bez upozornění na oříznutí.
6. **`595-601` (nízká)** - `LIKE '%q%'` full-scan hledání na 5 sloupcích.
7. **`56, 158` (nízká)** - docstring odkazuje na neexistující funkci `find_incoming_document_payment_matches()` - skutečná je `find_payment_matches()` v `api/incoming_documents.py:119`.
8. **E-maily: v pořádku** - modul sám nikdy nevolá SMTP, jediná cesta jde přes `send_and_log(auto=True)`, která jen loguje `status='pending'` (ověřeno v `emails.py:164-187`).
9. **VDD automatika: gate funkční** - kontrola `requires_advance_invoice` + fallback klíčová slova proběhne vždy před `create_payment_tax_document()`, žádná jiná automatická cesta nenalezena. Živě: `shop_documents` 0 řádků (starých 25 mylných VDD smazáno po incidentu z WORKFLOW.md bodu 19).
10. Standardní přehledová obrazovka existuje a je funkční (filtr, částky, směr, export chybí). Chybějící soft-delete/bulk akce dávají smysl (append-only zrcadlo bankovního výpisu) - doporučeno explicitně zapsat jako výjimku z bodu 11.

## tracking.py (428 řádků)

1. **`132, 167, 210, 245` (nízká-střední)** - veřejné POST tracking endpointy bez rate limitu, umožňují generovat velký počet unikátních řádků (6sloupcový UNIQUE KEY u `*_daily`) a tím zvětšovat DB.
2. **`345-350` (nízká-střední)** - `GROUP BY` nad celou `page_views` bez podpůrného composite indexu ve větvi `range=all` - zatím 170 řádků, riziko při růstu provozu.
3. **`404, 415` (nízká)** - `date_where.replace('den', ...)` je křehké string-replace řešení na SQL fragmentu.
4. Žádné bare except, žádné TODO, žádné duplicity. Živě aktivní modul (nasazen 2026-08-22, sbírá data denně).

## system_pipeline.py (284 řádků)

1. **`231` (střední, reálný bug)** - registr modulu `tracking` má `ts_columns=("day",)`, ale skutečný sloupec v `page_views_daily`/`category_views_daily` se jmenuje `den`. Protože je to jediná hodnota v tuple a `_check_table` chybu tiše polkne (`except Exception: continue`), dashboard bude **vždy** hlásit `last_activity=None` pro tracking modul, i když reálně žije. Návrh: opravit `"day"` → `"den"`.
2. **`262-284` (nízká-střední)** - ~30 modulů × až 2 SQL dotazy sekvenčně na jeden GET (~40-50 round-tripů). Přijatelné pro nízkofrekvenční admin dashboard, riziko jen při auto-refreshi na časovač.
3. **`84` (nízká)** - `except Exception: continue` u zjišťování timestamp sloupce je široké a beze stopy, ale vnější `except` v `_module_status` (255-259) chybu stejně zachytí a zobrazí adminovi - reálný dopad malý.
4. Nový modul (nasazen dnes, 2026-08-26), read-only agregátor bez vlastní tabulky - dobrá příležitost, jak přímo v tomto panelu Robertovi zviditelnit mrtvý `inquiries.py` modul (metrika `_check_inquiries` počítá stejný `crm_leads WHERE source='web'` dotaz, který ukázal 0).

## remeslo.py (11433 řádků)

**Kontext**: `TASKS.md` už eviduje desítky nálezů (match_groups párování, `price_czk` workflow, bezpečnost registrace, CASCADE bug - opraveno, self-service role, výkonové audity `/api/remeslo/compare`) - NEOPAKOVÁNO zde. Modul je stále v pilotní fázi bez reálného provozu na obchodní straně: `remeslo_jobs` 2, `remeslo_offers` **0**, `remeslo_invoices` **0**, `remeslo_pricelist_items` **0**, `remeslo_craftsmen` 3, `remeslo_customers` 2 - jen katalog cen materiálu (`remeslo_material_prices` 10205 řádků) je reálně naplněný.

1. **`10983-10994` a `11027-11038` (VYSOKÁ, nový nález, porušení bodu 16)** - `public_remeslo_offer_accept`/`public_remeslo_offer_decline` volají `send_email()` (z `app.py`) přímo a synchronně na veřejném neautentizovaném endpointu při potvrzení/odmítnutí nabídky zákazníkem. Obchází centrální pending-frontu (`send_and_log`), kterou projekt zavedl 2026-08-22 přesně kvůli tomuto pravidlu. Kód je nasazený, ale zatím se nespustil (`remeslo_offers` má 0 řádků). Návrh: přepsat na zápis `status='pending'` do `system_emails` stejným vzorem jako `issue_email_verification()`, doplnit rate-limit na accept/decline.
2. **`11334-11335` (nízká)** - `remeslo_customers_list` hledání přes 8 sloupců s oboustranným `LIKE '%q%'`, zatím 2 řádky celkem, do budoucna kandidát na FULLTEXT index.
3. Bare except: 0× holý `except:`, 10× `except Exception` - všechny prošetřeny, žádný nepolyká chybu tiše (reconnect pojistky, kompenzační rollback, logované selhání se srozumitelnou chybou uživateli).
4. TODO/FIXME/HACK: 0 výskytů.
5. N+1: žádný nový nález - kontrolované INSERT smyčky jsou bounded (položky jedné kalkulace/faktury), velké srovnávací dotazy už byly opakovaně auditované a opravené dřív.
6. Mrtvý kód: 14 `_calc_*` kalkulačních funkcí vypadají nevolané přímo, ale jsou registrované v dispatch slovníku `CALCULATOR_FUNCTIONS` - nejde o mrtvý kód.
7. Nový modul "Zákazníci" (2026-08-21, `remeslo_customers`) už bod 11 splňuje kompletně od začátku (soft-delete, audit log, hromadné akce) - dobrý precedent.

---

# Skupina 2/3: support/CRM/doklady (support, cutting, crm, quotes, drive, incoming_documents, approvals, scene_offers, fleet, leg_fbx_import)

Metodologie: živé DB počty ověřeny přímo (systemd-run + `.env`, hlavní
produkční DB), kód procházen `grep -n`/přímým čtením, `WORKFLOW.md`
(AKTIVNÍ POKYNY 1-20) a `TASKS.md` prohledány pro už evidované nálezy.

## Nejzávažnější nález skupiny 2 (aktivně běžící porušení bodu 16)

**`scene_offers.py` má 5 míst obcházejících e-mailovou schvalovací frontu**,
z toho jedno je **denně automaticky spouštěný cron timer**
(`konfigurator-offer-expiry-reminder.timer`, ověřeno živě `enabled`+`active`,
`OnCalendar=*-*-* 08:00:00`) - `run_offer_expiry_reminder_cli()`
(`scene_offers.py:2464`, `send_email` na `2532` a `2545`) posílá e-mail
přímo zákazníkovi bez jakéhokoli schválení, KAŽDÝ DEN. Na rozdíl od
nálezu v remeslo.py (skupina 3, kód nasazen, ale zatím se nespustil),
tenhle běží aktivně už teď. Zbylá 4 místa (`public_offer_accept`,
`public_offer_decline`, `public_offer_note` - všechny na zákaznicky
dosažitelných veřejných endpointech) obcházejí frontu stejným způsobem.
Souhrnně napříč skupinou 2 jde o 9 výskytů téhle třídy chyby ve 3
modulech (scene_offers.py 5×, fleet.py 2×, support.py 2×) - `crm.py` má
od 2026-08-24 správnou referenční opravu (`emails.send_and_log(...,
auto=True)`, `crm.py:618-664`), stojí za použití jako šablona pro opravu
zbylých modulů.

## support.py (1824 řádků)

**Živý stav:** aktivní, denně používaný modul. `shop_support_conversations`=53
(poslední `created_at` 2026-08-26), `shop_support_messages`=94, přílohy=106,
`support_email_triage_runs`=5 (poslední běh 2026-08-26 16:40),
`support_email_triage_proposals`=67, `email_sync_log`=46.

1. **[VYSOKÁ]** `support_admin_reply()` (`support.py:640`, `send_email()` na
   řádku `676`) posílá odpověď zákazníkovi přímo přes `send_email()` z
   `app.py` - bez `emails.send_and_log(..., auto=True)`, bez záznamu do
   `shop_emails`/"Emaily odchozí", selhání SMTP mizí jen do `print()`. Je
   to přesně stejná chyba, jakou Robert 2026-08-24 nechal opravit v
   `crm.py:618-664` ("odpověď odeslaná z poptávky musí skončit ve
   schvalovací frontě... VZDY auto=True"). Návrh: zrcadlit tu opravu.
2. **[VYSOKÁ]** `_maybe_notify_new_message()` (`support.py:276`,
   `send_email()` na řádku `295`) posílá interní notifikaci (mobil
   admina) automaticky při každé nové zákaznické zprávě, přímým
   `send_email()`, mimo schvalovací frontu - v rozporu s doslovným
   zněním WORKFLOW.md bodu 16 ("plošný zákaz... žádný příjemce není
   výjimkou"). Doporučeno vyjasnit s Robertem, zda má pravidlo 16 platit
   i na čistě interní provozní alerty, nebo se má formálně zúžit.
3. **[STŘEDNÍ]** `support_admin_delete()` (`support.py:531`) a
   `support_admin_bulk_delete()` (`support.py:1046`) dělají trvalý
   `DELETE FROM shop_support_conversations`, přestože ve stejném souboru
   existuje archivační mechanismus (`support_admin_archive`,
   `support.py:708`) - v rozporu s bodem 11.2. Vzniklo 2026-07-26 na
   přímou žádost Roberta, před formalizací pravidla 2026-08-21 - stojí
   za potvrzení, zda má zůstat trvalá výjimka.
4. **[NÍZKÁ]** N+1 v `_move_conversation_to_crm()` (`support.py:801`,
   smyčka `support.py:858`) - INSERT + SELECT příloh na každou zprávu
   zvlášť; dopad nízký (málo zpráv na konverzaci).
5. **Rule 17 splněno**: `lead_id_override` umožňuje ruční přiřazení k
   existující poptávce na 3 místech (`support.py:801`, `926`,
   `1578-1641`).
6. Dashboard "Ke schválení" prolinkování - **již evidováno v TASKS.md**.

## crm.py (1483 řádků)

**Živý stav:** aktivní. `crm_leads`=17 (poslední aktivita 2026-08-26),
`crm_lead_messages`=26, `crm_classifier_sender_rules`=3,
`crm_classifier_words`=1093. Naopak `crm_lead_notes`=0,
`crm_lead_tasks`=0, `crm_lead_message_attachments`=0 - tři podpůrné
tabulky bez jediného řádku dat; stojí za ověření, zda k nim existuje
cesta v UI.

1. **[POZITIVNÍ VZOR]** `crm_admin_lead_reply()` (`crm.py:618-664`) je
   referenční správná implementace e-mailové schvalovací fronty
   (`emails.send_and_log(..., auto=True)`) - použít jako šablonu pro
   opravu `support.py`/`fleet.py`/`scene_offers.py`.
2. **[STŘEDNÍ]** `crm_admin_leads_bulk_delete()` (`crm.py:807-830`) dělá
   trvalý hard-delete poptávek (`DELETE FROM crm_leads`, kaskáda na
   messages/tasks/notes/attachments) - další instance stejného vzoru
   jako `support.py`/`drive.py`/`scene_offers.py` níže. V rozporu s
   bodem 11.2, ale zdokumentovaně vědomé rozhodnutí ("stejny vzor jako
   support.py::support_admin_bulk_delete").
3. **[NÍZKÁ]** `classify_incoming_email()` (`crm.py:145`) loguje selhání
   jen přes `print()`, ne trvale.
4. Import `drive._find_or_create_folder_path()` (`crm.py:325`) místo
   vlastní reimplementace - **správný vzor**, kontrast viz nález u
   `incoming_documents.py`.
5. Rule 17 splněno (sdílená logika se support.py). CRM self-service pro
   roli `remeslnik` - **již evidováno v TASKS.md**.

## approvals.py (202 řádků)

**Živý stav:** agreguje 6 tabulek, z nich `crm_quotes`=0 a
`shop_documents`=0 jsou prázdné (sekce "Nabídky"/"Doklady ke schválení"
tedy dnes vždy prázdné), `shop_purchase_orders`=1, `shop_reorder_items`=0,
`incoming_documents`=9 (aktivní).

1. **[STŘEDNÍ]** `GET /api/admin/approvals` (`approvals.py:52`) při
   KAŽDÉM požadavku nepodmíněně volá `_reorder_sync_from_stock(cur)`
   (`app.py:8223`), která obsahuje Python smyčku s `cur.execute`
   UPDATE/INSERT uvnitř pro každý produkt s deficitem skladu
   (`app.py:8233-8241`) - klasický N+1 zápisový pattern. Dashboard se
   navíc dle vlastního docstringu periodicky obnovuje z frontendu, takže
   tahle smyčka běží opakovaně na pozadí. Při 739 produktech v katalogu a
   rostoucím počtu podskladových položek reálné riziko zátěže DB. Dnes
   neškodí (`shop_reorder_items`=0). Návrh: přepsat na hromadný `INSERT
   ... ON DUPLICATE KEY UPDATE`.
2. **[NÍZKÁ]** Nekonzistence: sekce "reorder" se přidá do odpovědi jen
   `if rows:` (`approvals.py:60`), ostatní 4 sekce vždy (i prázdné) -
   může mást frontend logiku "sekce chybí" vs. "prázdná".
3. Dashboard prolinkování - **již evidováno v TASKS.md**.

## quotes.py (717 řádků)

**Živý stav - klíčový nález:** `crm_quotes`=0, `crm_quote_files`=0,
`crm_quote_folders`=0 (jen `crm_quote_sequence`=1 čítač). **717 řádků
kódu nad zcela prázdnými daty** - modul je ale funkčně zapojený do
`crm.py` (`get_or_create_quote_for_lead()` se volá při přechodu stavu
leadu, `crm.py:700,759`), takže nejde o mrtvý/nedostupný kód - spíš o
krok pipeline, který u žádného ze 17 leadů dosud reálně nenastal.
Doporučeno ověřit u Roberta prioritu/důvod.

1. Bez `send_email`/bare except v souboru - čistě CRUD/soubory.
2. `safe_stored_filename()` (`quotes.py:90`) - bezpečný vzor, správně
   reexportován a používán napříč `drive.py`/`incoming_documents.py`/
   `fleet.py`/`scene_offers.py`.

## drive.py (561 řádků)

**Živý stav:** aktivní. `shared_drive_files`=939 (poslední aktivita
2026-08-26), `shared_drive_folders`=115.

1. **[VYSOKÁ]** `drive_admin_folder_delete()` (`drive.py:291`) a
   `drive_admin_files_delete()` (`drive.py:481`) dělají skutečný trvalý
   `DELETE` + `os.remove()` na disku, u složky navíc kaskádovitě přes
   celý podstrom (`_collect_folder_subtree_ids`, `drive.py:277`) - žádný
   `is_active`/archivační příznak, žádná obnova. Přímý rozpor s bodem
   11.2. Návrh: zavést soft-delete.
2. **[NÍZKÁ]** `except OSError: pass` při mazání souboru z disku
   (`drive.py:319-320`, `499-501`) bez logu - osiřelý soubor by zmizel
   beze stopy.

## incoming_documents.py (551 řádků)

**Živý stav:** lehce používaný, ale živý. `incoming_documents`=9
(poslední 2026-08-24), `bank_transactions`=179.

1. **[STŘEDNÍ]** `_get_or_create_folder()` (`incoming_documents.py:361`)
   je skutečná duplicitní reimplementace
   `drive._find_or_create_folder_path()` (`drive.py:329`) - jednodušší
   kopie stejné logiky (get-or-create složky), místo importu sdíleného
   helperu jako to správně dělá `crm.py:325`. Návrh: nahradit voláním
   `drive._find_or_create_folder_path`.
2. **[NÍZKÁ]** N+1 v `incoming_documents_bulk_approve()`
   (`incoming_documents.py:232`, smyčka `244`) - na každý dokument cca
   5-7 dotazů + synchronní čtení/zápis celého souboru do paměti. Neškodí
   při 9 řádcích, nescaluje.
3. **[NÍZKÁ]** N+1 "skrytý" v `_serialize()`
   (`incoming_documents.py:175`) - `find_payment_matches(cur, row)`
   (`incoming_documents.py:119`) vydá vlastní `SELECT * FROM
   bank_transactions` pro každý řádek v `incoming_documents_list()`
   (`incoming_documents.py:183`, LIMIT 200), kde `amount_czk` je
   vyplněné. Dnes levné (9 řádků), při LIMIT 200 by šlo o desítky až
   stovky extra dotazů. Návrh: jeden hromadný dotaz s `GROUP
   BY`/okny místo per-řádku.

## scene_offers.py (2566 řádků, největší modul)

**Živý stav - klíčový nález:** `scene_offers` = **2 řádky za celou
historii** (id=41 „TEST" trvalá testovací nabídka založená 2026-08-06,
id=90 „Logiman0096" - jediná REÁLNÁ nabídka, založená 2026-08-11).
`scene_offer_acceptances`=0, `declines`=0, `notes`=0, `revisions`=0 - ani
jedna z obou nabídek nebyla nikdy přijata/odmítnuta/okomentována.
`page_events`=210, `views`=25 (poslední 2026-08-21) - návštěvy
zaznamenané, žádná konverze. 2566 řádků propracované funkcionality
(markup nástroje, PDF/3D rendery, QR platba, revize, expirace/upomínky)
stojí za jedinou reálnou nabídku bez konverze - doporučeno ověřit
prioritu u Roberta.

1. **[VYSOKÁ] Nejzávažnější nález celého auditu - 5 míst obchází
   e-mailovou schvalovací frontu (WORKFLOW.md bod 16):**
   1. `public_offer_accept()` (`scene_offers.py:1367`, `send_email`
      `1435`) - neautentizovaný veřejný endpoint po kliknutí zákazníka.
   2. `public_offer_decline()` (`scene_offers.py:1454`, `send_email`
      `1486`) - stejně.
   3. `public_offer_note()` (`scene_offers.py:1603`, `send_email`
      `1641`) - stejně.
   4.-5. `run_offer_expiry_reminder_cli()` (`scene_offers.py:2464`,
      `send_email` na `2532` a `2545`) - spouští se ze **systemd
      timeru `konfigurator-offer-expiry-reminder.timer`** (ověřeno
      živě: `enabled`+`active`, `OnCalendar=*-*-* 08:00:00`, denně) a
      posílá e-mail **přímo zákazníkovi** (`offer["customer_email"]`)
      plně automaticky, bez jakéhokoli lidského zásahu. **Toto je
      nejzávažnější instance z celého auditu** - cron-spouštěný,
      zákaznicky viditelný e-mail bez schválení, přesně to, co bod 16
      doslovně zakazuje, a aktivně běží už teď (na rozdíl od nálezu v
      remeslo.py, skupina 3, kde kód existuje, ale zatím se nespustil).
   Návrh: všech 5 míst přepsat na `emails.send_and_log(..., auto=True)`
   podle vzoru `crm.py:661`.
2. **[STŘEDNÍ]** `admin_scene_offers_bulk_delete()`
   (`scene_offers.py:2363-2422`) dělá skutečný trvalý `DELETE FROM
   scene_offers` (+ kaskáda + mazání souborů z disku) - rozpor s bodem
   11.2. Vzniklo 2026-08-05, před formalizací pravidla.
3. **[STŘEDNÍ]** Duplicitní reimplementace ARES IČO lookupu:
   `scene_offers.py:1338-1361` volá `https://ares.gov.cz/...` vlastní
   `urllib.request` implementací, zatímco `api/remeslo_registry.py:22-45`
   (`_http_json`, `ARES_BASE`, `check_ares_existence`) už má otestovaný
   klient na stejné API s lepším ošetřením chyb (rozlišuje
   404/timeout/format-drift). Návrh: sjednotit na sdílený helper.
4. **[NÍZKÁ]** `admin_scene_offers_list()` (`scene_offers.py:1913-1929`)
   má 3 korelované subquery v SELECT listu (view_count, total_dwell_ms s
   JOIN, accepted_name) na každý řádek stránky (výchozích 50/stránka) -
   N+1-podobný dopad při větším objemu dat. Dnes irelevantní (2 řádky).
5. **[NÍZKÁ]** Filtr v `admin_scene_offers_list()` pokrývá jen
   `offer_number`/`customer_name` (bod 11.4 žádá filtr přes všechny
   atributy) - chybí e-mail, stav, rozsah data.
6. 6× `except Exception` (`156, 1356, 1444, 1495, 1651, 2562`) - všechny
   mají log/JSON chybu, žádný tichý swallow.

## fleet.py (813 řádků)

**Živý stav - klíčový nález:** `fleet_trips`=**0 za celou historii**,
`trip_points`=0, `trip_stops`=0, `fleet_vehicles`=2 (založena
2026-08-05, 21 dní beze změny). 813 řádků GPS/knihy jízd nikdy
nezaznamenalo jedinou jízdu - stojí za ověření, zda je mobilní appka
reálně nasazená.

1. **[VYSOKÁ]** 2 místa posílají e-mail mimo schvalovací frontu:
   `send_email` na `fleet.py:683` (kontinuita km při ukončení jízdy, na
   natvrdo zadanou `FLEET_CONTINUITY_ALERT_EMAIL = "mandik@logiman.cz"`,
   `fleet.py:53`) a `fleet.py:805` (doklad o tankování). Oba automatické,
   bez schválení - rozpor s bodem 16 (doslovně nedělá výjimku pro
   interní adresy).
2. **[NÍZKÁ]** `FLEET_CONTINUITY_ALERT_EMAIL` natvrdo v kódu
   (`fleet.py:53`), zatímco `fuel_receipt_email` (`fleet.py:59`) je
   konfigurovatelný přes `app_settings` - nekonzistentní vzor v rámci
   téhož souboru.
3. Import `quotes.safe_stored_filename`/`drive.DRIVE_FILES_DIR` -
   legitimní sdílený vzor.

## cutting.py (1030 řádků)

**Živý stav:** `shop_cutting_plans`=2, `plan_units`=7, `remnants`=0,
`stock`=13, `settings`=13 - **veškerá aktivita naposledy 2026-08-08, 18
dní beze změny** (dnes 2026-08-26). Vypadá jako postavená, ale zatím
nevyužívaná funkce - stojí za ověření priority.

1. Žádné bare/broad except, TODO/FIXME - čistý kód.
2. `bulk_update_cutting_plan_units()` (`cutting.py:825`, per-řádek
   zbytková logika `853`) je zdokumentovaně nutný vzor (remnant logika
   nejde hromadně), ne bug.
3. Chybí `is_active`/archivační příznak u `shop_cutting_plans` (bod
   11.2) - nízká priorita vzhledem k minimálnímu využití.

## leg_fbx_import.py (327 řádků)

**Živý stav:** aktivní, navazuje na probíhající práci na 3D scéně
(bot8). `custom_shapes`=339 (poslední 2026-08-23),
`custom_shape_categories`=27.

1. **[NÍZKÁ]** `admin_legs_import_fbx()` (`leg_fbx_import.py:240,259`)
   ukládá a parsuje FBX bez vlastního limitu velikosti/timeoutu na
   `assimp_py` parsing - omezeno jen globálním nginx
   `client_max_body_size`. Riziko nízké (admin-only endpoint).
2. `parse_leg_fbx()` (`leg_fbx_import.py:122,130`) korektně převádí
   chyby parseru na `ValueError` s českou hláškou - dobrý vzor, žádný
   tichý swallow.
3. Sdílí validaci s ručním ukládáním tvarů (žádná duplicita,
   zdokumentovaný záměr).

---

## Napříč moduly - shrnutí systémových nálezů (skupina 2)

1. **Nejzávažnější třída chyby (bod 16 - e-maily bez schválení), 9
   výskytů ve 3 modulech**: `scene_offers.py` (5×, včetně denního cron
   jobu posílajícího zákazníkovi e-mail bez dotyku člověka), `fleet.py`
   (2×), `support.py` (2×). `crm.py` má od 2026-08-24 správnou
   referenční opravu stejné třídy chyby (`emails.send_and_log(...,
   auto=True)`) - doporučeno použít jako šablonu a rozšířit na zbylé 3
   moduly. **Meta-doporučení**: `api/qa_checks.py` už má AST-based
   kontrolu podobného typu (`check_email_link_from_request_host`,
   `qa_checks.py:1010-1047`, hledá `ast.Call` na `send_email` napříč
   `API_FILES`) - přesně podle vzoru z WORKFLOW.md bodu 8 stojí za
   doplnění nové kontroly `check_direct_send_email_bypass`, která najde
   `send_email(` volání mimo `emails.send_and_log`, aby se tahle třída
   chyby hlídala automaticky napříč celým backendem, ne jen v těchto 10
   modulech.
2. **Hard-delete v rozporu s bodem 11.2 - 5 nezávislých instancí**:
   `drive.py` (folders/files), `support.py` (konverzace), `crm.py`
   (leads), `scene_offers.py` (offers) - plus historicky obdobně
   `quotes.py`. Stojí za jedno společné rozhodnutí Roberta (zavést
   plošně soft-delete, nebo formálně potvrdit tyhle konkrétní "Smazat"
   tlačítka jako trvalé výjimky).
3. **„Postavené, ale prakticky nepoužívané" moduly** (dle živých DB
   dat): `quotes.py` (0 řádků dat, ale funkčně zapojený do crm.py
   pipeline), `fleet.py` (0 jízd za 21 dní), `scene_offers.py` (2
   nabídky/1 reálná konverze za 15 dní), `cutting.py` (18 dní bez
   aktivity). 4 z 10 auditovaných modulů - stojí za společné vyhodnocení
   priority dalšího ladění vs. reálné využití.
4. **Skutečná duplicitní reimplementace nalezena 2×**:
   `incoming_documents.py::_get_or_create_folder` vs.
   `drive.py::_find_or_create_folder_path`; `scene_offers.py` ARES
   lookup vs. `remeslo_registry.py::check_ares_existence`. V obou
   případech existuje správný vzor sdíleného importu jinde v kódu
   (`crm.py`), který stačí použít.
5. **Pozitivní zjištění**: žádný z 10 modulů neobsahuje bare `except:`
   (pokrývá to existující QA kontrola `check_bare_except`) ani
   TODO/FIXME. Rule 17 (ruční přiřazení k poptávce) je v
   `support.py`/`crm.py` triage flow prokazatelně implementováno
   správně na 3 místech.

---

# Celkový souhrn (31/31 modulů hotovo)

Audit pokryl všech ~31 backendových modulů importovaných v `api/app.py`.
Přibližně 60 jednotlivých nálezů napříč 3 skupinami (cca 21×
vysoká/21× střední/zbytek nízká závažnost - orientační, přesné třídění
viz jednotlivé sekce výš).

## Opraveno v rámci téhle práce (schváleno bot3 průběžně, mimo původní
## čistě auditní zadání)

Po nahlášení nálezů bot3 rozšířil zadání o okamžitou opravu 3 tříd
chyb, které skončily jako nejzávažnější a nejjistější (jasné porušení
existujícího pravidla + existující referenční vzor pro opravu):

1. **`system_pipeline.py`** - triviální oprava názvu sloupce
   (`"day"`→`"den"`), tracking modul teď v dashboardu správně hlásí
   živou aktivitu (commit `4b2bf1f`).
2. **`remeslo.py`** - 2 místa (accept/decline veřejné nabídky) přepsána
   na `system_emails` pending frontu (commit `4b2bf1f`).
3. **`scene_offers.py` + `api/app.py`** - opraven cirkulární import,
   který 6+ dní shazoval denní cron upomínek na vypršení nabídek
   (`konfigurator-offer-expiry-reminder.service`, živě potvrzeno
   `journalctl`), + 5 míst přepsáno na `system_emails` pending frontu
   (commit `532bba7`).
4. **`fleet.py` (2×) + `support.py` (2×)** - přepsány na
   `emails.send_and_log(auto=True)` podle referenčního vzoru
   `crm.py::crm_admin_lead_reply` (commit `532bba7`).

Všechny 4 opravy otestovány (py_compile, přímý běh CLI, live
insert+rollback/cleanup ověření DB zápisů), nasazeny, `/api/health`
ověřeno po každém restartu. Souhrnně **9 z 9 nalezených porušení
WORKFLOW.md bodu 16** (e-maily bez schválení admina) v auditovaných
modulech je teď opraveno.

## Čeká na Robertovo rozhodnutí (NEOPRAVENO, vědomě)

1. ~~**Hard-delete vs. WORKFLOW.md bod 11.2**~~ - **VYŘEŠENO (Robert,
   2026-08-27, přes bot3): záměrná výjimka, dokud je projekt v
   testovací/pre-launch fázi** - všech 12+ nezávislých instancí napříč
   `customers.py`, `documents.py` (nejcitlivější - vystavené
   faktury/VDD), `purchase_orders.py`, `products.py`, `orders.py`
   (včetně kaskádového mazání dokladů), `emails.py`, `gallery.py`/
   `gallery_items.py`, `drive.py`, `support.py`, `crm.py`,
   `scene_offers.py` zůstává BEZE ZMĚNY, není to omyl ani zpětné
   porušení pravidla - viz `WORKFLOW.md` bod 11.2 (poznámka doplněna
   `bot10`, 2026-08-27). Žádný fix. Až proběhne produkční cutover,
   rozhodnutí se musí přehodnotit znovu - do té doby toto NENÍ otevřený
   nález, příští audit ho nemá hlásit znovu.
2. **`bank_statements.py` "ghost VDD"** (řádky 380-402) - finanční
   integrita, čeká na návrh řešení (transakce/kompenzace) k Robertovu
   schválení, viz zadání bot3.
3. **`inquiries.py`** - 0 odeslání za 18 dní (formulář nikde neodkázán)
   + auto-match do CRM leadu bez ruční opravné cesty - čeká na návrh
   řešení k Robertovu schválení, viz zadání bot3.
4. **`dimension_match_fbx.py`** - endpoint "Převod" bez UI tlačítka -
   produktové rozhodnutí (dokončit vs. zrušit), do fronty pro Roberta.
5. Duplicity (`incoming_documents.py` folder helper, `scene_offers.py`
   ARES lookup), N+1 vzory, chybějící indexy, "postavené, ale prakticky
   nepoužívané" moduly (`quotes.py`, `fleet.py`, `cutting.py`,
   `scene_offers.py` samo o sobě) - nízká priorita, informativní.

## TOP doporučení (pořadí podle naléhavosti)

1. ~~Jedno rozhodnutí o hard-delete napříč celým projektem~~ -
   **VYŘEŠENO** (Robert, 2026-08-27: záměrná pre-launch výjimka, viz
   výš). Připomenout si až u produkčního cutoveru.
2. **`bank_statements.py` ghost-VDD** - **VYŘEŠENO** (bot10, 2026-08-26,
   commit `396cf5b` - vlastní nezávislé DB spojení pro INSERT
   dokladu+UPDATE, živě otestováno simulovaným selháním).
3. ~~Doplnit `check_direct_send_email_bypass` do `api/qa_checks.py`~~ -
   **VYŘEŠENO** (bot10, 2026-08-26, commit `2c01bee`) - AST kontrola
   nasazená a otestovaná, navíc hned odhalila 2 další, dosud
   NEOPRAVENÉ existující bypassy mimo tento audit
   (`app.py::auth_forgot_password`/`auth_send_temp_password`, reset
   hesla) - čeká na Robertovo rozhodnutí (viz níž).
4. **`inquiries.py` bod 1 (formulář bez odkazu)** - čeká na Robertovo
   rozhodnutí, jestli je nedostupnost záměr (kampaň/QR mimo web) nebo
   má být doplněn odkaz z webu. **Bod 2 (auto-match bez opravné cesty)
   VYŘEŠENO** (bot10, 2026-08-26, commit `e98a517` - obecný admin
   endpoint `PUT /api/admin/crm/leads/<id>/messages/<id>/move`, zatím
   BEZ UI napojení v `admin.html`).
5. ~~**NOVÉ (nalezeno kontrolou z bodu 3): `auth_forgot_password`/
   `auth_send_temp_password` v `app.py`**~~ - **VYŘEŠENO (Robert,
   2026-08-27): vědomá, trvalá výjimka z bodu 16** - reset hesla/
   dočasné heslo ZŮSTÁVAJÍ posílat přímo, bez fronty (bezpečnostní/
   časově kritický e-mail, čekání na schválení by škodilo víc než
   pomáhalo). Zapsáno do `WORKFLOW.md` bodu 16, okomentováno u obou
   funkcí v `api/app.py`, allowlistováno v
   `qa_checks.py::_SEND_EMAIL_APPROVED_WRAPPERS` - `check_direct_send_
   email_bypass` i budoucí audity to už neberou jako nález.
6. **4 "postavené, ale prakticky nepoužívané" moduly** (`quotes.py`,
   `fleet.py`, `scene_offers.py`, `cutting.py`) - společné vyhodnocení
   priority dalšího ladění vs. reálné využití, než se do nich investuje
   další práce.
