-- Fronta neklasifikovanych ("jine"/mimo eshop) e-mailu k rucnimu
-- prehledu - bot8, 2026-08-17 (pres bot3).
--
-- Kontext: Robert se rozhodl zrusit myslenku pevneho Gmail filtru a
-- misto toho chtel LLM klasifikaci "naziva" (viz AGENTS_LOG.md pro
-- cely prubeh) - pak upresnil zjednoduseni: "nepotrebuju to delat
-- zive, staci kdyz to udelame obcas v ramci teto komunikace" - takze
-- misto automatizovaneho volani Anthropic API v pozadi (zadny platny
-- klic stejne neni, viz AGENTS_LOG) se prubezny 2minutovy sync necha
-- bezet jako "hruby filtr" (crm_classifier_words, beze zmeny) a
-- MANUALNI/na-vyzadani review nad tim, co padlo do "jine" a NEBYLO
-- eshop-souvisejici, dela clovek/bot primo v konverzaci - k tomu ale
-- potrebuje mit CO cist. Bot3: "architektura: ... ostatni/nezaraditelne
-- -> nechavame neutralne stranou, ZADNA ZTRATA DAT" - predtim (viz
-- support_email_sync.py radek ~383-389 pred touto zmenou) se takove
-- e-maily nikam neukladaly, jen se posunul UID kurzor - fakticky ztrata
-- dat, presny opak zadani. Tahle tabulka tu deru zaplnuje.

CREATE TABLE email_review_queue (
  id INT AUTO_INCREMENT PRIMARY KEY,
  source_email VARCHAR(255) NOT NULL,
  source_name VARCHAR(255) NULL,
  subject VARCHAR(500) NULL,
  body_text MEDIUMTEXT NULL,
  received_at DATETIME NOT NULL,
  suggested_label VARCHAR(20) NOT NULL DEFAULT 'jine',
  -- 'nove' = jeste nikdo neprohlidnul, 'precteno' = clovek/bot uz
  -- posoudil a rozhodl, ze skutecne nikam nepatri (spam/newsletter/...).
  -- Pokud se pri rucnim review ukaze, ze to VE SKUTECNOSTI je poptavka
  -- nebo doklad, zapise se rucne do prislusne tabulky (crm_leads /
  -- incoming_documents) a tenhle radek se jen oznaci precteno - zadny
  -- automaticky presun, aby nevznikaly duplicity pri chybnem posouzeni.
  review_status VARCHAR(20) NOT NULL DEFAULT 'nove',
  reviewed_by INT NULL,
  reviewed_at DATETIME NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_erq_status (review_status),
  KEY idx_erq_received (received_at),
  CONSTRAINT fk_erq_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
