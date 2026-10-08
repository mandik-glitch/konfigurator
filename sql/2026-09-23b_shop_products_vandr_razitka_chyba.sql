-- Doplnek k 2026-09-23_shop_products_vandr_razitka.sql - bot3 2026-09-23
-- ostry nalez: automat bez tohohle hlasil systemd sluzbu jako "failed"
-- navzdy pri kazdem behu, jakmile narazil na kartu se znamou (spravne
-- odmitnutou) chybou vypoctu, protoze ji zkousel porad dokola.
--
-- vandr_razitka_chyba_otisk: sha256 GLB souboru, na kterem VYPOCET
-- SELHAL. scripts/2026-09-23_vandr_razitka_auto_dispatch.py kandidata s
-- otiskem shodnym s timhle sloupcem PRESKOCI (uz zname selhani na tomto
-- presnem souboru) - zmeni-li se GLB (novy export/oprava), otisk uz
-- nesedi a kandidat se zkusi znovu.
ALTER TABLE shop_products
  ADD COLUMN vandr_razitka_chyba_otisk CHAR(64) NULL;
