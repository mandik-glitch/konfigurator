-- E-mailovy klient + historie (bot3, 2026-07-25, v9).
--
-- Robert: "nachystej emailoveho klienta pro odesilani emailu primo ze
-- systemu, vcetne vedeni historie, napric sekcemi jako objednavky,
-- faktury, vsechny tyto typy dokladu, pridej dodaci listy, vse musi mit
-- prehledy s poradnym filtrovanim."
--
-- Rozhodnuti Roberta (AskUserQuestion, 2026-07-25):
--   - odesilani: RUCNE z adminu I AUTOMATICKY u klicovych udalosti (obojí
--     zvoleno) - viz api/emails.py a volani z orders.py/documents.py.
--   - priloha: PDF souvisejiciho dokladu se automaticky prednabizi.
--   - dodaci listy: NOVY typ dokladu v UZ EXISTUJICI tabulce shop_documents
--     (document_type='delivery_note') - zadna schema zmena tam NENI
--     potreba, document_type je VARCHAR(30) bez CHECK constraintu (viz
--     2026-07-25_documents.sql) - jen rozsireni DOCUMENT_TYPES v
--     api/documents.py.
--
-- Kazdy odeslany e-mail (rucni i automaticky) se zaznamena sem - historie
-- jde filtrovat/zobrazit jak podle objednavky (order_id), tak podle
-- konkretniho dokladu (document_id, NULL u potvrzeni objednavky / zmeny
-- stavu / vlastniho e-mailu bez prilohy), tak CELKOVE pres
-- GET /api/admin/emails (stejny vzor filtrovani/countu jako
-- GET /api/admin/documents z (13)).
--
-- Pouziti: mysql -h 80.211.73.226 -u <db_user> -p xebyhtfeaj < 2026-07-25_emails.sql

CREATE TABLE IF NOT EXISTS shop_emails (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    order_id            INT NOT NULL,
    document_id         INT NULL,                -- ktery doklad byl prilohou (PDF) - NULL u potvrzeni objednavky/zmeny stavu/vlastniho e-mailu bez prilohy
    template_key        VARCHAR(30) NOT NULL,     -- 'order_confirmation' | 'status_change' | 'proforma_invoice' | 'payment_tax_document' | 'invoice' | 'delivery_note' | 'custom'
    recipient_email     VARCHAR(255) NOT NULL,
    cc_email            VARCHAR(255) NULL,
    subject             VARCHAR(500) NOT NULL,
    body_text           MEDIUMTEXT NOT NULL,
    status              VARCHAR(10) NOT NULL DEFAULT 'sent',   -- 'sent' | 'failed'
    error_message       TEXT NULL,
    trigger_type        VARCHAR(10) NOT NULL DEFAULT 'manual', -- 'manual' | 'auto'
    sent_by             VARCHAR(150) NULL,        -- jmeno admina, nebo "Systém (automaticky)"
    sent_by_user_id     INT NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_shop_emails_order (order_id),
    KEY idx_shop_emails_document (document_id),
    KEY idx_shop_emails_created (created_at),
    KEY idx_shop_emails_recipient (recipient_email),
    CONSTRAINT fk_shop_emails_order FOREIGN KEY (order_id) REFERENCES shop_orders(id),
    CONSTRAINT fk_shop_emails_document FOREIGN KEY (document_id) REFERENCES shop_documents(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
