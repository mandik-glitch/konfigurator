-- Řemeslo - most Nabídka -> Faktura (bot14, 2026-08-20, Robertův pokyn
-- "testy průchodnosti všemi moduly"). Zjištěno živě: z přijaté nabídky
-- nešlo jedním klikem (ani žádnou cestou) založit fakturu - žádný
-- backend most mezi remeslo_offers a remeslo_invoices neexistoval,
-- Faktury podporovaly jen "vytvořit z kalkulace". source_offer_id je
-- jen INFORMATIVNÍ odkaz (traceability "vytvořeno z"), stejný princip
-- jako source_calculation_id - položky se PŘEBÍRAJÍ jako snapshot
-- (viz _import_offer_items v api/remeslo.py), žádný živý přepočet při
-- pozdější změně nabídky.
--
-- Použití: python api/db_migrate_remeslo.py sql/2026-08-20_remeslo_invoices_source_offer.sql

ALTER TABLE remeslo_invoices
    ADD COLUMN source_offer_id INT NULL AFTER source_calculation_id,
    ADD CONSTRAINT fk_remeslo_inv_source_offer
        FOREIGN KEY (source_offer_id) REFERENCES remeslo_offers(id) ON DELETE SET NULL;
