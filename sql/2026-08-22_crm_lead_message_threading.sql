-- Skutecne e-mailove threadovani poptavek v CRM - bot10, 2026-08-22.
--
-- Kontext (Robert pres bot3): crm.find_or_create_lead() parovala novou
-- zpravu k existujici poptavce VYHRADNE podle contact_email - presna
-- obdoba incidentu #42 (viz sql/2026-08-17_support_message_threading.sql),
-- ktery byl opraven pro Emaily prichozi, ale nikdy se nezrcadlil do CRM.
--
-- Oprava pridava sloupec pro ULOZENI Message-ID hlavicky KAZDE
-- synchronizovane e-mailove zpravy (NULL u zprav zalozenych rucne v
-- adminu/verejnym formularem - ty nemaji vlastni RFC 5322 Message-ID) -
-- dalsi prichozi e-mail se pak paruje SKUTECNYM threadovanim (jeho
-- vlastni In-Reply-To/References hlavicky odkazujici na tenhle ulozeny
-- Message-ID), ne uz jen podle shodne adresy odesilatele. Viz
-- api/crm.py::find_or_create_lead() pro presnou logiku pouziti.
--
-- Stejny typ/index jako shop_support_messages.message_id_header
-- (sql/2026-08-17_support_message_threading.sql), pro konzistenci.
--
-- Pouziti: python api/db_migrate.py sql/2026-08-22_crm_lead_message_threading.sql

ALTER TABLE crm_lead_messages
    ADD COLUMN message_id_header VARCHAR(255) NULL
    COMMENT 'RFC 5322 Message-ID hlavicky synchronizovaneho e-mailu (NULL u rucne zalozenych/verejny formular zprav) - pro skutecne threadovani, viz api/crm.py::find_or_create_lead()',
    ADD KEY idx_message_id_header (message_id_header);
