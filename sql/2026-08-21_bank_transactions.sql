-- Bankovní výpisy FIO (bot10, 2026-08-21, Robert přes bot3): "potřebujeme
-- bankovní výpisy do levého panelu administrace... zobrazovat POUZE
-- příjaté platby (kredit, ne debetní/odchozí), možnost hledat podle
-- částky, navážeme na FIO banku". Vzor append/cache lokálně (jako
-- remeslo_material_price_history/incoming_documents) - NEsahat pro data
-- při každém loadu přímo na FIO (rate limit FIO API je jen 1 dotaz/30s
-- na token, viz FIO_API_Bankovnictvi.pdf v14 kap. 5.2), místo toho
-- periodicky synchronizovat sem a admin panel čte odsud.
--
-- Ukládají se JEN příchozí platby (amount_czk > 0) - Robertovo zadání
-- "pouze přijaté platby" aplikováno už na úrovni synchronizace/importu
-- (api/bank_statements.py), ne až filtrem v UI - odchozí platby se do
-- téhle tabulky vůbec nezapisují.
--
-- fio_transaction_id (FIO "ID pohybu", sloupec column22 v JSON odpovědi)
-- je jednoznačný a NIKDY se neopakuje (FIO dokumentace, kap. 5.3.1) -
-- UNIQUE klíč umožňuje bezpečné INSERT IGNORE při opakované synchronizaci
-- překrývajících se období, bez rizika duplicit.
--
-- raw_json (celý řádek transakce z FIO odpovědi) uložen pro budoucí
-- potřebu (např. párování s objednávkou podle VS, které zatím není
-- předmětem tohoto zadání) - žádné pole se tím neztrácí, i kdyby se
-- později ukázalo, že sloupcový výběr níže nestačí.
--
-- Pouziti: python api/db_migrate.py sql/2026-08-21_bank_transactions.sql

SET SESSION lock_wait_timeout = 10;

CREATE TABLE IF NOT EXISTS bank_transactions (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    fio_transaction_id     BIGINT NOT NULL,
    transaction_date        DATE NOT NULL,
    amount_czk               DECIMAL(14,2) NOT NULL,
    currency                 CHAR(3) NOT NULL DEFAULT 'CZK',
    counter_account          VARCHAR(255) NULL,
    counter_account_name    VARCHAR(255) NULL,
    counter_bank_code       VARCHAR(10) NULL,
    counter_bank_name       VARCHAR(255) NULL,
    variable_symbol          VARCHAR(20) NULL,
    constant_symbol           VARCHAR(20) NULL,
    specific_symbol           VARCHAR(20) NULL,
    user_identification      VARCHAR(255) NULL,
    message_for_recipient    VARCHAR(255) NULL,
    transaction_type          VARCHAR(255) NULL,
    performed_by              VARCHAR(255) NULL,
    comment                    VARCHAR(255) NULL,
    instruction_id             VARCHAR(20) NULL,
    raw_json                    JSON NULL,
    is_test_data               TINYINT(1) NOT NULL DEFAULT 0,
    synced_at                   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_bank_tx_fio_id (fio_transaction_id),
    KEY idx_bank_tx_date (transaction_date),
    KEY idx_bank_tx_amount (amount_czk),
    KEY idx_bank_tx_vs (variable_symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Stav synchronizace (kdy naposledy proběhla, odkud pokračovat příště) -
-- prostý key-value pattern jako app_settings, ale samostatná tabulka
-- (ne přes app_settings), protože jde o 1 řádek se strukturovanými
-- sloupci, ne o volný JSON blob - čitelnější pro přímý SELECT při ladění.
CREATE TABLE IF NOT EXISTS bank_sync_state (
    id                   TINYINT NOT NULL PRIMARY KEY DEFAULT 1,
    last_synced_date     DATE NULL,
    last_sync_at         DATETIME NULL,
    last_sync_status     VARCHAR(20) NULL,
    last_sync_error      VARCHAR(500) NULL,
    last_sync_count      INT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO bank_sync_state (id) VALUES (1);
