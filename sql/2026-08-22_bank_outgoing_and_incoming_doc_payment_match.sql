-- Bankovni vypisy: zaznamenat i odchozi platby + parovani s Prijatymi
-- doklady (proti duplicitni uhrade) - bot10, 2026-08-22.
-- (Robert pres bot3: "z bankovnich vypisu je videt i odchozi platby,
-- sparujme je s evidovanymi prijatymi doklady, at admin vidi uhradu
-- a nezaplati omylem duplicitne")
--
-- bank_transactions.direction: 'prijem' (Objem > 0, puvodni chovani,
-- DEFAULT - existujici radky zustavaji beze zmeny) / 'vydaj' (Objem < 0,
-- nove ukladane). amount_czk zustava VZDY kladne cislo (absolutni
-- hodnota) bez ohledu na smer - direction rika, kterym smerem to slo,
-- ne znamenko - jednodussi porovnani s incoming_documents.amount_czk
-- (taky vzdy kladne), viz api/bank_statements.py.
ALTER TABLE bank_transactions
  ADD COLUMN direction VARCHAR(10) NOT NULL DEFAULT 'prijem',
  ADD KEY idx_bank_tx_direction (direction);

-- incoming_documents: potvrzena shoda s odchozi bankovni platbou -
-- VZDY jen po rucnim potvrzeni adminem (nikdy automaticky, castka +
-- casove okno je jen navrh/tip, ne spolehlivy klic jako VS u objednavek).
ALTER TABLE incoming_documents
  ADD COLUMN paid_bank_transaction_id INT NULL,
  ADD COLUMN paid_at DATETIME NULL,
  ADD CONSTRAINT fk_incdoc_paid_bank_transaction
    FOREIGN KEY (paid_bank_transaction_id) REFERENCES bank_transactions(id) ON DELETE SET NULL;
