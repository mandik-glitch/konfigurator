-- Řemeslo - Modul 9 (Kalkulačky + Ceník), CAST 1: Ceník - bot11, 2026-08-19.
-- Viz REMESLO_KONCEPT.md "Modul 9" pro schéma/zdůvodnění (schváleno
-- bot3/Robertem před implementaci).
--
-- Aktuální cena zůstává mutable pole na remeslo_pricelist_items (rychlé
-- čtení "kolik to teď stojí"), remeslo_pricelist_item_price_history je
-- append-only log zapisovaný PŘED každou změnou price_czk/vat_percent/
-- valid_from (v api/remeslo.py, ne trigger).
--
-- Použití: python api/db_migrate.py sql/2026-08-19_remeslo_pricelist.sql

CREATE TABLE IF NOT EXISTS remeslo_pricelist_categories (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id    INT NULL,        -- NULL = systemova kategorie (sdilena
                                      -- vsemi), vyplnene = vlastni kategorie
                                      -- KONKRETNIHO remeslnika ("Pridat
                                      -- vlastni kategorii")
    name            VARCHAR(255) NOT NULL,
    is_system       TINYINT NOT NULL DEFAULT 0,
    sort_order      INT NOT NULL DEFAULT 0,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_pricelist_categories_craftsman
        FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id) ON DELETE CASCADE,
    KEY idx_craftsman (craftsman_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_pricelist_items (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    category_id         INT NOT NULL,
    craftsman_id        INT NOT NULL,           -- cena je VZDY per-remeslnik
                                                 -- (jeho vlastni nakupni cena od
                                                 -- JEHO dodavatele), i u systemove
                                                 -- polozky/kategorie
    name                VARCHAR(255) NOT NULL,
    unit                VARCHAR(20) NOT NULL,
    price_czk           DECIMAL(10,2) NULL,     -- NULL = "nenacenovano", nikdy
                                                 -- tise nahrazovano nulou
    vat_percent         DECIMAL(5,2) NULL,
    valid_from          DATE NULL,              -- "Platna k"
    supplier            VARCHAR(255) NULL,
    note                TEXT NULL,
    is_used             TINYINT NOT NULL DEFAULT 1,
    is_mandatory        TINYINT NOT NULL DEFAULT 0,
    is_system           TINYINT NOT NULL DEFAULT 0,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_pricelist_items_category
        FOREIGN KEY (category_id) REFERENCES remeslo_pricelist_categories(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_pricelist_items_craftsman
        FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id) ON DELETE CASCADE,
    KEY idx_category (category_id),
    KEY idx_craftsman (craftsman_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_pricelist_item_price_history (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    item_id         INT NOT NULL,
    price_czk       DECIMAL(10,2) NULL,
    vat_percent     DECIMAL(5,2) NULL,
    valid_from      DATE NULL,
    changed_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_pricelist_item_price_history_item
        FOREIGN KEY (item_id) REFERENCES remeslo_pricelist_items(id) ON DELETE CASCADE,
    KEY idx_item (item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Seed: systemove kategorie (is_system=1, craftsman_id=NULL) - sdilene
-- vsemi remeslniky, polozky uvnitr NECHAVAME prazdne (kazdy remeslnik
-- si doplni vlastni nakupni ceny pres "+ Vlastni material"). Zahrnuje
-- kategorie pro budoucich 9 kalkulacek (mimo "Univerzalni kalkulace",
-- ta nema vlastni kategorii/predmet) + kategorie navic jen pro Cenik
-- (bez vlastni kalkulacky, viz TASKS.md zadani).
INSERT INTO remeslo_pricelist_categories (craftsman_id, name, is_system, sort_order)
SELECT * FROM (SELECT NULL AS craftsman_id, 'Zámková dlažba' AS name, 1 AS is_system, 10 AS sort_order) t
WHERE NOT EXISTS (SELECT 1 FROM remeslo_pricelist_categories WHERE name='Zámková dlažba' AND is_system=1)
UNION ALL SELECT * FROM (SELECT NULL, 'Obklady a dlažby', 1, 20) t
WHERE NOT EXISTS (SELECT 1 FROM remeslo_pricelist_categories WHERE name='Obklady a dlažby' AND is_system=1)
UNION ALL SELECT * FROM (SELECT NULL, 'Malování', 1, 30) t
WHERE NOT EXISTS (SELECT 1 FROM remeslo_pricelist_categories WHERE name='Malování' AND is_system=1)
UNION ALL SELECT * FROM (SELECT NULL, 'Sádrokarton', 1, 40) t
WHERE NOT EXISTS (SELECT 1 FROM remeslo_pricelist_categories WHERE name='Sádrokarton' AND is_system=1)
UNION ALL SELECT * FROM (SELECT NULL, 'Podlahy', 1, 50) t
WHERE NOT EXISTS (SELECT 1 FROM remeslo_pricelist_categories WHERE name='Podlahy' AND is_system=1)
UNION ALL SELECT * FROM (SELECT NULL, 'Fasáda a zateplení', 1, 60) t
WHERE NOT EXISTS (SELECT 1 FROM remeslo_pricelist_categories WHERE name='Fasáda a zateplení' AND is_system=1)
UNION ALL SELECT * FROM (SELECT NULL, 'Betonáž', 1, 70) t
WHERE NOT EXISTS (SELECT 1 FROM remeslo_pricelist_categories WHERE name='Betonáž' AND is_system=1)
UNION ALL SELECT * FROM (SELECT NULL, 'Zemní práce', 1, 80) t
WHERE NOT EXISTS (SELECT 1 FROM remeslo_pricelist_categories WHERE name='Zemní práce' AND is_system=1)
UNION ALL SELECT * FROM (SELECT NULL, 'Elektroinstalace', 1, 90) t
WHERE NOT EXISTS (SELECT 1 FROM remeslo_pricelist_categories WHERE name='Elektroinstalace' AND is_system=1)
UNION ALL SELECT * FROM (SELECT NULL, 'Pergoly', 1, 100) t
WHERE NOT EXISTS (SELECT 1 FROM remeslo_pricelist_categories WHERE name='Pergoly' AND is_system=1)
UNION ALL SELECT * FROM (SELECT NULL, 'Střechy', 1, 110) t
WHERE NOT EXISTS (SELECT 1 FROM remeslo_pricelist_categories WHERE name='Střechy' AND is_system=1)
UNION ALL SELECT * FROM (SELECT NULL, 'Voda/topení', 1, 120) t
WHERE NOT EXISTS (SELECT 1 FROM remeslo_pricelist_categories WHERE name='Voda/topení' AND is_system=1)
UNION ALL SELECT * FROM (SELECT NULL, 'Zdění', 1, 130) t
WHERE NOT EXISTS (SELECT 1 FROM remeslo_pricelist_categories WHERE name='Zdění' AND is_system=1)
UNION ALL SELECT * FROM (SELECT NULL, 'Zateplení', 1, 140) t
WHERE NOT EXISTS (SELECT 1 FROM remeslo_pricelist_categories WHERE name='Zateplení' AND is_system=1);
