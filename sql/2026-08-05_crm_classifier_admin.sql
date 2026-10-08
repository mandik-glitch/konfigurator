-- Vyjimky podle odesilatele/domeny (Robert: chce admin panel "pro
-- nastavovani filtru a klicovych spojeni"). pattern: "jmeno@domena.cz"
-- = presna shoda, "@domena.cz" = shoda CELE domeny odesilatele.
-- rule_type: 'ignore' (nikdy nezpracovavat, ani jako poptavku, ani do
-- Podpory - absolutni override, kontroluje se JAKO PRVNI, pred
-- slovnim klasifikatorem) | 'force_poptavka' (obejde slovni
-- klasifikator, rovnou poptavka) | 'force_shop_related' (obejde
-- _is_shop_related_email, rovnou Podpora - jen kdyz email uz neskoncil
-- jako poptavka).
CREATE TABLE crm_classifier_sender_rules (
  id INT AUTO_INCREMENT PRIMARY KEY,
  pattern VARCHAR(255) NOT NULL,
  rule_type VARCHAR(20) NOT NULL,
  note VARCHAR(255) NULL,
  created_by INT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_ccsr_pattern (pattern),
  CONSTRAINT fk_ccsr_user FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Prepinatelna kriteria "vztah k eshopu" (_is_shop_related_email v
-- api/support_email_sync.py) - jednoradkova tabulka, stejny vzor jako
-- email_sync_state/crm_quote_sequence.
CREATE TABLE crm_classifier_settings (
  id INT PRIMARY KEY DEFAULT 1,
  check_app_users TINYINT(1) NOT NULL DEFAULT 1,
  check_shop_customers TINYINT(1) NOT NULL DEFAULT 1,
  check_shop_orders TINYINT(1) NOT NULL DEFAULT 1,
  check_support_conversations TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO crm_classifier_settings (id) VALUES (1);
