-- Trvaly kurzor pro IMAP synchronizaci (nahrazuje nespolehlive
-- SEARCH UNSEEN, ktere se rozbiji, kdyz si e-mail nekdo precte v
-- normalnim Gmailu drive nez to stihne 2minutovy tik synchronizace -
-- viz AGENTS_LOG.md pro cely kontext incidentu). Jednoradkova
-- tabulka, stejny vzor jako crm_quote_sequence.
CREATE TABLE email_sync_state (
  id INT PRIMARY KEY DEFAULT 1,
  last_uid INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO email_sync_state (id, last_uid) VALUES (1, 0);
