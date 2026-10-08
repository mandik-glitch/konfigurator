-- Manifest automatickeho razitkovace zakaznickych obrazku (Robert 2026-09-11
-- pres bot3: "nech postavit automaticky razitkovac na vsechny obrazky na
-- webu, originaly ulozit bokem"). Bot9 (motor), bot10 (napojeni na upload,
-- 11 nezavislych mist zapisu - VSECHNY pisou do TEHOZ manifestu, jinak by
-- vratnost platila jen pro cast souboru), bot16 (2D podklad loga).
--
-- Bez zaznamu tady neni razitkovani vratne, jen doufajici - viz
-- scripts/obrazky_razitko.py pro zapisovaci/idempotencni logiku.
CREATE TABLE IF NOT EXISTS image_watermark_manifest (
  rel_path             VARCHAR(500) NOT NULL COMMENT 'cesta relativni k webapp/, napr. content-files/gallery/x.jpg',
  original_backup_path VARCHAR(500) NOT NULL COMMENT 'kam se ulozil netknuty original, MIMO webapp/ (nikdy verejne dostupny)',
  original_sha256      CHAR(64)     NOT NULL,
  stamped_sha256       CHAR(64)     NOT NULL COMMENT 'idempotence: pred zapisem se porovna SHA ziveho souboru s timhle',
  stamped_at           DATETIME     NOT NULL,
  params_json          TEXT         NOT NULL COMMENT 'krytí/velikost/pozice pouzite pri tomhle otisku (parametry, ne konstanty)',
  logo_version         VARCHAR(40)  NOT NULL,
  PRIMARY KEY (rel_path)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
