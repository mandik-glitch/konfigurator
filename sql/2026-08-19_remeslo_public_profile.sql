-- Řemeslo - Modul 7 část A: veřejný profil řemeslníka (bot3, 2026-08-19).
-- Viz REMESLO_KONCEPT.md "Modul 7" pro celý kontext/zdůvodnění.
--
-- Zveřejnění NENÍ automatické (public_profile_enabled výchozí 0) -
-- řemeslník/admin to musí explicitně zapnout. Kontakt je SAMOSTATNÝ
-- příznak (public_contact_enabled) - zveřejnění profilu neznamená
-- automaticky zveřejnění telefonu/e-mailu.
--
-- Ukázky práce (fotky) NEJSOU vybírané ze zakázek (ochrana soukromí
-- klientů - fotka interiéru cizího domu nesmí skončit veřejně bez
-- svolení) - řemeslník je nahrává PŘÍMO pro veřejný profil, přes
-- stejný obecný gallery_items mechanismus (owner_type=
-- 'remeslo_craftsman_public'), žádná nová tabulka pro fotky potřeba.

ALTER TABLE remeslo_craftsmen
    ADD COLUMN public_slug VARCHAR(80) NULL UNIQUE AFTER code,
    ADD COLUMN public_profile_enabled TINYINT(1) NOT NULL DEFAULT 0 AFTER public_slug,
    ADD COLUMN public_contact_enabled TINYINT(1) NOT NULL DEFAULT 0 AFTER public_profile_enabled,
    ADD COLUMN public_bio TEXT NULL AFTER public_contact_enabled;
