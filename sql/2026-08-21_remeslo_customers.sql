-- Zakaznici jako vlastni evidence per remeslnik (Robert, 2026-08-21:
-- "cekam na ty zakazniky") - drive jmeno zakaznika zilo jen jako
-- textove pole na kazde zakazce/nabidce/fakture zvlast, nic to
-- nespojovalo a hlasovy Moderator nemel odkud spolehlive poznat
-- "uz ho znam" (viz pripad "Novak" - existoval jen v historii jine
-- remeslnicke zakazky, ne jako vlastni zaznam).
CREATE TABLE IF NOT EXISTS remeslo_customers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  craftsman_id INT NOT NULL,
  name VARCHAR(255) NOT NULL,
  phone VARCHAR(50) NULL,
  email VARCHAR(255) NULL,
  note TEXT NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_remeslo_customers_craftsman (craftsman_id),
  INDEX idx_remeslo_customers_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
