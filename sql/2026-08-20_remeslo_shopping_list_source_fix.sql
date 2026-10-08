-- Řemeslo - Nákupní seznam: oprava po adversariální revizi (bot9, 2026-08-20).
--
-- NALEZ 1 (vazny): davkove scrapery (scripts/*_scrape_*.py) pri kazdem
-- prescrapovani kategorie DELETE+INSERT radek v remeslo_material_prices
-- (novy id), misto UPDATE na miste. price_id FK s ON DELETE CASCADE
-- proto TICHE MAZAL polozky nakupniho seznamu pri kazde rutinni obnove
-- katalogu - presny opak "seznamu, ktery si remeslnik odnese".
--
-- NALEZ 2 (vazny): uspora (MAX(price_czk) v kategorii) nefiltrovala
-- s.active=1 jako /compare - deaktivovany dodavatel (jehoz cenove
-- radky zustavaji v DB, jen active=0) mohl tise zkreslit vypocet.
--
-- Oprava: misto price_id (nestabilni, meni se pri kazdem prescrapu) se
-- uklada source_id (stabilni - "tenhle dodavatel pro tuhle kategorii"),
-- aktualni cena se dohledava az za behu (stejny vzor jako uz pouziva
-- scripts/2026-08-20_remeslo_material_request_batch.py pro upsert -
-- (category_id, source_id) je uz jinde v projektu spolehany jako
-- stabilni par).
--
-- Tabulka je z DNESNIHO DNE, zadna produkcni data - bezpecne ALTER.

ALTER TABLE remeslo_shopping_list_items
    DROP FOREIGN KEY fk_remeslo_shoplist_price,
    DROP COLUMN price_id,
    ADD COLUMN source_id INT NOT NULL AFTER category_id,
    ADD CONSTRAINT fk_remeslo_shoplist_source
        FOREIGN KEY (source_id) REFERENCES remeslo_price_sources(id) ON DELETE CASCADE;
