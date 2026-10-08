-- Mini-shop: pravni dokumenty shopu (podminky, soukromi, vraceni ...) - bot5, 2026-10-02 (Robert pres bot3: slovensky shop se spousti zive, pravni stranky u poptavkoveho formulare).
-- Jeden dokument = (rodina shopu, druh, jazyk), text po jazycich jako u produktu: import jako draft, schvaluje Robert na /miniweb-schvaleni.html, verejne jen approved (GET /api/miniweb/legal -> documents).
-- Dokument je jako ostatni texty BEZ ZNACKY: prodejce je jen v legal.seller, v textu "prodavajici".
CREATE TABLE IF NOT EXISTS miniweb_documents (
  id INT NOT NULL AUTO_INCREMENT,
  family VARCHAR(40) NOT NULL COMMENT 'rodina shopu (packstations ...), shodna s miniweb_shops.family',
  kind VARCHAR(20) NOT NULL COMMENT 'terms | privacy | returns | shipping | cookies',
  lang VARCHAR(8) NOT NULL COMMENT 'jazyk dokumentu (sk, en, de ...), stejny tvar jako car_storefronts.lang',
  title VARCHAR(255) NOT NULL,
  body MEDIUMTEXT NOT NULL COMMENT 'cisty text s odstavci (HTML se pri importu odstrani)',
  status ENUM('draft','approved') NOT NULL DEFAULT 'draft' COMMENT 'verejnosti se servi jen approved, staff v nahledu i draft',
  approved_by INT DEFAULT NULL,
  approved_at DATETIME DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_miniweb_documents (family, kind, lang),
  KEY idx_miniweb_documents_lang (lang)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
