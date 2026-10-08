-- Overovani e-mailu pri registraci + fronta systemovych (ne-objednavkovych)
-- e-mailu cekajicich na schvaleni admina (bot13, 2026-08-23).
--
-- Kontext: bezpecnostni review verejne registrace Remesla (bot14,
-- 2026-08-20, AGENTS_LOG.md "BEZPECNOSTNI REVIEW verejne registrace
-- Remesla") + Robertovo rozhodnuti implementovat vsechny 3 body (bot3
-- koordinace, 2026-08-23). Bod 1 (overeni e-mailu) - novy ucet zustava
-- neaktivni (app_users.active=0), dokud nepotvrdi e-mail klikem na
-- odkaz s tokenem z teto tabulky.
--
-- WORKFLOW.md bod 16 (Robert 2026-08-22, plosny zakaz automatickeho
-- odesilani e-mailu bez schvaleni admina) plati i pro overovaci e-mail -
-- neni vyjimkou (viz AGENTS_LOG.md, dotaz bota13 na bota3 pred timhle
-- commitem). Overovaci e-mail se proto NEODESILA primo - zaloguje se
-- do system_emails jako 'pending' a ceka na rucni schvaleni v adminu
-- (GET/PUT /api/admin/system-emails, viz api/system_emails.py), stejny
-- princip jako shop_emails (api/emails.py) u objednavkovych e-mailu.
-- Samostatna tabulka misto pretezovani shop_emails, protoze ta ma
-- order_id NOT NULL s FK na shop_orders - systemovy e-mail (overeni
-- uctu) zadnou objednavku nema.

CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    token       VARCHAR(64) NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME NOT NULL,
    used        TINYINT(1) NOT NULL DEFAULT 0,
    UNIQUE KEY uq_evt_token (token),
    KEY idx_evt_user (user_id),
    -- ON DELETE CASCADE (ne RESTRICT) - remeslo_register() ma kompenzacni
    -- DELETE FROM app_users, kdyz selze druhy krok (zapis remeslo_craftsmen
    -- v cross-DB transakci); bez CASCADE by uz vlozeny verification token
    -- tenhle DELETE shodil na FK constraint chybe.
    CONSTRAINT fk_evt_user FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS system_emails (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    user_id             INT NULL,
    kind                VARCHAR(30) NOT NULL,       -- 'email_verification' (dalsi typy pribudou postupne)
    recipient_email     VARCHAR(255) NOT NULL,
    subject             VARCHAR(500) NOT NULL,
    body_text           MEDIUMTEXT NOT NULL,
    status              VARCHAR(10) NOT NULL DEFAULT 'pending',  -- 'pending' | 'sent' | 'failed' | 'rejected'
    error_message       TEXT NULL,
    trigger_type        VARCHAR(10) NOT NULL DEFAULT 'auto',
    sent_by             VARCHAR(150) NULL,
    sent_by_user_id     INT NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_system_emails_user (user_id),
    KEY idx_system_emails_status (status),
    KEY idx_system_emails_created (created_at),
    CONSTRAINT fk_system_emails_user FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- email_verified odlisuje "cely nikdy nepotvrdil e-mail" od "admin ucet
-- rucne deaktivoval" (obojí dnes sdili app_users.active) - potrebne pro
-- spravnou hlasku pri loginu (nabidnout znovuodeslani vs. "kontaktuj
-- admina"). DEFAULT 1 = vsechny STAVAJICI ucty (zalozene pred timhle
-- pravidlem) se povazuji za overene, zadne zpetne zamykani.
ALTER TABLE app_users
    ADD COLUMN email_verified TINYINT(1) NOT NULL DEFAULT 1 AFTER active;
