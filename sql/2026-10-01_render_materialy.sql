-- Ucinna prirazovaci tabulka renderovacich materialu katalogu (bot10, 2026-10-01; zadani Roberta:
-- "vsechny polozky katalogu mimo karoserie -> material z knihovny Vandr materialu", hlinik vsude alumi2,
-- laminodesky cub_seda, elektrozlab bila, perfopanely grey, neaktivni SSE dily nechat).
--
-- KANDIDAT - NESPUSTENO. Pousti Robert: !/opt/konfigurator/scripts/2026-09-03_bot16_mysql_apply.sh /opt/konfigurator/sql/2026-10-01_render_materialy.sql
-- (wrapper cte heslo z api/.env a nevypisuje ho). IDEMPOTENTNI: lze pustit opakovane (CREATE TABLE IF NOT EXISTS,
-- sloupce se pridaji jen kdyz chybi - MySQL 8 nezna ADD COLUMN IF NOT EXISTS, proto information_schema + PREPARE,
-- seed materialu ON DUPLICATE KEY UPDATE klic=klic = NEPREPISE pozdejsi upravy z adminu).
--
-- CO SE MENI NA STAVAJICICH TABULKACH: jen PRIDANI jednoho NULL sloupce render_material_key VARCHAR(40) na
-- shop_products, cfg_dily, content_categories (ALGORITHM=INSTANT = bez kopie tabulky; NULL = "dedit / beze zmeny",
-- dnesni chovani se nemeni). ZAMERNE bez FOREIGN KEY na tyhle 3 tabulky: ADD FOREIGN KEY by na produkcnich tabulkach
-- znamenal kopii tabulky (zamek zapisu); platnost klice hlida API (api/render_materialy.py) a lib funkce
-- render_material_key(); materialy se nemazou, jen aktivni=0.
--
-- Collation: COLLATE utf8mb4_0900_ai_ci (STAV.md "Nove tabulky" - mix collations shodi JOIN).
-- Kontrola kolizi (SELECT na zivou DB 2026-10-01): tabulky render_materialy / render_material_casti /
-- render_material_navrh NEEXISTUJI, sloupec render_material_key neexistuje ani v jedne ze 3 tabulek;
-- cfg_dily.id je VARCHAR(64), shop_products.id INT -> render_material_casti.dil_id je VARCHAR(64).
--
-- Rollback (kdyby bylo treba): DROP TABLE render_material_casti, render_material_navrh, render_materialy;
--   ALTER TABLE shop_products DROP COLUMN render_material_key; (totez cfg_dily, content_categories).

