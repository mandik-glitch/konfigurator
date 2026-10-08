-- Auta - strom Znacka -> Model -> karoserie/velikosti pro 3D scenu
-- (Robert 2026-08-05: "vyzaduj si pristup ke mne na PC do slozky
-- karoserii aut, nasledne vsechny nahrajes do 3D sceny... Leve menu,
-- separatni strom Auta rozdeleno podle znacek a modelu do kategorii,
-- velikosti budou uz na jedne urovni"). Format zdrojovych souboru
-- .fbx/.stp/.step - prevod na GLB pres existujici pipeline
-- (fbx_convert.py/step_convert.py, uz pouzivana pro profily katalogu).
CREATE TABLE car_makes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL UNIQUE,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE car_models (
  id INT AUTO_INCREMENT PRIMARY KEY,
  make_id INT NOT NULL,
  name VARCHAR(100) NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_car_model (make_id, name),
  CONSTRAINT fk_cm_make FOREIGN KEY (make_id) REFERENCES car_makes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- "velikosti budou uz na jedne urovni" - zadna dalsi tabulka na
-- velikost/variantu, je to primo tenhle radek (name = napr. "L2H2",
-- "Kombi", "Furgon kratky"...).
CREATE TABLE car_bodies (
  id INT AUTO_INCREMENT PRIMARY KEY,
  model_id INT NOT NULL,
  name VARCHAR(150) NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  glb_file VARCHAR(255) NULL,
  original_filename VARCHAR(255) NULL,
  conversion_error TEXT NULL,
  uploaded_by INT NULL,
  uploaded_at DATETIME NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_cb_model (model_id),
  CONSTRAINT fk_cb_model FOREIGN KEY (model_id) REFERENCES car_models(id) ON DELETE CASCADE,
  CONSTRAINT fk_cb_user FOREIGN KEY (uploaded_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
