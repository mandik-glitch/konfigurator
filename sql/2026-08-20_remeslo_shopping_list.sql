-- Řemeslo - Nákupní seznam napříč dodavateli (Modul 1, bot9, 2026-08-20).
-- Robert: "srovnávač musí dávat řemeslníkovi něco, co si odnese - dnes
-- si porovná ceny, ale pak si stejně ručně píše, co koupí kde."
--
-- Jeden radek = jedna KATEGORIE materialu + AKTUALNE ZVOLENY dodavatel
-- pro ni (price_id). Vyber jineho dodavatele pro STEJNOU kategorii
-- NEVYTVARI duplicitni radek - UNIQUE (craftsman_id, category_id)
-- vynucuje "jeden zvoleny dodavatel na kategorii", prepsani je UPSERT
-- (viz POST /api/remeslo/shopping-list).
--
-- Pouziti: python api/db_migrate_remeslo.py sql/2026-08-20_remeslo_shopping_list.sql

CREATE TABLE IF NOT EXISTS remeslo_shopping_list_items (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id   INT NOT NULL,
    category_id    INT NOT NULL,
    price_id       INT NOT NULL,   -- FK remeslo_material_prices - AKTUALNE zvoleny dodavatel+cena pro tuhle kategorii
    quantity       DECIMAL(10,3) NOT NULL DEFAULT 1,
    purchased      TINYINT NOT NULL DEFAULT 0,
    added_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_shoplist_craftsman
        FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_shoplist_category
        FOREIGN KEY (category_id) REFERENCES remeslo_material_categories(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_shoplist_price
        FOREIGN KEY (price_id) REFERENCES remeslo_material_prices(id) ON DELETE CASCADE,
    UNIQUE KEY uq_craftsman_category (craftsman_id, category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
