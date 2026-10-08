# Mini-shop: košík a objednávka konfigurovatelného stolu (fáze 3 pro SK; bot5, 2026-10-03)

**Stav: KÓD A TESTY HOTOVÉ, NENASAZENO.** Nasazení: `bash scripts/nasad_cekajici_bot5.sh objednavky` (po sadách konfigurace, pravni, ceny) s PŘÍMÝM povolením Roberta. Předtím DDL (pouští bot3/Robert):
`systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 sql/2026-10-03_miniweb_orders_enabled.py` (idempotentní, jen přidává sloupce
`miniweb_shops.orders_enabled`, `shop_orders.shipping_review|vat_mode|vat_check`). Objednávky jsou **za přepínačem**: bez `orders_enabled=1` odpovídají endpointy 404 a mini-shop se nemění. Zapnutí:
`scripts/miniweb_shop.py --slug packstations-sk --orders on --apply` (config pak nese `checkout_mode:"order"`). Testy: `test_miniweb_objednavky.py` 44, `test_miniweb_vies.py` 14, `test_admin_puvod.py` 7.

## Rozhodnutí (Robert přes bot3 2026-10-03)
- Objednávka hosta (bez účtu): firma + IČO povinné, IČ DPH volitelné. Vzniká **řádná objednávka v hlavním přehledu** (shop_orders) s původem (`order_host`, `order_lang`), vlastní (bez dealera).
- **Cena** jen ze serveru: Kč bez DPH z konfigurátoru → EUR (`miniweb_cena`: kurz z řádku shopu nebo živý Fio, marže, celé EUR za kus). **K úhradě v Kč = cena v EUR × kurz objednávky** (jediný český účet 2100198113/2010, QR v CZK);
  řádky objednávky nesou Kč = EUR × kurz, `admin_note` nese snímek (EUR, kurz, marže, DPH, doprava).
- **DPH**: dodáváme z ČR. Země ≠ CZ a PLATNÉ IČ DPH (VIES) = 0 % (reverse_charge, doložka na dokladu přijde v kroku 3); IČ DPH neplatné podle VIES = objednávku odmítneme (422 `vat_id_not_valid`); VIES nedostupné = 0 %
  jen u formálně platného čísla a objednávka je označena **k ruční kontrole** (`is_urgent=1` + poznámka); bez IČ DPH nebo země CZ = CZ sazba 21 %.
