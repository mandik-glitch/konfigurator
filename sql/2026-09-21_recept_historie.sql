-- Historie rucnich editaci receptu z adminu (Robert 2026-09-21: "pravidla
-- postupy pro geometrii chci mit na nejake tabuli v adminu v prehledu" +
-- "tak abych to mohl kdykoli editovat").
--
-- Proc vlastni tabulka a ne jen `version` sloupec: recepty se dosud menily
-- vyhradne skriptem, takze predchozi zneni bylo vzdy dohledatelne v gitu
-- (skript + zaloha v backups/). Rucni editace z prohlizece zadnou takovou
-- stopu nenechava - bez historie by se puvodni zneni pravidla ztratilo
-- nenavratne. Kazda editace tedy zapise PREDCHOZI hodnotu sem.
CREATE TABLE IF NOT EXISTS recept_historie (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  tabulka       VARCHAR(64)  NOT NULL,
  recept_id     INT          NOT NULL,
  cesta         VARCHAR(255) NOT NULL COMMENT 'klic v JSON definition, tecka = zanoreni',
  akce          ENUM('upravit','pridat','smazat') NOT NULL,
  hodnota_pred  MEDIUMTEXT   NULL,
  hodnota_po    MEDIUMTEXT   NULL,
  verze_pred    INT          NULL,
  verze_po      INT          NULL,
  kdo           VARCHAR(128) NOT NULL,
  kdy           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_recept (tabulka, recept_id, kdy),
  KEY idx_kdy (kdy)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
