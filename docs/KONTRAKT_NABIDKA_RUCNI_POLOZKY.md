# Ruční položky online nabídky (bot8, 2026-10-06)

Robert: *„možnost pro admina připsat do online nabídky další položky ručně z katalogu včetně vložení 3D modelu, parametrů a ceny“* a *„ručně jen jako volný text s načtením obrázku (1–2 ks) a ceny“*.
Admin je přidá v **Upravit nabídku** (pod tabulkou). Bez migrace: jsou to řádky `scene_offers.items` s klíčem `manual`. Kód: `api/scene_offers.py` (`_over_rucni_polozky`), `webapp/admin/js/crm-nabidky.js`
(`renderOfferEditManual`), `webapp/nabidka-online.html` (`manualCardsHtml`, `wireManualItems`). Testy: `scripts/2026-10-06_nabidka_montaz_polozky_testy/README.md`.

## Tvar řádku

```
{ "name", "dim", "qty": "N ks", "unit_price", "total",                       // jako řádky ze scény (PDF, stránka, objednávka je čtou stejně)
  "product_id" + "layer": "produkt"                                         // jen typ katalog
  "manual": { "typ": "katalog" | "text", "popis", "model": true,            // model jen u katalogu a jen když produkt má GLB
              "obrazky": ["polozka_<id nabídky>_<16 hex>.png|jpg", …] } }  // jen u typu text, nejvýš 2
```

Server vše znovu ověřuje (admin formulář jde obejít): cizí klíče zahodí, `total = qty × cena` přepočítá, produkt a GLB musí existovat, obrázek musí být nahraný k téže nabídce.
Limity: 20 položek / nabídka, název 200, rozměr 120, popis 2 000 znaků, množství 1–999 (celé, „N“ i „N ks“), cena 0–10 000 000 (bere i „1 234,5“), obrázky 2 / položka a 60 nahraných / nabídka.

## Pořadí a obyčejné řádky

Ruční položky jdou **vždy na konec** kusovníku. Obyčejné řádky (ze 3D scény / z konfigurace / z Vandru) nejde přidat, smazat, přejmenovat ani přeházet (jsou provázané s výkresy přes `mesh_group`;
řádek konfigurace zůstává první) – PUT s jiným počtem / jmény obyčejných řádků dostane 400. Mění se jen množství a ceny jako dosud.

## Endpointy (všechny v `api/scene_offers.py`)

| metoda a cesta | kdo | co |
|---|---|---|
| `PUT /api/admin/scene-offers/<id>` | `nabidky/upravit` | ukládá kusovník vč. ručních položek (revize se archivuje jako dřív) |
| `POST /api/admin/scene-offers/<id>/item-images` `{image: data URI}` | `nabidky/upravit` | nahraje PNG / JPEG (≤ 6 MB, kontrola hlavičky), vrátí `{key, url}` |
| `GET /api/admin/scene-offers/<id>/item-images/<key>` | `nabidky/zobrazit` | náhled v adminu |
| `GET /api/public/offers/<token>/item-image/<key>` | token | jen když ho nabídka (items) odkazuje a je aktivní / platná |
| `GET /api/public/offers/<token>/item-model/<product_id>` | token | GLB z katalogu jen když nabídka obsahuje položku s tímto produktem a `manual.model`; ETag / 304 |
| `GET /api/admin/scene-offers/<id>/edit-data` | | nově `rucni_polozky: {max, obrazky_max}` = příznak, že backend umí ruční položky |

## Admin

Editor (hledání v katalogu `/api/shop/products?all=1&q=`, cena z katalogu předvyplněná a přepsatelná, popis z katalogu bez HTML, 3D model zatrhnutý když ho produkt má; volný text s 1–2 obrázky,
fotky > 1,5 MB se zmenší na max 1 600 px JPEG; řazení ↑↓, odebrání ✕) se ukáže **jen když edit-data nese `rucni_polozky`** – statika je živá dřív než API, bez příznaku by starý backend uložil neověřená data.
Uložení počká na dokončení nahrávání obrázku. Odebraný obrázek zůstane jako soubor na disku (strop 60 / nabídka).

## Zákaznická stránka

Řádky jsou v cenové tabulce za obyčejnými (s odkazem „podrobnosti ↓“), pod tabulkou karty **Doplňující položky**: popis, obrázky (klik = zvětšení, Esc zavře), 3D model přes sdílený prohlížeč V3D
(`mode real`, lišta nad plátnem, bez kót) – načte se **až když je karta vidět**; selhání = karta bez modelu. Text se vkládá jako text (ne HTML). Tisk: bez 3D plátna a odkazů.

## Objednávka

Přijetí nabídky vloží ruční položky do `shop_order_items` jako ostatní řádky (`product_id` u katalogu, NULL u volného textu); množství i celkem se násobí počtem kusů, který zákazník zvolil.

## Omezení

- Montáž v % se počítá z celé ceny nabídky, tedy i z ručních položek.
- Model z katalogu se ukazuje tak, jak je v katalogu (bez animací a kót).
- Automatické PDF nabídky je od 2026-08-06 zrušené, takže starší PDF u starých nabídek ruční položky nemají.
