# Návrh: hromadné akce nad vybranými řádky (napříč tabulkami v adminu)

Autor: bot4 ("optimizer"). Robert (2026-07-26) poslal screenshot Shoptet
administrace (Přehled produktů → zaškrtnutí řádků → dropdown "FUNKCE":
Smazat produkt i varianty, Zviditelnit, Skrýt, Nastavit viditelnost,
Přesunout, Zkopírovat, Změnit výchozí kategorii, Změnit příznak, Odebrat
z importu, Přidat kategorii, Odebrat kategorii) a požádal: *"připrav
rozšíření backendu pro bota 3 ať máme na všech tabulkách napříč podobné
možnosti jako na tomto screenu."*

Tohle je **návrh pro bota 3** (backend/objednávky/RBAC) k implementaci -
bot4 do `api/app.py` ani do jiných bot3 souborů (`orders.py`,
`customers.py`, `purchase_orders.py`, `gallery.py`, `support.py`) přímo
nezasahuje, jen připravuje podklad + katalog konkrétních akcí, aby se
nevymýšlelo od nuly. UI stranu (checkboxy, dropdown, toolbar) bude řešit
bot2 - viz sekce 5, frontend vzor už ostatně částečně existuje.

## 1. Co už v systému existuje (zjištěno průzkumem `admin.html` + `app.py`)

Hromadné akce **nejsou nová věc** - už existují na 2 místech, akorát
každé řešené samostatně/duplicitně:

- **Tab "Sklad e-shopu" (`tab-shop`, produkty)** - checkbox sloupec +
  `#shopSelectAll` + toolbar `#shopBulkToolbar` (výběr kategorie +
  tlačítka Archivovat/Obnovit). Backend: `PUT /api/shop/products/bulk`
  (`app.py:1602`) - bere `{"ids":[...], "category_id"?, "is_archived"?,
  "active"?}`, whitelistuje pole, jedno hromadné `UPDATE ... WHERE id IN
  (...)`, zaloguje do `audit_log`.
- **Tab "Doplnění skladu" (`tab-reorder`)** - checkbox sloupec +
  `#reorderSelectAll` + toolbar `#reorderBulkToolbar` (označit k
  objednání / vrátit / vytvořit nákupní objednávku z vybraných).
  Backend: `POST /api/shop/reorder-items/select` (`app.py:2329`) +
  navazující tvorba PO z vybraných položek.
- **Zákazníci** mají `DELETE /api/admin/customers` (`customers.py:513`)
  - ale to je "smazat VŠECHNY" s `confirm_count` pojistkou, ne mazání
    VYBRANÉ podmnožiny. Jiný vzor, nezaměňovat.

Všechny ostatní tabulky (objednávky, zákazníci - výběrové mazání,
dodavatelé, nákupní objednávky, uživatelé, galerie, kategorie, support,
doklady, e-maily, ceny/příslušenství) **nemají žádný checkbox ani
hromadnou akci** - jen řádkové akce (klik na řádek → modal, nebo tlačítko
"Smazat" per řádek).

RBAC: `require_permission(section, action)` v `app.py:316`, sekce =
`PERMISSION_SECTIONS` (`objednavky`, `nakupni_objednavky`, `doklady`,
`emaily`, `zakaznici`, `doprava_platba`, `produkty_sklad`,
`kategorie_obsah`, `ceny_prislusenstvi`, `uzivatele`, `nastaveni`,
`audit_log`, `kosiky`), akce = `zobrazit/vytvorit/upravit/smazat`. Každá
hromadná akce musí použít STEJNOU sekci/akci jako odpovídající řádková
akce dané entity (žádná nová sekce jen kvůli bulk).

## 2. Doporučený obecný backend vzor

**Necentralizovat do jednoho "mega" endpointu** (`POST /api/bulk` se
dispatch podle entity by komplikoval `require_permission`, protože každá
entita má jinou sekci). Místo toho: **sdílené pomocné funkce + samostatný
endpoint per entita**, stejně jako dnes (`.../bulk`), jen bez kopírování
stejné validace v každém endpointu znovu.

