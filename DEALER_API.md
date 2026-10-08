# API pro dealery - objednávka z webu dealera (cesta „dokončí se na webu dealera")

> **ODLOŽENO (Robert přes bot3, 2026-10-02): API cesty b a feed se NENABÍZEJÍ, nerozvíjejí a nemažou.** Dealeři dostanou e-shop na našich doménách (objednávka se dokončí u nás), vložený blok ani feed nebudou. Kód a testy zůstávají beze změny, klíče `sk_`/`ft_` se nevydávají.

Verze 1, etapa 1 (bot5, 2026-10-02). Zdroj pravdy je kód `api/dealer_orders.py`, `api/dealer_feed.py` a testy `scripts/2026-10-02_dealeri_testy/test_objednavky.py`, `test_feed.py`.
Dealer si na svém webu dokončí objednávku se svým zákazníkem a u nás ji zadá **serverovým voláním**. Nakupuje za **dealerskou cenu**
(sleva, ne provize), platí **předem** zálohovou fakturou, zboží jde **koncovému zákazníkovi dealera**. Webhooky v etapě 1 nejsou (stav se zjišťuje dotazem).
Jen běžné produkty ze stejné nabídky jako feed a widget; **žádné sestavy, montáž ani zakázkové řezání**.

## Přístup
- Dealer musí být aktivní a mít v administraci cestu objednávky „dealer". Správce mu vydá **tajný klíč** `sk_<8hex>_<tajná část>` (ukáže se jednou, u nás je jen hash)
  s rozsahem `quote` (kalkulace) a/nebo `orders` (objednávky), volitelně s povolenými IP adresami. Klíč se posílá `Authorization: Bearer sk_...`, nikdy do prohlížeče.
- Všechno jsou JSON požadavky (`Content-Type: application/json`, max 64 kB), odpovědi `Cache-Control: no-store`, bez CORS. Peníze v **Kč bez DPH**, DPH 21 % se přičítá v zálohové faktuře.
- Neplatný, odvolaný nebo cizí klíč = vždy `401 invalid_key`. Limit požadavků na klíč (výchozí 120/min), zápis objednávek navíc 30/min.

## POST /api/dealer/v1/quote (rozsah quote) - cenová kalkulace, nic se nezapisuje
```json
{"items": [{"product_id": 123, "qty": 2}], "delivery_zip": "110 00", "shipping_method_id": 4}
```
`shipping_method_id` je nepovinné: bez něj dostanete jen nabídku dopravy (`shipping_options`) a součty bez dopravy. Odpověď: `items[]` (`unit_price_net_czk`,
`line_net_czk`, `price_basis` dealer|sale, `availability` skladem|na_dotaz), `items_net_czk`, `shipping_options[]`, `shipping`, `total_net_czk`, `vat_czk`,
`amount_due_czk` (částka k úhradě = zaokrouhlená na celé Kč, přesně jako zálohová faktura), `in_stock` (false = něco není skladem, zálohová faktura se pak vystaví až po domluvě).

## POST /api/dealer/v1/orders (rozsah orders) - vytvoření objednávky
```json
{"external_ref": "ESHOP-10234", "items": [{"product_id": 123, "qty": 2}],
 "recipient": {"name": "Jan Novák", "street": "Ulice 5", "city": "Praha", "zip": "110 00", "phone": "+420 777 123 456"},
 "shipping_method_id": 4, "note": "Zavolat před doručením", "expected_total_net_czk": 1234.50}
```
- `external_ref` = vaše unikátní označení objednávky (1-64 znaků `A-Z a-z 0-9 . _ : -`). **Idempotence:** stejný `external_ref` se stejným obsahem (produkty a množství, příjemce, PSČ, doprava)
  vrátí `200` a původní objednávku (`Idempotent-Replayed: true`, `idempotent_replay: true`), nic se nevytvoří znovu; jiný obsah = `409 external_ref_conflict`. Při výpadku spojení tedy bezpečně zopakujte.
