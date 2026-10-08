-- Robert 2026-08-24: "odesílané odpovědi v poptávce udělej fajfku
-- pokud je odpověď odeslána" - propojeni operatorske zpravy ve
-- vlakne poptavky na jeji skutecny stav odeslani v shop_emails
-- (pending/sent/failed), aby se dalo zobrazit ✓/⏳/✗ primo u zpravy.

ALTER TABLE crm_lead_messages ADD COLUMN IF NOT EXISTS email_log_id INT NULL AFTER message_id_header;
