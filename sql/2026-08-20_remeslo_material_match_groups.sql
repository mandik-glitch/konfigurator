-- Řemeslo - Srovnávač: "match group" vrstva pro PŘÍMÉ srovnání stejné
-- věci napříč dodavateli (bot14, 2026-08-20, Robertovo zadání).
--
-- Robert poslal vzorovou tabulku: řádky = obecný typ položky napříč
-- dodavateli (spojka A / spojka B / koleno X1A...), sloupce =
-- dodavatelé, čísla = cena - PŘÍMÉ srovnání stejné věci, ne dnešní
-- cenové řazení celé kategorie. Dřív ověřeno živě: přesná shoda
-- product_name napříč dodavateli je téměř nulová (1 produkt z 8800+)
-- - dodavatelé prodávají různé značky/SKU stejného typu zboží, takže
-- párování musí jít podle TYPU+ROZMĚRU vytaženého z názvu, ne podle
-- přesné shody textu.
--
-- ÚMYSLNĚ ADITIVNÍ - žádná změna/mazání remeslo_material_prices.
-- remeslo_material_price_match je jen vazební tabulka (1 cenový
-- řádek patří max do JEDNÉ skupiny - UNIQUE (material_price_id)),
-- žádný cenový řádek se nikdy nepřepisuje ani neduplikuje. Položka
-- BEZ řádku v remeslo_material_price_match = nespárovaná, chová se
-- přesně jako dřív (flat cenový seznam v /api/remeslo/compare).
--
-- match_method - dnes jen 'auto_regex' (typ+rozměr vytažený z názvu
-- skriptem), sloupec připraven na budoucí 'manual' (ruční oprava/
-- doplnění admina), aby šlo v UI kdykoli rozlišit důvěryhodnost.
--
-- Použití: python api/db_migrate_remeslo.py sql/2026-08-20_remeslo_material_match_groups.sql

CREATE TABLE IF NOT EXISTS remeslo_material_match_groups (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    category_id     INT NOT NULL,
    canonical_name  VARCHAR(255) NOT NULL,
    item_type       VARCHAR(100) NULL,
    dimension_key   VARCHAR(100) NULL,
    match_method    VARCHAR(20) NOT NULL DEFAULT 'auto_regex',
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_mmg_category
        FOREIGN KEY (category_id) REFERENCES remeslo_material_categories(id) ON DELETE CASCADE,
    UNIQUE KEY uq_category_type_dim (category_id, item_type, dimension_key),
    KEY idx_category (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_material_price_match (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    material_price_id   INT NOT NULL,
    match_group_id      INT NOT NULL,
    matched_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_mpm_price
        FOREIGN KEY (material_price_id) REFERENCES remeslo_material_prices(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_mpm_group
        FOREIGN KEY (match_group_id) REFERENCES remeslo_material_match_groups(id) ON DELETE CASCADE,
    UNIQUE KEY uq_price (material_price_id),
    KEY idx_group (match_group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
