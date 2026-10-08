-- Řemeslo - modul 8c rozšíření: veřejná ONLINE nabídka + import položek
-- z kalkulace - bot13, 2026-08-19, na přímý pokyn Roberta (přes bot3):
-- "chci i online verzi nabídky, stejný princip jako u konfigurátoru,
-- jen jiná data/vzhled podle profese řemeslníka" + "položky nabídky se
-- NEZADÁVAJÍ ručně od nuly, ale TAHAJÍ SE Z KALKULAČEK" (viz TASKS.md
-- "Faktury a Finance" 2026-08-19, stejné pravidlo platí i pro Nabídky).
--
-- Token/hash vzor 1:1 podle api/scene_offers.py (scene_offers.
-- view_token_hash) - syrový token se nikde neukládá, jen SHA-256 hash.
-- Generuje se VŽDY při vytvoření nabídky (ne až na vyžádání), jde
-- regenerovat (viz remeslo_collaborators.access_token_hash pro stejný
-- princip regenerace uvnitř tohoto projektu).
--
-- remeslo_offer_acceptances/remeslo_offer_declines jsou APPEND-ONLY
-- (stejný princip jako scene_offer_acceptances/scene_offer_declines) -
-- opakované potvrzení/odmítnutí není chyba, jen další řádek.
--
-- source_calculation_id je jen TRACEABILITY (odkud nabídka vznikla),
-- NE živý odkaz - položky se vždy kopírují se SNAPSHOTEM názvu/
-- množství/ceny v okamžiku převzetí (stejný princip jako revize
-- kalkulace/nabídky), pozdější změna kalkulace nabídku tiše nezmění.
--
-- Použití: python api/db_migrate.py sql/2026-08-19_remeslo_offers_online.sql

ALTER TABLE remeslo_offers
    ADD COLUMN source_calculation_id INT NULL AFTER job_id,
    ADD COLUMN view_token_hash CHAR(64) NULL AFTER note,
    ADD UNIQUE KEY uq_view_token_hash (view_token_hash),
    ADD CONSTRAINT fk_remeslo_offers_source_calculation
        FOREIGN KEY (source_calculation_id) REFERENCES remeslo_calculations(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS remeslo_offer_acceptances (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    offer_id       INT NOT NULL,
    name           VARCHAR(255) NOT NULL,
    contact_email  VARCHAR(255) NULL,
    contact_phone  VARCHAR(50) NULL,
    ip_address     VARCHAR(45) NULL,
    accepted_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_offer_acceptances_offer
        FOREIGN KEY (offer_id) REFERENCES remeslo_offers(id) ON DELETE CASCADE,
    KEY idx_offer (offer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_offer_declines (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    offer_id       INT NOT NULL,
    reason         TEXT NULL,
    ip_address     VARCHAR(45) NULL,
    declined_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_offer_declines_offer
        FOREIGN KEY (offer_id) REFERENCES remeslo_offers(id) ON DELETE CASCADE,
    KEY idx_offer (offer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
