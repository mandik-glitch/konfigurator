-- Sdileny disk (nahrada Google Drive sdilenych slozek) - bot5, 2026-08-01.
--
-- Robert: "na google drive máme sdílené složky a chci je tam zrušit a
-- vést sdílený disk (složky prostě uložiště) na našem serveru" ->
-- upresneno pres AskUserQuestion: vlastni modul primo v administraci
-- (stejne prihlaseni jako admin), postaveny na uz overenem vzoru
-- slozky/soubory z Nabidek (viz api/quotes.py, sql/2026-08-01_crm_quotes.sql).
--
-- Na rozdil od Nabidek NENI strom vazany na zadny "korenovy" zaznam
-- (tam kazda nabidka mela vlastni strom) - je to JEDEN globalni
-- sdileny strom pro celou firmu, viditelny/editovatelny kazdym
-- prihlasenym adminem s pravem "sdileny_disk".
--
-- Soubory NEJSOU pod webapp/ (cely adresar je nginxem servirovan
-- staticky, viz /etc/nginx/sites-enabled/konfigurator) - ukladaji se
-- do /opt/konfigurator/private-files/shared-drive/ (mimo nginx
-- docroot, pristup jen pres autentizovany Flask endpoint), stejny
-- princip jako u Nabidek.

-- Podslozky - self-referential adjacency list, stejny vzor jako
-- crm_quote_folders/content_categories.parent_id. parent_folder_id
-- NULL = slozka v koreni disku.
CREATE TABLE shared_drive_folders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  parent_folder_id INT NULL,
  name VARCHAR(255) NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_by INT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_sdf_parent (parent_folder_id),
  CONSTRAINT fk_sdf_parent FOREIGN KEY (parent_folder_id) REFERENCES shared_drive_folders(id) ON DELETE CASCADE,
  CONSTRAINT fk_sdf_created_by FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Soubory libovolneho typu (stejne jako crm_quote_files - PDF/DOCX/
-- XLSX/JPG/cokoli, zadne ALLOWED_EXT omezeni jako u gallery_items).
-- folder_id NULL = soubor v koreni disku (dovoleno zamerne, stejny
-- duvod jako u Nabidek).
CREATE TABLE shared_drive_files (
  id INT AUTO_INCREMENT PRIMARY KEY,
  folder_id INT NULL,
  filename VARCHAR(255) NOT NULL,
  stored_filename VARCHAR(255) NOT NULL,
  content_type VARCHAR(150) NULL,
  size_bytes INT NULL,
  uploaded_by INT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_sdfiles_folder (folder_id),
  CONSTRAINT fk_sdfiles_folder FOREIGN KEY (folder_id) REFERENCES shared_drive_folders(id) ON DELETE CASCADE,
  CONSTRAINT fk_sdfiles_uploaded_by FOREIGN KEY (uploaded_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
