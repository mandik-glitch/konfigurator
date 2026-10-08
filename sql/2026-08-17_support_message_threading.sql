-- Skutecne e-mailove threadovani konverzaci v Podpore - bot10, 2026-08-17.
--
-- Kontext (Robert pres bot3, po nahlasenem bugu u konverzace #42):
-- api/support_email_sync.py::_find_or_create_conversation() drive
-- parovala konverzaci VYHRADNE podle odesilatelovy e-mailove adresy -
-- jakmile pro danou adresu jednou existovala konverzace, KAZDY dalsi
-- e-mail od stejne adresy (bez ohledu na predmet/obsah) se navzdy
-- prilepil do TE SAME radky. U konverzace #42 se tak do jednoho vlakna
-- smichaly zcela nesouvisejici e-maily (viz AGENTS_LOG.md pro presny
-- popis incidentu).
--
-- Oprava pridava sloupec pro ULOZENI Message-ID hlavicky KAZDE
-- synchronizovane e-mailove zpravy (NULL u zprav z jinych zdroju -
-- widget/admin odpoved nemaji vlastni RFC 5322 Message-ID) - dalsi
-- prichozi e-mail se pak paruje SKUTECNYM threadovanim (jeho vlastni
-- In-Reply-To/References hlavicky odkazujici na tenhle ulozeny
-- Message-ID), ne uz jen podle shodne adresy odesilatele. Viz
-- api/support_email_sync.py pro presnou logiku pouziti.
--
-- Pouziti: python api/db_migrate.py sql/2026-08-17_support_message_threading.sql

ALTER TABLE shop_support_messages
    ADD COLUMN message_id_header VARCHAR(255) NULL
    COMMENT 'RFC 5322 Message-ID hlavicky synchronizovaneho e-mailu (NULL u widget/admin zprav) - pro skutecne threadovani, viz _find_or_create_conversation()',
    ADD KEY idx_message_id_header (message_id_header);
