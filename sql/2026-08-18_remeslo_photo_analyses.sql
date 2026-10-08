-- Řemeslo - modul 2 (Foto: AI-vision analýza fotek řemeslníků -
-- čtení výkresů, počítání předmětů na fotce) - bot12, 2026-08-18.
-- Viz REMESLO_KONCEPT.md pro celý kontext.
--
-- Robert (přes bot3): ANTHROPIC_API_KEY v konfigurátoru je stále
-- neplatný (401) - žádný živý automatický běh, jen "příležitostné
-- zpracování v rámci komunikace" (Robert/bot pošle fotku, ručně ji
-- vyhodnotí přes Claude Code a výsledek doplní zpátky). Stejný vzor
-- jako `email_review_queue` (sql/2026-08-17_email_review_queue.sql) -
-- fronta "pending" záznamů čekajících na ruční review, ne
-- automatizovaná AI smyčka na pozadí.
--
-- `craftsman_id` zatím vždy NULL - appka Řemeslo je zatím čistě
-- interní (žádní skuteční uživatelé-řemeslníci), sloupec je tu
-- dopředu pro budoucí napojení na `remeslo_craftsmen`.

CREATE TABLE remeslo_photo_analyses (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  craftsman_id        INT NULL,
  filename            VARCHAR(255) NOT NULL,
  original_filename   VARCHAR(255) NULL,
  context_note        TEXT NULL,
  status              ENUM('pending','reviewed') NOT NULL DEFAULT 'pending',
  analysis_result      TEXT NULL,
  reviewed_by         INT NULL,
  reviewed_at         DATETIME NULL,
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_rpa_status (status),
  KEY idx_rpa_craftsman (craftsman_id),
  CONSTRAINT fk_rpa_craftsman FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id) ON DELETE SET NULL,
  CONSTRAINT fk_rpa_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
