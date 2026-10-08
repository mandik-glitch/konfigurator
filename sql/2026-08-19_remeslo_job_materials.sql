-- Řemeslo - modul 2 rozšíření: itemizovaná evidence materiálu k
-- zakázce (bot11, 2026-08-19, na zadání Roberta přes bot3 - inspirace
-- appkou Buildo, viz REMESLO_APPKY_VIDEO_SCREENSHOTY.md sekce
-- "Buildo": položka materiálu má název+množství+cenu+fotku, ne jen
-- jedno souhrnné číslo jako dosavadní remeslo_jobs.costs_czk).
--
-- cena_czk je CELKOVÁ cena položky (ne cena za jednotku) - mnozstvi/
-- jednotka jsou čistě popisné (např. "5" + "m"), nenásobí se s cenou.
-- Jednodušší a jednoznačnější pro řemeslníka zapisujícího "trubka 5 m
-- za 450 Kč", než dohadovat jednotkovou cenu.
--
-- FAKTURACE/DOKLADY SE NESTAVÍ (Robert, 2026-08-19, REMESLO_KONCEPT.md)
-- - tahle tabulka je čistě INTERNÍ evidence nákladů řemeslníka, ne
-- fakturační podklad/doklad.
--
-- ON DELETE CASCADE na job_id - položka materiálu nemá žádný smysl/
-- život nezávislý na zakázce (na rozdíl od remeslo_jobs.craftsman_id,
-- kde řemeslník žije dál i po smazání zakázky - proto tam žádný
-- cascade není). Foto k položce znovupoužívá api/gallery_items.py
-- (owner_type='remeslo_job_material') - úklid osiřelých fotek při
-- smazání zakázky řeší api/remeslo.py remeslo_job_delete() explicitně
-- PŘED touhle kaskádou (gallery_items nemá skutečné FK, je to
-- polymorfní tabulka).
--
-- Použití: python api/db_migrate.py sql/2026-08-19_remeslo_job_materials.sql

CREATE TABLE IF NOT EXISTS remeslo_job_materials (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    job_id      INT NOT NULL,
    nazev       VARCHAR(255) NOT NULL,
    mnozstvi    DECIMAL(10,2) NULL,
    jednotka    VARCHAR(20) NULL,
    cena_czk    DECIMAL(10,2) NULL,
    poznamka    TEXT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_job_materials_job
        FOREIGN KEY (job_id) REFERENCES remeslo_jobs(id) ON DELETE CASCADE,
    KEY idx_job (job_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
