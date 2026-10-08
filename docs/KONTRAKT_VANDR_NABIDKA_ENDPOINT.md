# Kontrakt: tlačítko „Vytvořit online nabídku“ na kartě Vandr (bot10, 2026-10-02)

Odpovědi na dotazy bot16 (tlačítko na `product.html`) + stav endpointu. Platí pro `api/vandr_scene_offers.py::vandr_vyroba_vytvorit_nabidku`.
3D část (pohyby v online nabídce) se napojí do téhož endpointu zpětně kompatibilně, viz konec.

## Endpoint
`POST /api/admin/vandr-vyroba/<shop_product_id>/nabidka`, bez těla (žádné JSON vstupy), cookie session jako ostatní admin API.

## 1) Idempotence: NENÍ idempotentní
Každé zavolání vytvoří **novou nabídku** (nové `offer_id`, nové `offer_number`, nový token). Žádná deduplikace podle karty. Proto v UI:
tlačítko po klepnutí zablokovat do odpovědi, před voláním potvrzení („Vytvořit novou online nabídku z této karty?“), po úspěchu ukázat odkaz
a tlačítko nenabízet hned znovu. Chceš-li deduplikaci (jedna otevřená nabídka na kartu), řekni - přidám volitelný `?reuse=1`, dnes neexistuje.

## 2) Odpověď (HTTP 201)
```json
{ "status": "ok", "offer_id": 123, "offer_number": "N-2026-0123", "online_url": "/nabidka-online.html?t=<token>",
  "rozmer_mm": [x, y, z], "pocet_profilu": 40, "vandr_car_name": "Ford Transit L3H3 FWD" }
```
Pole `offer_id`, `offer_number`, `online_url` potvrzuji. `online_url` je relativní (doplň origin). Chyby: HTTP 400/404/500 s `{"error": "<česká věta pro admina>"}`
(např. „Karta ještě nemá hotový 3D model“, „Karta ještě nemá cenu“, „Načtení dat z Vandru selhalo“). Zobraz text beze změny.
**Přibude (zpětně kompatibilně, po napojení 3D):** `v3d` (true/false), `v3d_duvod` (text, když `v3d:false`), `v3d_varovani` (pole textů jen pro admina),
`v3d_ms`, `v3d_cache`. Při `v3d:false` je nabídka platná se statickým modelem jako dnes; UI to jen zobrazí jako poznámku.

## 3) Kdo smí
`@require_permission("sdileny_disk", "zobrazit")` = **ne „jen admin“, ale kdokoli, kdo má v RBAC právo `sdileny_disk/zobrazit`** (admin ano, jiné role jen když jim ho Robert dal).
UI proto podmiň stejným právem (ne `role==='admin'`). Bez práva vrací endpoint 403.

## 4) Kdy tlačítko skrýt: podmínky přesně jako v endpointu
Karta smí mít tlačítko, jen když platí všechno: `sku` začíná `VD-`, `glb_file` je vyplněný (a soubor existuje na disku), `price_czk_placeholder` není NULL.
Jinak endpoint vrací 400. Pro konfigurovatelný stůl (např. karta 4934, SKU není `VD-…`) tlačítko **skrýt**.
Staff JSON karty ať nese `can_create_offer: {ok: true|false, duvod: "…"}`; stejnou logiku vystavím jako funkci
`vandr_scene_offers.can_create_offer(karta_row) -> (bool, duvod)`, ať se pravidlo nedublikuje (přidá se spolu s napojením 3D).

## 5) Montáž v %
Endpoint žádný vstup `montaz_pct` nebere. Nabídka vzniká s `scene_offers.OFFER_OPTIONS_DEFAULT` (+ `vandr_single_drawing`, `hidden_payment_method`),
sazbu montáže řeší bot5 (`offer_options.montaz_pct`, `_offer_montaz_pct`). Má-li ji admin volit při vytvoření z karty, musí bot5 potvrdit a
doplním volitelný `{"montaz_pct": <číslo>}` v těle (výchozí = dnešní chování). Do té doby UI žádné pole montáže nezobrazuje.
