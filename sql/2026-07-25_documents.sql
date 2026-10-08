-- Doklady (zalohova faktura, danovy doklad k prijate platbe, faktura) -
-- bot3, 2026-07-25, v6.
--
-- Kontext: Robert dodal vzorove doklady (vzorova objednavka.pdf,
-- proformaInvoice_26080012.pdf, invoice_26010042.pdf,
-- proofPayment_vdd26080018-01.pdf - vsechny puvodne ze Shoptet.cz) a chce
-- v systemu zavedeny vsechny jejich pole/promenne ve dvou workflow:
--   WORKFLOW1 (platba predem prevodem): objednavka -> zalohova faktura ->
--     danovy doklad k prijate platbe (VDD) -> konecna faktura (odecte VDD)
--   WORKFLOW2 (dobirka/karta): objednavka -> rovnou faktura
-- Rozhodnuti Roberta (AskUserQuestion, 2026-07-25):
--   - rozsah: datovy model + PDF generovani (moje volba, "bez preference")
--   - workflow se urcuje AUTOMATICKY podle platebni metody
--     (shop_payment_methods.requires_advance_invoice)
--   - cislovani novych dokladu stylem Shoptet RRMMxxxx (samostatna rada
--     na kazdy typ dokladu, per-rok pocitadlo, MM = mesic vystaveni)
--   - ceny v e-shopu jsou BEZ DPH -> na dokladech se pripocitava 21 % DPH
--     navic (VAT_RATE = 21, hardcoded v api/documents.py - zadna jina
--     sazba se v datech nevyskytovala)
--
-- Cislo objednavky (order_number, format "OBJ-YYYY-NNNNN") NENI cislo
-- dokladu ve stylu Shoptet - zustava beze zmeny. Jako variabilni symbol
-- (numericky, bez pismen) pouzivame primo shop_orders.id.
--
-- Firemni udaje dodavatele (LOGIMAN s.r.o.) jsou zatim HARDCODED v
-- api/documents.py (jednoduchy staticky config, ne DB tabulka) - pokud by
-- se nekdy zmenily (napr. cislo uctu), je potreba upravit kod a nasadit.
--
-- Pouziti: mysql -h 80.211.73.226 -u <db_user> -p xebyhtfeaj < 2026-07-25_documents.sql

-- Priznak na platebni metode - urcuje, ktere workflow se pro objednavku
-- s touto platbou pouzije.
ALTER TABLE shop_payment_methods
    ADD COLUMN requires_advance_invoice TINYINT(1) NOT NULL DEFAULT 0;

-- "Bankovni prevod predem" odpovida konceptu zalohove faktury (WORKFLOW1).
-- Ostatni (Dobirka, Platba kartou) zustavaji na WORKFLOW2 (rovnou faktura).
UPDATE shop_payment_methods SET requires_advance_invoice = 1
    WHERE name = 'Bankovní převod předem';

-- Evidence prijeti platby na objednavce (nezavisle na produkcnim statusu
-- ve shop_orders.status - platba muze prijit driv i pozdeji nez zmena
-- stavu vyroby). Kazde zavolani "oznacit platbu jako prijatou" vygeneruje
-- 1 VDD doklad (podporuje i vicero castecnych plateb - viz part_number
-- ve shop_documents).
ALTER TABLE shop_orders
    ADD COLUMN payment_received_at DATETIME NULL,
    ADD COLUMN payment_received_total_czk DECIMAL(12,2) NOT NULL DEFAULT 0;

-- Pocitadlo cisel dokladu - samostatna rada pro kazdy typ a rok (RRMMxxxx,
-- kde xxxx je poradove cislo NARUSTAJICI CELY ROK, MM je jen mesic
-- aktualniho vystaveni - presne podle vzorku: invoice_26010042 (leden,
-- por. 42) a proformaInvoice_26080012 (srpen, por. 12) jsou ruzne typy,
-- tedy ruzne rady).
CREATE TABLE IF NOT EXISTS shop_document_sequences (
    document_type   VARCHAR(30) NOT NULL,
    seq_year        INT NOT NULL,
    next_number     INT NOT NULL DEFAULT 1,
    PRIMARY KEY (document_type, seq_year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Hlavni tabulka dokladu. Kazdy doklad je NEMENNY snapshot (stejny princip
-- jako billing_*/shipping_*/customer_group_* na shop_orders) - pozdejsi
-- zmena objednavky/profilu/cen uz vystaveny doklad zpetne nezmeni.
CREATE TABLE IF NOT EXISTS shop_documents (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    order_id                INT NOT NULL,
    document_type           VARCHAR(30) NOT NULL,  -- 'proforma_invoice' | 'payment_tax_document' | 'invoice'
    document_number         VARCHAR(30) NOT NULL,  -- zobrazovane cislo (napr. "26080012" nebo "VDD26080018-01")
    seq_year                INT NOT NULL,
    seq_number              INT NOT NULL,
    part_number             INT NULL,              -- poradi v ramci objednavky pro VDD (1,2,... u castecnych plateb)
    related_document_id     INT NULL,               -- faktura/VDD -> odkaz na zalohovou fakturu, kterou odecita/dokladuje
    variable_symbol         VARCHAR(20) NOT NULL,
    constant_symbol         VARCHAR(20) NULL,
    specific_symbol         VARCHAR(20) NULL,
    payment_method_label    VARCHAR(100) NULL,
    issue_date              DATETIME NOT NULL,
    due_date                DATE NULL,
    taxable_supply_date     DATE NULL,
    recipient_snapshot      JSON NOT NULL,          -- prijemce (jmeno/firma/adresa/ICO/DIC/tel/e-mail)
    delivery_snapshot       JSON NULL,               -- dorucovaci adresa (chybi u VDD)
    items_snapshot          JSON NOT NULL,           -- polozky dokladu (viz api/documents.py pro presny tvar)
    vat_breakdown           JSON NOT NULL,           -- soucet DPH po sazbach [{rate, base_czk, vat_czk, total_czk}]
    note                    TEXT NULL,
    total_without_vat_czk   DECIMAL(12,2) NOT NULL DEFAULT 0,
    total_vat_czk           DECIMAL(12,2) NOT NULL DEFAULT 0,
    total_with_vat_czk      DECIMAL(12,2) NOT NULL DEFAULT 0,
    rounding_czk            DECIMAL(6,2) NOT NULL DEFAULT 0,
    advance_deduction_czk   DECIMAL(12,2) NOT NULL DEFAULT 0,   -- odecet jiz uhrazene zalohy (jen u 'invoice', kdyz existuje predchozi zalohova faktura)
    advance_document_number VARCHAR(30) NULL,        -- cislo zalohove faktury, ktera byla odectena (jen k zobrazeni na PDF)
    amount_due_czk          DECIMAL(12,2) NOT NULL DEFAULT 0,  -- "K ZAPLACENI" (0 u VDD a u faktury plne kryte zalohou)
    issued_by               VARCHAR(150) NULL,       -- jmeno admina, nebo "Systém" pro automaticky vystavenou zalohovou fakturu
    created_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_shop_documents_type_number (document_type, document_number),
    KEY idx_shop_documents_order (order_id),
    CONSTRAINT fk_shop_documents_order FOREIGN KEY (order_id) REFERENCES shop_orders(id),
    CONSTRAINT fk_shop_documents_related FOREIGN KEY (related_document_id) REFERENCES shop_documents(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
