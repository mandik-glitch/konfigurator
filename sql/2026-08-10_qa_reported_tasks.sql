-- Robert 2026-08-10 ("stisknu opravit a nic... rovnou poslat botovi
-- (vytvorit ukol)") - tlacitko "Opravit" u QA nalezu bez zaznamu v
-- administraci (kodove bugy, duplicate_sku, missing_glb_file,
-- orphaned_gallery_items) uz jen kopirovalo popis do schranky -
-- misto toho ted uklada nalez sem, aby sel videt/spravovat primo v
-- administraci (Dashboard, panel "Nahlasene ukoly"), bez nutnosti
-- upravovat opravneni souboru TASKS.md (www-data do nej nemuze psat).
CREATE TABLE qa_reported_tasks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  check_key VARCHAR(100) NOT NULL,
  finding_key VARCHAR(255) NOT NULL,
  label VARCHAR(255) NOT NULL,
  detail TEXT NOT NULL,
  -- Robert 2026-08-10 ("pokud admin stiskne opravit, ma se tato chyba
  -- hned zacit resit" -> AskUserQuestion: "oznacit jako VYSOKA
  -- PRIORITA pro dalsi session", NE automaticka oprava kodu) - vsechny
  -- nalezy z tlacitka "Opravit" (script "hledani chyb") sem prichazi
  -- s priority=1, aby je dalsi bot session videla jako prvni.
  priority TINYINT(1) NOT NULL DEFAULT 0,
  status ENUM('open','done') NOT NULL DEFAULT 'open',
  created_by INT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  resolved_at DATETIME NULL,
  KEY idx_qa_reported_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
