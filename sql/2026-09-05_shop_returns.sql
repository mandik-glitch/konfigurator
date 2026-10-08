-- Reklamace a vratky (bot18, 2026-09-05, Robert pres bot3, navazuje na
-- OFBiz srovnani "Za hranice objednavky" + navrh "Reklamace a vratky").
-- Samostatna entita navazana na shop_orders pres order_id - shop_orders
-- (status/delivery_state/billing_state) se timhle NEMENI, stejny princip
-- jako u Party modelu a delivery_state/billing_state.
--
-- Rozliseni return_type (reklamace vs. odstoupeni) - ceske pravo je resi
-- jinak (reklamace = posuzovani opravnenosti + 30denni lhuta, odstoupeni
-- = automaticky narok do 14 dni, zadne posuzovani).
--
-- Robertova rozhodnuti (2026-09-05, pres bot3):
-- 1. Dobropis - zaporna hodnota (standardni ucetni vzor).
-- 2. Poskozene/vadne zbozi se NEVRACI do prodejniho skladu.
-- 3. Self-service - zakaznik muze zalozit sam (created_by_user_id misto
--    "jen admin", muze byt i zakaznikuv vlastni ucet).
-- 4. Vymena - ZADNY automaticky flow, jen volitelny odkaz na jakoukoli
--    novou objednavku (replacement_order_id), admin ho pripoji rucne az
--    tu novou objednavku sam zalozi (stejnym zpusobem, jakym uz dnes
--    vznika kterakoli rucni objednavka) - zadny novy samostatny typ.

SET SESSION lock_wait_timeout = 10;

CREATE TABLE shop_returns (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  return_number VARCHAR(30) NOT NULL,
  return_type ENUM('reklamace','odstoupeni') NOT NULL,
  status ENUM('pozadovano','posuzovano','schvaleno','prijato','vyrizeno','zamitnuto','zruseno')
    NOT NULL DEFAULT 'pozadovano',
  reason TEXT NULL,
  resolution ENUM('refund','repair','rejected') NULL,
  admin_note TEXT NULL,
  credit_note_document_id INT NULL,
  replacement_order_id INT NULL,
  created_by_user_id INT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY idx_return_number (return_number),
  KEY idx_shop_returns_order (order_id),
  CONSTRAINT fk_shop_returns_order FOREIGN KEY (order_id) REFERENCES shop_orders(id),
  CONSTRAINT fk_shop_returns_credit_note FOREIGN KEY (credit_note_document_id)
    REFERENCES shop_documents(id) ON DELETE SET NULL,
  CONSTRAINT fk_shop_returns_replacement_order FOREIGN KEY (replacement_order_id)
    REFERENCES shop_orders(id) ON DELETE SET NULL,
  CONSTRAINT fk_shop_returns_created_by FOREIGN KEY (created_by_user_id)
    REFERENCES app_users(id) ON DELETE SET NULL
);

CREATE TABLE shop_return_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  return_id INT NOT NULL,
  order_item_id INT NOT NULL,
  qty INT NOT NULL,
  unit_price_czk DECIMAL(12,2) NOT NULL,
  item_condition ENUM('nepouzite','poskozene','vadne') NOT NULL DEFAULT 'nepouzite',
  KEY idx_shop_return_items_return (return_id),
  KEY idx_shop_return_items_order_item (order_item_id),
  CONSTRAINT fk_shop_return_items_return FOREIGN KEY (return_id)
    REFERENCES shop_returns(id) ON DELETE CASCADE,
  CONSTRAINT fk_shop_return_items_order_item FOREIGN KEY (order_item_id)
    REFERENCES shop_order_items(id)
);

CREATE TABLE shop_return_status_history (
  id INT AUTO_INCREMENT PRIMARY KEY,
  return_id INT NOT NULL,
  status VARCHAR(20) NOT NULL,
  changed_by INT NULL,
  changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  note TEXT NULL,
  KEY idx_shop_return_status_history_return (return_id),
  CONSTRAINT fk_shop_return_status_history_return FOREIGN KEY (return_id)
    REFERENCES shop_returns(id) ON DELETE CASCADE
);
