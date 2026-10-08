-- Ulozeni vypoctenych 3D razitek pro Vandr karty PRIMO na shop_products,
-- NIKDY do product_assemblies (Robert/bot3, 2026-09-23: "2. vetev se
-- vepisuje do tabulky pro 1. vetev, to nelze" - viz take
-- 2026-09-22_vandr_fbx_watcher.py hlavicka: "Vandr karty product_
-- assemblies VUBEC NEMAJI"). product_turntable_frames.assembly_id je
-- uz NULLable ("snimky patri produktu, ne sablone") - render pipeline
-- pro tuhle cestu byla navrzena uz driv, jen build_job() ji zatim
-- neumel (viz 2026-09-23_vandr_razitka_auto_dispatch.py).
--
-- vandr_razitka_json: stejna struktura jako davky "logo-ochrana-vandr-*"
-- dilu, ktere pocita scripts/2026-09-23_vandr_razitka_spocitat.py -
-- pole objektu {part_id, position, quaternion, scale, role, ...}.
-- vandr_razitka_glb_otisk: sha256 GLB souboru v dobe vypoctu razitek -
-- zmeni-li se GLB (novy export), otisk nesedi, razitka jsou zastarala
-- a prepocitaji se (stejny princip jako razitkovac.otisk_sestavy, jen
-- fingerprint souboru misto seznamu dilu, protoze tady zadny "seznam
-- ostatnich dilu" krome monolitickeho GLB neexistuje).
ALTER TABLE shop_products
  ADD COLUMN vandr_razitka_json LONGTEXT NULL,
  ADD COLUMN vandr_razitka_glb_otisk CHAR(64) NULL,
  ADD COLUMN vandr_razitka_hotovo_at DATETIME NULL;