Návrh dvou helperů do `app.py` (vedle `log_audit`), které si `orders.py`/
`customers.py`/atd. naimportují stejně jako `get_conn`/`require_permission`:

```python
def parse_bulk_ids(body):
    """Validace {"ids":[...]} - vraci (ids:list[int], error_response|None)."""
    ids = body.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return None, (jsonify({"error": "Vyber alespoň jednu položku."}), 400)
    try:
        return [int(i) for i in ids], None
    except (TypeError, ValueError):
        return None, (jsonify({"error": "Neplatná id."}), 400)


def bulk_update_fields(cur, table, ids, field_updates):
    """field_updates: {sloupec: hodnota}. Vraci pocet updatnutych radku.
    NEPOUZIVAT pro entity, kde zmena pole ma VEDLEJSI UCINKY (napr. zmena
    stavu objednavky odecita/vraci sklad, zmena stavu nakupni objednavky
    generuje pohyby) - tam se musi HROMADNE VOLAT existujici jednopolozkova
    funkce v cyklu (viz sekce 4), ne primy UPDATE."""
    if not field_updates:
        raise ValueError("bulk_update_fields: prazdne field_updates")
    placeholders = ",".join(["%s"] * len(ids))
    set_clause = ", ".join(f"{col}=%s" for col in field_updates)
    cur.execute(
        f"UPDATE {table} SET {set_clause} WHERE id IN ({placeholders})",
        list(field_updates.values()) + ids,
    )
    return cur.rowcount


def bulk_delete(cur, table, ids):
    placeholders = ",".join(["%s"] * len(ids))
    cur.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", ids)
    return cur.rowcount
```

Použití v konkrétním endpointu (příklad, ne finální kód):

```python
@app.post("/api/admin/gallery/bulk-delete")
@require_permission("kategorie_obsah", "smazat")
def gallery_bulk_delete():
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err: return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            deleted = bulk_delete(cur, "shop_gallery_images", ids)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "bulk_delete", "gallery_image", None, f"{deleted} obrázků")
    return jsonify({"status": "ok", "deleted": deleted})
```

**Pravidlo pro entity s vedlejšími účinky** (objednávky, nákupní
objednávky - mění sklad/generují doklady): hromadná akce NESMÍ dělat
holý `UPDATE`. Musí v cyklu zavolat STÁVAJÍCÍ jednopoložkovou funkci
(např. tu, co dnes obsluhuje `PUT /api/admin/orders/<id>`), sesbírat
úspěchy/chyby per položka a vrátit `{"updated": N, "failed": [{"id":,
"error":}, ...]}` - žádná položka se nesmí "ztratit" beze zprávy, pokud
selže (např. objednávka už je `zrušena` a přechod není povolen).

## 3. Konvence API kontraktu (pro konzistenci napříč entitami)

- Metoda/cesta: `POST /api/admin/<entita>/bulk-<akce>` (např.
  `/api/admin/orders/bulk-status`, `/api/admin/gallery/bulk-delete`,
  `/api/admin/products/bulk-visibility`) - explicitní akce v URL, ne
  jeden endpoint s `{"action": "..."}` polem (čitelnější v logu requestů,
  jednodušší per-akce permission úvahy do budoucna, kdyby se lišily).
