-- Řemeslo - modul 8b (bot13, 2026-08-19, na zadání Roberta přes bot3):
-- Nastavení -> Fakturace. Viz REMESLO_KONCEPT.md "Modul 8b" pro plný
-- kontext.
--
-- remeslo_invoicing_settings je 1:1 k remeslo_craftsmen (craftsman_id
-- je zároveň PK) - řádek vzniká LAZILY až při prvním uložení formuláře
-- (ne automaticky s craftsmanem), stejně jako u jiných volitelných
-- rozšíření v projektu.
--
-- remeslo_numbering_sequences je SAMOSTATNÁ tabulka (ne sloupce na
-- invoicing_settings), protože nabídky a (budoucí) faktury mají
-- NEZÁVISLE konfigurovatelnou číselnou řadu - viz doc_type. Řada pro
-- 'faktura' se tímhle modulem jen PŘIPRAVUJE (konfigurace), žádný
-- endpoint ji reálně nespotřebovává - fakturace samotná zůstává
-- gated (ověření identity), viz REMESLO_KONCEPT.md "Mimo současný
-- scope" / AGENTS_LOG.md 2026-08-19 (BitFaktura nález).
--
-- current_number/current_year: FOR UPDATE zamyka radek pri generovani
-- cisla (stejny vzor jako remeslo_professions.next_seq v modulu 1/4),
-- current_number se resetuje na start_number-1 pri prechodu na novy
-- rok, POKUD include_year=1.
--
-- Použití: python api/db_migrate.py sql/2026-08-19_remeslo_invoicing_settings.sql

CREATE TABLE IF NOT EXISTS remeslo_invoicing_settings (
    craftsman_id         INT PRIMARY KEY,
    vat_payer             TINYINT(1) NOT NULL DEFAULT 0,
    bank_account_number   VARCHAR(30) NULL,
    bank_code             VARCHAR(10) NULL,
    iban                  VARCHAR(34) NULL,
    swift                 VARCHAR(11) NULL,
    default_due_days      SMALLINT NOT NULL DEFAULT 14,
    default_vat_rate      DECIMAL(5,2) NOT NULL DEFAULT 21.00,
    currency              VARCHAR(3) NOT NULL DEFAULT 'CZK',
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_invoicing_craftsman
        FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_numbering_sequences (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id    INT NOT NULL,
    doc_type        ENUM('nabidka','faktura') NOT NULL,
    prefix          VARCHAR(20) NOT NULL DEFAULT '',
    `separator`     VARCHAR(5) NOT NULL DEFAULT '-',
    digit_count     TINYINT NOT NULL DEFAULT 4,
    start_number    INT NOT NULL DEFAULT 1,
    include_year    TINYINT(1) NOT NULL DEFAULT 1,
    current_number  INT NOT NULL DEFAULT 0,
    current_year    INT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_numbering_craftsman
        FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id),
    UNIQUE KEY uq_craftsman_doctype (craftsman_id, doc_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
