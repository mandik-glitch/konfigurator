-- FBX->GLB konverzni automat (scripts/2026-09-23_vandr_fbx_konverze_
-- auto_dispatch.py) - Robert primo 2026-09-23: "udelej ten automat"
-- (po rucni jednorazove davce 8 karet, kdyz bot10 nemel cas).
--
-- vandr_konverze_chyba_fbx_otisk: sha256 ZDROJOVEHO FBX souboru, na
-- kterem konverze SELHALA (chybny export, neznamy hlavni profil bez
-- overene T-drazky apod.) - stejny vzor jako vandr_razitka_chyba_otisk
-- (2026-09-23b) - kandidat se stejnym otiskem FBX se PRESKOCI, ne
-- zkousi znovu porad dokola; zmeni-li se zdrojovy FBX (novy export),
-- otisk uz nesedi a zkusi se znovu.
ALTER TABLE shop_products
  ADD COLUMN vandr_konverze_chyba_fbx_otisk CHAR(64) NULL;
