-- Řemeslo - modul 7 část B (bot11, 2026-08-19, na zadání Roberta přes
-- bot3, PRIORITNÍ): individuální neveřejné pokyny spolupracovníkům -
-- viz REMESLO_KONCEPT.md "Modul 7 — Mini-web řemeslníka", podsekce
-- "Část B". Bot3 souběžně staví Část A (veřejný SEO profil na
-- /r/<slug>, remeslo_craftsmen.public_slug/public_profile_enabled) -
-- tahle migrace je NEZÁVISLÁ (nová tabulka + jeden nullable sloupec),
-- žádný konflikt se schématem Části A.
--
-- Token BEZPEČNOST - stejný princip jako scene_offers.view_token_hash
-- (api/scene_offers.py, "token samotny se nikde neuklada, jen jeho
-- SHA-256 hash"): access_token_hash ukládá jen SHA-256 hash, syrový
-- token (secrets.token_urlsafe(32)) se vrátí adminovi JEN JEDNOU při
-- vytvoření/zobrazení odkazu, appka ho dál nezná. Odkaz je NEindexovaný
-- (meta robots noindex na webapp/remeslo-spolupracovnik.html), NE
-- veřejný profil jako Část A - princip "neveřejný odkaz" (nezapsané
-- YouTube video).
--
-- can_see_price/can_see_client_contact - ODLEHČENÁ sada příznaků (NE
-- plná RBAC matice jako u appky Timoty, viz REMESLO_APPKY_HLOUBKOVY_
-- PRUZKUM.md - vědomě přeskočeno dřív). Základ (co dělat/kde/jaký
-- materiál) je VŽDY viditelný bez výjimky (Robert, REMESLO_KONCEPT.md)
-- - tyhle příznaky řídí jen věci NAD rámec základu.
--
-- collaborator_id na remeslo_jobs: nullable, jedna zakázka = jeden
-- přiřazený spolupracovník (stačí pro v1, potvrzeno bot3) - ON DELETE
-- SET NULL (smazání spolupracovníka nemá smazat zakázku, jen ji
-- odpojit - na rozdíl od remeslo_job_materials, které bez zakázky
-- nedávají smysl).
--
-- Použití: python api/db_migrate.py sql/2026-08-19_remeslo_collaborators.sql

CREATE TABLE IF NOT EXISTS remeslo_collaborators (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    craftsman_id            INT NOT NULL,
    jmeno                   VARCHAR(255) NOT NULL,
    access_token_hash       CHAR(64) NOT NULL,
    active                  TINYINT(1) NOT NULL DEFAULT 1,
    can_see_price           TINYINT(1) NOT NULL DEFAULT 0,
    can_see_client_contact  TINYINT(1) NOT NULL DEFAULT 0,
    created_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_remeslo_collaborators_craftsman
        FOREIGN KEY (craftsman_id) REFERENCES remeslo_craftsmen(id),
    UNIQUE KEY uq_access_token_hash (access_token_hash),
    KEY idx_craftsman (craftsman_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE remeslo_jobs
    ADD COLUMN collaborator_id INT NULL AFTER craftsman_id,
    ADD CONSTRAINT fk_remeslo_jobs_collaborator
        FOREIGN KEY (collaborator_id) REFERENCES remeslo_collaborators(id) ON DELETE SET NULL,
    ADD KEY idx_collaborator (collaborator_id);
