-- Skutecny cas odeslani e-mailu (bot5, 2026-10-08; pozadavek bot16 po Robertovi:
-- "tohle se nabidlo k odeslani a pritom schvaleni v dashboardu jsem udelal az ted").
--
-- shop_emails.created_at / system_emails.created_at = cas ZARAZENI do fronty (u automatickych e-mailu se schvaluje az pozdeji), ne cas odeslani.
-- Novy nullable sloupec sent_at = okamzik, kdy e-mail skutecne odesel (status 'sent'); u cekajicich / zamitnutych / neuspesnych zustava NULL.
-- Zpetne kompatibilni: stary kod sloupec nezna a nic mu nechybi, proto jde migrace pustit hned, nemusi cekat na nasazeni API.
-- Idempotentni: ALTER pousti scripts/2026-10-08_bot5_sent_at_migrace.py jen kdyz sloupec chybi, doplneni plni jen radky se sent_at IS NULL.

ALTER TABLE shop_emails ADD COLUMN sent_at DATETIME NULL AFTER created_at;
ALTER TABLE system_emails ADD COLUMN sent_at DATETIME NULL AFTER created_at;

-- Zpetne doplneni --------------------------------------------------------
-- rucne odeslane (odesly v okamziku vzniku radku): sent_at = created_at
UPDATE shop_emails SET sent_at = created_at
 WHERE status = 'sent' AND trigger_type = 'manual' AND sent_at IS NULL;

-- automaticke (cekaly na schvaleni): cas schvaleni z audit_log (api/emails.py::admin_email_review loguje 'Schváleno: ...' hned po odeslani)
UPDATE shop_emails e
   SET e.sent_at = (SELECT MAX(a.created_at) FROM audit_log a
                     WHERE a.entity_type = 'email' AND a.action = 'update' AND a.entity_id = e.id AND a.detail LIKE 'Schváleno:%')
 WHERE e.status = 'sent' AND e.trigger_type = 'auto' AND e.sent_at IS NULL;

-- systemove e-maily (vzdy schvalovane): totez z audit_log entity_type 'system_email'
UPDATE system_emails s
   SET s.sent_at = (SELECT MAX(a.created_at) FROM audit_log a
                     WHERE a.entity_type = 'system_email' AND a.action = 'update' AND a.entity_id = s.id AND a.detail LIKE 'Schváleno:%')
 WHERE s.status = 'sent' AND s.sent_at IS NULL;