-- ---------------------------------------------------------------------------------------------------------------
-- 1) Knihovna materialu (jeden radek = jeden material, ktery umi Blender render i nahled v adminu)
-- ---------------------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS render_materialy (
  klic            VARCHAR(40)  NOT NULL,
  nazev           VARCHAR(120) NOT NULL,
  nazev_blender   VARCHAR(120) NULL,
  knihovna_soubor VARCHAR(255) NULL,
  knihovna_file_id INT         NULL,
  three_json      JSON         NULL,
  poradi          INT          NOT NULL DEFAULT 0,
  aktivni         TINYINT(1)   NOT NULL DEFAULT 1,
  poznamka        VARCHAR(500) NULL,
  created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (klic),
  KEY idx_render_materialy_poradi (aktivni, poradi)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='nazev_blender = PRESNY nazev materialu v .blend knihovne (vc. mezer, napr. "Red "); knihovna_file_id NULL = soubor se hleda podle jmena na Sdilenem disku';

-- ---------------------------------------------------------------------------------------------------------------
-- 2) Material po CASTECH vicetelesoveho dilu (GLB mesh/uzel Solid_0, Solid_1, ... -> klic)
-- ---------------------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS render_material_casti (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  zdroj       ENUM('product','cfg') NOT NULL,
  dil_id      VARCHAR(64)  NOT NULL,
  mesh_klic   VARCHAR(120) NOT NULL,
  render_material_key VARCHAR(40) NOT NULL,
  created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_render_material_casti (zdroj, dil_id, mesh_klic),
  KEY idx_render_material_casti_klic (render_material_key),
  CONSTRAINT fk_render_material_casti_klic FOREIGN KEY (render_material_key)
    REFERENCES render_materialy (klic) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='dil_id = shop_products.id jako text (zdroj=product) nebo cfg_dily.id (zdroj=cfg); mesh_klic = jmeno uzlu v GLB (Solid_N)';

-- ---------------------------------------------------------------------------------------------------------------
-- 3) Navrh z analyzy 2026-10-01 (jen cteni pro admin: stav OK/SPORNE/VYNECHANO, "pouzit navrh", navrh po castech).
--    Plni scripts/2026-10-01_render_materialy_predvyplneni.py (--apply). Nic z toho NEOVLIVNUJE render.
-- ---------------------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS render_material_navrh (
  zdroj          ENUM('product','cfg') NOT NULL,
  dil_id         VARCHAR(64)  NOT NULL,
  navrzeny_klic  VARCHAR(40)  NULL,
  stav           ENUM('OK','SPORNE','VYNECHANO') NOT NULL,
  pravidlo       VARCHAR(600) NULL,
  navrh_casti_json JSON       NULL,
  created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (zdroj, dil_id),
  KEY idx_render_material_navrh_stav (stav)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='podklad z analyzy materialu (navrh.csv + souhrn.md); skutecne prirazeni je render_material_key na kartach/dilech/kategoriich';

-- ---------------------------------------------------------------------------------------------------------------
-- 4) Sloupec render_material_key (NULL = dedit z vyssi urovne / beze zmeny) - idempotentne
-- ---------------------------------------------------------------------------------------------------------------
SET @rm_sql = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE shop_products ADD COLUMN render_material_key VARCHAR(40) NULL COMMENT ''render_materialy.klic; NULL = dedit z cfg_dily/kategorie/mapy barev'', ALGORITHM=INSTANT',
  'SELECT ''shop_products.render_material_key uz existuje'' AS info')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'shop_products' AND COLUMN_NAME = 'render_material_key');
PREPARE rm_st FROM @rm_sql; EXECUTE rm_st; DEALLOCATE PREPARE rm_st;

SET @rm_sql = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE cfg_dily ADD COLUMN render_material_key VARCHAR(40) NULL COMMENT ''render_materialy.klic; NULL = dedit z kategorie/mapy barev'', ALGORITHM=INSTANT',
  'SELECT ''cfg_dily.render_material_key uz existuje'' AS info')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cfg_dily' AND COLUMN_NAME = 'render_material_key');
PREPARE rm_st FROM @rm_sql; EXECUTE rm_st; DEALLOCATE PREPARE rm_st;

SET @rm_sql = (SELECT IF(COUNT(*) = 0,
  'ALTER TABLE content_categories ADD COLUMN render_material_key VARCHAR(40) NULL COMMENT ''render_materialy.klic; NULL = dedit z nadrazene kategorie'', ALGORITHM=INSTANT',
  'SELECT ''content_categories.render_material_key uz existuje'' AS info')
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'content_categories' AND COLUMN_NAME = 'render_material_key');
PREPARE rm_st FROM @rm_sql; EXECUTE rm_st; DEALLOCATE PREPARE rm_st;

