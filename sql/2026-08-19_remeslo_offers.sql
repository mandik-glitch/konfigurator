-- Řemeslo - modul 8c (bot13, 2026-08-19, na zadání Roberta přes bot3):
-- Nabídky (/nabidky). Viz REMESLO_KONCEPT.md "Modul 8c" pro plný
-- kontext.
--
-- number je vygenerované při založení přes remeslo_numbering_sequences
-- (doc_type='nabidka') - unikátní, string ne int (obsahuje prefix/rok).
--
-- Revize = NOVÝ ŘÁDEK s revision_of_id ukazujícím na PŘEDCHOZÍ verzi
-- (ne přepis původní) - historie zůstává dohledatelná, revision_number
-- se pro zobrazení "verze N" inkrementuje o 1 oproti revidované nabídce.
-- ON DELETE SET NULL - smazání starší verze nemá strhnout novější.
--
-- Šablona (is_template=1): customer_name/customer_ico/... zůstávají
-- volitelné (NOT NULL customer_name platí jen logicky na frontendu
-- pro NEšablony, DB sloupec je proto NULL-friendly by default kdyby
-- šablona zatím zákazníka nemá - viz API validace).
--
-- Použití: python api/db_migrate.py sql/2026-08-19_remeslo_offers.sql

CREATE TABLE IF NOT EXISTS remeslo_offers (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id      INT NOT NULL,
    job_id            INT NULL,
    number            VARCHAR(40) NOT NULL,
    title             VARCHAR(255) NOT NULL,
    customer_name     VARCHAR(255) NULL,
    customer_ico      VARCHAR(20) NULL,
    customer_dic      VARCHAR(20) NULL,
    customer_address  VARCHAR(500) NULL,
    status            ENUM('koncept','vystaveno','reakce_zakaznika','revize') NOT NULL DEFAULT 'koncept',
    valid_until       DATE NULL,
    is_template       TINYINT(1) NOT NULL DEFAULT 0,
    active            TINYINT(1) NOT NULL DEFAULT 1,
    total_czk         DECIMAL(10,2) NOT NULL DEFAULT 0,
    note              TEXT NULL,
    revision_of_id    INT NULL,
    revision_number   INT NOT NULL DEFAULT 1,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_offers_craftsman
        FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id),
    CONSTRAINT fk_remeslo_offers_job
        FOREIGN KEY (job_id) REFERENCES remeslo_jobs(id) ON DELETE SET NULL,
    CONSTRAINT fk_remeslo_offers_revision_of
        FOREIGN KEY (revision_of_id) REFERENCES remeslo_offers(id) ON DELETE SET NULL,
    UNIQUE KEY uq_number (number),
    KEY idx_craftsman (craftsman_id),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_offer_items (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    offer_id          INT NOT NULL,
    popis             VARCHAR(500) NOT NULL,
    mnozstvi          DECIMAL(10,2) NOT NULL DEFAULT 1,
    jednotka          VARCHAR(20) NOT NULL DEFAULT 'ks',
    cena_za_jednotku  DECIMAL(10,2) NOT NULL DEFAULT 0,
    sort_order        INT NOT NULL DEFAULT 0,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_offer_items_offer
        FOREIGN KEY (offer_id) REFERENCES remeslo_offers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
