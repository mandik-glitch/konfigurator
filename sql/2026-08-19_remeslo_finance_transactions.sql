-- Řemeslo - Modul 10b (Finance) - bot14, 2026-08-19.
-- Viz REMESLO_KONCEPT.md "Modul 10" pro plné zdůvodnění (schváleno
-- bot3/Robertem před implementací).
--
-- 3. vrstva NAD Fakturami (10a) a Evidencí zakázek (modul 2) - vlastní
-- ÚČETNÍ DENÍK potvrzených peněžních událostí, ne duplicitní úložiště.
-- remeslo_job_materials eviduje ODHADOVANÉ/PLÁNOVANÉ náklady zakázky -
-- tahle tabulka eviduje SKUTEČNĚ potvrzené pohyby (přijatá platba
-- faktury, potvrzený zaplacený náklad).
--
-- "Bez dvojího započtení": UNIQUE KEY na job_material_id hlídá, že
-- jedna plánovaná položka remeslo_job_materials může být "Potvrdit
-- jako náklad" nanejvýš 1x (NULL hodnoty - běžné ruční transakce bez
-- vazby - MySQL unikátnost nekontroluje). invoice_id NENÍ unikátní -
-- částečné platby faktury jsou legitimně víc řádků; paid_czk faktury
-- se počítá za běhu (SUM), neukládá se jako druhý zdroj pravdy.
--
-- Foto dokladu -> náklad: znovupoužívá api/gallery_items.py
-- (owner_type='remeslo_finance_transaction'), žádná nová upload logika.
--
-- GATING: stejný app_settings flag jako Faktury (10a) -
-- 'remeslo_faktury_finance_enabled'.
--
-- Použití: python api/db_migrate.py sql/2026-08-19_remeslo_finance_transactions.sql

CREATE TABLE IF NOT EXISTS remeslo_finance_transactions (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id      INT NOT NULL,
    type              ENUM('prijem','naklad') NOT NULL,
    category          VARCHAR(50) NOT NULL,
    amount_czk        DECIMAL(10,2) NOT NULL,
    transaction_date  DATE NOT NULL,
    note              TEXT NULL,
    invoice_id        INT NULL,
    job_id            INT NULL,
    job_material_id   INT NULL,
    author_user_id    INT NOT NULL,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_fin_craftsman
        FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id),
    CONSTRAINT fk_remeslo_fin_invoice
        FOREIGN KEY (invoice_id) REFERENCES remeslo_invoices(id) ON DELETE SET NULL,
    CONSTRAINT fk_remeslo_fin_job
        FOREIGN KEY (job_id) REFERENCES remeslo_jobs(id) ON DELETE SET NULL,
    CONSTRAINT fk_remeslo_fin_job_material
        FOREIGN KEY (job_material_id) REFERENCES remeslo_job_materials(id) ON DELETE SET NULL,
    UNIQUE KEY uq_job_material (job_material_id),
    KEY idx_craftsman (craftsman_id),
    KEY idx_type_date (type, transaction_date),
    KEY idx_invoice (invoice_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
