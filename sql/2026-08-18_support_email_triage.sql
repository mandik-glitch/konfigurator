-- Trideni prichozich e-mailu (Emaily prichozi) - bot3, 2026-08-18.
--
-- Robert: tlacitko "Tridit" v Emaily prichozi ma zadat botovi ukol
-- vytridit konverzace a navrhnout, kam kazda dal patri + co s
-- prilohami; navrh se zobrazi v panelu, kde Robert kazdy radek
-- schvali/zamitne. STEJNY princip jako `email_review_queue`/
-- `remeslo_photo_analyses` - ANTHROPIC_API_KEY tu neni platny, zadne
-- zive automaticke AI volani, posouzeni dela bot rucne a zapise
-- vysledek sem.
--
-- Schvaleni/zamitnuti v teto verzi jen ZAZNAMENA rozhodnuti (auditni
-- stopa) - needela samo presun/archivaci/smazani, to Robert provede
-- existujicimi ovladacimi prvky (Archivovat/Uzavrit/Smazat), az navrh
-- potvrdi. Muze se pozdeji rozsirit na automaticke provedeni.

CREATE TABLE support_email_triage_runs (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  requested_by        INT NOT NULL,
  status              ENUM('pending','ready_for_review','done') NOT NULL DEFAULT 'pending',
  requested_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at        DATETIME NULL,
  processed_by_note   VARCHAR(255) NULL,
  CONSTRAINT fk_setr_user FOREIGN KEY (requested_by) REFERENCES app_users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE support_email_triage_proposals (
  id                    INT AUTO_INCREMENT PRIMARY KEY,
  run_id                INT NOT NULL,
  conversation_id       INT NOT NULL,
  -- 'crm' (poptavka), 'doklad' (prijaty doklad), 'podpora' (ponechat
  -- v Emaily prichozi), 'spam' (navrh k archivaci/smazani), 'jine'
  -- (nejasne, potreba rucni posouzeni) - stejne kategorie jako
  -- existujici klasifikator v support_email_sync.py/crm.py.
  proposed_destination  VARCHAR(20) NOT NULL,
  destination_label     VARCHAR(255) NOT NULL,
  reasoning             TEXT NULL,
  attachment_note       TEXT NULL,
  review_status         ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
  reviewed_by           INT NULL,
  reviewed_at           DATETIME NULL,
  KEY idx_setp_run (run_id),
  CONSTRAINT fk_setp_run FOREIGN KEY (run_id) REFERENCES support_email_triage_runs(id) ON DELETE CASCADE,
  CONSTRAINT fk_setp_conv FOREIGN KEY (conversation_id) REFERENCES shop_support_conversations(id) ON DELETE CASCADE,
  CONSTRAINT fk_setp_reviewer FOREIGN KEY (reviewed_by) REFERENCES app_users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
