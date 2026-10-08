-- bot3 2026-09-11: manifestovy radek u obnovenych souboru tvrdil (pres
-- stamped_sha256), ze soubor je otisknuty, i kdyz na disku lezi original -
-- "neni to historie, je to nepravdive tvrzeni o aktualnim stavu."
-- reverted_at = NULL znamena "aktualne otisknuto (nebo nikdy neobnoveno)",
-- vyplnene = casova znacka, kdy byl zivy soubor vracen na original a
-- soucasny stav NENI otisknuty - historie (original_sha256/stamped_sha256/
-- params_json z posledniho otisku) zustava zachovana.
ALTER TABLE image_watermark_manifest
    ADD COLUMN reverted_at DATETIME NULL AFTER stamped_at;
