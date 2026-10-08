-- CRM/Podpora - "objednávka" trideni kategorie: propojeni misto pouhe
-- archivace (Robert, 2026-08-22, u diagramu pipeline, potvrzeno durazne:
-- "objednavka se nearchivuje !!! jde do objednavek"). Puvodni chovani
-- (archivace, bot11 2026-08-19) predpokladalo, ze objednavka existuje
-- viditelne jinde (Logy.cz kopie) - predpoklad byl spatny.
--
-- ON DELETE SET NULL (ne RESTRICT jako shop_emails.order_id) - vazba je
-- "mekka" reference pro zobrazeni v detailu objednavky, ne auditni
-- zaznam o skutecne provedene akci; smazani objednavky nema smysl
-- blokovat kvuli stare Podpora konverzaci, jen se odpoji.
ALTER TABLE shop_support_conversations
  ADD COLUMN linked_order_id INT NULL AFTER archived,
  ADD KEY idx_shop_support_conversations_linked_order (linked_order_id),
  ADD CONSTRAINT fk_shop_support_conversations_linked_order
    FOREIGN KEY (linked_order_id) REFERENCES shop_orders(id) ON DELETE SET NULL;
