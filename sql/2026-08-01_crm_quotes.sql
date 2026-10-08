-- Nabidky (obchodni cenove nabidky) - bot5, 2026-08-01.
--
-- Robert: "priprav plan pro strukturu nabidek melo by se to dit
-- automaticky z poptavky ale i rucne a kazdou nabidku chci mit
-- vedenou jako adresar a ten muze mit dalsi slozky pod slozky protoze
-- jedne nabidky se muze tykat mnoho ruznych typu dokladu" + "Cislovani
-- ctyricifernte cislo a zatim RM zatim nazev klienta" + "kdyz vznikne
-- adresar pro konkretni poptavku ulozi se do nej vsechny prilohy z
-- toho daneho e-mailu" + "zaroven ... i pripadne budouci prilohy
-- jinych e-mailu vlakno".
--
-- Viz api/quotes.py pro kompletni logiku. Soubory NEJSOU pod webapp/
-- (cely adresar je nginxem servirovan staticky, viz
-- /etc/nginx/sites-enabled/konfigurator "location / { root
-- /opt/konfigurator/webapp; ... }") - ukladaji se do
-- /opt/konfigurator/private-files/ (mimo nginx docroot, pristup jen
-- pres autentizovany Flask endpoint).

-- Globalni ctyrmistne cislo (ne per rok/typ jako shop_document_sequences
-- - Robert zminil jen "ctyriciferne cislo"). Zamyka se FOR UPDATE stejne
-- jako shop_document_sequences (viz api/documents.py).
CREATE TABLE crm_quote_sequence (
  id INT PRIMARY KEY DEFAULT 1,
  next_number INT NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT INTO crm_quote_sequence (id, next_number) VALUES (1, 1);

-- Nabidka = korenovy "adresar". lead_id NULLABLE + ON DELETE SET NULL,
-- aby nabidka PREZILA smazani leadu (crm_admin_lead_reject dela fyzicke
-- DELETE FROM crm_leads pri presunu do Podpory). client_label/
-- contact_email jsou SNAPSHOT sloupce (stejna filozofie jako
-- shop_documents.recipient_snapshot) - nabidka zustane citelna i po
-- zaniku/odpojeni leadu.
CREATE TABLE crm_quotes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  lead_id INT NULL,
  customer_id INT NULL,
  quote_number VARCHAR(4) NOT NULL,        -- "0001" (zero-padded)
  client_label VARCHAR(255) NOT NULL,      -- "zatim nazev klienta"
  contact_email VARCHAR(255) NULL,
  title VARCHAR(500) NULL,
  created_by INT NULL,                     -- NULL = zalozeno automaticky systemem
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_crm_quotes_number (quote_number),
  KEY idx_crm_quotes_lead (lead_id),
  CONSTRAINT fk_crm_quotes_lead FOREIGN KEY (lead_id) REFERENCES crm_leads(id) ON DELETE SET NULL,
  CONSTRAINT fk_crm_quotes_customer FOREIGN KEY (customer_id) REFERENCES shop_customers(id) ON DELETE SET NULL,
  CONSTRAINT fk_crm_quotes_created_by FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Podslozky - self-referential adjacency list, stejny vzor jako
-- content_categories.parent_id.
CREATE TABLE crm_quote_folders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  quote_id INT NOT NULL,
  parent_folder_id INT NULL,
  name VARCHAR(255) NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_cqf_quote (quote_id, parent_folder_id),
  CONSTRAINT fk_cqf_quote FOREIGN KEY (quote_id) REFERENCES crm_quotes(id) ON DELETE CASCADE,
  CONSTRAINT fk_cqf_parent FOREIGN KEY (parent_folder_id) REFERENCES crm_quote_folders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Soubory libovolneho typu (PDF/DOCX/XLSX/JPG/vykresy...) - proto NE
-- gallery_items (ten ma ALLOWED_EXT jen pro fotky/video/audio).
-- folder_id NULL = soubor v KORENI nabidky (zamerne dovoleno - e-mailove
-- prilohy se ukladaji automaticky bez zasahu admina, vynucovat vychozi
-- slozku by pridalo komplexitu bez prinosu).
CREATE TABLE crm_quote_files (
  id INT AUTO_INCREMENT PRIMARY KEY,
  quote_id INT NOT NULL,
  folder_id INT NULL,
  filename VARCHAR(255) NOT NULL,           -- zobrazovany (puvodni) nazev
  stored_filename VARCHAR(255) NOT NULL,    -- nazev na disku (nahodny token)
  content_type VARCHAR(150) NULL,
  size_bytes INT NULL,
  source VARCHAR(30) NOT NULL DEFAULT 'upload',  -- 'upload' | 'email_attachment'
  source_message_id INT NULL,               -- vyplneno pri source='email_attachment'
  uploaded_by INT NULL,                     -- NULL = automaticky/e-mail
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_cqfiles_quote (quote_id, folder_id),
  CONSTRAINT fk_cqfiles_quote FOREIGN KEY (quote_id) REFERENCES crm_quotes(id) ON DELETE CASCADE,
  CONSTRAINT fk_cqfiles_folder FOREIGN KEY (folder_id) REFERENCES crm_quote_folders(id) ON DELETE SET NULL,
  CONSTRAINT fk_cqfiles_message FOREIGN KEY (source_message_id) REFERENCES crm_lead_messages(id) ON DELETE SET NULL,
  CONSTRAINT fk_cqfiles_uploaded_by FOREIGN KEY (uploaded_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Prilohy e-mailu k poptavce - ukladaji se VZDY, bez ohledu na to, jestli
-- uz nabidka existuje (nabidka muze vzniknout az pozdeji, kdyz lead
-- prejde do stavu 'nabidnuto' - viz api/crm.py). ON DELETE CASCADE z
-- crm_lead_messages (smazani leadu pres crm_admin_lead_reject tyto
-- radky smaze spolu s nim) - proto MUSI mit crm_quote_files vlastni
-- NEZAVISLOU kopii (viz "kdyz vznikne adresar ... ulozi se do nej
-- vsechny prilohy" - kopirovani, ne presun/live odkaz).
CREATE TABLE crm_lead_message_attachments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  message_id INT NOT NULL,
  filename VARCHAR(255) NOT NULL,
  stored_filename VARCHAR(255) NOT NULL,
  content_type VARCHAR(150) NULL,
  size_bytes INT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_clma_message (message_id),
  CONSTRAINT fk_clma_message FOREIGN KEY (message_id) REFERENCES crm_lead_messages(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
