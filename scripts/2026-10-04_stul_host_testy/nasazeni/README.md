# Objednávka stolu HOSTEM, montáž (volitelná, nastavitelné %) a doprava ke schválení - hlavní e-shop (bot5, 2026-10-04)

**Stav: KÓD A TESTY HOTOVÉ, NENASAZENO.** Nasazení: `bash scripts/2026-10-04_stul_host_testy/nasazeni/deploy_stul_host.sh` (přímé povolení Roberta; na ostro při nasazení API 3:30/12:30). Patche proti HEAD, proto potřebuje ČISTÉ
`api/konfigurace_kosik.py`, `api/orders.py`, `api/miniweb_objednavky_admin.py`, `api/app.py` (rozpracovaná změna bot8 v `konfigurace_kosik.py`/`stul_shop.py` musí být nejdřív commitnutá). Testy: `test_stul_objednavka_host.py` 32 (hostovská objednávka, schválení
dopravy a záloha, sazba montáže), `test_kosik_konfigurace.py` 54, `test_miniweb_objednavky.py` 63 + regrese zástupce/dealerů. Žádná data v provozu (TEMP tabulky, stav živých tabulek se před/po porovnává).

## Rozhodnutí Roberta (přes bot9, 2026-10-04)
- Objednávka stolu HOSTEM bez registrace = ANO (košík v prohlížeči, cena vždy ze serveru, DPH CZ 21 %, e-maily jen přes schvalovací frontu, žádná automatická proforma).
- **Montáž je vždy volitelná**, cena = **% z ceny konfigurace bez DPH** (výchozí 12 %, volí se přímo v zaměstnaneckém Generátoru stolu, zákazník % NEVIDÍ a nemění), v objednávce SAMOSTATNÝ řádek „Montáž – STL-…“, DPH 21 %. Podle volby montáže zaměstnanec ručně určí cenu dopravy při schválení.
- **Doprava u hlavního e-shopu ke schválení zaměstnancem**: objednávka vznikne s cenou dopravy 0 a příznakem `shipping_review=1`, zálohová faktura až po schválení (`POST /api/admin/orders/<id>/shipping`, nově i pro objednávky hlavního e-shopu), e-mail s fakturou do schvalovací fronty.

## 1. Hostovský košík - kalkulace `POST /api/shop/stul/quote` (veřejné, bez přihlášení)
Tělo: `{items:[{product_id (karta stolu, dnes 4934), qty 1-99, montaz?: true|false, configuration:{selection, rules_version}}], delivery_zip?}` (košík drží prohlížeč v localStorage, bez ceny a hashe).
200: `{currency:"CZK", prices_include_vat:false, valid, lines:[{product_id, name, qty, made_to_order:true, stock_qty:null, unit_price_czk (bez DPH, bez montáže), line_total_czk, montaz_zvolena, montaz_czk (za kus), montaz_total_czk,
configuration:{valid, changed, kod, hash, selection, rules_version, summary:[{label,value}], errors[], weight_kg (null, dokud je hmotnost neúplná), weight_complete}}], subtotal_goods_czk, subtotal_montaz_czk, subtotal_czk, vat:{rate:21, amount, total_with_vat},
shipping_options:[{id:"toptrans", label, net:null|Kč, estimated:true, reason?:"zip_missing|weight_incomplete|price_unavailable"}, {id:"quote", net:null}, {id:"pickup", net:0}], notes[]}`. Tvar řádku je shodný s `GET /api/cart` (made_to_order, unit_price_czk, configuration.*).
Zákazník sazbu montáže nevidí: ve veřejných odpovědích NENÍ `montaz_pct`, jen částka (`montaz_czk`). Neplatná konfigurace = řádek `valid:false` s chybami (200, nepočítá se); stará pravidla 409 `rules_changed`; jiný nebo NEAKTIVNÍ produkt 422 `product_not_available`;
montáž při vypnuté sazbě (0 %) 409 `montaz_unavailable`; mnozstvi/polozky 400 `items_invalid`; chybějící konfigurace 400 `configuration_required`; 413/429.