- `expected_total_net_czk` (doporučeno) = částka z kalkulace; když se mezitím změnila cena, přijde `409 price_changed` s aktuálními částkami a nic se nevytvoří.
- Cena a doprava se **vždy počítají u nás**, pole navíc (cena, sleva, kupon...) se odmítnou `400 unknown_field`. Stejný produkt vícekrát se sloučí.
- Fakturace jde na **dealera** (firma, IČO, adresa z jeho profilu; chybí-li něco, `409 dealer_profile_incomplete`), doručení na `recipient`. Texty nesmí obsahovat `<` ani `>`.
- `201` + `order`: `order_number`, `external_ref`, `status`, `items[]`, `shipping`, `delivery`, `total_net_czk`, `vat_czk`, `amount_due_czk` a **`payment`** (`variable_symbol`, `document_number`,
  `amount_due_czk`, `due_date`, `bank_account`, `iban`, `method`). Je-li něco mimo sklad, je `payment: null` (zálohová faktura se vystaví po domluvě dostupnosti).
- Potvrzení objednávky a zálohová faktura jdou na e-mail dealera přes schvalování u nás (nikdy automaticky ven, nikdy koncovému zákazníkovi). Expedujeme po **přijetí platby**.

## GET /api/dealer/v1/orders/<external_ref> a GET /api/dealer/v1/orders (rozsah orders)
Stav jedné objednávky (stejný tvar jako `order` výše + `paid`, `paid_at`, `shipped_at`, `status_label`) a seznam od nejnovější (`?page=`, `?page_size=` max 50). Cizí a neexistující = `404 not_found`.

## Feed produktů (rozsah feed) - pro dealery s vlastním e-shopem
`GET /api/dealer/v1/feed.csv` a `GET /api/dealer/v1/feed.xml` s **feed tokenem** `ft_<8hex>_<tajná část>` (`Authorization: Bearer ft_...`, nebo `?token=ft_...` pro importéry bez hlaviček; token má jen
rozsah `feed`, objednávat s ním nejde, kdykoli se dá vyměnit). CSV je UTF-8, oddělovač `;`, CRLF, XML má kořen `<products>`. Obsah = stejné produkty jako ve widgetu (bez sestav, bez značky a dodavatele, bez 3D, bez nákladů a přesného skladu).
- **Cesta „dealer"**: `?markup=<0-500>` je povinné (vaše přirážka v %), ve feedu je **jen výsledná cena** = dealerská cena x (1 + markup/100) (`price_net_czk`, `price_gross_czk`, `vat_rate`); odkazy na nás se neuvádějí.
- **Cesta „our" (provize)**: veřejné ceny, `link` = odkaz přes váš proklik (`/api/dealer/go/<kód>?to=/produkt/<slug>`), takže se objednávka z něj přiřadí vám.
- Sloupce: `id, sku, name, description, unit, category, weight_g, length_mm, width_mm, height_mm, availability, price_net_czk, price_gross_czk, vat_rate, currency, link, image_1..image_5` (URL obrázků jsou absolutní).
- Odpověď má `ETag` (`If-None-Match` -> `304`) a drží se 10 minut v paměti; stahujte nejvýš jednou za pár minut. Dokud správce nenastaví veřejnou adresu (`app_settings.dealer_public_base_url`, https, neutrální doména), vrací feed `503 feed_not_configured`.

## Chyby
Tvar `{"error": "<cesky text>", "code": "<kod>", "field": "<pole>"}`. Kódy: `invalid_json`, `invalid_request`, `unknown_field` (400), `invalid_key` (401), `scope_denied`, `ip_not_allowed`,
`dealer_inactive`, `order_path_not_dealer` (403), `not_found` (404), `external_ref_conflict`, `price_changed`, `dealer_profile_incomplete` (409), `payload_too_large` (413),
`product_not_available`, `no_dealer_price`, `shipping_unavailable`, `order_too_large`, `order_rejected` (422), `rate_limited`, `daily_limit`, `open_orders_limit` (429), `payment_unavailable`, `feed_not_configured` (503), `internal_error`/`price_mismatch` (500).

## Limity (app_settings, nastavuje správce)
`dealer_api_max_orders_per_day` (100), `dealer_api_max_open_unpaid` (30 nezaplacených objednávek), `dealer_api_max_order_net_czk` (500 000 Kč bez DPH). Nejvýše 50 různých produktů a 10 000 ks na produkt v objednávce.
