-- Robert 2026-08-24: "chci vidět, co hromadíme v mailboxu u nás" -
-- kompletní audit log KAŽDÉ zprávy, kterou support_email_sync.py
-- kdy zpracoval, bez ohledu na výsledek (poptávka/doklad/podpora,
-- i zahozené/ignorované/duplicitní) - dnešní incidenty (ztracená
-- příloha, objednávka v dokladech, duplicitní poptávka) ukázaly,
-- že bez tohohle není vidět, co se skutečně děje se vším, co projde
-- mailboxem, jen s tím, co "vyhrálo" a skončilo v některé z
-- existujících front (Poptávky/Doklady/Podpora).

CREATE TABLE IF NOT EXISTS email_sync_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  imap_uid INT NULL,
  message_id_header VARCHAR(998) NULL,
  from_email VARCHAR(255) NULL,
  from_name VARCHAR(255) NULL,
  subject VARCHAR(998) NULL,
  outcome VARCHAR(40) NOT NULL,
  lead_id INT NULL,
  conversation_id INT NULL,
  document_id INT NULL,
  note VARCHAR(255) NULL,
  processed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_email_sync_log_uid (imap_uid),
  INDEX idx_email_sync_log_msgid (message_id_header(191)),
  INDEX idx_email_sync_log_processed (processed_at),
  INDEX idx_email_sync_log_outcome (outcome)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
