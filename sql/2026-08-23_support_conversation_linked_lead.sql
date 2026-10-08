-- "Poptavka jako stitek v E-mailech prichozich" (bot10, 2026-08-23,
-- Robert: "jako stitek opticky uz v emailech"). Dnes klasifikace
-- "poptavka" (api/support_email_sync.py) zapise e-mail VYHRADNE do
-- crm_leads/crm_lead_messages - do shop_support_conversations
-- (E-maily prichozi) se vubec nedostane, takze Robert je v hlavni
-- schrance nikdy nevidi.
--
-- Rozhodnuti (Robert/bot3, 2026-08-23, mezi dvema navrzenymi
-- pristupy): DUAL-WRITE + stitek, NE sjednoceni obou front do jedne
-- UNION query. Poptavky zustavaji vlastni zalozka/uloziste (hodnota
-- obchodu/ukoly/poznamky beze zmeny) - navic se ale PRI KLASIFIKACI
-- "poptavka" zalozi/aktualizuje i odpovidajici radek v shop_support_
-- conversations, s temhle sloupcem odkazujicim na puvodni lead. Zadny
-- zasah do stavajici query/paginace/filtru E-mailu prichozich - jen
-- dalsi radek jako kterykoli jiny, s viditelnym stitkem "Poptavka".
--
-- Stejny vzor jako linked_order_id (sql/2026-08-22_support_
-- conversation_linked_order.sql) - ON DELETE SET NULL (mekka
-- reference pro zobrazeni, ne auditni zaznam - smazani leadu nema
-- smysl blokovat kvuli stare Podpora konverzaci).
ALTER TABLE shop_support_conversations
  ADD COLUMN linked_lead_id INT NULL AFTER linked_order_id,
  ADD KEY idx_shop_support_conversations_linked_lead (linked_lead_id),
  ADD CONSTRAINT fk_shop_support_conversations_linked_lead
    FOREIGN KEY (linked_lead_id) REFERENCES crm_leads(id) ON DELETE SET NULL;
