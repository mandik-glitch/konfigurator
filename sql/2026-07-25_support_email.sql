-- Podpora - Faze 2 (e-mailova synchronizace) - bot1, 2026-07-25/26.
-- Robert: "[jake prichozi emaily maji spadnout do Podpory] Uplne vsechny
-- nove e-maily" + "[oznacit jako precteno] Ano" + potvrzeni pouzit
-- existujici Gmail App Password (uz je v .env jako SMTP_PASSWORD, funguje
-- shodne pro SMTP i IMAP).
--
-- Kazdy novy e-mail v mandik@logiman.cz (IMAP imap.gmail.com) se stane
-- konverzaci/zpravou v Podpore (podle e-mailu odesilatele - viz
-- api/support_email_sync.py) - i kdyz odesilatel neni prihlaseny uzivatel
-- ani drivejsi navstevnik widgetu. CHECK constraint proto rozsiren o
-- "identifikovano jen e-mailem" (bez customer_user_id/guest_session_id).
--
-- email_subject drzi predmet PRVNIHO e-mailu v konverzaci, aby operatorska
-- odpoved (odeslana pres existujici SMTP, viz app.py send_email()) mohla
-- pouzit citelne "Re: <predmet>" misto genericke hlasky.

ALTER TABLE shop_support_conversations
  ADD COLUMN email_subject VARCHAR(500) NULL AFTER source,
  DROP CHECK chk_shop_support_identity,
  ADD CONSTRAINT chk_shop_support_identity
    CHECK (customer_user_id IS NOT NULL OR guest_session_id IS NOT NULL OR customer_email IS NOT NULL);
