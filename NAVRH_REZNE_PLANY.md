# Návrh — řezné plány profilů a deskových materiálů podle zakázek

Autor: bot4 (Claude / Cowork, role "optimizer"), 2026-07-25.
Stav: NÁVRH, čeká na potvrzení Robertem před implementací DB migrace a nasazením.
Inspirace/studijní podklad: cutlistoptimizer.com (viz shrnutí v chatu se
zadáním) — 1D optimalizace pro tyče/profily, 2D optimalizace pro desky/panely.

## 0. Kontext zjištěný v kódu (proč tenhle návrh vypadá takhle)

- `shop_order_items` (viz `sql/2026-07-25_orders_schema.sql`, `api/orders.py`)
  dnes uchovává jen `product_name_snapshot` + `qty` + cena — žádný rozměr
  jednotlivého kusu k řezání.
- Katalog `cfg_dily` (profily z 3D scény, `api/app.py`) má u každého profilu
  jen REFERENČNÍ vzorek (`length_mm_ref`, typicky 1000 mm) + průřez
  (`cross_section_mm`) — to je vzorek pro 3D náhled, ne objednaná délka.
- `webapp/scene.html` / AI modul (`/api/ai/generate`) už ALE umí zadat
  libovolnou `length_mm` na díl (max `PROFILE_MAX_LENGTH_MM`, viz
  `PROFILY_KATALOG.md` bod 1: max 3000 mm) — tohle je skutečná řezaná
  délka konkrétního kusu v sestavě.
- Robert (2026-07-25, v chatu k tomuto úkolu): **"rozměry materiálu budou
  vycházet z produktů, vzniklé z 3D scény"** — tzn. plánovaný tok je
  3D scéna (kusovník sestavy) → položka objednávky s konkrétním rozměrem
  kusu (délka u profilu, W×H u desky), ne fixní katalogová položka jako
  dnešní `shop_products`. Tahle vazba (scéna → objednávka s rozměry) ještě
  NENÍ implementovaná — je to nutná součást téhle práce, ne jen navazující
  modul.

## 1. Datový model — rozšíření `shop_order_items`

Místo nové tabulky navrhuji rozšířit přímo `shop_order_items` (drží se
stávající konvence "položka objednávky = snapshot v okamžiku objednání",
viz `orders.py` docstring) o sloupce, všechny NULLable (staré položky typu
"produkt z katalogu" beze změny):

```sql
ALTER TABLE shop_order_items
  ADD COLUMN cut_kind        VARCHAR(10)  NULL,   -- 'profil' | 'deska' | NULL (běžný produkt)
  ADD COLUMN material_key    VARCHAR(40)  NULL,   -- např. '30x30' (profil) nebo 'MDF_18' (deska)
  ADD COLUMN length_mm       DECIMAL(8,1) NULL,   -- profil: řezaná délka
  ADD COLUMN width_mm        DECIMAL(8,1) NULL,   -- deska: šířka kusu
  ADD COLUMN height_mm       DECIMAL(8,1) NULL,   -- deska: výška/hloubka kusu
  ADD COLUMN grain_locked    TINYINT(1)   NOT NULL DEFAULT 0, -- deska: nesmí se otočit o 90°
  ADD COLUMN source_scene_id VARCHAR(64)  NULL;   -- volitelná vazba na uloženou scénu/sestavu
```

`qty` na položce = počet stejných kusů (stejná délka/rozměr) v rámci
objednávky — beze změny stávající logiky.

## 2. Datový model — skladové (stock) rozměry materiálu

Nová tabulka, admin-editovatelná (stejný vzor jako `shop_shipping_methods`
CRUD v `orders.py`):

```sql
CREATE TABLE shop_cutting_stock (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    cut_kind      VARCHAR(10)  NOT NULL,  -- 'profil' | 'deska'
    material_key  VARCHAR(40)  NOT NULL,  -- váže se na cut_kind+material_key v shop_order_items
    label         VARCHAR(100) NOT NULL,  -- "Tyč 6000 mm" / "Deska MDF 18mm 2800x2070"
    stock_length_mm DECIMAL(8,1) NULL,    -- profil
    stock_width_mm  DECIMAL(8,1) NULL,    -- deska
    stock_height_mm DECIMAL(8,1) NULL,    -- deska
    price_czk      DECIMAL(12,2) NOT NULL DEFAULT 0,
    active         TINYINT(1) NOT NULL DEFAULT 1,
    sort_order     INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE shop_cutting_settings (
    material_key   VARCHAR(40) PRIMARY KEY,
    kerf_mm        DECIMAL(5,2) NOT NULL DEFAULT 3.0,  -- šířka řezu (pilový kotouč)
    orientation_locked TINYINT(1) NOT NULL DEFAULT 0    -- deska: směr vláken závazný globálně
);
```

