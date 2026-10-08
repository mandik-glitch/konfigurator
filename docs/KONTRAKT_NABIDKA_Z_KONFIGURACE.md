# Kontrakt: konfigurace stolu → online nabídka (bot5, 2026-10-06)

Zadání Robert (2026-10-06): tlačítko „promítnout konfiguraci stolu do online nabídky“ v KAŽDÉM generátoru (systém 30 / 35 / 40 / 41).
Rozdělení: **bot5 backend + stránka nabídky**, **bot16 tlačítko a dialog** (sdílený kód generátorů), bot8 `stul_shop` (výběr, cena, GLB), bot10 sanitizer GLB a data systémů.
Rozhodnutí Roberta (2026-10-06, klik v okně bot5): **tlačítko zatím vidí a nabídku tvoří JEN zaměstnanec**; zákaznické tlačítko až později na jeho pokyn.
První verze: **jedna nabídka = jedna konfigurace s množstvím**; do rozpracované nabídky se zatím nepřidává (seznam otevřených nabídek se nepotřebuje).
Stav: backend se kóduje; do nasazení API endpoint neexistuje → UI musí tlačítko ukázat až po úspěšné sondě (viz „Sonda“).

## Sonda (pro UI před nasazením)
`GET /api/admin/konfigurace/nabidka` → `200 {"ok": true, "verze": 1}` jen pro přihlášeného zaměstnance s právem; `401`/`403` = bez práva (tlačítko skrýt), `404` = backend ještě neběží (tlačítko skrýt).

## Vytvoření nabídky
`POST /api/admin/konfigurace/nabidka` (JSON). Právo: sekce `nabidky`, akce `vytvorit` (stejné jako ruční tvorba nabídky); bez práva `403`.

```json
{
  "product_id": 4934,
  "configuration": {"selection": {"...": "..."}, "rules_version": "2026-10-05.2"},
  "qty": 1,
  "montaz_pct": null,
  "delivery_country": "CZ",
  "customer": {"name": "Jan Novák", "email": "jan@firma.cz"},
  "hash": "volitelné, kontrolní hash konfigurace, kterou uživatel vidí"
}
```
- `product_id` = karta generátoru (4934 / 4954 / 4955 / 4959 …); **systém se pozná z karty** (stejně jako v košíku). Karta nemusí být aktivní (staff); musí být konfigurovatelná (`stul_shop.konfigurovatelny`).
- `configuration.selection` + `rules_version` stačí. Cenu, kód, hash, kusovník a model si server spočítá sám; cokoli od klienta navíc (cena, název, kusovník) se ignoruje. `hash` je volitelný: když je a server dostane jiný, vrací `409 configuration_changed` (uživatel vidí jinou konfiguraci než server vyhodnotil).
- `qty` 1–99 (výchozí 1) = VÝCHOZÍ počet kusů na stránce nabídky (zákazník ho tam smí změnit, jako u všech nabídek); `total_price` nabídky je cena 1 ks. V odpovědi `price`/`line.total_net_czk` jsou za `qty` kusů.
- `montaz_pct`: `null` = výchozí sazba stolů (`app_settings.stul_montaz_pct`, dnes 12), číslo 0–100 = sazba pro tuto nabídku (0 = montáž se nenabízí). Montáž je v nabídce VOLITELNÁ služba mimo cenu (rozhoduje `_offer_montaz_pct`, platí jen pro dodání v ČR; do zahraničí se vynutí 0).
- `delivery_country` ISO-2 (výchozí `CZ`). `customer` nepovinné (jméno, e-mail; e-mail se NIKAM neposílá, pravidlo 16).

### Odpověď `201`
```json
{
  "offer_id": 123, "offer_number": "Logiman5015", "online_url": "/nabidka-online.html?t=<token>",
  "line": {"kod": "S30-…", "hash": "…", "qty": 1, "unit_net_czk": 26180, "total_net_czk": 26180},
  "price": {"net_czk": 26180, "vat_rate": 21, "vat_czk": 5498, "gross_czk": 31678},
  "montaz": {"pct": 12, "czk": 3142},
  "rules_version": "2026-10-05.2", "v3d": true, "v3d_duvod": null
}
```
- Cena = **prodejní cena generátoru bez DPH** (stejný zdroj `configurator_price` jako košík; žádná zvláštní „staff cena“). Skupinová sleva zákazníka, kupóny a dealerská cena se na konfiguraci neuplatní. Montáž je zvlášť (`montaz`), není v `price`.
- `v3d:false` = nabídka vznikla, ale bez interaktivního 3D (model se nepodařilo postavit); stránka ukáže souhrn bez modelu.
- Po úspěchu UI otevře `online_url` v novém panelu/záložce (to je stránka, kterou uvidí zákazník; relativní adresa). Úprava nabídky je v adminu pod `offer_id`.
- Endpoint NENÍ idempotentní (dva kliky = dvě nabídky): tlačítko drží stav „Vytvářím…“ do odpovědi. Limit 30 nabídek za hodinu na uživatele (429 `rate_limited`).
- Platba u těchto nabídek je jen předem (výroba na zakázku, jako košík a mini-shop); e-mail zákazníkovi se NIKAM neposílá (pravidlo 16).

### Chyby (kódy jako u košíku, tělo `{"error": "<kód>", "message": "…"}`)
| status | `error` | význam |
|---|---|---|
| 400 | `invalid_selection` / `items_invalid` | neplatný tvar výběru (`invalid_selection`); neplatné `qty`, `montaz_pct`, `delivery_country`, `customer` (`items_invalid`) |
| 403 | `forbidden` | bez práva `nabidky.vytvorit` |
| 404 | `not_configurable` | karta není konfigurovatelný stůl |
| 409 | `rules_changed` | pravidla generátoru se změnila, načíst konfiguraci znovu |
| 409 | `configuration_changed` | zadaný `hash` nesedí na serverem vyhodnocenou konfiguraci |
| 409 | `price_on_request` | cena konfigurace není k dispozici |
| 422 | `invalid_configuration` + `errors:[{slot,message}]` | konfiguraci nelze vyrobit |
| 429 | `rate_limited` | příliš mnoho nabídek (limit na uživatele) |

## Co stránka nabídky ukáže (bot5)
`source = configurator`: 3D model (V3D, sanitizovaný snímek GLB, stažení není), souhrn voleb (bez čísel dílů a dodavatelů), kód konfigurace, množství, cena bez DPH + DPH, volitelná montáž. Cena i konfigurace jsou SNÍMEK v okamžiku vytvoření (pozdější změna ceníku nebo pravidel vydanou nabídku nezmění). Přijetí nabídky zakládá objednávku s řádkem konfigurace (`product_id` NULL, kód, snímek) a montáží jako samostatným řádkem, stejně jako košík.