## 2. Objednávka hosta `POST /api/shop/stul/order`
Tělo: `{name (kontaktní osoba), email, phone, company?, company_id? (IČO, povinné když company), vat_id? (DIČ), delivery:{street, city, zip (5 číslic)}, billing:{same:true}|{street,city,zip} (výchozí = dodací),
shipping:"toptrans"|"quote"|"pickup", payment:"transfer", note?, consent:true (podmínky + zpracování údajů), website:"" (honeypot), expected_total_net? (Kč bez DPH z kalkulace vč. montáže), items (jako výše)}`.
201: `{reference (číslo objednávky), status:"received", total:{net, currency:"CZK", rate:21, amount, total_with_vat}, shipping:{id, net, review:true}, payment:null, next:"proforma_after_shipping_confirmation", idempotent_replay:false}`.
Host na obrazovce vidí číslo objednávky a že **zálohovou fakturu s platebními údaji pošleme e-mailem po potvrzení dopravy** (e-mail jde až po schválení zaměstnancem, QR a proforma se na stránce NEZOBRAZUJÍ).
Chyby `{error, field?}`: 400 `name_required|email_invalid|phone_invalid|delivery_required|street_required|city_required|zip_invalid|shipping_invalid|payment_invalid|consent_required|company_id_required|company_id_invalid|vat_id_invalid|expected_total_invalid|items_invalid|configuration_required`
(pole `delivery.street` atd.), 409 `rules_changed|price_changed|montaz_unavailable|order_in_progress`, 422 `invalid_configuration|product_not_available|order_too_large|order_rejected`, 429 `rate_limited|too_many_orders` (5 za 10 min z IP, 5 za den na e-mail).
Dvojité odeslání (stejný obsah do 5 min) = 200 se stejným číslem a `idempotent_replay:true`. Objednávka je bez účtu (`user_id` NULL, `order_host`/`order_lang` = host a cs, v admin přehledu původ „host · cs“); host, který se později zaregistruje se stejným e-mailem, SVÉ staré objednávky v účtu nevidí
(párování na účet jen pevným odkazem, ne podle e-mailu; zaměstnanec je může propojit).

## 3. Montáž - sazba (zaměstnanec, Generátor stolu)
`GET /api/stul/montaz` (zaměstnanec) → `{pct, default:12, available, stored}`; `PUT /api/stul/montaz {pct}` (RBAC nastaveni/upravit, jako PUT /api/stul/pravidla) 0 až 100 (0 = montáž se nenabízí, jiné hodnoty/text/bool 400 `pct_invalid`), audit_log.
Ukládá se do `app_settings.stul_montaz_pct`; NENÍ to `sestava_typ_sluzba` (JEDNO rozhodnutí o sazbě, `konfigurace_kosik.montaz_pct_pro_typ` pro STUL_SKLAD čte jen tuhle hodnotu; chybí = 12 %). Kalkulace, košík i objednávka berou sazbu hned.
Základ: cena konfigurace bez DPH (`price.net` z generátoru, před balným se NEodečítá nic navíc; u přihlášeného zákazníka se skupinová sleva na montáž NEuplatňuje, montáž se počítá z ceníkové ceny a přičte se až po slevě; host slevu nemá).
Přihlášený košík (`POST /api/cart/items {montaz_zvolena:true}`) zůstává: řádek košíku ukazuje cenu vč. montáže, v OBJEDNÁVCE jsou od teď dva řádky (konfigurace + „Montáž – kód“).

## 4. Doprava ke schválení (i pro přihlášené)
`POST /api/orders` s konfigurací stolu, jejíž hmotnost je neúplná, a dopravou Toptrans už NEvrací 409 `weight_incomplete`: objednávka vznikne s dopravou „Toptrans – cena ke schválení“ (0 Kč), `shipping_review=1` a BEZ automatické zálohové faktury.
Zaměstnanec: `POST /api/admin/orders/<id>/shipping {shipping_price_czk, approve, vat_ok?, note?}` (viz mini-shop README) - uloží cenu, přepočte celkem, při `approve:true` vystaví zálohovou fakturu a e-mail zařadí do schvalovací fronty. Osobní odběr se nemění (bez příznaku).
Neúplná hmotnost u OSTATNÍHO zboží se zatím nedetekuje (jen konfigurace stolu); hmotnosti dílů stolu doplňuje Robert (pak se Toptrans spočítá sám).

## Co ještě není
Admin záložka/UI pro schvalování dopravy u objednávek hlavního e-shopu (bot16: detail objednávky nese `shipping_review`, použít stejné tlačítko jako u mini-shopu), texty obchodních podmínek pro spotřebitele (souhlas `consent` = podmínky + GDPR, odkaz řeší frontend), SK/EN verze.
