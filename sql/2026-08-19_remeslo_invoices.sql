-- Řemeslo - Modul 10a (Faktury) - bot14, 2026-08-19.
-- Viz REMESLO_KONCEPT.md "Modul 10" pro plné zdůvodnění (schváleno
-- bot3/Robertem před implementací).
--
-- Odděleno od remeslo_offers (modul 8c) - vlastní tabulka, vlastní
-- číselná řada (remeslo_numbering_sequences doc_type='faktura', dosud
-- jen KONFIGUROVANÁ, žádný endpoint ji nespotřebovával - tenhle modul
-- je první, kdo ji reálně použije).
--
-- Položky se NEZADÁVAJÍ ručně od nuly - snapshot z uložené Kalkulace
-- (remeslo_calculations/remeslo_calculation_items, přes stejnou
-- _import_calculation_items() jako u Nabídek) nebo ruční založení bez
-- kalkulace. source_calculation_id/source_calculation_item_id jsou jen
-- INFORMATIVNÍ odkaz (traceability "vytvořeno z"), ŽÁDNÝ živý přepočet
-- při změně kalkulace/ceníku - stejný snapshot princip jako
-- remeslo_offers.source_calculation_id.
--
-- ŽÁDNÝ revizní řetěz (na rozdíl od Nabídky/Kalkulace) - vystavená
-- faktura (status='vystaveno') se na backendu WRITE-LOCKUJE (položky i
-- částky needitovatelné), jediný další povolený přechod je
-- '→stornovano'. Dobropis/opravný doklad je mimo v1 (není v zadání).
--
-- GATING: appka tenhle modul zatím NESPOUŠTÍ pro reálné řemeslníky -
-- viz app_settings klíč 'remeslo_faktury_finance_enabled' (seed na
-- konci, výchozí VYPNUTO) a guard v api/remeslo.py.
--
-- Použití: python api/db_migrate.py sql/2026-08-19_remeslo_invoices.sql

CREATE TABLE IF NOT EXISTS remeslo_invoices (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id          INT NOT NULL,
    job_id                INT NULL,
    source_calculation_id INT NULL,
    number                VARCHAR(40) NOT NULL,
    variable_symbol       VARCHAR(20) NULL,
    customer_name         VARCHAR(255) NOT NULL,
    customer_ico          VARCHAR(20) NULL,
    customer_dic          VARCHAR(20) NULL,
    customer_address      VARCHAR(500) NULL,
    status                ENUM('koncept','vystaveno','stornovano') NOT NULL DEFAULT 'koncept',
    issue_date            DATE NOT NULL,
    due_date              DATE NOT NULL,
    tax_point_date        DATE NULL,
    payment_method        ENUM('prevodem','hotove','kartou') NOT NULL DEFAULT 'prevodem',
    total_czk             DECIMAL(10,2) NOT NULL DEFAULT 0,
    note                  TEXT NULL,
    active                TINYINT(1) NOT NULL DEFAULT 1,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_inv_craftsman
        FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id),
    CONSTRAINT fk_remeslo_inv_job
        FOREIGN KEY (job_id) REFERENCES remeslo_jobs(id) ON DELETE SET NULL,
    CONSTRAINT fk_remeslo_inv_calc
        FOREIGN KEY (source_calculation_id) REFERENCES remeslo_calculations(id) ON DELETE SET NULL,
    -- UNIKATNOST JEN PER-REMESLNIK, ne globalne - cislo dokladu ma
    -- smysl jen v ramci jedne remeslnikovy vlastni rady (dva ruzni
    -- OSVC legitimne mohou mit oba "FAK-2026-0001" s vychozim
    -- prefixem). Globalni UNIQUE KEY (number) by pri druhem
    -- remeslnikovi s vychozim nastavenim cislovani spadl na
    -- IntegrityError misto hezke chybove hlasky - odhaleno vlastnim
    -- test_client testem (bot14, 2026-08-19). POZOR: remeslo_offers
    -- (modul 8c, bot13) ma STEJNY globalni UNIQUE KEY uq_number - stejna
    -- latentni chyba tam zatim NEOPRAVENA, viz AGENTS_LOG.md.
    UNIQUE KEY uq_craftsman_number (craftsman_id, number),
    KEY idx_craftsman (craftsman_id),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_invoice_items (
    id                          INT AUTO_INCREMENT PRIMARY KEY,
    invoice_id                  INT NOT NULL,
    source_calculation_item_id  INT NULL,
    popis                       VARCHAR(500) NOT NULL,
    mnozstvi                    DECIMAL(10,2) NOT NULL DEFAULT 1,
    jednotka                    VARCHAR(20) NOT NULL DEFAULT 'ks',
    cena_za_jednotku            DECIMAL(10,2) NOT NULL DEFAULT 0,
    vat_percent                 DECIMAL(5,2) NOT NULL DEFAULT 21.00,
    sort_order                  INT NOT NULL DEFAULT 0,
    created_at                  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_inv_items_invoice
        FOREIGN KEY (invoice_id) REFERENCES remeslo_invoices(id) ON DELETE CASCADE,
    CONSTRAINT fk_remeslo_inv_items_calc_item
        FOREIGN KEY (source_calculation_item_id) REFERENCES remeslo_calculation_items(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Gating flag - vychozi VYPNUTO, zamerne BEZ UI prepinace (viz
-- REMESLO_KONCEPT.md "Gating"). INSERT IGNORE, ať běh migrace zůstává
-- idempotentní a nepřepíše ruční UPDATE, kterým Robert modul časem
-- zapne.
INSERT IGNORE INTO app_settings (setting_key, setting_value) VALUES
    ('remeslo_faktury_finance_enabled', '0');
