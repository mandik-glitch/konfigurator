-- Deskove materialy: format tabule, ze ktere se rezou kusy (Robert
-- 2026-08-08: "Deskové materiály mají různé formáty tabulí ze kterých
-- se řeže takže dej do skladových karet deskový materiálů ten formát
-- tabule k vyplňování"). Analogie k cfg_dily.length_mm (referencni
-- delka tyce) u profilu - tady referencni rozmer CELE tabule, ne
-- konkretniho vyrezaneho kusu (ten uz je pocitan zive ve scene.html
-- pres currentBoardDimsMm).
ALTER TABLE shop_products
  ADD COLUMN board_sheet_width_mm INT NULL AFTER is_board_material,
  ADD COLUMN board_sheet_height_mm INT NULL AFTER board_sheet_width_mm;
