-- Zivy chat / podpora - bot1, 2026-07-25 (Faze 1 z SUPPORT_SYSTEM_NAVRH.md).
-- Robert: "udelej stejny system jako je zde: https://supportbox.cz/funkce/
-- ... bude potreba jej implementovat jak do dokladu tak do 3D sceny, abych
-- mohl uzivatelum nejak radit online" -> "stav to hned".
--
-- v1 rozsah: zivy chat widget v 3D konfiguratoru (scene.html) + operatorska
-- konzole v adminu ("Podpora" tab). Cely konfigurator je za loginem
-- (rozhodnuti 2026-07-23, viz scene.html komentar u redirectToLogin), takze
-- zakaznik je VZDY prihlaseny app_users - zadna anonymni e-mailova
-- identifikace v v1 neni potreba (na rozdil od puvodniho navrhu v
-- SUPPORT_SYSTEM_NAVRH.md, ktery pocitalo i s neprihlasenymi navstevniky).
--
-- Fazi 2 (e-mail sync) a faze 3 (kontext dokladu u konverzace) budou
-- pripojeny pozdeji - sloupce customer_email/source uz jsou pripravene,
-- aby se schema pri tom nemuselo menit.
--
-- Pouziti (na serveru, s pristupem k DB definovanym v /opt/konfigurator/api/.env):
--   mysql -h 80.211.73.226 -u <db_user> -p xebyhtfeaj < 2026-07-25_support.sql

CREATE TABLE IF NOT EXISTS shop_support_conversations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_user_id INT NOT NULL,
  customer_email VARCHAR(255),
  customer_name VARCHAR(255),
  source VARCHAR(20) NOT NULL DEFAULT 'widget_scene',   -- 'widget_scene' | 'widget_doklady' | 'email' (faze 2+)
  status VARCHAR(20) NOT NULL DEFAULT 'open',           -- 'open' | 'closed'
  unread_by_admin TINYINT(1) NOT NULL DEFAULT 1,
  unread_by_customer TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  last_message_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_shop_support_conv_user
    FOREIGN KEY (customer_user_id) REFERENCES app_users(id) ON DELETE CASCADE,
  KEY idx_status_last (status, last_message_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS shop_support_messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  conversation_id INT NOT NULL,
  sender_type VARCHAR(20) NOT NULL,   -- 'customer' | 'operator' | 'system'
  sender_user_id INT NULL,            -- app_users.id odesilatele (zakaznik i operator jsou app_users)
  sender_name VARCHAR(255),
  body TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_shop_support_msg_conv
    FOREIGN KEY (conversation_id) REFERENCES shop_support_conversations(id) ON DELETE CASCADE,
  KEY idx_conversation_created (conversation_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
