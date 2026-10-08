-- Rezne kusy BEZ vazby na objednavku (bot5, 2026-09-03, Robert pres bot3 - "hned").
-- Slouzi VYHRADNE jako bezkolizni zdroj ID pro piece_id v
-- shop_cutting_plan_units.pieces_json (JSON sloupec nemuze mit FK,
-- viz api/cutting.py::generate_cutting_plan) - piece_id manualniho
-- kusu je vzdy -id tohoto radku, stejna konvence jako uz existujici
-- zbytky (`-r["id"]` v _build_plans). Zadna FK vazba na cutting plan
-- samotny (radek muze byt pouzity opakovane/nikdy, cistě audit + ID
-- zdroj, viz docstring generate_cutting_plan).
--
-- Pouziti (na DB instance "Configurator", xebyhtfeaj @ 80.211.73.226):
--   mysql -h 80.211.73.226 -u <user> -p xebyhtfeaj < 2026-09-03_cutting_manual_pieces.sql

CREATE TABLE IF NOT EXISTS shop_cutting_manual_pieces (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    cut_kind        VARCHAR(10) NOT NULL,
    material_key    VARCHAR(40) NOT NULL,
    length_mm       DECIMAL(10,1) NULL,
    width_mm        DECIMAL(10,1) NULL,
    height_mm       DECIMAL(10,1) NULL,
    qty             INT NOT NULL,
    label           VARCHAR(200) NULL,
    created_by      INT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_scmp_user FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
