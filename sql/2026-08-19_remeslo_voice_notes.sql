-- Řemeslo - hlasový zápis zakázky (bot3, 2026-08-19). Viz
-- REMESLO_APPKY_HLOUBKOVY_PRUZKUM.md souhrn ("jaká funkce by
-- řemeslníka nadchla" - žádná z 14 zkoumaných appek nemá hlasový
-- zápis) a AGENTS_LOG.md pro celou historii rozhodnutí (ElevenLabs
-- klíč bez STT oprávnění -> přechod na lokální faster-whisper kvůli
-- omezenému CPU serveru a Robertovu požadavku "neindexovat" u
-- třetí strany).
--
-- ASYNCHRONNÍ fronta (Robert 2026-08-19: "řemeslník čekat nebude,
-- řekne něco a jde dál") - stejný vzor "pending -> zpracováno" jako
-- remeslo_photo_analyses, ale tady review dělá automaticky worker
-- (lokální Whisper), ne člověk. status='failed' pro chyby přepisu
-- (poškozený soubor, prázdné ticho...), ne mlčky mizí.
--
-- `craftsman_id` zatím vždy NULL (Řemeslo nemá zatím reálné
-- uživatele-řemeslníky, stejně jako u photo_analyses) - sloupec
-- připraven dopředu pro budoucí napojení.

CREATE TABLE remeslo_voice_notes (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  craftsman_id        INT NULL,
  created_by          INT NULL,
  filename            VARCHAR(255) NOT NULL,
  status              ENUM('pending','done','failed') NOT NULL DEFAULT 'pending',
  transcript          TEXT NULL,
  error_message       TEXT NULL,
  duration_sec        DECIMAL(6,2) NULL,
  processing_ms       INT NULL,
  processed_at        DATETIME NULL,
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_rvn_status (status),
  KEY idx_rvn_craftsman (craftsman_id),
  CONSTRAINT fk_rvn_craftsman FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id) ON DELETE SET NULL,
  CONSTRAINT fk_rvn_created_by FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
