-- Cislelne rady dokladu - vlastni prefix per typ (bot10, 2026-08-22).
--
-- Robert: "obj mají svoji řadu i prefix, zálohovky mají také svoji řadu
-- číselnou i prefix" - kazdy typ dokladu ma mit ODLISITELNY prefix
-- (dnes VDD ma vlastni prefix "VDD" hardcoded primo v Pythonu
-- (documents.py::create_payment_tax_document), zalohova faktura/
-- faktura/dodaci list ZADNY prefix nemaji - cislo vypada identicky
-- jako cislo objednavky, zamena). Nove admin editovatelne (viz
-- "Nastaveni ciselne rady dokladu" v adminu), ne natvrdo v kodu.
--
-- Prefix je konceptualne VLASTNOST TYPU dokladu (ne konkretniho roku) -
-- ulozeno denormalizovane na kazdem (document_type, seq_year) radku,
-- admin editace (PUT /api/admin/document-sequences/<document_type>)
-- prepise prefix na VSECH existujicich radcich stejneho typu najednou
-- (viz api/documents.py). Nove roky pri lazy-insertu (_next_document_
-- number) zdedi prefix z nejnovejsiho existujiciho radku stejneho typu.
--
-- Seed hodnoty: VDD zachovava presne stavajici konvenci (uz vydane
-- doklady maji "VDD..." v document_number - zmena by je nesladila s
-- pripadnymi novymi). Ostatni typy dostavaji rozumny vychozi prefix,
-- Robert si je muze kdykoli prejmenovat pres novou admin obrazovku.

ALTER TABLE shop_document_sequences
  ADD COLUMN prefix VARCHAR(10) NOT NULL DEFAULT '' AFTER document_type;

UPDATE shop_document_sequences SET prefix = 'VDD' WHERE document_type = 'payment_tax_document';
UPDATE shop_document_sequences SET prefix = 'ZF'  WHERE document_type = 'proforma_invoice';
UPDATE shop_document_sequences SET prefix = 'F'   WHERE document_type = 'invoice';
UPDATE shop_document_sequences SET prefix = 'DL'  WHERE document_type = 'delivery_note';
