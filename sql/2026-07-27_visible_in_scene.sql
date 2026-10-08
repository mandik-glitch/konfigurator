-- Nahrazuje pevne zadrátovaný VISIBLE_CATALOG_IDS Set v scene.html
-- databázovým příznakem - bot1, 2026-07-27, součást FBX->GLB auto-pipeline
-- (Robert: "jakmile se fbx modely nahrají šupni je do scény do katalogu").
ALTER TABLE cfg_dily
  ADD COLUMN visible_in_scene TINYINT(1) NOT NULL DEFAULT 0 AFTER glb_file;

-- Zachovat současný stav (5 profilů, které Robert už dřív osobně
-- zkontroloval a potvrdil jako správné - viz scene.html VISIBLE_CATALOG_IDS
-- před touto migrací).
UPDATE cfg_dily SET visible_in_scene = 1
  WHERE id IN ('Object_1', 'Object_2', 'Object_7', 'Object_11', 'Object_14');
