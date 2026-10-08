-- Řemeslo - jednoduché verzování nabídek (bot14, 2026-08-20, Robertovo
-- rozhodnutí k nálezu "položky nabídky jdou jen přidat/smazat" -
-- viz AGENTS_LOG.md).
--
-- Robert: "položky se mají dat upravit KDYKOLI, a navíc se mají
-- nabídky VERZOVAT - každá významná změna nabídky (PO odeslání
-- zákazníkovi) vytvoří novou verzi, historie zůstává dohledatelná
-- (kdo/kdy změnil, původní i nová hodnota)."
--
-- ÚMYSLNĚ ODLIŠNÉ od existujícího "revize" mechanismu (modul 8c,
-- POST .../revise = NOVÝ ŘÁDEK s revision_of_id/revision_number,
-- vlastní číslo dokumentu a veřejný odkaz - zákaznická re-nabídka po
-- jeho reakci). Tohle je LEHKÝ interní audit log JAKÉKOLI úpravy
-- (i drobná oprava překlepu/ceny) na TOMTÉŽ dokumentu/čísle, bez
-- vytváření nové NAB-.... řady a bez nutnosti novou verzi zákazníkovi
-- znovu explicitně posílat. "verze" sloupec (remeslo_offers) a
-- revision_number jsou dva nezávislé počítadla se zcela jiným
-- významem - nezaměňovat.
--
-- snapshot_json = stav TĚSNĚ PŘED aplikací téhle změny (hlavička +
-- položky) - srovnáním dvou po sobě jdoucích verzí jde dohledat
-- přesně "co bylo předtím". change_summary je lidsky čitelný
-- jednořádkový popis (pole: stará hodnota -> nová hodnota).
--
-- Verzuje se JEN když offer.status != 'koncept' (tj. po prvním
-- odeslání) - koncept se může měnit volně bez logu (ještě nic
-- neviděl zákazník).
--
-- Použití: python api/db_migrate_remeslo.py sql/2026-08-20_remeslo_offer_versions.sql

ALTER TABLE remeslo_offers
    ADD COLUMN version INT NOT NULL DEFAULT 1 AFTER revision_number;

CREATE TABLE IF NOT EXISTS remeslo_offer_versions (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    offer_id            INT NOT NULL,
    version_number      INT NOT NULL,
    changed_by_user_id  INT NOT NULL,
    changed_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    change_summary      TEXT NOT NULL,
    snapshot_json       JSON NOT NULL,
    CONSTRAINT fk_remeslo_offer_versions_offer
        FOREIGN KEY (offer_id) REFERENCES remeslo_offers(id) ON DELETE CASCADE,
    KEY idx_offer (offer_id, version_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
