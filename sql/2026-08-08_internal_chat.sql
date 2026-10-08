-- Interni tymovy chat na Dashboardu (Robert 2026-08-08: "na dashboard
-- pridej chatovaci okno pro vsechny prihlasene v systemu") - JEDNA
-- sdilena mistnost pro cely tym, ne soukrome zpravy. Zamerne plocha
-- tabulka bez "conversation" obalu (na rozdil od shop_support_messages,
-- kde ma smysl vic vlaken zaraz) - stejny jednoduchy vzor jako
-- crm_lead_notes.
CREATE TABLE internal_chat_messages (
  id INT PRIMARY KEY AUTO_INCREMENT,
  sender_user_id INT NULL,
  sender_name VARCHAR(255) NOT NULL,
  body TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (sender_user_id) REFERENCES app_users(id) ON DELETE SET NULL,
  KEY idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