-- ---------------------------------------------------------------------------------------------------------------
-- 5) Seed 11 materialu (PBR z rozboru knihoven 2026-10-01; three_json je JEN nahled v adminu, render bere Blender
--    material z knihovny). ON DUPLICATE KEY UPDATE klic=klic = pri opakovani nic neprepise.
--    NEOVERENO: three_json hodnoty roughness u black/klt1 (rozbor z uzlu/textur, ne z cisel v souboru).
--    cub_seda a bila: .blend knihovna na Sdilenem disku ZATIM NENI (nazev_blender/knihovna_soubor jsou NAVRZENE
--    nazvy; admin pise "knihovna chybi", dokud soubor nevznikne - viz poznamka).
-- ---------------------------------------------------------------------------------------------------------------
INSERT INTO render_materialy (klic, nazev, nazev_blender, knihovna_soubor, three_json, poradi, aktivni, poznamka) VALUES
 ('alumi2',       'Hliník (Alumi2)',            'Alumi2',       'Alumi2.blend',
    JSON_OBJECT('color','#B5B4AF','metalness',1,'roughness',0.28,'clearcoat',0,'clearcoatRoughness',0),
    10, 1, 'Hliníkové profily všude (Robert 2026-10-01). Knihovna Alumi2.blend, materiál Alumi2.'),
 ('grey',         'Šedý zinek (Grey)',          'Grey',         'grey.blend',
    JSON_OBJECT('color','#5A5A58','metalness',0.073,'roughness',0.266,'clearcoat',0,'clearcoatRoughness',0),
    20, 1, 'Zinkové spojky, desky perfopanelů, eurobox. Pozor: modrecelo.blend obsahuje navíc vlastní materiál "Grey" (shodné jméno).'),
 ('black',        'Černý plast / guma (Black)', 'Black',        'Black.blend',
    JSON_OBJECT('color','#000000','metalness',0,'roughness',0.36,'clearcoat',0,'clearcoatRoughness',0),
    30, 1, 'Černé plasty, zámky, kolečka, guma.'),
 ('chrome',       'Chrom',                      'Chrome',       'chrome.blend',
    JSON_OBJECT('color','#F8F7F2','metalness',1,'roughness',0.12,'clearcoat',0,'clearcoatRoughness',0),
    40, 1, 'Šrouby, čepy, pružiny, osy.'),
 ('brown',        'Hnědá překližka (brown)',    'brown',        'brown.blend',
    JSON_OBJECT('color','#2A1407','metalness',0.53,'roughness',0.32,'clearcoat',0,'clearcoatRoughness',0),
    50, 1, 'Překližka / PR10. Název materiálu v knihovně je malými písmeny.'),
 ('klt1',         'Modrý plast KLT (KLT1)',     'KLT1',         'KLT1.blend',
    JSON_OBJECT('color','#002A95','metalness',0.224,'roughness',0.35,'clearcoat',0.08,'clearcoatRoughness',0),
    60, 1, 'Matný modrý plast KLT boxů. Navrženo i pro výstupky elektrožlabu (GLB zatím jeden mesh).'),
 ('multibox',     'Multibox modrý',             'Multibox',     'Multibox.blend',
    JSON_OBJECT('color','#00039A','metalness',1,'roughness',0.5,'clearcoat',1,'clearcoatRoughness',0),
    70, 1, 'Přihrádky Multibox (soubor ~24 MB).'),
 ('red',          'Červená',                    'Red ',         'red.blend',
    JSON_OBJECT('color','#C1121F','metalness',0,'roughness',0.08,'clearcoat',0,'clearcoatRoughness',0),
    80, 1, 'POZOR: název materiálu v knihovně má na konci MEZERU ("Red ") - nemazat.'),
 ('blue_ceramic', 'Modrá keramika (čela šuplíků)', 'Blue Ceramic', 'modrecelo.blend',
    JSON_OBJECT('color','#0700FF','metalness',0.076,'roughness',0.05,'clearcoat',1,'clearcoatRoughness',0),
    90, 1, 'Lesklá glazura - čela šuplíků (soubor modrecelo.blend).'),
 ('cub_seda',     'Šedý laminát (CUB seda)',    'CUB seda',     'cub_seda.blend',
    JSON_OBJECT('color','#D5D5D5','metalness',0,'roughness',0.25,'clearcoat',0,'clearcoatRoughness',0),
    100, 1, 'Laminodesky a plastové výplně (Robert 2026-10-01). KNIHOVNA cub_seda.blend NA SDÍLENÉM DISKU ZATÍM NENÍ (navržený název); nativní materiál "CUB seda" z Vandr GLB: base 0.736 lin., rough 0.25, metal 0.'),
 ('bila',         'Bílý lak',                   'Bila',         'bila.blend',
    JSON_OBJECT('color','#F4F4F1','metalness',0,'roughness',0.28,'clearcoat',0,'clearcoatRoughness',0),
    110, 1, 'Elektrožlab, lakovaný plech (Robert 2026-10-01). NAVRŽENO bílý lak, KNIHOVNA bila.blend NA SDÍLENÉM DISKU ZATÍM NENÍ; ve Vandr GLB je nativní "CUB bila" (rough 0.25, metal 0).')
ON DUPLICATE KEY UPDATE klic = klic;

-- Kontrolni vypis (nic nemeni)
SELECT klic, nazev_blender, CONCAT('[', nazev_blender, ']') AS nazev_blender_ohraniceny, knihovna_soubor, aktivni
FROM render_materialy ORDER BY poradi;
