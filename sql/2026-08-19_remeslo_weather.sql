-- Řemeslo - počasí navázané na kalkulačky (technologická varování) -
-- bot14, 2026-08-19. Viz REMESLO_KONCEPT.md "Počasí navázané na
-- kalkulačky" (schváleno bot3/Robertem vč. site_city sloupce).
--
-- !!! DB "Remeslnik" - aplikovat VYHRADNE pres:
--     python api/db_migrate_remeslo.py sql/2026-08-19_remeslo_weather.sql
--
-- remeslo_weather_cache: MET Norway POZADUJE lokalni cache (Terms of
-- Service) - TTL resi aplikace (3 h), tabulka jen uklada posledni
-- payload per zaokrouhlena souradnice (2 des. mista ~ 1 km; MET chce
-- max 4). Zadne varovani se NEuklada - pocitaji se za behu.
--
-- remeslo_geo_cache: Nominatim (OSM) vyzaduje cache vysledku - mesto
-- se geokoduje JEDNOU navzdy (mesta se nestehuji).
--
-- remeslo_jobs.site_city: misto realizace zakazky (dosud zadna adresa
-- na zakazce nebyla) - fallback na mesto z profilu remeslnika.

CREATE TABLE IF NOT EXISTS remeslo_weather_cache (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    lat         DECIMAL(5,2) NOT NULL,
    lon         DECIMAL(5,2) NOT NULL,
    payload     MEDIUMTEXT NOT NULL,
    fetched_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_coords (lat, lon)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS remeslo_geo_cache (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    place        VARCHAR(255) NOT NULL,
    lat          DECIMAL(9,6) NULL,
    lon          DECIMAL(9,6) NULL,
    resolved_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_place (place)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE remeslo_jobs
    ADD COLUMN site_city VARCHAR(255) NULL AFTER customer_address;