- Tělo vždy obsahuje `{"ids": [int, ...], ...další pole dle akce}`.
- Odpověď vždy `{"status": "ok", "updated"|"deleted": N, "failed": [...]}
  (`failed` jen tam, kde má smysl - viz sekce 2).
- Vždy `log_audit(admin["id"], "bulk_<akce>", "<entity_type>", None,
  "<N> položek: <shrnutí>")` - jeden log řádek za celou dávku, ne per
  položka (jinak audit log zahltí, viz existující `bulk_update`/
  `bulk_delete` vzor v `app.py:1637`/`1672`).
- Vždy stejná `require_permission(section, action)` jako řádková akce
  dané entity.

## 4. Katalog konkrétních akcí per tabulka (návrh rozsahu, priorita moje)

| Tabulka (tab) | Chybí dnes | Navržené hromadné akce | Poznámka |
|---|---|---|---|
| **Objednávky** (`tab-orders`) | vše | Hromadná změna stavu (respektovat jednosměrný přechod stavů - `orders.py:934` logiku), hromadné nastavení příznaku "urgentní" | Stav MUSÍ jít přes stávající funkci (sklad se odečítá/vrací) - viz sekce 2 |
| **Zákazníci** (`tab-customers`) | vše (jen "smazat vše" existuje) | Smazat VYBRANÉ (doplněk k `DELETE /api/admin/customers`), hromadné přiřazení do skupiny zákazníků | |
| **Dodavatelé** (v `tab-purchaseorders`) | vše | Aktivovat/deaktivovat vybrané | |
| **Nákupní objednávky** (`tab-purchaseorders`) | vše | Hromadná změna stavu | Pozor na navázané sklad. pohyby/doklady - přes existující funkci, ne holý UPDATE |
| **Produkty e-shopu** (`tab-shop`) | částečně (kategorie, archiv) | DOPLNIT: hromadné smazání vybraných, hromadná viditelnost (`active` už je v bulk endpointu podporováno poli, jen chybí UI toggle) | Rozšíření stávajícího `PUT /api/shop/products/bulk`, ne nový endpoint |
| **Galerie** (`tab-gallery`) | vše | Smazat vybrané, hromadná viditelnost/aktivní | |
| **Kategorie** (`tab-categories`) | vše | Přesunout vybrané pod jinou nadřazenou kategorii | Odpovídá Shoptet "Přesunout" |
| **Uživatelé** (`tab-users`) | vše | Hromadná změna role, aktivovat/deaktivovat | POZOR: nesmí jít odebrat aktivní stav poslednímu adminovi - stejná pojistka jako (pokud existuje) u řádkové akce |
| **Podpora** (`tab-support`) | vše | Hromadné uzavření/změna stavu konverzace | |
| **Doplnění skladu** (`tab-reorder`) | má bulk už | - | beze změny |

Sloupce "Zkopírovat", "Změnit příznak", "Odebrat z importu" ze
Shoptet screenshotu nemají v našem datovém modelu dnes přímý ekvivalent
(žádný "flag"/tag sloupec u produktů, žádný koncept "import" u
jednotlivé položky mimo Shoptet sync) - **otevřená otázka pro bota 3/
Roberta** níže, ne že bych to zamlčel.

## 5. Frontend (informativně pro bota 2, ne úkol bota 3)

Až budou endpointy hotové, UI strana může replikovat existující vzor
1:1 (`admin.html`: `.bulk-toolbar` CSS třída ~řádek 154-159,
`updateShopBulkToolbar`/`shopSelectAll.onchange` ~2507-2530,
`updateReorderBulkToolbar` ~4028) - stejná checkbox+toolbar kostra,
jen navázaná na nové endpointy. Nemá cenu to teď duplicitně
předepisovat, stačí odkaz na existující funkční příklad v kódu.

## 6. Otevřené otázky (pro Roberta/bota 3, ne blokující start práce)

1. Existuje/má se zavést "příznak"/tag u produktů (Shoptet "Změnit
   příznak")? Dnes v `shop_products` není.
2. Má smysl "Odebrat z importu" - u nás analogie by byla např. odpojení
   produktu od Shoptet synchronizace (`shoptet_id = NULL`)? Rizikové,
   potřeba Robertovo potvrzení než se implementuje.
3. Priorita pořadí implementace - já bych začal Objednávkami a
   Zákazníky (nejčastěji používané tabulky), ale nechávám na botovi 3/
   Robertovi.

---
*Návrh, ne hotová implementace. Bot4 nezasahoval do žádných bot3/bot2
souborů - viz `AGENTS_LOG.md` pro záznam.*
