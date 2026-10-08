-- Historie planovaneho/rucniho nasazeni serveroveho kodu (bot16, 2026-10-01, Robert pres bot3:
-- "uz me nebavi delat restart"). Jeden radek = jeden beh scripts/nasazeni.py, i preskoceny a "nic"
-- (WORKFLOW.md pravidlo 28: automat musi mit pozorovatelny stav). Cte ho panel "Nasazeni serveru"
-- na Dashboardu (api/deploy_runs.py) a `scripts/restart_konfigurator.sh --stav`.
--
-- status: bezi | ok | varovani | selhalo | preskoceno | nic | prerusen
-- trigger_type: plan (timer) | rucni
-- commits_json: [{hash, ts, predmet}] commity do api/*.py, ktere se timto behem nasazuji
-- detail_json: mereni (pauza obsluhy, selhane pozadavky, smoke, journal, nginx 5xx, blokatory...)
--
-- Tabulku zaklada i scripts/nasazeni.py (CREATE TABLE IF NOT EXISTS), aby fungoval i bez migrace -
-- DDL musi zustat shodne.
-- COLLATE utf8mb4_0900_ai_ci (NE _unicode_ci): zbytek DB bezi na _0900_ai_ci, mix collations shodi JOIN.
CREATE TABLE IF NOT EXISTS deploy_runs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  started_at DATETIME NOT NULL,
  finished_at DATETIME NULL,
  trigger_type VARCHAR(16) NOT NULL,
  status VARCHAR(24) NOT NULL,
  reason VARCHAR(600) NULL,
  head_before VARCHAR(40) NULL,
  head_after VARCHAR(40) NULL,
  commits_count INT NOT NULL DEFAULT 0,
  commits_json MEDIUMTEXT NULL,
  detail_json MEDIUMTEXT NULL,
  duration_s DECIMAL(8,2) NULL,
  requested_by VARCHAR(40) NULL,
  KEY idx_deploy_runs_started (started_at),
  KEY idx_deploy_runs_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