- **Doprava**: `toptrans` (odhad ceníkem `orders._resolve_toptrans_price` podle PSČ DODACÍ adresy a hmotnosti; bez ÚPLNÉ hmotnosti dílů se cena nepočítá, dnes platí vždy), `quote` (po dohodě), `pickup` (osobní odběr 0).
  KAŽDÁ objednávka z mini-shopu (i osobní odběr, cena 0) je **ke schválení zaměstnancem** (`shop_orders.shipping_review=1`; od 2026-10-03 podle externí revize #9); proforma vznikne až po schválení (krok 2, zatím NENÍ). Žádná automatická proforma a žádný e-mail (pravidlo 16).
- **Fakturační i dodací adresa** jako v hlavním e-shopu.

## Kontrakt (bot16)
`POST /api/miniweb/quote {country, delivery_zip?, vat_id?, items:[{product_id (id produktu mini-shopu), qty 1-99, configuration:{selection, rules_version}}]}` → `{currency:"EUR", prices_include_vat:false, country, valid,
lines:[{product_id, name, qty, net_unit, net_total, configuration:{valid, changed, kod, hash, selection, rules_version, summary[{label,value}], errors[]}}], subtotal, total_goods,
shipping_options:[{id:"toptrans", label, net (EUR|null), estimated:true, reason?:"weight_incomplete"|"zip_missing"|"price_unavailable"}, {id:"quote", net:null}, {id:"pickup", net:0}],
vat:{applied, rate, mode:"standard"|"reverse_charge", reason:"no_vat_id"|"domestic"|"valid_vat_id"|"valid_vat_id_unverified"|"vat_id_not_valid", amount, total_with_vat, manual_check}, notes[]}`.
Neplatná konfigurace v quote = řádek `valid:false` s chybami (200); stará pravidla 409 `rules_changed`; jiný produkt 422 `product_not_available`.
`POST /api/miniweb/vat-check {country, vat_id}` → `{valid:true|false|null, status:"valid"|"invalid"|"unavailable", vat}` (null = VIES nedostupné).
`POST /api/miniweb/orders {country, company, company_id, vat_id?, name, email, phone, billing:{street,city,zip}, delivery:{same:true}|{same:false,street,city,zip}, shipping:"toptrans"|"quote"|"pickup", payment:"transfer",
note?, b2b_confirm:true, consent:true, website:"" (honeypot), expected_total_net? (EUR zboží z quote), items}` → 201 `{reference, status:"received", total:{net (zboží + doprava, je-li známa), currency:"EUR", with_vat}, vat, shipping:{id, net|null, review},
shipping_review, payment:null, next:"proforma_after_shipping_confirmation", idempotent_replay:false}`; dvojitý klik do 5 minut = 200 se stejnou objednávkou a `idempotent_replay:true`.
Chyby `{error, field?}`: 400 `name_required|email_invalid|phone_invalid|company_required|company_id_required|company_id_invalid|vat_id_invalid|street_required|city_required|zip_invalid|delivery_required|shipping_invalid|payment_invalid|consent_required|b2b_confirm_required|country_invalid|items_invalid|configuration_required|expected_total_invalid`
(pole `billing.street` atd.), 409 `rules_changed|price_changed` (+`current_total_net`), 422 `invalid_configuration` (+`errors`)|`product_not_available`|`vat_id_not_valid`|`order_too_large`, 429 `rate_limited|too_many_orders`, 503 `price_unavailable` (chybí marže/kurz).
Admin: `GET /api/admin/orders` nese `order_host`, `order_lang`, `origin_label` ("host · jazyk", hlavní e-shop "e-shop"), `shipping_review`, `vat_mode`, `vat_check`, odpověď `origins:[{key,label,count?}]`, filtry `?origin=eshop|<host>`, `?shipping_review=1`.
Detail `GET /api/admin/orders/<id>`: položka `configuration` (zaměstnanec plný snímek vč. `bom`, `price_summary`, `weight_kg`, `weight_complete`).

## Krok 2 (HOTOVO v sadě): schválení dopravy a zálohová faktura
`POST /api/admin/orders/<id>/shipping {shipping_price_czk (Kč bez DPH), approve:true|false, vat_ok?, note?}` (RBAC objednavky/upravit, při approve i doklady/vytvorit): uloží cenu dopravy, přepočte `total_czk`; `approve:true` navíc vystaví zálohovou
fakturu STEJNOU funkcí jako automat hlavního e-shopu a zařadí e-mail do schvalovací fronty (pravidlo 16); `shipping_review` → 0. Odmítnutí: 409 `not_miniweb_order`, `shipping_not_in_review` (druhé schválení), `proforma_exists`, `vat_check_required` (IČ DPH neověřeno ve VIES, potřeba `vat_ok:true`),
`vat_regime_not_supported` (DPH 0 % – do kroku 3), 400 `shipping_price_invalid|invalid_request`. Testy (část S v `test_miniweb_objednavky.py`, celkem 53).

## Co ještě NENÍ (krok 3)
3. Doklady s DPH 0 % a doložkou (documents.py má pevnou sazbu 21 %; sdílený modul, plné testy hlavního e-shopu).
Dále: skutečný SK tarif Toptrans (slovenská PSČ ceník mapuje na pásmo 700 km), hmotnosti dílů (bot8: 4933 laminodeska, 4930 šuplíky, 4931 perfopanel, 4929 LED, 4932 elektrožlab, 4928 držák PET, 4916 kolečka, 3025 ložisková jednotka),
texty e-mailů a dokladů ve slovenštině, ověření IČO v registrech.

## Externí revize 2026-10-03 (openai1, docs/kontrola_openai1_minishop_2026-10-03.md) - opraveno v backendu
#1 opakování objednávky jen při STEJNÉM obsahu (otisk `[ORDER-FP]` v admin_note + zámek `GET_LOCK`, odpověď z uloženého snímku), #2 `storefront_id` z ověřeného kontextu (alias domény), #5 snímek ceny: zákaznický text bez `[`/`]`, bere se POSLEDNÍ `[EUR-SNAPSHOT]`, #7 `price_delta` pryč u všech voleb bez nastavení,
#8/#3 admin shopů: kontrola ceny po každé změně u zapnutých objednávek, live shop nesmí mít skryté ceny (`price_policy`), #9 `shipping_review=1` vždy, #14 země poptávky ze seznamu shopu, #16 jen řetězce (objekt/pole = nezadáno, země objekt = `country_invalid`), IČO samé nuly = `company_id_invalid`,
#4 `legal.seller` z `company_info` (doplněk `documents.SUPPLIER`), #10 `GET /api/miniweb/products?slug=` (jazykový nebo základní slug, bez ohledu na limit seznamu).
