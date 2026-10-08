-- Modul 1 (bot10, 2026-08-20) - REMESLO_KONCEPT.md "Sledovani vyvoje
-- ceny" (Robert, TRVALE - "srovnavac je hlavni produkt"). Append-only
-- log zapisovany PRED kazdou SKUTECNOU zmenou ceny (log-on-change,
-- presny vzor remeslo_pricelist_item_price_history u Ceniku, viz
-- sql/2026-08-19_remeslo_pricelist.sql + api/remeslo.py Modul 9).
--
-- KLICOVY ROZDIL OD CENIKU: Cenik ma stabilni item_id (polozky se
-- edituji na miste). remeslo_material_prices.id NENI stabilni - vsech
-- 8 davkovych scraperu dela `DELETE ... WHERE category_id=X AND
-- source_id=Y` + fresh INSERT VSECH polozek na KAZDEM behu, takze id
-- kazde polozky se pri kazdem prescrapovani zmeni. Historie je proto
-- klicovana na (source_id, product_url) - stabilni identita produktu
-- napric behy, stejny anchor jako uz existujici TRVALE PRAVIDLO
-- "Cena na vyzadani" (product_url = "umisteni polozky", meni se jen
-- pri chybe, ne pri kazde obnove/prescrapovani).
--
-- url_hash (generated STORED sloupec, MD5 z product_url) obchazi
-- jakekoli prefix-index limity na VARCHAR(500) - index primo na
-- CHAR(32) je levny a presny bez ohledu na delku skutecne URL.
--
-- RUST TABULKY POD KONTROLOU: zapisuje se JEN kdyz se cena SKUTECNE
-- zmenila oproti posledni zname hodnote (vetsina prescrapovani/obnov
-- najde stejnou cenu = 0 zapisu). Zadne proaktivni prorezavani zatim
-- (Robert, 2026-08-20: "dokud tabulka realne nenaroste, je to reseni
-- problemu, ktery nemame") - revidovat az bude realny duvod.
--
-- Pouziti: python api/db_migrate_remeslo.py sql/2026-08-20_remeslo_material_price_history.sql

SET SESSION lock_wait_timeout = 10;

CREATE TABLE IF NOT EXISTS remeslo_material_price_history (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    source_id       INT NOT NULL,
    product_url     VARCHAR(500) NOT NULL,
    url_hash        CHAR(32) GENERATED ALWAYS AS (MD5(product_url)) STORED,
    price_czk       DECIMAL(10,2) NOT NULL,
    changed_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_mph_source
        FOREIGN KEY (source_id) REFERENCES remeslo_price_sources(id) ON DELETE CASCADE,
    KEY idx_lookup (source_id, url_hash, changed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