Profily: `material_key` = průřez (`"30x30"`, `"45x90"`, ...) — napojuje se
na existující katalog průřezů z `PROFILY_KATALOG.md` bod 2b (11
průřezů). Desky: `material_key` = typ/tloušťka materiálu (zatím žádný
katalog desek v projektu neexistuje — je potřeba ho založit, mimo rozsah
tohoto návrhu, pokud nechceš přidat rovnou).

## 3. Algoritmus (`api/cutting.py`, čistě funkce bez DB závislosti — testovatelné izolovaně)

**1D (profily):** First-Fit-Decreasing bin packing přes dostupné skladové
délky daného průřezu (víc velikostí skladem povoleno, algoritmus zkouší
nejdřív "vejde se do už rozřezané tyče", pak novou nejmenší vhodnou).
Mezi řezy se odečítá `kerf_mm`. Přednostně plní tyče, na kterých zbyde co
nejméně odpadu (best-fit varianta).

**2D (desky):** Guillotine shelf algoritmus — díly seřazené sestupně podle
výšky, "police" (shelf) na desce podle výšky, uvnitř police plněno zleva
doprava podle šířky. Guillotine (řez od okraje k okraji) je záměrně
zvolený i přes o něco horší využití než volné 2D bin-packing algoritmy,
protože odpovídá tomu, jak reálně řeže formátovací pila (viz i chování
cutlistoptimizer.com) — řezný plán musí být fyzicky proveditelný, ne jen
matematicky nejúspornější. Respektuje `grain_locked` (bez rotace o 90°) a
`kerf_mm` mezi díly.

**Výstup obou:** seznam "mosaic" (jedna skladová tyč/deska + na ní
umístěné kusy s pozicí), statistiky (využitá/odpadní plocha nebo délka,
počet potřebných tyčí/desek, nevešlé kusy).

## 4. API a UI

- `GET /api/admin/orders/<id>/cutting-plan` — spočítá a vrátí plán ze
  všech položek objednávky s `cut_kind IS NOT NULL`, seskupeno po
  `material_key`. Bez uložení do DB (přepočítá se na vyžádání) v první
  verzi — pokud budeš chtít historii/verzování plánu, přidám tabulku
  `shop_cutting_plans` (uložený snapshot, podobně jako `shop_orders`
  → PDF dokumenty v `documents.py`).
- UI (oblast bot2 — admin rozhraní; napíšu do `AGENTS_LOG.md`, ať to
  nekoliduje): panel v detailu objednávky "Řezný plán" s grafickým
  náhledem (SVG tyče/desky s vyznačenými řezy) + tabulka
  spotřeby/odpadu, tlačítko export PDF (přes `documents.py`, na dílnu).

## 5. Otázky — POTVRZENO Robertem (2026-07-25)

1. **Katalog deskových materiálů — počáteční sada (rozšiřitelná):**
   - Překližka 10 mm, skladový formát **2500 × 1250 mm**.
   - MDF 8 mm, skladový formát **2800 × 2070 mm**.
   Obě jako řádky v `shop_cutting_stock` (`cut_kind='deska'`,
   `material_key` např. `"preklizka_10"` / `"mdf_8"`). Ceny zatím
   placeholder (0 Kč), dokud Robert nedodá ceník — stejný postup jako u
   `PREHLED_ROZHODNUTI.md` materiálových hustot.
2. **Skladové délky profilů:** reálná tyč od dodavatele je max
   **3005 mm**, ale plánuje se s rezervou na **max 3000 mm** (bezpečná
   marže na nerovný konec / prořez). `shop_cutting_stock` pro profily
   tedy `stock_length_mm = 3000` (ne 3005) — sedí i s
   `PROFILE_MAX_LENGTH_MM` v `PROFILY_KATALOG.md`.
3. **Vazba scéna → objednávka s rozměry:** řeší **jiný bot**, NE bot4.
   Bot4 (tahle oblast) se tedy nedotýká `webapp/scene.html` ani toku
   vytvoření objednávky (`api/orders.py::_resolve_and_insert_order`) —
   jen převezme položky objednávky, jakmile v nich rozměry budou
   (`length_mm`/`width_mm`/`height_mm` dle bodu 1 návrhu), a spočítá z
   nich řezný plán. Sloupce v `shop_order_items` (bod 1) je ale potřeba
   mít v DB dřív, než ta druhá práce začne položky s rozměry ukládat —
   koordinace kdo/kdy spouští tu konkrétní migraci patří do
   `AGENTS_LOG.md`, ne do domněnky.
4. **Kerf (šířka řezu)** — zatím bez explicitního potvrzení, ponechávám
   navrhovaný výchozí odhad **3 mm** (nastavitelný per-materiál v
   `shop_cutting_settings`, viz bod 2) — snadno se doladí později, nejde
   o blokující rozhodnutí pro strukturu.
